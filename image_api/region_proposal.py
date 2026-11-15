"""Callable semantic panel selection; independent of routing and answer planning.

Selections are proposals, not certified view boundaries. Invalid/ambiguous
layout results preserve the full submitted source rather than dropping scope.
The caller owns inference/image lifetime and request budgets.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from gemini import AsyncGeminiClient, GeminiError, GeminiRequestTooLarge
from .errors import ApiError
from .images import PreparedImage

PROMPT_VERSION = "region-proposal-v3"
TARGET_KINDS = ("door", "window", "toilet", "shower", "bathtub", "bath_fixture", "room", "floor", "schedule_row", "other")
Coordinate = Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False, strict=True)]
Nonblank = Annotated[str, Field(min_length=1, max_length=500, strict=True)]


class _Region(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    box_2d: tuple[Coordinate, Coordinate, Coordinate, Coordinate]
    reason: Nonblank

    @model_validator(mode="after")
    def valid_region(self):
        y0, x0, y1, x1 = self.box_2d
        if x0 >= x1 or y0 >= y1 or not self.reason.strip():
            raise ValueError("Region must have positive area and a visible reason")
        return self


class _Layout(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    status: Literal["selected", "ambiguous", "unreadable"]
    regions: list[_Region] = Field(max_length=4)
    limitations: list[Nonblank] = Field(max_length=10)
    target_kind: Literal["door", "window", "toilet", "shower", "bathtub", "bath_fixture", "room", "floor", "schedule_row", "other"] = "other"

    @model_validator(mode="after")
    def valid_layout(self):
        if any(not item.strip() for item in self.limitations):
            raise ValueError("Limitations cannot be blank")
        if self.status == "selected" and not self.regions:
            raise ValueError("A selected layout needs regions")
        if self.status != "selected" and not self.limitations:
            raise ValueError("An unresolved layout needs a limitation")
        if len({r.box_2d for r in self.regions}) != len(self.regions):
            raise ValueError("Duplicate regions")
        return self


def region_proposal_schema() -> dict:
    """Small native grammar; strict local validation enforces bounds/lengths."""
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["selected", "ambiguous", "unreadable"]},
            "regions": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "box_2d": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                    "reason": {"type": "string"}},
                "required": ["box_2d", "reason"]}},
            "limitations": {"type": "array", "items": {"type": "string"}},
            "target_kind": {"type": "string", "enum": list(TARGET_KINDS)}},
        "required": ["status", "regions", "limitations", "target_kind"]}


@dataclass(frozen=True)
class ProposedRegion:
    id: str
    source_box: tuple[int, int, int, int]
    reason: str


@dataclass(frozen=True)
class RegionProposalResult:
    regions: tuple[ProposedRegion, ...]
    status: Literal["selected", "full_source"]
    limitations: tuple[str, ...]
    source_sha256: str
    requested_model: str
    returned_model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    elapsed_ms: int
    prompt_version: str = PROMPT_VERSION
    target_kind: str = "other"


class GeminiRegionProposer:
    def __init__(self, client: AsyncGeminiClient, *, padding_fraction: float = 0.02):
        if isinstance(padding_fraction, bool) or not math.isfinite(padding_fraction) or not 0 <= padding_fraction <= .25:
            raise ValueError("Panel padding must be between zero and 0.25")
        self.client = client
        self.padding_fraction = padding_fraction
        self._instruction = Path(__file__).with_name("region_proposal_prompt.txt").read_text(encoding="utf-8")

    async def propose(self, image: PreparedImage, question: str, *, layout_hint: dict | None = None) -> RegionProposalResult:
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ApiError(422, "invalid_question", "Supply a nonblank question of at most 4000 characters.")
        if image.width <= 0 or image.height <= 0 or image.model_width <= 0 or image.model_height <= 0:
            raise ApiError(422, "invalid_image", "The image has invalid display dimensions.")
        started = perf_counter()
        system = (self._instruction + f"\nAttached inference dimensions: {image.model_width} x {image.model_height} pixels. "
                  "It shows the whole submitted source, possibly uniformly resized. The host maps normalized rectangles "
                  "back to original source pixels. Return complete question-relevant drawing panels, not object boxes.")
        if layout_hint:
            system += "\nLocal preparation hints (unverified observations): " + json.dumps(layout_hint, ensure_ascii=False)
        try:
            reply = await self.client.generate_candidates(question.strip(), system=system,
                image=image.path, schema=region_proposal_schema())
        except GeminiRequestTooLarge:
            raise ApiError(413, "prepared_request_too_large", "The image exceeds Gemini's inline request limit.") from None
        except GeminiError as exc:
            diagnostic = {"usage": exc.usage, "returned_model": exc.returned_model}
            if exc.status_code in {401, 402, 403, 404}:
                raise ApiError(503, "provider_configuration", "Check Gemini configuration and billing on the backend.", **diagnostic) from None
            if exc.retryable:
                raise ApiError(503, "provider_unavailable", "The inference provider is temporarily unavailable.", retryable=True, **diagnostic) from None
            raise ApiError(502, "provider_error", "The inference provider could not select drawing regions.", **diagnostic) from None

        limitations = ()
        target_kind = "other"
        status = "full_source"
        regions = (ProposedRegion("region-full-source", (0, 0, image.width, image.height),
                                  "Full submitted source retained because panel selection was unresolved."),)
        try:
            layout = _Layout.model_validate_json(reply.text)
            target_kind = layout.target_kind
            limitations = tuple(layout.limitations)
            if layout.status == "selected":
                mapped = []
                for i, region in enumerate(layout.regions, 1):
                    y0, x0, y1, x1 = region.box_2d
                    a, b = x0 * image.width / 1000, y0 * image.height / 1000
                    c, d = x1 * image.width / 1000, y1 * image.height / 1000
                    dx, dy = (c-a) * self.padding_fraction, (d-b) * self.padding_fraction
                    box = (max(0, math.floor(a-dx)), max(0, math.floor(b-dy)),
                           min(image.width, math.ceil(c+dx)), min(image.height, math.ceil(d+dy)))
                    mapped.append(ProposedRegion(f"region-{i:03d}", box, region.reason.strip()))
                regions, status = tuple(mapped), "selected"
        except (ValidationError, ValueError):
            limitations = ("Invalid panel proposal; full source retained to preserve scope.",)
        return RegionProposalResult(
            regions=regions, status=status, limitations=limitations, source_sha256=image.sha256,
            requested_model=self.client.settings.model, returned_model=reply.model,
            prompt_tokens=reply.usage.prompt_tokens if reply.usage else None,
            completion_tokens=reply.usage.completion_tokens if reply.usage else None,
            elapsed_ms=max(0, round((perf_counter()-started)*1000)), target_kind=target_kind)

"""One image/question to schema-validated, unreviewed candidate proposals."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Annotated, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from contracts.models import ImageCandidateResponse, ImageDecisionTrace
from gemini import AsyncGeminiClient, GeminiError, GeminiRequestTooLarge
from nemotron import AsyncNemotronClient, NemotronError, completion_text

from .config import ApiSettings
from .errors import ApiError
from .images import PreparedImage
from drawing_preprocessor.core import PIPELINE_VERSION

PROMPT_VERSION = "candidate-v2"
Coordinate = Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False, strict=True)]
Nonblank = Annotated[str, Field(min_length=1, max_length=1000)]


class _CandidateFields(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    category: Annotated[str, Field(min_length=1, max_length=100)]
    source_label: Annotated[str, Field(max_length=500)] | None = None
    uncertain: bool = Field(strict=True)
    uncertainty_reason: Nonblank | None = None
    visual_cue: Nonblank

    @model_validator(mode="after")
    def valid_proposal(self):
        if not self.category.strip() or not self.visual_cue.strip():
            raise ValueError("candidate category and cue must not be blank")
        if self.uncertain:
            if not self.uncertainty_reason or not self.uncertainty_reason.strip():
                raise ValueError("uncertain candidates need an explanation")
        elif self.uncertainty_reason is not None:
            raise ValueError("certain candidates must have a null uncertainty reason")
        return self


class _Proposal(_CandidateFields):
    bbox_1000: tuple[Coordinate, Coordinate, Coordinate, Coordinate]

    @model_validator(mode="after")
    def valid_box(self):
        x1, y1, x2, y2 = self.bbox_1000
        if x1 >= x2 or y1 >= y2:
            raise ValueError("candidate boxes must have positive area")
        return self


class _Proposals(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    status: Literal["ok", "partial", "unreadable", "unsupported"]
    candidates: list[_Proposal] = Field(max_length=100)
    limitations: list[Nonblank] = Field(max_length=100)

    @model_validator(mode="after")
    def valid_result(self):
        if any(not item.strip() for item in self.limitations):
            raise ValueError("limitations must not be blank")
        if self.status != "ok" and not self.limitations:
            raise ValueError("a non-ok result requires an explanation")
        if self.status in {"unreadable", "unsupported"} and self.candidates:
            raise ValueError("unreadable and unsupported results must not contain candidates")
        if len(self.candidates) == 100 and self.status != "partial":
            raise ValueError("reaching the candidate limit requires a partial result")
        records = [(item.category, item.bbox_1000) for item in self.candidates]
        if len(set(records)) != len(records):
            raise ValueError("duplicate category and geometry records")
        return self


@dataclass(frozen=True)
class _ProviderResult:
    batch: _Proposals
    requested_model: str
    returned_model: str
    prompt_version: str
    prompt_tokens: int | None
    completion_tokens: int | None


class CandidateProvider(Protocol):
    async def propose(self, image: PreparedImage, question: str) -> _ProviderResult: ...


def _invalid_output(*, usage=None, returned_model: str | None = None) -> ApiError:
    return ApiError(502, "invalid_model_output",
                    "The inference response was incomplete or did not contain valid candidates.",
                    usage=usage, returned_model=(returned_model if returned_model in
                        ("gemini-4-hydrogen", "gemini-4-carbon") else None))


class NemotronCandidateProvider:
    def __init__(self, client: AsyncNemotronClient, settings: ApiSettings):
        self.client = client
        self.settings = settings
        self._instruction = Path(__file__).with_name("prompt.txt").read_text(encoding="utf-8")

    async def propose(self, image: PreparedImage, question: str) -> _ProviderResult:
        schema = json.dumps(_Proposals.model_json_schema(), ensure_ascii=False)
        system = (
            f"{self._instruction}\n"
            f"The inference image is {image.model_width} pixels wide and {image.model_height} pixels high.\n"
            "It contains the entire submitted display image, possibly uniformly resized, without cropping or rearranging panels.\n"
            "Return bbox_1000 normalized to the entire inference image. Original display coordinates are mapped by the server.\n"
            f"JSON Schema:\n{schema}"
        )
        try:
            reply = await self.client.ask(
                question,
                system=system,
                images=[image.path],
                response_format={"type": "json_object"},
                max_tokens=self.settings.max_tokens,
            )
        except NemotronError as exc:
            if exc.status_code in {401, 403, 404}:
                raise ApiError(503, "provider_configuration", "The inference provider is not configured for this service.") from None
            if exc.retryable:
                raise ApiError(503, "provider_unavailable", "The inference provider is temporarily unavailable.", retryable=True) from None
            raise ApiError(502, "provider_error", "The inference provider could not complete the request.") from None

        try:
            return _ProviderResult(
                batch=_Proposals.model_validate_json(completion_text(reply)),
                requested_model=self.client.settings.model, returned_model=reply.model,
                prompt_version=PROMPT_VERSION,
                prompt_tokens=reply.usage.prompt_tokens if reply.usage else None,
                completion_tokens=reply.usage.completion_tokens if reply.usage else None,
            )
        except (NemotronError, ValidationError, ValueError):
            raise _invalid_output() from None


class _GeminiProposal(_CandidateFields):
    box_2d: tuple[Coordinate, Coordinate, Coordinate, Coordinate] = Field(
        description="[ymin, xmin, ymax, xmax], normalized to 0..1000 over the entire image.")


class _GeminiProposals(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    status: Literal["ok", "partial", "unreadable", "unsupported"]
    candidates: list[_GeminiProposal] = Field(max_length=100)
    limitations: list[Nonblank] = Field(max_length=100)


def _gemini_response_schema() -> dict:
    """Keep the native decoding grammar small; local models enforce all limits.

    Google expands bounded arrays/numbers into decoding states. A candidate
    array bounded to 100 complex objects can exceed those limits even though
    the JSON Schema itself is small. Keep structure and tuple length native,
    and enforce inventory/coordinate limits with the strict models above.
    """
    schema = _GeminiProposals.model_json_schema()
    for field in ("candidates", "limitations"):
        schema["properties"][field].pop("maxItems", None)
    candidate = schema["$defs"]["_GeminiProposal"]
    box = candidate["properties"]["box_2d"]
    candidate["properties"]["box_2d"] = {
        "type": "array", "items": {"type": "number"},
        "minItems": 4, "maxItems": 4, "description": box["description"],
    }
    # Required nullable fields avoid multiplying paths for optional anyOfs.
    for field in ("source_label", "uncertainty_reason"):
        candidate["properties"][field] = {"type": ["string", "null"]}
    candidate["required"] = list(candidate["properties"])
    return schema


class GeminiCandidateProvider:
    def __init__(self, client: AsyncGeminiClient):
        self.client = client
        self._instruction = Path(__file__).with_name("gemini_prompt.txt").read_text(encoding="utf-8")

    async def propose(self, image: PreparedImage, question: str) -> _ProviderResult:
        system = (
            f"{self._instruction}\n"
            f"The attached inference image is {image.model_width} pixels wide and {image.model_height} pixels high.\n"
            "It contains the entire submitted display image, possibly uniformly resized, without cropping or rearranging panels.\n"
            "Normalize box_2d to this entire image; the server maps to original display pixels."
        )
        try:
            reply = await self.client.generate_candidates(
                question, system=system, image=image.path, schema=_gemini_response_schema())
        except GeminiRequestTooLarge:
            raise ApiError(413, "prepared_request_too_large",
                           "The prepared image and question exceed Gemini's inline request limit. Use a smaller image.") from None
        except GeminiError as exc:
            if exc.code == "invalid_model_output":
                raise _invalid_output(usage=exc.usage, returned_model=exc.returned_model) from None
            if exc.status_code in {401, 402, 403, 404}:
                raise ApiError(503, "provider_configuration",
                               "Check Gemini API key, model access, and billing on the backend.") from None
            if exc.retryable:
                raise ApiError(503, "provider_unavailable",
                               "The inference provider is temporarily unavailable.", retryable=True) from None
            raise ApiError(502, "provider_error", "The inference provider could not complete the request.") from None

        try:
            raw = _GeminiProposals.model_validate_json(reply.text)
            proposals = []
            for candidate in raw.candidates:
                y1, x1, y2, x2 = candidate.box_2d
                proposals.append({**candidate.model_dump(exclude={"box_2d"}),
                                  "bbox_1000": (x1, y1, x2, y2)})
            batch = _Proposals.model_validate({"status": raw.status, "candidates": proposals,
                                               "limitations": raw.limitations})
            return _ProviderResult(
                batch=batch, requested_model=self.client.settings.model, returned_model=reply.model,
                prompt_version="gemini-candidate-v1",
                prompt_tokens=reply.usage.prompt_tokens if reply.usage else None,
                completion_tokens=reply.usage.completion_tokens if reply.usage else None,
            )
        except (ValidationError, ValueError):
            raise _invalid_output(usage=reply.usage, returned_model=reply.model) from None


class CandidateService:
    def __init__(self, client: AsyncNemotronClient | None, settings: ApiSettings, *,
                 provider: CandidateProvider | None = None):
        self.provider = provider if provider is not None else NemotronCandidateProvider(client, settings)

    async def extract(self, image: PreparedImage, question: str,
                      request_id: str, *,
                      on_trace: Callable[[ImageDecisionTrace], None] | None = None,
                      on_handoff: Callable[[str], None] | None = None,
                      deadline: float | None = None) -> ImageCandidateResponse:
        started = perf_counter()
        if on_handoff:
            on_handoff(self.provider.client.settings.model)
        result = await self.provider.propose(image, question)
        batch = result.batch
        try:
            candidates = []
            for index, proposal in enumerate(batch.candidates, start=1):
                x1, y1, x2, y2 = proposal.bbox_1000
                candidates.append({
                    "id": f"candidate-{index:03d}",
                    "category": proposal.category,
                    "source_label": proposal.source_label,
                    "geometry": {
                        "kind": "box",
                        # The full-source overview preserves normalized extent.
                        # Keep the public geometry in the original display frame,
                        # not the potentially resized inference pixel frame.
                        "minimum": [x1 * image.width / 1000, y1 * image.height / 1000],
                        "maximum": [x2 * image.width / 1000, y2 * image.height / 1000],
                    },
                    "uncertain": proposal.uncertain,
                    "uncertainty_reason": proposal.uncertainty_reason,
                    "visual_cue": proposal.visual_cue,
                })
            return ImageCandidateResponse.model_validate({
                "request_id": request_id,
                "image": {
                    "sha256": image.sha256,
                    "inference_sha256": image.inference_sha256,
                    "width": image.width,
                    "height": image.height,
                    "coordinate_system": "display_pixels_top_left",
                },
                "status": batch.status,
                "candidates": candidates,
                "limitations": batch.limitations,
                "provenance": {
                    "requested_model": result.requested_model,
                    "returned_model": result.returned_model,
                    "prompt_version": result.prompt_version,
                    "preprocessing": {
                        "mode": image.preprocessing_mode,
                        "pipeline_version": PIPELINE_VERSION if image.prepared_id else None,
                        "prepared_id": image.prepared_id,
                        "input_width": image.model_width,
                        "input_height": image.model_height,
                    },
                },
                "metrics": {
                    "elapsed_ms": max(0, round((perf_counter() - started) * 1000)),
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "preparation_ms": image.preparation_ms,
                    "preparation_cache_hit": image.preparation_cache_hit,
                },
            })
        except (ValidationError, ValueError):
            # Neither provider text nor Pydantic input dumps cross this boundary.
            raise _invalid_output() from None

"""One candidate-membership check, without creating further object proposals."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from gemini import AsyncGeminiClient, GeminiError, GeminiRequestTooLarge
from .errors import ApiError
from .images import PreparedImage


PROMPT_VERSION = "candidate-verification-v1"
Verdict = Literal["supported", "rejected", "ambiguous"]


class _Verification(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    verdict: Verdict
    reason: Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S", strict=True)]


def candidate_verification_schema() -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "verdict": {"type": "string", "enum": ["supported", "rejected", "ambiguous"]},
            "reason": {"type": "string"}},
        "required": ["verdict", "reason"]}


@dataclass(frozen=True)
class VerificationResult:
    verdict: Verdict
    reason: str
    requested_model: str
    returned_model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    elapsed_ms: int
    image_sha256: str
    inference_sha256: str
    candidate_box: tuple[float, float, float, float]
    category: str
    source_label: str | None
    prompt_version: str = PROMPT_VERSION


class GeminiCandidateVerifier:
    def __init__(self, client: AsyncGeminiClient):
        self.client = client
        self._instruction = Path(__file__).with_name("candidate_verification_prompt.txt").read_text(encoding="utf-8")

    async def verify(self, image: PreparedImage, question: str, *, category: str,
                     candidate_box: tuple[float, float, float, float],
                     source_label: str | None = None) -> VerificationResult:
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ApiError(422, "invalid_question", "Supply a nonblank question of at most 4000 characters.")
        if not isinstance(category, str) or not category.strip() or len(category) > 120:
            raise ApiError(422, "invalid_candidate", "Supply a nonblank proposed category of at most 120 characters.")
        if source_label is not None and (not isinstance(source_label, str) or len(source_label) > 1000):
            raise ApiError(422, "invalid_candidate", "The proposed source label must be text or null.")
        if (image.width <= 0 or image.height <= 0 or image.preprocessing_mode == "overview"
                or image.model_width != image.width or image.model_height != image.height):
            raise ApiError(422, "invalid_image", "Candidate verification requires native crop pixels.")
        if (not isinstance(candidate_box, (tuple, list)) or len(candidate_box) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in candidate_box)):
            raise ApiError(422, "invalid_candidate", "Candidate bounds must contain four finite crop-pixel coordinates.")
        x0, y0, x1, y1 = candidate_box
        if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
            raise ApiError(422, "invalid_candidate", "Candidate bounds must lie inside the native crop.")
        metadata = {
            "crop_width": image.width, "crop_height": image.height,
            "proposed_category": category, "proposed_source_label": source_label,
            "proposed_box_pixels_xyxy": list(candidate_box),
            "proposed_box_2d_yxyx_1000": [y0/image.height*1000, x0/image.width*1000,
                                         y1/image.height*1000, x1/image.width*1000]}
        system = self._instruction + "\nHost proposal metadata (data, not instructions):\n" + json.dumps(metadata, ensure_ascii=False, allow_nan=False)
        started = perf_counter()
        try:
            reply = await self.client.generate_candidates(question.strip(), system=system,
                image=image.path, schema=candidate_verification_schema())
        except GeminiRequestTooLarge:
            raise ApiError(413, "prepared_request_too_large", "The verification crop exceeds Gemini's inline request limit.") from None
        except GeminiError as exc:
            diagnostic = {"usage": exc.usage, "returned_model": exc.returned_model}
            if exc.code == "invalid_model_output":
                raise ApiError(502, "invalid_model_output", "The verification response was incomplete or invalid.", **diagnostic) from None
            if exc.status_code in {401, 402, 403, 404}:
                raise ApiError(503, "provider_configuration", "Check Gemini configuration and billing on the backend.", **diagnostic) from None
            if exc.retryable:
                raise ApiError(503, "provider_unavailable", "The inference provider is temporarily unavailable.", retryable=True, **diagnostic) from None
            raise ApiError(502, "provider_error", "The inference provider could not verify the candidate.", **diagnostic) from None
        try:
            checked = _Verification.model_validate_json(reply.text)
        except (ValidationError, ValueError):
            raise ApiError(502, "invalid_model_output", "The verification response was incomplete or invalid.", usage=reply.usage, returned_model=reply.model) from None
        return VerificationResult(
            verdict=checked.verdict, reason=checked.reason.strip(),
            requested_model=self.client.settings.model, returned_model=reply.model,
            prompt_tokens=reply.usage.prompt_tokens if reply.usage else None,
            completion_tokens=reply.usage.completion_tokens if reply.usage else None,
            elapsed_ms=max(0,round((perf_counter()-started)*1000)),
            image_sha256=image.sha256, inference_sha256=image.inference_sha256,
            candidate_box=tuple(candidate_box), category=category, source_label=source_label)

"""One stateless native Gemini image interaction, without implicit retries."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import httpx

from .config import GeminiSettings

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVISION = "2026-05-20"
MAX_REQUEST_BYTES = 20_000_000
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_ERROR_RESPONSE_BYTES = 64 * 1024
# Retain machine categories only. Provider messages and arbitrary code strings
# may echo an API key, a question, or image data and must never be retained.
PROVIDER_ERROR_CODES = frozenset({
    "invalid_request", "failed_precondition", "out_of_range", "parameter_unknown",
    "authentication", "payment_required", "permission_denied", "not_found",
    "model_not_found", "already_exists", "aborted", "too_many_requests",
    "internal", "internal_error", "unavailable", "deadline_exceeded", "cancelled",
    "INVALID_ARGUMENT", "FAILED_PRECONDITION", "OUT_OF_RANGE", "UNAUTHENTICATED",
    "PERMISSION_DENIED", "NOT_FOUND", "ALREADY_EXISTS", "ABORTED",
    "RESOURCE_EXHAUSTED", "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED",
    "CANCELLED", "UNKNOWN", "UNIMPLEMENTED", "DATA_LOSS",
})


class GeminiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None,
                 retryable: bool = False, code: str = "provider_error",
                 provider_code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.code = code
        # Safe metadata only; populated from validated counters on decoded
        # unsuccessful responses, without retaining raw bodies/continuation state.
        self.usage: GeminiUsage | None = None
        self.returned_model: str | None = None
        self.provider_code = (provider_code if isinstance(provider_code, str)
                              and provider_code in PROVIDER_ERROR_CODES else None)


class GeminiRequestTooLarge(GeminiError):
    def __init__(self):
        super().__init__("The prepared Gemini request exceeds the 20 MB inline limit.",
                         status_code=413, code="request_too_large")


@dataclass(frozen=True)
class GeminiUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None


@dataclass(frozen=True)
class GeminiReply:
    text: str = field(repr=False)
    model: str
    usage: GeminiUsage | None = None


def _invalid_response() -> GeminiError:
    return GeminiError("Gemini returned an incomplete or invalid model response.",
                       code="invalid_model_output")


def _counter(usage: dict[str, Any], name: str) -> int | None:
    value = usage.get(name)
    if value is not None and (type(value) is not int or value < 0):
        raise _invalid_response()
    return value


def _parse_usage(value: dict[str, Any]) -> GeminiUsage | None:
    usage = value.get("usage")
    if usage is None:
        return None
    if not isinstance(usage, dict):
        raise _invalid_response()
    inputs = _counter(usage, "total_input_tokens")
    outputs = _counter(usage, "total_output_tokens")
    thoughts = _counter(usage, "total_thought_tokens")
    return GeminiUsage(
        prompt_tokens=inputs,
        completion_tokens=outputs + thoughts if outputs is not None and thoughts is not None else None,
        output_tokens=outputs, thought_tokens=thoughts,
    )


def _parse_reply(value: Any) -> GeminiReply:
    try:
        return _parse_completed_reply(value)
    except GeminiError as exc:
        if isinstance(value, dict):
            try:
                exc.usage = _parse_usage(value)
            except GeminiError:
                pass  # Malformed usage never becomes zero or a successful result.
            model = value.get("model")
            if model in ("gemini-4-hydrogen", "gemini-4-carbon"):
                exc.returned_model = model
        raise


def _parse_completed_reply(value: Any) -> GeminiReply:
    if not isinstance(value, dict) or value.get("status") != "completed":
        raise _invalid_response()
    model = value.get("model")
    if (not isinstance(model, str) or not model.strip() or len(model) > 200
            or any(character.isspace() for character in model)):
        raise _invalid_response()
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps:
        raise _invalid_response()
    texts: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            raise _invalid_response()
        if step.get("type") == "thought":
            # Never treat a summary or encrypted signature as candidate JSON.
            continue
        if step.get("type") != "model_output":
            # A tool call/result or unexpected action is outside this interface.
            raise _invalid_response()
        content = step.get("content")
        if not isinstance(content, list) or not content:
            raise _invalid_response()
        for part in content:
            if (not isinstance(part, dict) or part.get("type") != "text"
                    or not isinstance(part.get("text"), str)):
                raise _invalid_response()
            texts.append(part["text"])
    text = "".join(texts).strip()
    if not text:
        raise _invalid_response()
    return GeminiReply(text=text, model=model, usage=_parse_usage(value))


async def _provider_error_code(response: httpx.Response) -> str | None:
    """Read a bounded diagnostic and discard everything except known categories."""
    chunks: list[bytes] = []
    length = 0
    try:
        async for chunk in response.aiter_bytes(chunk_size=8192):
            length += len(chunk)
            if length > MAX_ERROR_RESPONSE_BYTES:
                return None
            chunks.append(chunk)
        value = json.loads(b"".join(chunks))
    except (httpx.HTTPError, ValueError, UnicodeError, RecursionError):
        # The status is already known. Broken or non-JSON diagnostic content
        # must not replace its error category or introduce a retry.
        return None
    error = value.get("error") if isinstance(value, dict) else None
    if isinstance(error, dict):
        for name in ("code", "status"):
            code = error.get(name)
            if isinstance(code, str) and code in PROVIDER_ERROR_CODES:
                return code
    return None


def _status_error(status: int, provider_code: str | None = None) -> GeminiError:
    messages = {
        400: "Gemini rejected the request; check model parameters and project prerequisites.",
        401: "Gemini authentication failed; check the backend GEMINI_API_KEY.",
        402: "Gemini billing requires attention; check the project's available credits.",
        403: "Gemini access denied; check project permissions and billing.",
        404: "The Gemini endpoint or requested model is unavailable to this project.",
        413: "Gemini rejected the image request as too large.",
        429: "Gemini rate limit or quota reached; try again later.",
    }
    return GeminiError(messages.get(status, "The Gemini request failed."), status_code=status,
                       retryable=status in {408, 409, 429} or status >= 500,
                       provider_code=provider_code)


class AsyncGeminiClient:
    def __init__(self, settings: GeminiSettings | None = None, *,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings if settings is not None else GeminiSettings.from_env()
        self._http = httpx.AsyncClient(
            transport=transport, follow_redirects=False,
            timeout=httpx.Timeout(self.settings.timeout_seconds,
                                  connect=min(10, self.settings.timeout_seconds)),
        )

    async def generate_candidates(self, question: str, *, system: str,
                                  image: Path, schema: dict) -> GeminiReply:
        if not question.strip() or not system.strip() or not isinstance(schema, dict) or not schema:
            raise GeminiError("Gemini image requests require a question, instructions, and response schema.")
        try:
            with Path(image).open("rb") as stream:
                content = stream.read(MAX_REQUEST_BYTES + 1)
        except OSError:
            raise GeminiError("Could not read the prepared image for Gemini.") from None
        if len(content) > MAX_REQUEST_BYTES:
            raise GeminiRequestTooLarge()
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise GeminiError("Gemini image candidates require a prepared PNG image.")
        body = {
            "model": self.settings.model,
            "system_instruction": system,
            "input": [
                {"type": "text", "text": question},
                {"type": "image", "mime_type": "image/png",
                 "data": base64.b64encode(content).decode("ascii")},
            ],
            "generation_config": {
                "thinking_level": self.settings.thinking_level,
                "thinking_summaries": "none",
                "max_output_tokens": self.settings.max_output_tokens,
            },
            "response_format": {"type": "text", "mime_type": "application/json", "schema": schema},
            "store": False,
        }
        try:
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise GeminiError("Could not encode the Gemini candidate request.") from None
        if len(encoded) > MAX_REQUEST_BYTES:
            raise GeminiRequestTooLarge()
        try:
            async with self._http.stream(
                "POST", ENDPOINT, content=encoded,
                headers={"x-goog-api-key": self.settings.api_key.get_secret_value(),
                         "Api-Revision": API_REVISION, "Content-Type": "application/json"},
            ) as response:
                if not response.is_success:
                    raise _status_error(response.status_code, await _provider_error_code(response))
                chunks: list[bytes] = []
                length = 0
                async for chunk in response.aiter_bytes():
                    length += len(chunk)
                    if length > MAX_RESPONSE_BYTES:
                        raise _invalid_response()
                    chunks.append(chunk)
            value = json.loads(b"".join(chunks))
        except httpx.TimeoutException:
            raise GeminiError("Gemini timed out.", retryable=True) from None
        except httpx.HTTPError:
            raise GeminiError("Could not reach the Gemini endpoint.", retryable=True) from None
        except (json.JSONDecodeError, UnicodeError):
            raise _invalid_response() from None
        return _parse_reply(value)

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncGeminiClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

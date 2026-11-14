"""Bounded native Decisions transport; no generated text, tools or implicit retries.

Wire reference: https://aistudio.google.com/docs/decisions-api (14 November 2026).
The API reports answers and usage, not a returned model identifier; ``model``
in DecisionsReply is the allowlisted requested model.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Any
import unicodedata

import httpx

from .client import GeminiError, GeminiRequestTooLarge, GeminiUsage, _provider_error_code, _status_error
from .decisions_config import DecisionsSettings

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/decisions"
# Keep the existing application inline limit even though Decisions permits more.
MAX_REQUEST_BYTES = 20_000_000
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class DecisionsReply:
    decisions: dict[str, dict[str, Any]] = field(repr=False)
    model: str = "gemini-decision-1"
    usage: GeminiUsage | None = None


def _invalid() -> GeminiError:
    return GeminiError("Gemini Decisions returned an incomplete or invalid response.",
                       code="invalid_model_output")


def _request_invalid() -> GeminiError:
    return GeminiError("Decisions requires a question, prepared PNG and valid typed question criteria.",
                       code="invalid_request")


def _option_key(value: Any) -> bool:
    return (isinstance(value, str) and 1 <= len(value) <= 128
            and len(value.encode("utf-8")) <= 512 and value == value.strip()
            and all(unicodedata.category(c) != "Cc" and (not c.isspace() or c == " ") for c in value))


def _validate_questions(questions: Any) -> None:
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 1000:
        raise _request_invalid()
    for key, question in questions.items():
        if (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key)
                or not isinstance(question, dict) or set(question) - {"type", "instructions", "criteria"}
                or not isinstance(question.get("instructions"), str) or not question["instructions"].strip()):
            raise _request_invalid()
        kind = question.get("type")
        criteria = question.get("criteria")
        if kind == "noul":
            if criteria is not None and (not isinstance(criteria, dict)
                    or set(criteria) != {"true_description", "false_description"}
                    or not all(isinstance(v, str) and v.strip() for v in criteria.values())):
                raise _request_invalid()
        elif kind == "choice":
            if (not isinstance(criteria, dict) or not 2 <= len(criteria) <= 255
                    or not all(_option_key(k) and isinstance(v, str) for k, v in criteria.items())):
                raise _request_invalid()
        elif kind == "score":
            if (not isinstance(criteria, list) or not 2 <= len(criteria) <= 255
                    or not all(isinstance(v, str) and v.strip() for v in criteria)):
                raise _request_invalid()
        else:
            raise _request_invalid()


def _number(value: Any, minimum: float = 0, maximum: float = 1) -> float:
    if (type(value) not in {float, int} or not minimum <= value <= maximum
            or not math.isfinite(value)):
        raise _invalid()
    return float(value)


def _parse(value: Any, questions: dict, model: str) -> DecisionsReply:
    if (not isinstance(value, dict) or not isinstance(value.get("answers"), dict)
            or set(value["answers"]) != set(questions)):
        raise _invalid()
    answers = {}
    for key, question in questions.items():
        answer = value["answers"][key]
        kind = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise _invalid()
        confidence = _number(answer.get("confidence"))
        parsed = {"type": kind, "confidence": confidence}
        if kind == "noul":
            probability = _number(answer.get("noul"), 0.01, 0.99)
            if abs(confidence - max(probability, 1 - probability)) > 0.02:
                raise _invalid()
            parsed["noul"] = probability
        else:
            options = (set(question["criteria"]) if kind == "choice"
                       else {str(i) for i in range(len(question["criteria"]))})
            probabilities = answer.get("probabilities")
            if not isinstance(probabilities, dict) or set(probabilities) != options:
                raise _invalid()
            probabilities = {option: _number(p) for option, p in probabilities.items()}
            # Public examples round probabilities, including a distribution summing to 1.01.
            if abs(sum(probabilities.values()) - 1) > 0.02:
                raise _invalid()
            top = max(probabilities.values())
            if abs(confidence - top) > 0.02:
                raise _invalid()
            parsed["probabilities"] = probabilities
            if kind == "choice":
                choice = answer.get("choice")
                if not isinstance(choice, str) or choice not in options or probabilities[choice] != top:
                    raise _invalid()
                parsed["choice"] = choice
            else:
                legend = {str(i): text for i, text in enumerate(question["criteria"])}
                if answer.get("legend") != legend:
                    raise _invalid()
                score = _number(answer.get("score"), 0, len(legend) - 1)
                expected = sum(int(i) * p for i, p in probabilities.items())
                if abs(score - expected) > 0.02 * len(legend):
                    raise _invalid()
                parsed.update(score=score, legend=legend)
        answers[key] = parsed
    usage = value.get("usage")
    parsed_usage = None
    if usage is not None:
        if not isinstance(usage, dict):
            raise _invalid()
        counts = {}
        for name in ("total_input_tokens", "total_output_tokens"):
            count = usage.get(name)
            if count is not None and (type(count) is not int or count < 0):
                raise _invalid()
            counts[name] = count
        if counts["total_output_tokens"] not in {0, None}:
            raise _invalid()
        parsed_usage = GeminiUsage(prompt_tokens=counts["total_input_tokens"],
                                   completion_tokens=counts["total_output_tokens"],
                                   output_tokens=counts["total_output_tokens"])
    return DecisionsReply(decisions=answers, model=model, usage=parsed_usage)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise _invalid()
        value[key] = item
    return value


class AsyncDecisionsClient:
    def __init__(self, settings: DecisionsSettings | None = None, *,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings if settings is not None else DecisionsSettings.from_env()
        self._http = httpx.AsyncClient(
            transport=transport, follow_redirects=False,
            timeout=httpx.Timeout(self.settings.timeout_seconds),
        )

    async def decide(self, question: str, *, image: Path, questions: dict,
                     context: str = "") -> DecisionsReply:
        try:
            if not isinstance(question, str) or not question.strip() or not isinstance(context, str):
                raise _request_invalid()
            _validate_questions(questions)
            # Snapshot the caller's criteria before awaiting network work.
            questions = json.loads(json.dumps(questions, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise _request_invalid() from None
        try:
            with Path(image).open("rb") as stream:
                content = stream.read(MAX_REQUEST_BYTES + 1)
        except OSError:
            raise GeminiError("Could not read the prepared image for Decisions.") from None
        if len(content) > MAX_REQUEST_BYTES:
            raise GeminiRequestTooLarge()
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise _request_invalid()
        body = {
            "model": self.settings.model,
            "input": [
                {"type": "text", "text": context + "\nQuestion (source data): " + question},
                {"type": "image", "mime_type": "image/png",
                 "data": base64.b64encode(content).decode("ascii")},
            ],
            "questions": questions,
        }
        try:
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise _request_invalid() from None
        if len(encoded) > MAX_REQUEST_BYTES:
            raise GeminiRequestTooLarge()
        try:
            async with self._http.stream(
                "POST", ENDPOINT, content=encoded,
                headers={"x-goog-api-key": self.settings.api_key.get_secret_value(),
                         "Content-Type": "application/json"},
            ) as response:
                if not response.is_success:
                    raise _status_error(response.status_code, await _provider_error_code(response))
                chunks = []
                length = 0
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    length += len(chunk)
                    if length > MAX_RESPONSE_BYTES:
                        raise _invalid()
                    chunks.append(chunk)
            value = json.loads(b"".join(chunks), object_pairs_hook=_unique_object)
        except httpx.TimeoutException as exc:
            # Keep transport diagnostics bounded and independent of provider text.
            phase = next((name for kind, name in (
                (httpx.ConnectTimeout, "connect"), (httpx.WriteTimeout, "write"),
                (httpx.ReadTimeout, "read"), (httpx.PoolTimeout, "pool"),
            ) if isinstance(exc, kind)), None)
            raise GeminiError("Gemini Decisions timed out.", retryable=True,
                              code="provider_timeout", timeout_phase=phase) from None
        except httpx.HTTPError:
            raise GeminiError("Could not reach the Gemini Decisions endpoint.", retryable=True) from None
        except (ValueError, UnicodeError, RecursionError):
            raise _invalid() from None
        return _parse(value, questions, self.settings.model)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def close(self) -> None:
        await self.aclose()

    async def __aenter__(self) -> AsyncDecisionsClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

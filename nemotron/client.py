"""Text, image and JSON completions with bounded retries and safe errors.

Model output is an observation/proposal, never evidence of drawing completeness.
This adapter does not execute tools, query plans or model-generated code.
"""
from __future__ import annotations

import base64
import json
import math
from pathlib import Path
from typing import Any, Sequence, TypeVar

import httpx
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, ValidationError

from .config import NemotronSettings

T = TypeVar("T", bound=BaseModel)
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class NemotronError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def _api_error(exc: APIError | httpx.HTTPError | json.JSONDecodeError) -> NemotronError:
    # Provider error bodies/SDK exception strings can echo request secrets or
    # source content. Return actionable categories without serializing either.
    if isinstance(exc, APITimeoutError):
        return NemotronError("Nemotron timed out after the configured retry budget.", retryable=True)
    if isinstance(exc, APIConnectionError):
        return NemotronError("Could not connect to the Verda endpoint; check network access and VERDA_BASE_URL.", retryable=True)
    if isinstance(exc, APIStatusError):
        code = exc.status_code
        messages = {
            400: "Request rejected; check the model's image/JSON/thinking parameter support.",
            401: "Authentication rejected; check VERDA_INFERENCE_KEY in .env.",
            403: "Access denied; check that the inference key can access this deployment.",
            404: "Endpoint or model not found; check VERDA_BASE_URL and VERDA_MODEL.",
            413: "Request too large; use smaller images or fewer images per request.",
            429: "Verda rate limit or quota reached after the configured retry budget.",
        }
        return NemotronError(f"{messages.get(code, 'Verda request failed.')} (HTTP {code})",
                             status_code=code, retryable=code in {408, 409, 429} or code >= 500)
    return NemotronError("The Verda endpoint returned an invalid response or transport error.")


def _validate_completion(value: Any) -> ChatCompletion:
    # The SDK can return raw text for an HTML proxy response and constructs
    # models permissively by default. Validate the external protocol boundary.
    if not isinstance(value, ChatCompletion):
        raise NemotronError("The Verda endpoint returned an invalid completion response.")
    try:
        return ChatCompletion.model_validate(value.model_dump(warnings=False))
    except ValidationError:
        raise NemotronError("The Verda endpoint returned a malformed completion response.") from None


def _image_part(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open("rb") as stream:
            content = stream.read(MAX_IMAGE_BYTES + 1)
    except OSError:
        raise NemotronError("Could not read an input image; supply a readable local PNG, JPEG or WebP file.") from None
    if len(content) > MAX_IMAGE_BYTES:
        raise NemotronError("An input image exceeds the 20 MiB client limit; crop or resize it first.")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        media_type = "image/webp"
    else:
        raise NemotronError("Unsupported image data; supply PNG, JPEG or WebP (render PDF pages first).")
    encoded = base64.b64encode(content).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded}"}}


def _messages(prompt: str, system: str | None, images: Sequence[str | Path]) -> list[dict[str, Any]]:
    if not prompt.strip():
        raise NemotronError("The prompt must not be empty.")
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    content: Any = prompt
    if images:
        content = [{"type": "text", "text": prompt}, *[_image_part(path) for path in images]]
    messages.append({"role": "user", "content": content})
    return messages


def completion_text(completion: ChatCompletion) -> str:
    """Require a finished textual answer; never treat truncated JSON as valid."""
    if not completion.choices or completion.choices[0].message is None:
        raise NemotronError("Nemotron returned no completion choice.")
    choice = completion.choices[0]
    if choice.finish_reason == "length":
        raise NemotronError("Nemotron reached the output token limit; increase VERDA_MAX_TOKENS or shorten the request.")
    if choice.finish_reason != "stop":
        raise NemotronError("Nemotron did not finish a text answer; inspect the finish reason or tool calls.")
    if not isinstance(choice.message.content, str) or not choice.message.content.strip():
        raise NemotronError("Nemotron returned no answer text; check thinking mode and the output token budget.")
    return choice.message.content.strip()


def _json_system(response_model: type[T], system: str | None) -> str:
    schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
    return f"{system or ''}\nReturn one JSON object matching this JSON Schema. Return only JSON.\n{schema}".strip()


def _parse_json(completion: ChatCompletion, response_model: type[T]) -> T:
    text = completion_text(completion)
    try:
        return response_model.model_validate_json(text)
    except ValidationError:
        raise NemotronError("Nemotron's JSON answer does not match the requested response schema.") from None


class _ClientBase:
    def __init__(self, settings: NemotronSettings | None):
        self.settings = settings if settings is not None else NemotronSettings.from_env()

    def _client_options(self) -> dict[str, Any]:
        return {
            "api_key": self.settings.api_key.get_secret_value(),
            "base_url": self.settings.base_url,
            "timeout": httpx.Timeout(self.settings.timeout_seconds, connect=min(10, self.settings.timeout_seconds)),
            "max_retries": self.settings.max_retries,
        }

    def _request(self, messages: Sequence[dict[str, Any]], *, max_tokens: int | None = None,
                 temperature: float | None = None, response_format: dict[str, Any] | None = None,
                 tools: list[dict[str, Any]] | None = None, tool_choice: Any = None) -> dict[str, Any]:
        tokens = self.settings.max_tokens if max_tokens is None else max_tokens
        sampling = self.settings.temperature if temperature is None else temperature
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens <= 0:
            raise NemotronError("max_tokens must be a positive integer.")
        if not isinstance(sampling, (float, int)) or not math.isfinite(sampling) or not 0 <= sampling <= 2:
            raise NemotronError("temperature must be a finite number between 0 and 2.")
        if not messages:
            raise NemotronError("At least one chat message is required.")
        body: dict[str, Any] = {
            "model": self.settings.model, "messages": list(messages),
            "max_tokens": tokens, "temperature": sampling,
        }
        if self.settings.enable_thinking is not None:
            body["extra_body"] = {"chat_template_kwargs": {"enable_thinking": self.settings.enable_thinking}}
        if response_format is not None:
            body["response_format"] = response_format
        if tools is not None:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        return body


class NemotronClient(_ClientBase):
    def __init__(self, settings: NemotronSettings | None = None, *, http_client: httpx.Client | None = None):
        super().__init__(settings)
        self._sdk = OpenAI(**self._client_options(), http_client=http_client)

    def chat(self, messages: Sequence[dict[str, Any]], **options: Any) -> ChatCompletion:
        request = self._request(messages, **options)
        try:
            return _validate_completion(self._sdk.chat.completions.create(**request))
        except (APIError, httpx.HTTPError, json.JSONDecodeError) as exc:
            raise _api_error(exc) from None

    def ask(self, prompt: str, *, system: str | None = None,
            images: Sequence[str | Path] = (), **options: Any) -> ChatCompletion:
        return self.chat(_messages(prompt, system, images), **options)

    def ask_json(self, prompt: str, response_model: type[T], *, system: str | None = None,
                 images: Sequence[str | Path] = (), **options: Any) -> T:
        completion = self.ask(prompt, system=_json_system(response_model, system), images=images,
                              response_format={"type": "json_object"}, **options)
        return _parse_json(completion, response_model)

    def close(self) -> None:
        self._sdk.close()

    def __enter__(self) -> NemotronClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncNemotronClient(_ClientBase):
    """Reusable async client; callers control concurrency for batch workloads."""

    def __init__(self, settings: NemotronSettings | None = None, *, http_client: httpx.AsyncClient | None = None):
        super().__init__(settings)
        self._sdk = AsyncOpenAI(**self._client_options(), http_client=http_client)

    async def chat(self, messages: Sequence[dict[str, Any]], **options: Any) -> ChatCompletion:
        request = self._request(messages, **options)
        try:
            return _validate_completion(await self._sdk.chat.completions.create(**request))
        except (APIError, httpx.HTTPError, json.JSONDecodeError) as exc:
            raise _api_error(exc) from None

    async def ask(self, prompt: str, *, system: str | None = None,
                  images: Sequence[str | Path] = (), **options: Any) -> ChatCompletion:
        return await self.chat(_messages(prompt, system, images), **options)

    async def ask_json(self, prompt: str, response_model: type[T], *, system: str | None = None,
                       images: Sequence[str | Path] = (), **options: Any) -> T:
        completion = await self.ask(prompt, system=_json_system(response_model, system), images=images,
                                    response_format={"type": "json_object"}, **options)
        return _parse_json(completion, response_model)

    async def close(self) -> None:
        await self._sdk.close()

    async def __aenter__(self) -> AsyncNemotronClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

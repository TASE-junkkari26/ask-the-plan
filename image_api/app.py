"""Local HTTP adapter for question-conditioned image candidates."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from contracts.models import ImageCandidateError, ImageCandidateResponse
from nemotron import AsyncNemotronClient, ConfigurationError, NemotronSettings
from .config import ApiSettings
from .errors import ApiError
from .images import prepare_image
from .service import CandidateService


def _error(request_id: str, status: int, code: str, message: str,
           retryable: bool = False) -> JSONResponse:
    value = ImageCandidateError(request_id=request_id, code=code, message=message,
                                retryable=retryable)
    return JSONResponse(value.model_dump(mode="json"), status_code=status)


class BodyLimitMiddleware:
    """Bound received bytes even when Content-Length is absent or incorrect."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise ApiError(413, "request_too_large", "Request exceeds the multipart body limit.")
            return message

        async def send_with_id(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                message = dict(message)
                message["headers"] = [*message.get("headers", []),
                                      (b"x-request-id", request_id.encode("ascii")),
                                      (b"cache-control", b"no-store")]
            await send(message)

        length = dict(scope.get("headers", [])).get(b"content-length")
        if length is not None:
            try:
                size = int(length)
                if size < 0:
                    raise ValueError
            except ValueError:
                return await _error(request_id, 422, "invalid_content_length",
                                    "Content-Length must be a nonnegative integer.")(scope, receive, send_with_id)
            if size > self.max_bytes:
                return await _error(request_id, 413, "request_too_large",
                                    "Request exceeds the multipart body limit.")(scope, receive, send_with_id)
        try:
            await self.app(scope, limited_receive, send_with_id)
        except Exception:
            if response_started:
                raise
            await _error(request_id, 500, "internal_error", "Internal candidate service error.")(
                scope, receive, send_with_id)


_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {"multipart/form-data": {"schema": {
            "type": "object", "required": ["image", "question"],
            "additionalProperties": False,
            "properties": {
                "image": {"type": "string", "format": "binary",
                          "description": "One PNG, JPEG or WebP image, at most 20 MiB."},
                "question": {"type": "string", "minLength": 1, "maxLength": 4000},
            },
        }}},
    },
}


def create_app(settings: ApiSettings | None = None, *,
               client_factory: Callable[[], AsyncNemotronClient] | None = None) -> FastAPI:
    """Build the app; injection keeps HTTP tests independent of keys/network."""
    settings = settings if settings is not None else ApiSettings.from_env()
    request_body = deepcopy(_REQUEST_BODY)
    request_body["requestBody"]["content"]["multipart/form-data"]["schema"]["properties"]["question"]["maxLength"] = settings.max_question_chars

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = None
        app.state.service = None
        app.state.in_flight = 0
        try:
            try:
                if client_factory is None:
                    model_settings = NemotronSettings.from_env().model_copy(update={"max_retries": 0})
                    client = AsyncNemotronClient(model_settings)
                else:
                    client = client_factory()
                app.state.service = CandidateService(client, settings)
            except ConfigurationError:
                # Keep health/docs available to diagnose missing local setup.
                pass
            yield
        finally:
            if client is not None:
                await client.close()

    app = FastAPI(title="Ask the Plan image candidates", version="0.1.0", lifespan=lifespan,
                  description="One image and question return unverified candidate boxes, without a final count or answer.")
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
                       expose_headers=["X-Request-ID"])

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return _error(request.state.request_id, exc.status_code, exc.code, exc.message, exc.retryable)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return _error(request.state.request_id, 422, "invalid_request", "Request does not match the API contract.")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return _error(request.state.request_id, exc.status_code, "http_error", "Request could not be handled.")

    @app.get("/health")
    async def health(request: Request):
        configured = request.app.state.service is not None
        return JSONResponse({"status": "ok" if configured else "unconfigured", "configured": configured},
                            status_code=200 if configured else 503)

    async def process(request: Request, request_id: str):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
            raise ApiError(415, "unsupported_media_type", "Send multipart/form-data with image and question fields.")
        # Read under the ASGI byte cap before multipart parsing allocates temp files.
        await request.body()
        try:
            async with request.form(max_files=1, max_fields=1, max_part_size=16 * 1024) as form:
                if (set(form) != {"image", "question"}
                        or len(form.getlist("image")) != 1 or len(form.getlist("question")) != 1):
                    raise ApiError(422, "invalid_request", "Supply exactly one image and one question.")
                upload, question = form["image"], form["question"]
                if not isinstance(upload, UploadFile) or not isinstance(question, str):
                    raise ApiError(422, "invalid_request", "Image must be a file and question must be text.")
                question = question.strip()
                if not 1 <= len(question) <= settings.max_question_chars:
                    raise ApiError(422, "invalid_question",
                                   f"Question must contain 1 to {settings.max_question_chars} characters.")
                content = await upload.read(settings.max_image_bytes + 1)
        except HTTPException:
            raise ApiError(422, "invalid_multipart", "Malformed multipart form or repeated/oversized fields.") from None
        if len(content) > settings.max_image_bytes:
            raise ApiError(413, "image_too_large", "Image exceeds the upload byte limit.")
        directory = TemporaryDirectory(prefix="ask-plan-image-")
        preparation = asyncio.create_task(asyncio.to_thread(prepare_image, content, settings, Path(directory.name)))
        try:
            # Shield the worker so a timeout cannot remove files it is still writing.
            image = await asyncio.shield(preparation)
            inference = asyncio.create_task(request.app.state.service.extract(image, question, request_id))
            disconnected = asyncio.create_task(until_disconnect(request))
            try:
                done, _ = await asyncio.wait((inference, disconnected), return_when=asyncio.FIRST_COMPLETED)
                if inference in done:
                    return await inference
                return await disconnected
            finally:
                for task in (inference, disconnected):
                    task.cancel()
                await asyncio.gather(inference, disconnected, return_exceptions=True)
        finally:
            if preparation.done():
                directory.cleanup()
            else:
                def cleanup_after_preparation(task):
                    if not task.cancelled():
                        task.exception()  # Retrieve a late worker error without logging source inputs.
                    directory.cleanup()
                preparation.add_done_callback(cleanup_after_preparation)

    async def until_disconnect(request: Request):
        while not await request.is_disconnected():
            await asyncio.sleep(0.1)
        raise ApiError(499, "client_disconnected", "Client disconnected before inference completed.", retryable=True)

    @app.post("/api/v1/candidates", response_model=ImageCandidateResponse,
              responses={status: {"model": ImageCandidateError} for status in
                         (413, 415, 422, 429, 499, 500, 502, 503, 504)},
              openapi_extra=request_body)
    async def candidates(request: Request):
        if request.app.state.service is None:
            raise ApiError(503, "not_configured", "Configure VERDA_INFERENCE_KEY on the backend.")
        if request.app.state.in_flight >= settings.max_concurrent:
            raise ApiError(429, "busy", "Candidate service is busy; try again later.", retryable=True)
        request.app.state.in_flight += 1
        try:
            return await asyncio.wait_for(process(request, request.state.request_id),
                                          timeout=settings.deadline_seconds)
        except asyncio.TimeoutError:
            raise ApiError(504, "deadline_exceeded", "Candidate request exceeded its total deadline.", retryable=True) from None
        finally:
            request.app.state.in_flight -= 1

    return app


app = create_app()

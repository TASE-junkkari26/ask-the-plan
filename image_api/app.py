"""Local HTTP adapters for image candidates and evidence-backed IFC queries."""
from __future__ import annotations

import asyncio
import hashlib
import anyio
from contextlib import asynccontextmanager
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
from time import perf_counter
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, StreamingResponse

from contracts.models import (CandidateImage, ImageCandidateError, ImageCandidateResponse,
                              ImageDecisionTrace, ImageCandidateProgress, ImageCandidateStreamEvent)
from gemini import AsyncGeminiClient
from gemini.decisions import AsyncDecisionsClient
from gemini.decisions_config import DecisionsSettings
from ifc_api.routes import install_ifc_routes
from ifc_api.service import IfcService, MAX_IFC_BODY_BYTES
from nemotron import AsyncNemotronClient, ConfigurationError, NemotronSettings
from .config import ApiSettings
from .errors import ApiError
from .preprocessing import ImagePreprocessor
from .service import CandidateService, GeminiCandidateProvider
from .routing import RoutedCandidateService


def _error(request_id: str, status: int, code: str, message: str,
           retryable: bool = False, decision_trace: ImageDecisionTrace | None = None) -> JSONResponse:
    value = ImageCandidateError(request_id=request_id, code=code, message=message,
                                retryable=retryable, decision_trace=decision_trace)
    return JSONResponse(value.model_dump(mode="json"), status_code=status)


class _CandidateStreamResponse(StreamingResponse):
    """Release admission even if the client disconnects before iteration starts."""

    def __init__(self, content, release, cleanup):
        super().__init__(content, media_type="application/x-ndjson",
                         headers={"X-Accel-Buffering": "no"})
        self.release = release
        self.cleanup = cleanup

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                # Sending may fail while the iterator is suspended at yield.
                # Stop its worker and close prepared files before admitting more work.
                with anyio.CancelScope(shield=True):
                    try:
                        await self.body_iterator.aclose()
                    finally:
                        await self.cleanup()
            finally:
                self.release()


class BodyLimitMiddleware:
    """Bound received bytes even when Content-Length is absent or incorrect."""

    def __init__(self, app, max_bytes: int, ifc_max_bytes: int = MAX_IFC_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes
        self.ifc_max_bytes = ifc_max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        # IFC uploads stream into multipart's spool instead of the image body
        # buffer. Preserve the image cap while allowing the viewer's file limit.
        max_bytes = (self.ifc_max_bytes if scope.get("path") == "/api/ifc/models"
                     else self.max_bytes)
        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes:
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
            if size > max_bytes:
                return await _error(request_id, 413, "request_too_large",
                                    "Request exceeds the multipart body limit.")(scope, receive, send_with_id)
        try:
            await self.app(scope, limited_receive, send_with_id)
        except ApiError as exc:
            if response_started:
                raise
            await _error(request_id, exc.status_code, exc.code, exc.message,
                         exc.retryable, scope.get("state", {}).get("decision_trace"))(scope, receive, send_with_id)
        except Exception:
            if response_started:
                raise
            await _error(request_id, 500, "internal_error", "Internal analysis service error.",
                         decision_trace=scope.get("state", {}).get("decision_trace"))(
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
               client_factory: Callable[[], AsyncNemotronClient] | None = None,
               gemini_client_factory: Callable[[], AsyncGeminiClient] | None = None,
               strong_client_factory: Callable[[], AsyncGeminiClient] | None = None,
               decisions_client_factory: Callable[[], AsyncDecisionsClient] | None = None) -> FastAPI:
    """Build the app; injection keeps HTTP tests independent of keys/network."""
    settings = settings if settings is not None else ApiSettings.from_env()
    request_body = deepcopy(_REQUEST_BODY)
    request_body["requestBody"]["content"]["multipart/form-data"]["schema"]["properties"]["question"]["maxLength"] = settings.max_question_chars

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = None
        gemini_client = None
        extra_clients = []
        app.state.service = None
        app.state.in_flight = 0
        app.state.preprocessor = ImagePreprocessor(settings)
        try:
            try:
                if client_factory is None:
                    model_settings = NemotronSettings.from_env().model_copy(update={"max_retries": 0})
                    client = AsyncNemotronClient(model_settings)
                else:
                    client = client_factory()
                if settings.provider == "nemotron":
                    app.state.service = CandidateService(client, settings)
            except ConfigurationError:
                # Keep health/docs available to diagnose missing local setup.
                pass
            app.state.ifc_service = IfcService(client)
            # IFC always retains its Nemotron client, regardless of image provider.
            if settings.provider == "gemini":
                try:
                    gemini_client = (gemini_client_factory() if gemini_client_factory is not None
                                     else AsyncGeminiClient())
                    app.state.service = CandidateService(
                        None, settings, provider=GeminiCandidateProvider(gemini_client))
                    if settings.routing_mode != "off":
                        baseline = app.state.service
                        # Reuse an already configured Hydrogen client, including injected transports.
                        if gemini_client.settings.model == "gemini-4-hydrogen":
                            normal_client = gemini_client
                        else:
                            normal_client = AsyncGeminiClient(gemini_client.settings.profile("normal"))
                            extra_clients.append(normal_client)
                        try:
                            strong_client = (strong_client_factory() if strong_client_factory is not None
                                             else AsyncGeminiClient(gemini_client.settings.profile(
                                                 "strong", thinking_level=settings.routing_strong_thinking_level)))
                            extra_clients.append(strong_client)
                            strong = CandidateService(None, settings, provider=GeminiCandidateProvider(strong_client))
                        except ConfigurationError:
                            strong = None
                        try:
                            decisions = (decisions_client_factory() if decisions_client_factory is not None
                                         else AsyncDecisionsClient(DecisionsSettings(
                                             api_key=gemini_client.settings.api_key,
                                             timeout_seconds=settings.routing_timeout_seconds)))
                            extra_clients.append(decisions)
                        except ConfigurationError:
                            decisions = None
                        app.state.service = RoutedCandidateService(
                            settings, decisions=decisions,
                            normal=CandidateService(None, settings, provider=GeminiCandidateProvider(normal_client)),
                            strong=strong, baseline=baseline)
                except ConfigurationError:
                    pass
            yield
        finally:
            # A timeout shields a running preparation worker. Drain it before
            # removing the session cache, just as request temp cleanup waits for
            # its preparation worker below.
            await asyncio.to_thread(app.state.preprocessor.close)
            if hasattr(app.state, "ifc_service"):
                await asyncio.to_thread(app.state.ifc_service.close)
            try:
                for owned in extra_clients:
                    await owned.close()
                if gemini_client is not None:
                    await gemini_client.close()
            finally:
                if client is not None:
                    await client.close()

    app = FastAPI(title="Ask the Plan analysis", version="0.1.0", lifespan=lifespan,
                  description="Image candidate regions and Nemotron-planned, engine-computed IFC answers with source evidence.")
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins,
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
                       expose_headers=["X-Request-ID"])

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return _error(request.state.request_id, exc.status_code, exc.code, exc.message, exc.retryable,
                      getattr(request.state, "decision_trace", None))

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

    async def read_input(request: Request):
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
        return content, question

    @asynccontextmanager
    async def prepared_input(request: Request, input_data):
        content, question = input_data
        directory = TemporaryDirectory(prefix="ask-plan-image-")
        preparation = asyncio.create_task(asyncio.to_thread(
            request.app.state.preprocessor.prepare, content, Path(directory.name)))
        try:
            # Shield the worker so a timeout cannot remove files it is still writing.
            image = await asyncio.shield(preparation)
            yield image, question
        finally:
            if preparation.done():
                directory.cleanup()
            else:
                def cleanup_after_preparation(task):
                    if not task.cancelled():
                        task.exception()  # Retrieve a late worker error without logging source inputs.
                    directory.cleanup()
                preparation.add_done_callback(cleanup_after_preparation)

    async def analyze(request: Request, request_id: str, prepared, *, on_handoff=None,
                      monitor_disconnect=True):
        image, question = prepared
        def handoff(model):
            if on_handoff:
                on_handoff(ImageCandidateProgress(
                    request_id=request_id, question_sha256=hashlib.sha256(question.encode()).hexdigest(),
                    image=CandidateImage(sha256=image.sha256, inference_sha256=image.inference_sha256,
                                         width=image.width, height=image.height), requested_model=model))
        inference = asyncio.create_task(request.app.state.service.extract(
            image, question, request_id,
            on_trace=lambda trace: setattr(request.state, "decision_trace", trace),
            on_handoff=handoff if on_handoff else None,
            deadline=request.state.analysis_deadline))
        disconnected = asyncio.create_task(until_disconnect(request)) if monitor_disconnect else None
        try:
            if disconnected is None:
                return await inference
            done, _ = await asyncio.wait((inference, disconnected), return_when=asyncio.FIRST_COMPLETED)
            if inference in done:
                return await inference
            return await disconnected
        finally:
            tasks = [task for task in (inference, disconnected) if task is not None]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def process(request: Request, request_id: str):
        async with prepared_input(request, await read_input(request)) as prepared:
            return await analyze(request, request_id, prepared)

    async def until_disconnect(request: Request):
        while not await request.is_disconnected():
            await asyncio.sleep(0.1)
        raise ApiError(499, "client_disconnected", "Client disconnected before inference completed.", retryable=True)

    async def stream_events(request: Request, prepared):
        # A single handoff plus one terminal frame. No provider work is retried.
        queue = asyncio.Queue(maxsize=2)
        handoff_sent = False

        def handoff(progress):
            nonlocal handoff_sent
            if handoff_sent:
                raise RuntimeError("Analyzer handoff already sent")
            handoff_sent = True
            queue.put_nowait(ImageCandidateStreamEvent(type="handoff", progress=progress))

        async def run():
            try:
                # Starlette listens for disconnects itself on older ASGI specs;
                # on 2.4+ it relies on send errors, so monitor while analysis waits.
                spec = tuple(int(part) for part in request.scope.get("asgi", {}).get("spec_version", "2.0").split("."))
                result = await asyncio.wait_for(analyze(
                    request, request.state.request_id, prepared,
                    on_handoff=handoff, monitor_disconnect=spec >= (2, 4)),
                    timeout=max(0.001, request.state.analysis_deadline - perf_counter()))
                event = ImageCandidateStreamEvent(type="result", result=result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if isinstance(exc, asyncio.TimeoutError):
                    exc = ApiError(504, "deadline_exceeded", "Candidate request exceeded its total deadline.", retryable=True)
                elif not isinstance(exc, ApiError):
                    exc = ApiError(500, "internal_error", "Internal analysis service error.")
                event = ImageCandidateStreamEvent(type="error", error=ImageCandidateError(
                    request_id=request.state.request_id, code=exc.code, message=exc.message,
                    retryable=exc.retryable, decision_trace=getattr(request.state, "decision_trace", None)))
            queue.put_nowait(event)

        worker = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                yield event.model_dump_json(exclude_none=True) + "\n"
                if event.type != "handoff":
                    break
        finally:
            with anyio.CancelScope(shield=True):
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)

    @app.post("/api/v1/candidates", response_model=ImageCandidateResponse,
              responses={200: {"content": {"application/x-ndjson": {"schema": {
                  "type": "string", "description": "Newline-delimited ImageCandidateStreamEvent frames: handoff, then result/error."}}}},
                  **{status: {"model": ImageCandidateError} for status in
                     (413, 415, 422, 429, 499, 500, 502, 503, 504)}},
              openapi_extra=request_body)
    async def candidates(request: Request):
        if request.app.state.service is None:
            key_name = "GEMINI_API_KEY" if settings.provider == "gemini" else "VERDA_INFERENCE_KEY"
            raise ApiError(503, "not_configured", f"Configure {key_name} on the backend.")
        if request.app.state.in_flight >= settings.max_concurrent:
            raise ApiError(429, "busy", "Candidate service is busy; try again later.", retryable=True)
        request.app.state.in_flight += 1
        request.state.analysis_deadline = perf_counter() + settings.deadline_seconds
        streaming = False
        preparation_context = None
        prepared = None
        released = False
        def release():
            nonlocal released
            if not released:
                released = True
                request.app.state.in_flight -= 1
        try:
            accepts = [part.split(";", 1)[0].strip().lower()
                       for part in request.headers.get("accept", "").split(",")]
            if "application/x-ndjson" in accepts:
                # Consume and validate the bounded upload before streaming headers;
                # body reading must not race StreamingResponse's disconnect listener.
                input_data = await asyncio.wait_for(read_input(request), timeout=settings.deadline_seconds)
                preparation_context = prepared_input(request, input_data)
                prepared = await asyncio.wait_for(preparation_context.__aenter__(),
                    timeout=max(0.001, request.state.analysis_deadline - perf_counter()))
                async def cleanup():
                    await preparation_context.__aexit__(None, None, None)
                response = _CandidateStreamResponse(stream_events(request, prepared), release, cleanup)
                streaming = True
                return response
            return await asyncio.wait_for(process(request, request.state.request_id),
                                          timeout=settings.deadline_seconds)
        except asyncio.TimeoutError:
            raise ApiError(504, "deadline_exceeded", "Candidate request exceeded its total deadline.", retryable=True) from None
        finally:
            if not streaming:
                try:
                    if prepared is not None:
                        await preparation_context.__aexit__(None, None, None)
                finally:
                    release()

    install_ifc_routes(app)
    return app


app = create_app()

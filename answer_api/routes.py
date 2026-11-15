"""Additive document registration and common answer HTTP/stream routes."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from time import perf_counter

import anyio
from fastapi import Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, StreamingResponse

from contracts import models as m
from document_engine import DocumentError
from image_api.detail import DetailOptions
from image_api.errors import ApiError

MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_SOURCE_BODY_BYTES = MAX_SOURCE_BYTES + 21 * 1024 * 1024


def document_error(exc):
    code = exc.code
    status = 410 if code in {'missing_source', 'source_expired', 'source_not_found', 'session_expired'} else 409 if 'mismatch' in code else 422
    return ApiError(status, code, str(exc), status == 410)


class _SourceResponse(FileResponse):
    def __init__(self, store, source_id, display):
        self.store, self.source_id, self.display = store, source_id, display
        session = store.get(source_id)
        super().__init__(session.display_path if display else session.original_path,
                         media_type='image/png' if display else session.media_type,
                         filename='display.png' if display else session.filename,
                         content_disposition_type='attachment', headers={'X-Content-Type-Options': 'nosniff'})

    async def __call__(self, scope, receive, send):
        with self.store.lease(self.source_id):
            await super().__call__(scope, receive, send)


def install_answer_routes(app, settings, *, prepare, analyze, stream_response):
    @app.post('/api/v1/sources')
    async def register_source(request: Request):
        if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'multipart/form-data':
            raise ApiError(415, 'unsupported_media_type', 'Send original file, displayed PNG image and snapshot JSON as multipart/form-data.')
        try:
            async with request.form(max_files=2, max_fields=1, max_part_size=16 * 1024) as form:
                if set(form) != {'file', 'image', 'snapshot'} or any(len(form.getlist(key)) != 1 for key in form):
                    raise ApiError(422, 'invalid_request', 'Supply exactly one original file, displayed PNG image and snapshot.')
                original, raster, value = form['file'], form['image'], form['snapshot']
                if not isinstance(original, UploadFile) or not isinstance(raster, UploadFile) or not isinstance(value, str):
                    raise ApiError(422, 'invalid_request', 'Source file and image must be uploads; snapshot must be JSON text.')
                try:
                    snapshot = m.AnswerSnapshot.model_validate_json(value)
                except (ValueError, ValidationError):
                    raise ApiError(422, 'invalid_snapshot', 'Snapshot does not match the source binding contract.') from None
                content = await original.read(MAX_SOURCE_BYTES + 1)
                image = await raster.read(settings.max_image_bytes + 1)
                if len(content) > MAX_SOURCE_BYTES or len(image) > settings.max_image_bytes:
                    raise ApiError(413, 'source_too_large', 'Original or display exceeds the document session byte limit.')
                from .service import cpu_work
                session = await cpu_work(request.app.state.documents.register, content, original.filename or 'source', image,
                                         snapshot.model_dump(exclude_none=True))
                return session.public()
        except HTTPException:
            raise ApiError(422, 'invalid_multipart', 'Malformed or oversized document registration fields.') from None
        except DocumentError as exc:
            raise document_error(exc) from None

    @app.delete('/api/v1/sources/{source_id}', status_code=204)
    async def remove_source(source_id: str, request: Request):
        await asyncio.to_thread(request.app.state.documents.delete, source_id)

    @app.get('/api/v1/sources/{source_id}')
    async def original_source(source_id: str, request: Request):
        try:
            return _SourceResponse(request.app.state.documents, source_id, False)
        except DocumentError as exc:
            raise document_error(exc) from None

    @app.get('/api/v1/sources/{source_id}/display')
    async def displayed_source(source_id: str, request: Request):
        try:
            return _SourceResponse(request.app.state.documents, source_id, True)
        except DocumentError as exc:
            raise document_error(exc) from None

    async def until_disconnect(request):
        while not await request.is_disconnected():
            await asyncio.sleep(.1)
        raise ApiError(499, 'client_disconnected', 'Client disconnected before the answer completed.', True)

    async def run(request, question, on_handoff=None):
        async def visual(session, text, request_id, budget, *, detail, on_handoff):
            if request.app.state.service is None:
                raise ApiError(503, 'not_configured', 'Configure the selected image provider on the backend.')
            if detail and request.app.state.detail_tools is None:
                raise ApiError(503, 'detail_not_configured', 'Detailed scan requires the Gemini image provider on the backend.')
            budget.check(2)
            options = DetailOptions(mode='tiles', max_calls=min(9, max(1, budget.attempts_remaining - 1)))
            content = await asyncio.to_thread(session.display_path.read_bytes)
            request.state.analysis_deadline = budget.deadline
            async with prepare(request, (content, text, options), 'detail' if detail else None) as prepared:
                request.state.decision_trace = None
                dispatched = None
                started = perf_counter()
                def dispatched_model(progress):
                    nonlocal dispatched
                    dispatched = progress.requested_model
                    if on_handoff is not None:
                        on_handoff(progress.model_copy(update={
                            'question_sha256': hashlib.sha256(question.question.encode('utf-8')).hexdigest()}))
                try:
                    observed = await analyze(request, request_id, prepared, on_handoff=dispatched_model,
                                             monitor_disconnect=False, tool='detail' if detail else None)
                except BaseException as exc:
                    trace = getattr(request.state, 'decision_trace', None)
                    if trace is not None and trace.calls:
                        budget.visual_trace(trace)
                    elif dispatched is not None:
                        budget.failed_visual(dispatched, started, exc)
                    raise
                budget.visual(observed)
                return observed
        try:
            return await request.app.state.answer_service.answer(question, request.state.request_id,
                                                                  visual=visual, on_handoff=on_handoff)
        except DocumentError as exc:
            raise document_error(exc) from None

    async def events(request, question):
        queue = asyncio.Queue(maxsize=2)
        sent = False

        def handoff(progress):
            nonlocal sent
            if not sent:
                sent = True
                queue.put_nowait({'schema_version': '0.1.0', 'type': 'handoff', 'progress': progress.model_dump(mode='json')})

        async def worker():
            try:
                response = await asyncio.wait_for(run(request, question, handoff), timeout=settings.deadline_seconds)
                event = {'schema_version': '0.1.0', 'type': 'result', 'result': response.model_dump(mode='json')}
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if isinstance(exc, asyncio.TimeoutError):
                    exc = ApiError(504, 'deadline_exceeded', 'The question exceeded its shared deadline.', True)
                elif not isinstance(exc, ApiError):
                    exc = ApiError(500, 'internal_error', 'Internal source-backed answer service error.')
                error = m.ImageCandidateError(request_id=request.state.request_id, code=exc.code,
                    message=exc.message, retryable=exc.retryable,
                    decision_trace=getattr(request.state, 'decision_trace', None))
                event = {'schema_version': '0.1.0', 'type': 'error', 'error': error.model_dump(mode='json')}
            queue.put_nowait(event)

        task, disconnected = asyncio.create_task(worker()), asyncio.create_task(until_disconnect(request))
        try:
            while True:
                next_event = asyncio.create_task(queue.get())
                try:
                    done, _ = await asyncio.wait((next_event, disconnected), return_when=asyncio.FIRST_COMPLETED)
                    if next_event not in done:
                        await disconnected
                    event = await next_event
                    yield json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n'
                    if event['type'] != 'handoff':
                        break
                finally:
                    next_event.cancel()
                    await asyncio.gather(next_event, return_exceptions=True)
        finally:
            with anyio.CancelScope(shield=True):
                task.cancel()
                disconnected.cancel()
                await asyncio.gather(task, disconnected, return_exceptions=True)

    @app.post('/api/v1/answers', response_model=m.AnswerResponse)
    async def answer(request: Request, question: m.AnswerRequest):
        # Fail expired/stale registrations before streaming headers, so clients
        # can re-register safely without repeating a paid analysis.
        if question.source_id:
            try:
                session = request.app.state.documents.get(question.source_id)
            except DocumentError as exc:
                raise document_error(exc) from None
            if session.source_sha256 != question.source_sha256:
                raise ApiError(409, 'source_mismatch', 'The question belongs to a different original source revision.')
            if question.snapshot is not None and question.snapshot != m.AnswerSnapshot.model_validate(session.public()['snapshot']):
                raise ApiError(409, 'snapshot_mismatch', 'The question belongs to a different displayed page/layout snapshot.')
        else:
            request.app.state.ifc_service._model(question.model_id, question.source_sha256)
        if request.app.state.in_flight >= settings.max_concurrent:
            raise ApiError(429, 'busy', 'Answer service is busy; try again later.', True)
        request.app.state.in_flight += 1
        released = False

        def release():
            nonlocal released
            if not released:
                released = True
                request.app.state.in_flight -= 1

        async def cleanup():
            pass

        accepts = [part.split(';', 1)[0].strip().lower() for part in request.headers.get('accept', '').split(',')]
        if 'application/x-ndjson' in accepts:
            return stream_response(events(request, question), release, cleanup)
        operation = asyncio.create_task(run(request, question))
        disconnected = asyncio.create_task(until_disconnect(request))
        try:
            done, _ = await asyncio.wait((operation, disconnected), timeout=settings.deadline_seconds,
                                         return_when=asyncio.FIRST_COMPLETED)
            if operation in done:
                return await operation
            if disconnected in done:
                return await disconnected
            raise ApiError(504, 'deadline_exceeded', 'The question exceeded its shared deadline.', True)
        finally:
            with anyio.CancelScope(shield=True):
                operation.cancel()
                disconnected.cancel()
                await asyncio.gather(operation, disconnected, return_exceptions=True)
                release()

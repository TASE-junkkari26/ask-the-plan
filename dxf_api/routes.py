"""Bounded, credential-free DXF previews on the existing local backend."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from contracts.models import DxfPreviewResponse
from image_api.errors import ApiError
from .render import MAX_DXF_BYTES, MAX_SVG_BYTES

DEADLINE_SECONDS = 45


async def render_in_process(source: Path, page: int) -> DxfPreviewResponse:
    output = source.parent / "preview.json"
    # Keep font caches within this request's temporary directory on every OS.
    env = {**os.environ, "XDG_CACHE_HOME": str(source.parent / "cache")}
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "dxf_api.worker", str(source), str(output), str(page),
        env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await process.wait()
        if process.returncode != 0 or not output.exists() or output.stat().st_size > MAX_SVG_BYTES * 2:
            raise ApiError(422, "dxf_render_failed", "This DXF layout could not be rendered. Try a PDF export.")
        value = json.loads(output.read_text(encoding="utf-8"))
        if "error" in value:
            error = value["error"]
            raise ApiError(error["status"], error["code"], error["message"])
        return DxfPreviewResponse.model_validate(value["preview"])
    finally:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()


async def _preview(request: Request) -> DxfPreviewResponse:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise ApiError(415, "unsupported_media_type", "Send multipart/form-data with a DXF file and page number.")
    with TemporaryDirectory(prefix="ask-plan-dxf-") as directory:
        source = Path(directory) / "source.dxf"
        try:
            async with request.form(max_files=1, max_fields=1, max_part_size=1024) as form:
                if set(form) != {"file", "page"} or any(len(form.getlist(k)) != 1 for k in form):
                    raise ApiError(422, "invalid_request", "Supply exactly one DXF file and one page number.")
                file, page = form["file"], form["page"]
                if not isinstance(file, UploadFile) or not isinstance(page, str) or not re.fullmatch(r"[1-9][0-9]{0,2}", page):
                    raise ApiError(422, "invalid_request", "Supply a DXF file and a positive page number.")
                size = 0
                with source.open("wb") as destination:
                    while content := await file.read(1024 * 1024):
                        size += len(content)
                        if size > MAX_DXF_BYTES:
                            raise ApiError(413, "dxf_size", "Choose a DXF file no larger than 35 MiB.")
                        destination.write(content)
                if not size:
                    raise ApiError(422, "empty_dxf", "This DXF file is empty.")
        except HTTPException:
            raise ApiError(422, "invalid_multipart", "Malformed or oversized DXF multipart fields.") from None
        render = asyncio.create_task(render_in_process(source, int(page)))

        async def until_disconnect():
            while not await request.is_disconnected():
                await asyncio.sleep(0.1)
            raise ApiError(499, "client_disconnected", "DXF preview cancelled.", retryable=True)

        disconnected = asyncio.create_task(until_disconnect())
        try:
            done, _ = await asyncio.wait((render, disconnected), return_when=asyncio.FIRST_COMPLETED)
            return await (render if render in done else disconnected)
        finally:
            for task in (render, disconnected):
                task.cancel()
            await asyncio.gather(render, disconnected, return_exceptions=True)


def install_dxf_routes(app: FastAPI):
    in_flight = 0

    @app.post("/api/dxf/preview", response_model=DxfPreviewResponse, openapi_extra={
        "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
            "type": "object", "required": ["file", "page"], "additionalProperties": False,
            "properties": {"file": {"type": "string", "format": "binary", "description": "One original DXF, up to 35 MiB."},
                           "page": {"type": "string", "pattern": "^[1-9][0-9]{0,2}$", "description": "1-based index into the source's nonempty layouts."}},
        }}}},
    })
    async def preview(request: Request):
        nonlocal in_flight
        if in_flight >= 2:
            raise ApiError(429, "dxf_busy", "DXF preview service is busy; try again later.", retryable=True)
        in_flight += 1
        try:
            return await asyncio.wait_for(_preview(request), timeout=DEADLINE_SECONDS)
        except asyncio.TimeoutError:
            raise ApiError(504, "dxf_timeout", "DXF preview exceeded its deadline. Export a smaller layout.", retryable=True) from None
        finally:
            in_flight -= 1

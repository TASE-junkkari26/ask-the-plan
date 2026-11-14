"""Install IFC endpoints on the existing local analysis API."""
from __future__ import annotations

import re
import asyncio

from fastapi import FastAPI, Request
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from contracts.models import IfcModelResponse, IfcQuestionRequest, IfcQuestionResponse
from image_api.errors import ApiError


def install_ifc_routes(app: FastAPI):
    @app.post("/api/ifc/models", response_model=IfcModelResponse, openapi_extra={
        "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
            "type": "object", "required": ["file", "source_sha256"], "additionalProperties": False,
            "properties": {"file": {"type": "string", "format": "binary", "description": "One original IFC STEP source, up to 512 MiB."},
                           "source_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$", "description": "SHA-256 of the viewer's original file bytes."}},
        }}}},
    })
    async def upload_ifc(request: Request):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
            raise ApiError(415, "unsupported_media_type", "Send multipart/form-data with file and source_sha256 fields.")
        try:
            # Starlette streams large files to its spool instead of creating a
            # second full-memory request.body() copy. Outer middleware caps bytes.
            async with request.form(max_files=1, max_fields=1, max_part_size=1024) as form:
                if set(form) != {"file", "source_sha256"} or any(len(form.getlist(k)) != 1 for k in form):
                    raise ApiError(422, "invalid_request", "Supply exactly one file and one source_sha256.")
                file, digest = form["file"], form["source_sha256"]
                if not isinstance(file, UploadFile) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise ApiError(422, "invalid_request", "Supply an IFC file and its lowercase SHA-256.")
                return await request.app.state.ifc_service.upload(file, digest)
        except HTTPException:
            raise ApiError(422, "invalid_multipart", "Malformed or oversized IFC multipart fields.") from None

    @app.post("/api/ifc/questions", response_model=IfcQuestionResponse)
    async def ask_ifc(request: Request, question: IfcQuestionRequest):
        return await request.app.state.ifc_service.question(question, request.state.request_id)

    @app.delete("/api/ifc/models/{model_id}", status_code=204)
    async def remove_ifc(model_id: str, request: Request):
        await asyncio.to_thread(request.app.state.ifc_service.delete, model_id)

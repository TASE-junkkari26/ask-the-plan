"""Bounded asynchronous bridge to the repository's pinned PDF.js worker."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
from pathlib import Path
import shutil
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .store import DocumentError, DocumentSession, _thaw

MAX_OUTPUT_BYTES = 8 * 1024 * 1024
WORKER_PATH = Path(__file__).resolve().parents[1] / "frontend" / "scripts" / "pdf-document-worker.mjs"


class NativeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class NativeSpan(NativeModel):
    id: str
    text: str
    native_transform: tuple[float, float, float, float, float, float]
    native_quad: list[tuple[float, float]] = Field(min_length=4, max_length=4)
    display_transform: tuple[float, float, float, float, float, float] | None = None
    display_bbox: tuple[float, float, float, float] | None = None
    width: float
    height: float
    has_eol: bool
    direction: str
    font_name: str
    vertical: bool
    bbox_quality: Literal["font_metrics_estimate"]


class NativePage(NativeModel):
    version: Literal["pdfjs-native-v1"]
    pdfjs_version: str
    source_sha256: str | None = None
    display_sha256: str | None = None
    source_revision: str | None = None
    page_index: int = Field(ge=0)
    page_count: int = Field(gt=0)
    page_rotation: int
    rotation: int
    source_bounds: tuple[float, float, float, float]
    native_user_unit: float = Field(gt=0)
    viewport_transform: tuple[float, float, float, float, float, float] | None
    display_width: int = Field(gt=0)
    display_height: int = Field(gt=0)
    mapping_verified: bool
    text_enumeration_complete: bool
    unresolved_items: int = Field(ge=0)
    spans: list[NativeSpan] = Field(max_length=100000)
    warnings: list[str]

    def lookup(self, literal: str, *, case_sensitive: bool = True, exact: bool = True) -> list[NativeSpan]:
        """Return all anchored matches; repeated identifiers stay ambiguous."""
        if not literal:
            raise DocumentError("invalid_lookup", "A native source lookup requires a nonempty literal.")
        needle = literal if case_sensitive else literal.casefold()
        found = []
        for span in self.spans:
            value = span.text if case_sensitive else span.text.casefold()
            if (value.strip() == needle.strip()) if exact else (needle in value):
                found.append(span)
        return found


async def _read_bounded(stream: asyncio.StreamReader, limit: int) -> bytes:
    chunks = []
    size = 0
    while chunk := await stream.read(min(65536, limit + 1 - size)):
        chunks.append(chunk)
        size += len(chunk)
        if size > limit:
            raise DocumentError("native_output_limit", "The PDF worker output exceeds its byte limit.")
    return b"".join(chunks)


async def _terminate(process: asyncio.subprocess.Process):
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    await process.wait()


async def extract_pdf(session: DocumentSession, *, timeout_seconds: float = 30,
                      node_executable: str | None = None, use_cache: bool = True) -> NativePage:
    """Extract one registered PDF page, retaining bytes until worker termination.

    The owner must hold ``DocumentStore.lease`` for the entire await. A browser's
    spans never enter this bridge. Matching hashes bind bytes, not their semantics.
    """
    if session.format != "pdf":
        raise DocumentError("unsupported_native_source", "Native PDF extraction requires a registered original PDF.")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("The PDF worker timeout must be positive.")
    if hashlib.sha256(session.original_path.read_bytes()).hexdigest() != session.source_sha256:
        raise DocumentError("source_hash_mismatch", "The registered original bytes no longer match their source hash.")
    key = hashlib.sha256(json.dumps({"version": "pdfjs-native-v1", "source": session.source_sha256,
                                     "display": session.display_sha256, "snapshot": _thaw(session.snapshot)},
                                    sort_keys=True).encode()).hexdigest()[:24]
    cache_path = session.original_path.parent / f"native-{key}.json"
    if use_cache and cache_path.is_file():
        try:
            if cache_path.stat().st_size <= MAX_OUTPUT_BYTES:
                raw = cache_path.read_bytes()
                cached = NativePage.model_validate_json(raw)
                if (cached.source_sha256 == session.source_sha256 and cached.display_sha256 == session.display_sha256
                        and cached.source_revision == session.source_revision):
                    return cached
        except (ValueError, OSError):
            pass
    node = node_executable or shutil.which("node")
    if not node or not WORKER_PATH.is_file():
        raise DocumentError("native_worker_unavailable", "Install Node.js and the locked frontend dependencies to extract native PDF text.")
    try:
        process = await asyncio.create_subprocess_exec(node, "--max-old-space-size=384", str(WORKER_PATH),
                                                      stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                      stderr=asyncio.subprocess.DEVNULL)
    except OSError as exc:
        raise DocumentError("native_worker_unavailable", "The local PDF.js worker could not be started.") from exc

    async def execute():
        payload = json.dumps({"source_path": str(session.original_path), "snapshot": _thaw(session.snapshot)}).encode()
        process.stdin.write(payload)
        await process.stdin.drain()
        process.stdin.close()
        output = await _read_bounded(process.stdout, MAX_OUTPUT_BYTES)
        await process.wait()
        try:
            decoded = json.loads(output)
        except (ValueError, UnicodeDecodeError) as exc:
            raise DocumentError("native_extraction_failed", "The PDF worker did not return valid structured output.") from exc
        if "error" in decoded:
            raise DocumentError(decoded["error"]["code"], decoded["error"]["message"])
        if process.returncode:
            raise DocumentError("native_extraction_failed", "The local PDF worker did not finish successfully.")
        page = NativePage.model_validate(decoded)
        page.source_sha256, page.display_sha256 = session.source_sha256, session.display_sha256
        page.source_revision = session.source_revision
        if use_cache:
            # Same-directory replace prevents a parallel reader from observing a partial cache.
            temporary = cache_path.with_suffix(".tmp-" + uuid4().hex)
            temporary.write_text(page.model_dump_json(), encoding="utf-8")
            temporary.replace(cache_path)
        return page
    try:
        return await asyncio.wait_for(execute(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        raise DocumentError("native_extraction_timeout", "Native PDF extraction exceeded its request deadline.") from exc
    finally:
        # Complete termination before the lease owner can remove source/session files.
        await asyncio.shield(_terminate(process))

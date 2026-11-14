"""Immutable original/display registrations with bounded, lease-aware lifetime."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
import shutil
from threading import RLock
from time import monotonic
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4

from PIL import Image, UnidentifiedImageError


class DocumentError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DocumentSession:
    source_id: str
    source_sha256: str
    display_sha256: str
    source_revision: str
    filename: str
    media_type: str
    format: str
    original_path: Path = field(repr=False)
    display_path: Path = field(repr=False)
    snapshot: Mapping
    display_width: int
    display_height: int

    def public(self) -> dict:
        return {"source_id": self.source_id, "source_sha256": self.source_sha256,
                "display_sha256": self.display_sha256, "source_revision": self.source_revision,
                "filename": self.filename, "media_type": self.media_type, "format": self.format,
                "snapshot": _thaw(self.snapshot), "display_width": self.display_width,
                "display_height": self.display_height}


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass
class _Entry:
    session: DocumentSession
    touched: float
    leases: int = 0
    removed: bool = False


def validate_snapshot(snapshot: dict, width: int, height: int, source_hash: str) -> dict:
    """A declared display context, not a claim of native coordinate validity."""
    if not isinstance(snapshot, dict):
        raise DocumentError("invalid_snapshot", "The source snapshot must be an object.")
    known = {"page_index", "layout_name", "rotation", "viewport_transform", "source_bounds", "display_width", "display_height", "source_revision", "source_sha256", "display_sha256"}
    if set(snapshot) - known:
        raise DocumentError("invalid_snapshot", "Unknown source snapshot fields.")
    result = dict(snapshot)
    page = result.setdefault("page_index", 0)
    if isinstance(page, bool) or not isinstance(page, int) or page < 0 or page > 99999:
        raise DocumentError("invalid_snapshot", "Select a nonnegative source page/layout index.")
    rotation = result.setdefault("rotation", 0)
    if isinstance(rotation, bool) or not isinstance(rotation, int) or rotation % 90:
        raise DocumentError("invalid_snapshot", "Source rotation must be a multiple of 90 degrees.")
    result["rotation"] = rotation % 360
    layout = result.get("layout_name")
    if layout is not None and (not isinstance(layout, str) or not layout.strip() or len(layout) > 1024):
        raise DocumentError("invalid_snapshot", "A layout name must preserve a nonempty source name.")
    for key, length in (("viewport_transform", 6), ("source_bounds", 4)):
        value = result.get(key)
        if value is not None and (not isinstance(value, (list, tuple)) or len(value) != length
                                  or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value)):
            raise DocumentError("invalid_snapshot", f"{key} needs {length} finite numbers.")
        if value is not None:
            result[key] = list(value)
    bounds = result.get("source_bounds")
    if bounds is not None and (bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        raise DocumentError("invalid_snapshot", "Source bounds need positive width and height.")
    matrix = result.get("viewport_transform")
    if matrix is not None and abs(matrix[0] * matrix[3] - matrix[1] * matrix[2]) < 1e-12:
        raise DocumentError("invalid_snapshot", "The viewport transform must be invertible.")
    for key, expected in (("display_width", width), ("display_height", height)):
        if key in result and result[key] != expected:
            raise DocumentError("snapshot_mismatch", "Display dimensions do not match the submitted PNG.")
        result[key] = expected
    if result.get("source_revision", source_hash) != source_hash:
        raise DocumentError("snapshot_mismatch", "Source revision does not match the original bytes.")
    result["source_revision"] = source_hash
    if result.get("source_sha256", source_hash) != source_hash:
        raise DocumentError("source_hash_mismatch", "Snapshot source hash does not match the original bytes.")
    result["source_sha256"] = source_hash
    return result


class DocumentStore:
    """A process-local temporary registry. Active leases are never evicted.

    Callers keep a lease until owned workers have stopped, including cancellation.
    ``delete`` hides a session immediately and cleans its bytes after the last lease.
    The owner supplies and removes ``root``; this class touches only its own children.
    """

    def __init__(self, root: Path, max_sessions: int = 8, ttl_seconds: float = 1800,
                 max_original_bytes: int = 64 * 1024 * 1024,
                 max_display_bytes: int = 20 * 1024 * 1024,
                 max_display_pixels: int = 40_000_000):
        if max_sessions < 1 or ttl_seconds <= 0:
            raise ValueError("Document store limits must be positive.")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self.max_original_bytes = max_original_bytes
        self.max_display_bytes = max_display_bytes
        self.max_display_pixels = max_display_pixels
        self._entries: dict[str, _Entry] = {}
        self._lock = RLock()
        self._closed = False

    def _remove(self, identifier: str):
        entry = self._entries.pop(identifier)
        shutil.rmtree(entry.session.original_path.parent)

    def _prune(self):
        now = monotonic()
        for identifier, entry in list(self._entries.items()):
            if not entry.leases and (entry.removed or now - entry.touched >= self.ttl_seconds):
                self._remove(identifier)

    def register(self, original: bytes, filename: str, display_png: bytes, snapshot: dict,
                 *, source_sha256: str | None = None, display_sha256: str | None = None) -> DocumentSession:
        if not original or len(original) > self.max_original_bytes:
            raise DocumentError("source_size_limit", "The original source is empty or exceeds the source byte limit.")
        if not display_png or len(display_png) > self.max_display_bytes:
            raise DocumentError("display_size_limit", "The display PNG is empty or exceeds the display byte limit.")
        # Paths remain opaque and server-owned even when the upload uses Windows separators.
        name = re.split(r"[/\\]", str(filename))[-1]
        if not name or len(name) > 1024 or "\x00" in name:
            raise DocumentError("invalid_source", "Supply an original source filename.")
        extension = Path(name).suffix.lower()
        types = {".pdf": ("pdf", "application/pdf"), ".svg": ("svg", "image/svg+xml"),
                 ".dxf": ("dxf", "application/dxf"), ".png": ("png", "image/png"),
                 ".jpg": ("jpeg", "image/jpeg"), ".jpeg": ("jpeg", "image/jpeg"),
                 ".webp": ("other", "image/webp"), ".gif": ("other", "image/gif"), ".bmp": ("other", "image/bmp")}
        if extension not in types:
            raise DocumentError("unsupported_source", "Register a PDF, SVG, DXF or supported original image.")
        if extension == ".pdf" and not original[:1024].lstrip().startswith(b"%PDF-"):
            raise DocumentError("invalid_source", "The original does not contain a PDF header.")
        source_hash = hashlib.sha256(original).hexdigest()
        display_hash = hashlib.sha256(display_png).hexdigest()
        if source_sha256 is not None and source_sha256 != source_hash:
            raise DocumentError("source_hash_mismatch", "The original source hash does not match its bytes.")
        if display_sha256 is not None and display_sha256 != display_hash:
            raise DocumentError("display_hash_mismatch", "The displayed raster hash does not match its bytes.")
        try:
            with Image.open(BytesIO(display_png)) as image:
                if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                    raise DocumentError("invalid_display", "Supply one already-upright display PNG.")
                width, height = image.size
                if width * height > self.max_display_pixels:
                    raise DocumentError("display_size_limit", "The display PNG exceeds the decoded pixel limit.")
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise DocumentError("invalid_display", "The display PNG could not be decoded.") from exc
        context = validate_snapshot(snapshot, width, height, source_hash)
        if context.get("display_sha256", display_hash) != display_hash:
            raise DocumentError("display_hash_mismatch", "Snapshot display hash does not match the submitted PNG.")
        context["display_sha256"] = display_hash
        with self._lock:
            if self._closed:
                raise DocumentError("source_store_closed", "The source registry is closed.")
            self._prune()
            while len(self._entries) >= self.max_sessions:
                available = [(entry.touched, identifier) for identifier, entry in self._entries.items() if not entry.leases]
                if not available:
                    raise DocumentError("source_store_busy", "All source sessions are in use; retry after current questions finish.")
                self._remove(min(available)[1])
            identifier = "source-" + uuid4().hex
            directory = self.root / identifier
            directory.mkdir(mode=0o700)
            try:
                original_path, display_path = directory / ("original" + extension), directory / "display.png"
                original_path.write_bytes(original)
                display_path.write_bytes(display_png)
                session = DocumentSession(identifier, source_hash, display_hash, source_hash, name,
                                          types[extension][1], types[extension][0], original_path,
                                          display_path, _freeze(context), width, height)
                (directory / "registration.json").write_text(json.dumps(session.public(), ensure_ascii=False), encoding="utf-8")
                self._entries[identifier] = _Entry(session, monotonic())
                return session
            except BaseException:
                shutil.rmtree(directory)
                raise

    def get(self, source_id: str) -> DocumentSession:
        with self._lock:
            self._prune()
            entry = self._entries.get(source_id)
            if entry is None or entry.removed:
                raise DocumentError("missing_source", "This source session is absent, expired or was removed; register it again.")
            entry.touched = monotonic()
            return entry.session

    @contextmanager
    def lease(self, source_id: str):
        with self._lock:
            session = self.get(source_id)
            self._entries[source_id].leases += 1
        try:
            yield session
        finally:
            with self._lock:
                entry = self._entries[source_id]
                entry.leases -= 1
                entry.touched = monotonic()
                if not entry.leases and entry.removed:
                    self._remove(source_id)

    def delete(self, source_id: str):
        with self._lock:
            entry = self._entries.get(source_id)
            if entry is not None:
                entry.removed = True
                if not entry.leases:
                    self._remove(source_id)

    def close(self):
        with self._lock:
            self._closed = True
            for identifier in list(self._entries):
                self.delete(identifier)

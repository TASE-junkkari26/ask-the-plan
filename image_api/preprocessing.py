"""Bounded, session-only raster preparation behind the candidate endpoint.

Always normalize through images.prepare_image first. The only alternative model
input is a retained full-source overview, never a heuristic region or main crop.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
import hashlib
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import RLock
from time import perf_counter

from contracts.models import PreparedDrawing
from drawing_preprocessor import PreprocessConfig, PreparationError, load_manifest, prepare_drawing

from .config import ApiSettings
from .errors import ApiError
from .images import PreparedImage, prepare_image


class ImagePreprocessor:
    """One instance per API lifespan; all cache writers are serialized.

    Cached artifacts are private backend files, not public resource URLs. Model
    images are copied to the request directory so LRU eviction cannot invalidate
    an in-flight inference. close() drains preparation before removing its cache.
    """

    def __init__(self, settings: ApiSettings):
        self.settings = settings
        self._temporary = TemporaryDirectory(prefix="ask-plan-prepared-")
        self.cache_root = Path(self._temporary.name)
        self._lock = RLock()
        self._closed = False
        self._entries: OrderedDict[str, PreparedDrawing] = OrderedDict()
        self._config = PreprocessConfig(
            overview_long_edge=settings.preprocess_overview_long_edge,
            max_source_pixels=settings.max_pixels,
            ocr="none",
        )

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                self._temporary.cleanup()
                self._entries.clear()

    def _check_open(self) -> None:
        if self._closed:
            raise ApiError(503, "preprocessor_closed", "The image preparation service is shutting down.")

    def _evict(self) -> None:
        while len(self._entries) > self.settings.preprocess_cache_entries:
            _, manifest = self._entries.popitem(last=False)
            path = self.cache_root / manifest.id
            # Only remove recorded artifact directories owned by this session.
            if (path.is_symlink() or path.resolve().parent != self.cache_root.resolve()
                    or path.name != manifest.id):
                raise PreparationError("Session cache path is invalid.")
            shutil.rmtree(path)

    def prepare(self, content: bytes, directory: Path) -> PreparedImage:
        started = perf_counter()
        with self._lock:
            self._check_open()
        image = prepare_image(content, self.settings, directory)
        if self.settings.preprocess_mode == "off":
            return replace(image, preparation_ms=(perf_counter() - started) * 1000)
        try:
            with self._lock:
                self._check_open()
                key = image.inference_sha256  # Canonical upright PNG, not incoming EXIF pixels.
                cached = self._entries.get(key)
                hit = False
                if cached is not None:
                    try:
                        checked = load_manifest(self.cache_root / cached.id / "manifest.json")
                        if checked.source_sha256 == key:
                            cached, hit = checked, True
                    except PreparationError:
                        pass
                if not hit:
                    cached = prepare_drawing(
                        image.path, self.cache_root, config=self._config,
                        source_uri="submitted-raster:sha256:" + key,
                    )
                self._entries[key] = cached
                self._entries.move_to_end(key)
                self._evict()

                model_path, model_sha = image.path, image.inference_sha256
                model_width, model_height = image.width, image.height
                if self.settings.preprocess_mode == "overview":
                    full = next(region for region in cached.regions if region.role == "full_source")
                    # Keep all page panels, scale bars, title blocks and relative
                    # positions. Region roles are never input-selection rules.
                    overview = (self.cache_root / cached.id / full.overview_uri).resolve()
                    if not overview.is_relative_to(self.cache_root.resolve()):
                        raise PreparationError("Session overview path is invalid.")
                    model_path = directory / "model-overview.png"
                    shutil.copyfile(overview, model_path)
                    if model_path.stat().st_size > self.settings.max_image_bytes:
                        raise ApiError(413, "prepared_image_too_large", "The prepared overview exceeds the inference image size limit.")
                    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
                    model_width, model_height = full.overview_width, full.overview_height
                return replace(
                    image, path=model_path, inference_sha256=model_sha,
                    inference_width=model_width, inference_height=model_height,
                    preprocessing_mode=self.settings.preprocess_mode, prepared_id=cached.id,
                    preparation_ms=(perf_counter() - started) * 1000, preparation_cache_hit=hit,
                )
        except (PreparationError, OSError):
            raise ApiError(500, "image_preparation_failed", "Could not prepare cached image artifacts.") from None

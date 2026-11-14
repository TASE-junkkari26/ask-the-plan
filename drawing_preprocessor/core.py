"""Immutable raster preparation and coordinate-preserving detail crops."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tempfile
from typing import Literal
import warnings

import numpy as np
from PIL import Image, ImageDraw, UnidentifiedImageError, __version__ as pillow_version
from pydantic import ValidationError

from contracts.models import InspectRegionArgs, OCRResult, PreparedDrawing, PreparedRegion
from .layout import RegionCandidate, detect_regions
from .ocr import language_fingerprint, recognize, tesseract_version

PIPELINE_VERSION = "0.1.0"


class PreparationError(ValueError):
    """Invalid input or an unavailable/corrupted artifact, safe for CLI output."""


@dataclass(frozen=True)
class PreprocessConfig:
    overview_long_edge: int = 1600
    analysis_long_edge: int = 1200
    padding: int = 12
    ocr: Literal["none", "tesseract"] = "none"
    ocr_languages: str = "eng"
    ocr_timeout_seconds: float = 30
    max_source_pixels: int = 50_000_000

    def __post_init__(self):
        for name in ("overview_long_edge", "analysis_long_edge"):
            value = getattr(self, name)
            minimum = 128 if name == "analysis_long_edge" else 64
            if type(value) is not int or not minimum <= value <= 8192:
                raise PreparationError(f"{name} must be an integer between {minimum} and 8192.")
        if type(self.padding) is not int or not 0 <= self.padding <= 512:
            raise PreparationError("padding must be an integer between 0 and 512.")
        if self.ocr not in {"none", "tesseract"}:
            raise PreparationError("ocr must be none or tesseract.")
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", self.ocr_languages):
            raise PreparationError("Invalid OCR language codes.")
        if (not math.isfinite(self.ocr_timeout_seconds) or not 0 < self.ocr_timeout_seconds <= 600):
            raise PreparationError("OCR timeout must be finite and between 0 and 600 seconds.")
        if type(self.max_source_pixels) is not int or not 1 <= self.max_source_pixels <= 100_000_000:
            raise PreparationError("max_source_pixels must be between 1 and 100000000.")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _artifact(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise PreparationError("Artifact path escapes its prepared drawing directory.")
    return path


def _resize(image: Image.Image, edge: int) -> Image.Image:
    scale = min(1.0, edge / max(image.size))
    size = tuple(max(1, round(side * scale)) for side in image.size)
    return image.copy() if size == image.size else image.resize(size, Image.Resampling.LANCZOS)


def load_manifest(path: str | Path) -> PreparedDrawing:
    """Load a manifest and verify the original and all prepared artifact hashes."""
    path = Path(path)
    try:
        if path.name != "manifest.json":
            raise PreparationError("Use the canonical manifest.json from the prepared directory.")
        manifest = PreparedDrawing.model_validate_json(path.read_text(encoding="utf-8"))
        checksums = json.loads(_artifact(path.parent, "checksums.json").read_text(encoding="utf-8"))
        required = {"manifest.json", manifest.original_uri, manifest.source_image_uri, "layout.png"}
        required.update(r.image_uri for r in manifest.regions)
        required.update(r.overview_uri for r in manifest.regions)
        if not isinstance(checksums, dict) or not required.issubset(checksums):
            raise PreparationError("Prepared artifact checksum inventory is incomplete.")
        for name in required:
            if _sha(_artifact(path.parent, name)) != checksums[name]:
                raise PreparationError("A prepared artifact has changed; prepare the source again.")
        if _sha(_artifact(path.parent, manifest.original_uri)) != manifest.source_sha256:
            raise PreparationError("Prepared original does not match the source hash.")
        return manifest
    except (OSError, ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, PreparationError):
            raise
        raise PreparationError("Cannot load prepared drawing; prepare the source again.") from None


def prepare_drawing(source: str | Path, output_root: str | Path, *,
                    config: PreprocessConfig | None = None, source_uri: str | None = None) -> PreparedDrawing:
    config = config or PreprocessConfig()
    source, output_root = Path(source), Path(output_root)
    try:
        # A single byte snapshot binds decoding, hashing and the archived source
        # even when another process replaces the incoming file during ingestion.
        with source.open("rb") as incoming:
            original_content = incoming.read(128 * 1024 * 1024 + 1)
        if len(original_content) > 128 * 1024 * 1024:
            raise PreparationError("Encoded raster exceeds the 128 MiB input limit.")
        source_sha = hashlib.sha256(original_content).hexdigest()
        # Decode once. Coordinates consistently refer to stored pixels, without
        # silently applying EXIF rotation or using a browser's auto-orientation.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(original_content)) as opened:
                if opened.format not in {"PNG", "JPEG", "WEBP", "TIFF", "BMP"}:
                    raise PreparationError("Supported input formats are PNG, JPEG, WebP, single-page TIFF and BMP.")
                if getattr(opened, "n_frames", 1) != 1:
                    raise PreparationError("Multi-page or animated images must be split into individual pages first.")
                if opened.width * opened.height > config.max_source_pixels:
                    raise PreparationError("Image exceeds max_source_pixels; supply a smaller source or raise the explicit limit.")
                orientation = opened.getexif().get(274, 1)
                extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "TIFF": ".tif", "BMP": ".bmp"}[opened.format]
                if "A" in opened.getbands() or "transparency" in opened.info:
                    rgba = opened.convert("RGBA")
                    image = Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba).convert("RGB")
                else:
                    image = opened.convert("RGB")
        version = tesseract_version() if config.ocr == "tesseract" else None
        config_identity = {**asdict(config), "pipeline_version": PIPELINE_VERSION,
                           "pillow_version": pillow_version, "numpy_version": np.__version__,
                           "ocr_version": version,
                           "ocr_language_data": language_fingerprint(config.ocr_languages) if config.ocr != "none" else {},
                           "source_uri": source_uri or source.name}
        config_sha = hashlib.sha256(_json(config_identity).encode()).hexdigest()
        identity = hashlib.sha256((source_sha + config_sha).encode()).hexdigest()[:32]
        prepared_id = f"prepared-{identity}"
        root = output_root.resolve() / prepared_id
        if root.is_symlink() or not root.resolve().is_relative_to(output_root.resolve()):
            raise PreparationError("Output drawing directory must stay inside the output root.")
        if source.resolve().is_relative_to(root):
            raise PreparationError("Input source must not be inside its target prepared directory.")
        cached_path = root / "manifest.json"
        try:
            cached = load_manifest(cached_path)
            if (cached.source_sha256 == source_sha and cached.config_sha256 == config_sha
                    and cached.id == prepared_id and cached.ocr.status != "failed"):
                return cached
        except PreparationError:
            pass
        root.mkdir(parents=True, exist_ok=True)
        source_frame_id = f"frame:{identity}:source"
        candidates, notices = detect_regions(image, analysis_long_edge=config.analysis_long_edge, padding=config.padding)
        if orientation not in (None, 1):
            notices.append("EXIF orientation is not applied. Generated PNGs and coordinates use the original stored pixel orientation.")
        notices.append("Region roles are layout proposals, not verified floor/view boundaries. Full source remains available.")
        with tempfile.TemporaryDirectory(prefix=".prepare-", dir=output_root.resolve()) as temporary:
            stage = Path(temporary)
            original_uri = "original" + extension
            (stage / original_uri).write_bytes(original_content)
            image.save(stage / "source.png")
            (stage / "regions").mkdir()
            regions = []
            all_candidates = [RegionCandidate((0, 0, *image.size), "full_source", "Uncropped source; no content is discarded.")]
            all_candidates.extend(c for c in candidates if c.bbox != (0, 0, *image.size))
            for index, candidate in enumerate(all_candidates):
                x0, y0, x1, y1 = candidate.bbox
                crop = image.crop(candidate.bbox)
                overview = _resize(crop, config.overview_long_edge)
                image_uri = "source.png" if index == 0 else f"regions/{index:03d}.png"
                overview_uri = f"regions/{index:03d}-overview.png"
                if index:
                    crop.save(stage / image_uri)
                overview.save(stage / overview_uri)
                regions.append(PreparedRegion(
                    id=f"view:{identity}:{index}", role=candidate.role, source_bbox=candidate.bbox,
                    frame_id=f"frame:{identity}:region:{index}", image_uri=image_uri,
                    width=crop.width, height=crop.height, overview_uri=overview_uri,
                    overview_width=overview.width, overview_height=overview.height,
                    overview_frame_id=f"frame:{identity}:overview:{index}",
                    to_source=[[1, 0, x0], [0, 1, y0], [0, 0, 1]],
                    overview_to_source=[[crop.width / overview.width, 0, x0],
                                        [0, crop.height / overview.height, y0], [0, 0, 1]], reason=candidate.reason,
                ))
            if config.ocr == "none":
                ocr = OCRResult(status="not_requested")
            else:
                ocr = recognize(stage / "source.png", frame_id=source_frame_id, width=image.width,
                                height=image.height, languages=config.ocr_languages,
                                timeout=config.ocr_timeout_seconds, version=version)
            notices.extend(ocr.warnings)
            manifest = PreparedDrawing(
                id=prepared_id, source_sha256=source_sha, config_sha256=config_sha, pipeline_version=PIPELINE_VERSION,
                source_uri=source_uri or source.name, original_uri=original_uri, source_image_uri="source.png",
                source_width=image.width, source_height=image.height, source_frame_id=source_frame_id,
                regions=regions, ocr=ocr, warnings=notices,
            )
            debug = _resize(image, 1400)
            draw = ImageDraw.Draw(debug)
            sx, sy = debug.width / image.width, debug.height / image.height
            for index, region in enumerate(regions[1:], 1):
                box = [region.source_bbox[0] * sx, region.source_bbox[1] * sy,
                       region.source_bbox[2] * sx, region.source_bbox[3] * sy]
                draw.rectangle(box, outline="#e05020", width=2)
                draw.text((box[0] + 3, box[1] + 3), str(index), fill="#e05020")
            debug.save(stage / "layout.png")
            (stage / "manifest.json").write_text(_json(manifest.model_dump(mode="json")), encoding="utf-8")
            checksums = {p.relative_to(stage).as_posix(): _sha(p) for p in stage.rglob("*") if p.is_file()}
            (stage / "checksums.json").write_text(_json(checksums), encoding="utf-8")
            # Publish artifact files first and the checksum commit marker last.
            # No recursive removal: a failed run can be regenerated in place.
            for relative in [*sorted(checksums), "checksums.json"]:
                target = _artifact(root, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                (stage / relative).replace(target)
        return manifest
    except PreparationError:
        raise
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise PreparationError("Cannot read/write raster source or prepared artifacts; check format, size and paths.") from None


def inspect_region(manifest_path: str | Path, view_id: str, bbox: list[float] | tuple, *,
                   coordinate_space: str = "view", output_long_edge: int | None = None) -> dict:
    """Crop source pixels using a registered view's pixel coordinates."""
    try:
        args = InspectRegionArgs(view_id=view_id, bbox=bbox, coordinate_space=coordinate_space,
                                 output_long_edge=output_long_edge)
    except ValidationError:
        raise PreparationError("Invalid crop arguments: require finite positive in-view bounds and a valid output size.") from None
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    region = next((item for item in manifest.regions if item.id == args.view_id), None)
    if region is None:
        raise PreparationError("Unknown view ID for this prepared drawing.")
    width, height = ((region.width, region.height) if args.coordinate_space == "view"
                     else (region.overview_width, region.overview_height))
    x0, y0, x1, y1 = args.bbox
    if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
        raise PreparationError("Crop bounds must stay within the selected view dimensions.")
    matrix = region.to_source if args.coordinate_space == "view" else region.overview_to_source
    source_bbox = (math.floor(x0 * matrix[0][0] + matrix[0][2]),
                   math.floor(y0 * matrix[1][1] + matrix[1][2]),
                   math.ceil(x1 * matrix[0][0] + matrix[0][2]),
                   math.ceil(y1 * matrix[1][1] + matrix[1][2]))
    # Numerical rounding at exact source boundaries is limited to that region.
    source_bbox = (max(region.source_bbox[0], source_bbox[0]), max(region.source_bbox[1], source_bbox[1]),
                   min(region.source_bbox[2], source_bbox[2]), min(region.source_bbox[3], source_bbox[3]))
    identity = hashlib.sha256(_json({"prepared": manifest.id, "bbox": source_bbox,
                                    "edge": args.output_long_edge}).encode()).hexdigest()[:24]
    relative = f"inspections/{identity}.png"
    try:
        with Image.open(_artifact(manifest_path.parent, manifest.source_image_uri)) as image:
            crop = image.crop(source_bbox)
            if args.output_long_edge is not None:
                crop = _resize(crop, args.output_long_edge)
            target = _artifact(manifest_path.parent, relative)
            target.parent.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix=".png", dir=target.parent, delete=False) as temporary:
                temporary_path = Path(temporary.name)
            try:
                crop.save(temporary_path)
                temporary_path.replace(target)
            finally:
                temporary_path.unlink(missing_ok=True)
            result = {
                "prepared_id": manifest.id, "view_id": region.id, "source_bbox": list(source_bbox),
                "image_uri": relative, "sha256": _sha(target), "width": crop.width, "height": crop.height,
                "frame_id": f"frame:inspection:{identity}", "source_frame_id": manifest.source_frame_id,
                "to_source": [[(source_bbox[2] - source_bbox[0]) / crop.width, 0, source_bbox[0]],
                              [0, (source_bbox[3] - source_bbox[1]) / crop.height, source_bbox[1]], [0, 0, 1]],
                "ocr_spans": [s.model_dump(mode="json") for s in manifest.ocr.spans
                              if s.bbox[0] < source_bbox[2] and s.bbox[2] > source_bbox[0]
                              and s.bbox[1] < source_bbox[3] and s.bbox[3] > source_bbox[1]],
            }
            return result
    except OSError:
        raise PreparationError("Cannot create requested inspection crop.") from None

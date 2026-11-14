"""Native raster region tools for a host-controlled drawing tool registry.

Arguments contain source-pixel bounds, never filesystem paths. The host supplies
the trusted PreparedImage and owns the output directory and its lifetime. These
operations neither infer semantic views nor establish inventory completeness.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
from typing import Sequence

from PIL import Image, UnidentifiedImageError

from .images import PreparedImage


SourceBox = tuple[int, int, int, int]
Transform = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
MAX_TILE_EDGE = 8192
MAX_TILES = 64
MAX_CROP_BYTES = 20 * 1024 * 1024


class RegionToolError(ValueError):
    """Invalid bounds, unavailable native pixels, or invalid tool limits."""


def validate_source_box(box: Sequence[int], width: int, height: int) -> SourceBox:
    """Validate integer [left, top, right, bottom], without clipping or padding."""
    if (type(width) is not int or type(height) is not int or width <= 0 or height <= 0):
        raise RegionToolError("Source dimensions must be positive integers.")
    if not isinstance(box, (list, tuple)) or len(box) != 4 or any(type(v) is not int for v in box):
        raise RegionToolError("Region bounds must contain four integer source-pixel coordinates.")
    left, top, right, bottom = box
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise RegionToolError("Region bounds must have positive area within the source image.")
    return left, top, right, bottom


@dataclass(frozen=True)
class RegionCrop:
    """A native crop plus the exact translation into its original display frame."""

    id: str
    source_box: SourceBox
    source_sha256: str
    canonical_source_sha256: str
    image: PreparedImage = field(repr=False)
    to_source: Transform

    def to_metadata(self) -> dict:
        """Return serializable tool metadata with no private artifact paths."""
        return {
            "id": self.id,
            "source_sha256": self.source_sha256,
            "canonical_source_sha256": self.canonical_source_sha256,
            "source_frame_id": "display:sha256:" + self.source_sha256,
            "frame_id": self.id,
            "coordinate_system": "display_pixels_top_left",
            "source_box": list(self.source_box),
            "width": self.image.width,
            "height": self.image.height,
            "sha256": self.image.sha256,
            "inference_sha256": self.image.inference_sha256,
            "to_source": [list(row) for row in self.to_source],
        }

    def map_box(self, minimum: Sequence[float], maximum: Sequence[float]) -> tuple[tuple[float, float], tuple[float, float]]:
        """Map crop-pixel candidate bounds to full display pixels exactly once."""
        if (not isinstance(minimum, (list, tuple)) or not isinstance(maximum, (list, tuple))
                or len(minimum) != 2 or len(maximum) != 2):
            raise RegionToolError("Candidate bounds must contain two coordinate pairs.")
        values = (*minimum, *maximum)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise RegionToolError("Candidate coordinates must be finite numbers.")
        x0, y0, x1, y1 = values
        if not (0 <= x0 < x1 <= self.image.width and 0 <= y0 < y1 <= self.image.height):
            raise RegionToolError("Candidate bounds must lie within the crop image.")
        left, top, _, _ = self.source_box
        return (left + x0, top + y0), (left + x1, top + y1)


def _open_native(image: PreparedImage) -> Image.Image:
    if (image.preprocessing_mode == "overview" or image.model_width != image.width
            or image.model_height != image.height):
        raise RegionToolError("Native source pixels are required; an overview cannot be cropped as the display source.")
    try:
        if image.path.stat().st_size > MAX_CROP_BYTES:
            raise RegionToolError("The prepared source image exceeds the image byte limit.")
        content = image.path.read_bytes()
        if hashlib.sha256(content).hexdigest() != image.inference_sha256:
            raise RegionToolError("The prepared source image no longer matches its recorded hash.")
        with Image.open(BytesIO(content)) as stored:
            if stored.format != "PNG" or stored.size != (image.width, image.height) or stored.mode != "RGB":
                raise RegionToolError("Region tools require the canonical full-size RGB PNG source.")
            stored.load()
            return stored.copy()
    except (OSError, UnidentifiedImageError):
        raise RegionToolError("The prepared source image could not be read.") from None


def _extract(image: PreparedImage, source: Image.Image, box: SourceBox, directory: Path) -> RegionCrop:
    identity = json.dumps([image.sha256, image.inference_sha256, box], separators=(",", ":"))
    region_id = "region-" + hashlib.sha256(identity.encode("ascii")).hexdigest()[:32]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (region_id + ".png")
    with source.crop(box) as crop, BytesIO() as encoded:
        crop.save(encoded, format="PNG")
        content = encoded.getvalue()
    if len(content) > MAX_CROP_BYTES:
        raise RegionToolError("The native crop exceeds the prepared image byte limit; use smaller regions.")
    sha = hashlib.sha256(content).hexdigest()
    # Stable repeat calls can reuse their own identical artifact, but never
    # overwrite an unrelated file or follow a pre-existing symbolic link.
    if path.is_symlink():
        raise RegionToolError("The crop artifact path is invalid.")
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError:
        try:
            matches = path.stat().st_size == len(content) and hashlib.sha256(path.read_bytes()).hexdigest() == sha
        except OSError:
            raise RegionToolError("The existing crop artifact could not be read.") from None
        if not matches:
            raise RegionToolError("The crop artifact conflicts with an existing file.") from None
    except OSError:
        raise RegionToolError("The native crop artifact could not be written.") from None
    left, top, right, bottom = box
    crop_image = PreparedImage(path=path, sha256=sha, inference_sha256=sha,
                               width=right-left, height=bottom-top)
    return RegionCrop(
        id=region_id, source_box=box, source_sha256=image.sha256,
        canonical_source_sha256=image.inference_sha256, image=crop_image,
        to_source=((1.0, 0.0, float(left)), (0.0, 1.0, float(top)), (0.0, 0.0, 1.0)),
    )


def crop_region(image: PreparedImage, box: Sequence[int], directory: Path) -> RegionCrop:
    """Extract unchanged native pixels from a host-provided canonical source."""
    valid = validate_source_box(box, image.width, image.height)
    with _open_native(image) as source:
        return _extract(image, source, valid, Path(directory))


def _axis_starts(length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [0]
    starts = list(range(0, length-tile+1, tile-overlap))
    if starts[-1] != length-tile:
        starts.append(length-tile)
    return starts


def _axis_count(length: int, tile: int, overlap: int) -> int:
    if length <= tile:
        return 1
    intervals, remainder = divmod(length-tile, tile-overlap)
    return intervals + 1 + bool(remainder)


def tile_boxes(box: Sequence[int], width: int, height: int, *, tile_size: tuple[int, int] = (1280, 1280),
               overlap: int = 160, max_tiles: int = 16) -> list[SourceBox]:
    """Plan complete overlapping coverage of an explicit region without I/O.

    The final tile on each axis is anchored to the region boundary, so its
    overlap may exceed the requested minimum. Tiles never exceed tile_size or
    extend outside the selected region. Exceeding the call budget is an error;
    the tool never silently drops tiles or enlarges/downsamples them.
    """
    left, top, right, bottom = validate_source_box(box, width, height)
    if (not isinstance(tile_size, (tuple, list)) or len(tile_size) != 2
            or any(type(v) is not int or not 1 <= v <= MAX_TILE_EDGE for v in tile_size)):
        raise RegionToolError("Tile dimensions must be positive integers no greater than 8192.")
    if type(overlap) is not int or not 0 <= overlap < min(tile_size):
        raise RegionToolError("Tile overlap must be a nonnegative integer smaller than each tile dimension.")
    if type(max_tiles) is not int or not 1 <= max_tiles <= MAX_TILES:
        raise RegionToolError("Tile count limit must be an integer between 1 and 64.")
    tw, th = tile_size
    # Check the limit before allocating coordinate lists, even for a very long,
    # thin source or untrusted planning dimensions.
    if _axis_count(right-left, tw, overlap)*_axis_count(bottom-top, th, overlap) > max_tiles:
        raise RegionToolError("The selected region needs more tiles than the configured limit.")
    xs = _axis_starts(right-left, tw, overlap)
    ys = _axis_starts(bottom-top, th, overlap)
    return [(left+x, top+y, min(left+x+tw, right), min(top+y+th, bottom)) for y in ys for x in xs]


def tile_regions(image: PreparedImage, box: Sequence[int], directory: Path, *,
                 tile_size: tuple[int, int] = (1280, 1280), overlap: int = 160,
                 max_tiles: int = 16) -> list[RegionCrop]:
    """Extract native tiles in deterministic row-major order with exact frames."""
    boxes = tile_boxes(box, image.width, image.height, tile_size=tile_size,
                       overlap=overlap, max_tiles=max_tiles)
    with _open_native(image) as source:
        return [_extract(image, source, crop_box, Path(directory)) for crop_box in boxes]


def _optimized_axis(length: int, preferred: int, overlap: int, maximum: int,
                    max_count: int) -> tuple[int, list[int]]:
    """Use a small native edge increase instead of an almost identical tail tile."""
    if length <= maximum:
        return length, [0]
    # This is the fewest intervals that can cover the axis while preserving
    # overlap under the allowed native edge limit. No image pixels are resized.
    step = maximum-overlap
    count = (length-overlap+step-1)//step
    if count > max_count:
        raise RegionToolError("The selected region needs more tiles than the configured limit.")
    # Choose only as much enlargement as complete coverage requires, rather
    # than always increasing each tile to the maximum permitted size.
    edge = max(preferred, (length+(count-1)*overlap+count-1)//count)
    span = length-edge
    starts = [round(i*span/(count-1)) for i in range(count)]
    return edge, starts


def optimized_tile_boxes(box: Sequence[int], width: int, height: int, *,
                         tile_size: tuple[int, int] = (1400, 1400), overlap: int = 200,
                         max_tiles: int = 16, slack_fraction: float = .20,
                         max_tile_edge: int = 2400) -> list[SourceBox]:
    """Plan minimal native coverage with bounded edge slack and balanced seams.

    A region slightly beyond the preferred edge is kept whole if it fits within
    slack_fraction. Larger regions use the fewest grid cells permitted by that
    bound; starts are evenly spaced instead of adding a near-duplicate tail.
    All coordinates stay inside the selected region. The source is never shrunk,
    semantic content is never trimmed, and exceeding max_tiles remains an error.
    The strict tile_boxes operation is unchanged for callers requiring exact caps.
    """
    left, top, right, bottom = validate_source_box(box, width, height)
    if (not isinstance(tile_size, (tuple, list)) or len(tile_size) != 2
            or any(type(v) is not int or not 1 <= v <= MAX_TILE_EDGE for v in tile_size)):
        raise RegionToolError("Tile dimensions must be positive integers no greater than 8192.")
    if type(overlap) is not int or not 0 <= overlap < min(tile_size):
        raise RegionToolError("Tile overlap must be a nonnegative integer smaller than each tile dimension.")
    if type(max_tiles) is not int or not 1 <= max_tiles <= MAX_TILES:
        raise RegionToolError("Tile count limit must be an integer between 1 and 64.")
    if (type(slack_fraction) not in (int, float) or not math.isfinite(slack_fraction)
            or not 0 <= slack_fraction <= .5):
        raise RegionToolError("Native tile slack must be a finite fraction between zero and 0.5.")
    if (type(max_tile_edge) is not int or not max(tile_size) <= max_tile_edge <= MAX_TILE_EDGE):
        raise RegionToolError("Maximum tile edge must contain the preferred tile dimensions and be at most 8192.")
    limits = [min(max_tile_edge, math.floor(edge*(1+slack_fraction))) for edge in tile_size]
    tw, xs = _optimized_axis(right-left, tile_size[0], overlap, limits[0], max_tiles)
    th, ys = _optimized_axis(bottom-top, tile_size[1], overlap, limits[1], max_tiles)
    if len(xs)*len(ys) > max_tiles:
        raise RegionToolError("The selected region needs more tiles than the configured limit.")
    return [(left+x, top+y, left+x+tw, top+y+th) for y in ys for x in xs]


def optimized_tile_regions(image: PreparedImage, box: Sequence[int], directory: Path, *,
                           tile_size: tuple[int, int] = (1400, 1400), overlap: int = 200,
                           max_tiles: int = 16, slack_fraction: float = .20,
                           max_tile_edge: int = 2400) -> list[RegionCrop]:
    """Extract optimized tiles through the same verified native crop machinery."""
    boxes = optimized_tile_boxes(box, image.width, image.height, tile_size=tile_size,
        overlap=overlap, max_tiles=max_tiles, slack_fraction=slack_fraction,
        max_tile_edge=max_tile_edge)
    with _open_native(image) as source:
        return [_extract(image, source, crop_box, Path(directory)) for crop_box in boxes]

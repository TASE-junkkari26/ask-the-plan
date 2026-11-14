"""Conservative whitespace layout proposals for raster drawing ingestion.

The boxes are navigation/cost-saving candidates, not semantic view segmentation.
Pixels and page rules are never removed from exported source/crop images. All
coordinates refer to the supplied image, with half-open right/bottom bounds.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class RegionCandidate:
    bbox: tuple[int, int, int, int]
    role: str
    reason: str


def _runs(values: np.ndarray) -> list[tuple[int, int]]:
    """True intervals, avoiding Python iteration over individual pixels."""
    edges = np.flatnonzero(np.diff(np.pad(values.astype(np.int8), (1, 1))))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


def _bands(occupied: np.ndarray, gap: int) -> list[tuple[int, int]]:
    runs = _runs(occupied)
    groups: list[tuple[int, int]] = []
    for start, end in runs:
        if groups and start - groups[-1][1] < gap:
            groups[-1] = (groups[-1][0], end)
        else:
            groups.append((start, end))
    return groups


def _ignore_long_rules(mask: np.ndarray) -> bool:
    """Ignore thin long rules in the analysis mask only, including page frames."""
    height, width = mask.shape
    row_candidates = mask.sum(axis=1) >= width * 0.80
    col_candidates = mask.sum(axis=0) >= height * 0.80
    removed = False
    for start, end in _runs(row_candidates):
        if end - start <= max(2, math.ceil(height * 0.005)):
            mask[max(0, start - 1):min(height, end + 1), :] = False
            removed = True
    for start, end in _runs(col_candidates):
        if end - start <= max(2, math.ceil(width * 0.005)):
            mask[:, max(0, start - 1):min(width, end + 1)] = False
            removed = True
    return removed


def detect_regions(
    image: Image.Image, *, analysis_long_edge: int = 1200, padding: int = 12,
) -> tuple[list[RegionCandidate], list[str]]:
    """Suggest padded content boxes separated by broad blank page areas.

    Runs on a bounded analysis raster. Dense content, uneven page backgrounds,
    too many fragments, or a blank raster return the full image. For uniform
    pages, every detected foreground run contributes to a candidate; there is
    no "largest connected component only" deletion of notes or separate views.
    Background estimation and thresholding can still miss low-contrast content,
    so the full-resolution original must remain available to callers.
    """
    if isinstance(analysis_long_edge, bool) or not isinstance(analysis_long_edge, int) or analysis_long_edge < 128:
        raise ValueError("analysis_long_edge must be an integer of at least 128")
    if isinstance(padding, bool) or not isinstance(padding, int) or padding < 0:
        raise ValueError("padding must be a nonnegative integer")
    source_width, source_height = image.size
    if source_width <= 0 or source_height <= 0:
        raise ValueError("image dimensions must be positive")
    full = (0, 0, source_width, source_height)

    def fallback(reason: str) -> tuple[list[RegionCandidate], list[str]]:
        return [RegionCandidate(full, "unknown", reason)], [reason]

    # Composite transparency rather than treating transparent RGB values as ink.
    rgba = image.convert("RGBA")
    rgb = Image.new("RGBA", rgba.size, "white")
    rgb.alpha_composite(rgba)
    rgb = rgb.convert("RGB")
    rgb.thumbnail((analysis_long_edge, analysis_long_edge), Image.Resampling.LANCZOS)
    pixels = np.asarray(rgb, dtype=np.int16)
    height, width = pixels.shape[:2]
    edge = max(1, min(height, width) // 100)
    border = np.concatenate((pixels[:edge].reshape(-1, 3), pixels[-edge:].reshape(-1, 3),
                             pixels[:, :edge].reshape(-1, 3), pixels[:, -edge:].reshape(-1, 3)))
    background = np.median(border, axis=0)
    border_distance = np.max(np.abs(border - background), axis=1)
    if float(np.mean(border_distance > 30)) > 0.20:
        return fallback("layout_uncertain_nonuniform_background")
    # A mostly dark perimeter is commonly a photograph/screenshot or a scanned
    # page on a dark surround. Cropping its largest light island is unsafe.
    if float(np.mean(background)) < 150:
        return fallback("layout_uncertain_dark_background")
    mask = np.max(np.abs(pixels - background), axis=2) > 22
    warnings: list[str] = []
    if _ignore_long_rules(mask):
        warnings.append("thin_long_rules_ignored_for_layout_only")
    density = float(mask.mean())
    if density > 0.35:
        return fallback("layout_uncertain_dense_or_noisy_content")
    if not mask.any():
        return fallback("layout_no_distinct_foreground")

    # XY whitespace grouping keeps entire horizontal text/legend bands together,
    # then separates genuinely distant side-by-side figures within each band.
    row_gap = max(12, math.ceil(height * 0.025))
    col_gap = max(24, math.ceil(width * 0.055))
    boxes: list[tuple[int, int, int, int]] = []
    for y1, y2 in _bands(mask.any(axis=1), row_gap):
        band = mask[y1:y2]
        columns = np.flatnonzero(band.any(axis=0))
        # Keep shallow headers/footers/legends in context as one band. Their
        # symbol column and explanation may be widely separated horizontally.
        column_bands = ([(int(columns[0]), int(columns[-1]) + 1)]
                        if y2 - y1 <= height * 0.15
                        else _bands(band.any(axis=0), col_gap))
        for x1, x2 in column_bands:
            submask = band[:, x1:x2]
            rows = np.flatnonzero(submask.any(axis=1))
            if not rows.size:
                continue
            boxes.append((x1, y1 + int(rows[0]), x2, y1 + int(rows[-1]) + 1))
    if not boxes or len(boxes) > 12:
        return fallback("layout_uncertain_fragmented_content")

    scale_x, scale_y = source_width / width, source_height / height
    mapped: list[tuple[int, int, int, int]] = []
    # Two analysis pixels of safety preserve resampling/filter edge support;
    # explicit caller padding is in source pixels, independent of analysis size.
    for x1, y1, x2, y2 in boxes:
        bounds = (max(0, math.floor((x1 - 2) * scale_x) - padding),
                  max(0, math.floor((y1 - 2) * scale_y) - padding),
                  min(source_width, math.ceil((x2 + 2) * scale_x) + padding),
                  min(source_height, math.ceil((y2 + 2) * scale_y) + padding))
        mapped.append(bounds)
    largest = max(range(len(mapped)), key=lambda i: (mapped[i][2] - mapped[i][0]) * (mapped[i][3] - mapped[i][1]))
    candidates = [RegionCandidate(
        bounds,
        "drawing_candidate" if i == largest else "context_candidate",
        "foreground bounds grouped by whitespace; semantic role unverified",
    ) for i, bounds in enumerate(mapped)]
    warnings.append("layout_roles_are_heuristic_candidates")
    return candidates, warnings

"""Optional bounded raster heuristics for omitted-window inspection regions.

Thin parallel/low-contrast axis-aligned linework can suggest where to look,
including internal balcony glazing. These regions are not detected windows,
semantic classifications, counts, calibration or evidence of completeness.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, UnidentifiedImageError

from .region_tools import validate_source_box

ANALYSIS_EDGE = 1800
MAX_SOURCE_PIXELS = 50_000_000
MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_REGION_EDGE = 1600


def _cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        return None


def _box(value, width, height):
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("Existing boxes must contain four finite source coordinates.")
    a, b, c, d = value
    if not (0 <= a < c <= width and 0 <= b < d <= height):
        raise ValueError("Existing boxes must lie inside the source image.")
    return a, b, c, d


def _union(a, b):
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def propose_window_regions(image_path: str | Path, *, source_box: Sequence[int] | None = None,
                           existing_boxes=(), max_regions: int = 2) -> tuple[tuple[int, int, int, int], ...]:
    """Return at most two bounded, half-open native-source inspection boxes.

    Missing OpenCV returns no proposals. Invalid inputs raise ValueError; callers
    retain their normal detection path. The source must already be upright.
    """
    if type(max_regions) is not int or not 0 <= max_regions <= 2:
        raise ValueError("Window inspection permits zero to two regions.")
    if not isinstance(existing_boxes, (list, tuple)) or len(existing_boxes) > 100:
        raise ValueError("At most 100 existing window boxes are supported.")
    path = Path(image_path)
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("Raster exceeds the inspection byte limit.")
        with Image.open(path) as opened:
            width, height = opened.size
            if width * height > MAX_SOURCE_PIXELS:
                raise ValueError("Raster exceeds the inspection pixel limit.")
            if getattr(opened, "n_frames", 1) != 1 or opened.getexif().get(274, 1) != 1:
                raise ValueError("Inspection requires one already-upright raster frame.")
            bounds = (0, 0, width, height) if source_box is None else validate_source_box(source_box, width, height)
            known = [_box(value, width, height) for value in existing_boxes]
            if not max_regions:
                return ()
            cv2 = _cv2()
            if cv2 is None:
                return ()
            region = opened.crop(bounds).convert("RGBA")
            white = Image.new("RGBA", region.size, "white")
            white.alpha_composite(region)
            grey = white.convert("L")
            scale = min(1., ANALYSIS_EDGE / max(grey.size))
            size = max(1, round(grey.width * scale)), max(1, round(grey.height * scale))
            if size != grey.size:
                grey = grey.resize(size, Image.Resampling.LANCZOS)
            pixels = np.asarray(grey)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError("Could not inspect the source raster.") from exc

    if min(pixels.shape) < 24 or np.mean(pixels) < 90:
        return ()
    # Local contrast preserves linework over coloured/grey room fills. Original
    # darkness is checked separately so solid wall interiors do not become frames.
    local = cv2.GaussianBlur(pixels, (31, 31), 0).astype(np.int16)
    ink = ((pixels < 210) & (pixels.astype(np.int16) < local - 9)).astype(np.uint8) * 255
    if np.mean(ink > 0) > .48:
        return ()
    ah, aw = pixels.shape
    sx, sy = aw / (bounds[2]-bounds[0]), ah / (bounds[3]-bounds[1])
    for a, b, c, d in known:
        # A little contextual expansion suppresses repeated proposals for already
        # detected frames; it never deletes an existing model observation.
        a, c = math.floor((a-bounds[0])*sx)-10, math.ceil((c-bounds[0])*sx)+10
        b, d = math.floor((b-bounds[1])*sy)-10, math.ceil((d-bounds[1])*sy)+10
        a, b, c, d = max(0,a), max(0,b), min(aw,c), min(ah,d)
        if a < c and b < d:
            ink[b:d, a:c] = 0

    seeds = []
    minimum = max(20, round(min(aw, ah) * .022))
    maximum_thickness = max(4, min(14, round(min(aw, ah) * .014)))
    for vertical in (True, False):
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, minimum) if vertical else (minimum, 1))
        lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
        count, _, stats, _ = cv2.connectedComponentsWithStats(lines, 8)
        runs = []
        for x, y, w, h, area in stats[1:min(count, 5001)]:
            length, thickness = (h, w) if vertical else (w, h)
            if (length < minimum or length > 1000 or thickness > maximum_thickness
                    or length < 5 * thickness or x <= 1 or y <= 1 or x+w >= aw-1 or y+h >= ah-1):
                continue
            box = int(x), int(y), int(x+w), int(y+h)
            # A truly solid dark rectangle is a poor omission hint. Standalone
            # pale underresolved lines remain eligible; paired black lines below
            # can still form a frame with a visible white interior.
            solid = float(np.mean(pixels[y:y+h, x:x+w] < 80))
            runs.append((box, solid))
            if solid < .86:
                seeds.append((vertical, box, float(length)))
        for i, (a, _) in enumerate(runs[:400]):
            for b, _ in runs[i+1:400]:
                cross_gap = max(a[0],b[0])-min(a[2],b[2]) if vertical else max(a[1],b[1])-min(a[3],b[3])
                overlap = min(a[3],b[3])-max(a[1],b[1]) if vertical else min(a[2],b[2])-max(a[0],b[0])
                shorter = min(a[3]-a[1],b[3]-b[1]) if vertical else min(a[2]-a[0],b[2]-b[0])
                if not (0 <= cross_gap <= 14 and overlap >= .6 * shorter):
                    continue
                union = _union(a,b)
                if float(np.mean(pixels[union[1]:union[3],union[0]:union[2]] < 80)) < .86:
                    seeds.append((vertical, union, float(overlap)))

    # Join close collinear runs into inspection strips; this is not a window
    # instance merge. The full attached crop still carries wall/door context.
    groups = []
    for vertical, box, score in sorted(seeds, key=lambda t: (-t[2], t[1])):
        for group in groups:
            if group[0] != vertical:
                continue
            old = group[1]
            cross = abs((box[0]+box[2]-old[0]-old[2])/2) if vertical else abs((box[1]+box[3]-old[1]-old[3])/2)
            gap = max(box[1],old[1])-min(box[3],old[3]) if vertical else max(box[0],old[0])-min(box[2],old[2])
            union = _union(old,box)
            if (cross <= 16 and gap <= 110 and (union[2]-union[0])/sx <= MAX_REGION_EDGE-100
                    and (union[3]-union[1])/sy <= MAX_REGION_EDGE-100):
                group[1], group[2] = union, group[2]+score
                break
        else:
            groups.append([vertical,box,score])
    result = []
    for vertical, box, score in sorted(groups, key=lambda g: (-g[2],g[1])):
        cross_span = box[2]-box[0] if vertical else box[3]-box[1]
        # Isolated strokes and broad grids/wall bands lack a compact frame-like
        # cross-section. This intentionally favors precision over exhaustive ROIs.
        if not 3 <= cross_span <= 20:
            continue
        pad = 44
        a = max(bounds[0], math.floor(bounds[0]+(box[0]-pad)/sx))
        b = max(bounds[1], math.floor(bounds[1]+(box[1]-pad)/sy))
        c = min(bounds[2], math.ceil(bounds[0]+(box[2]+pad)/sx))
        d = min(bounds[3], math.ceil(bounds[1]+(box[3]+pad)/sy))
        if c-a > MAX_REGION_EDGE or d-b > MAX_REGION_EDGE or (c-a)*(d-b) > min(650000, .4*(bounds[2]-bounds[0])*(bounds[3]-bounds[1])):
            continue
        candidate = a,b,c,d
        if any(max(0,min(c,x[2])-max(a,x[0])) * max(0,min(d,x[3])-max(b,x[1])) > .7 * min((c-a)*(d-b),(x[2]-x[0])*(x[3]-x[1])) for x in result):
            continue
        result.append(candidate)
        if len(result) == max_regions:
            break
    return tuple(result)


def find_solid_window_boxes(image_path: str | Path, boxes) -> tuple[int, ...]:
    """Flag strong solid-wall contradictions for a caller's visual verification.

    Returned indices are not rejected detections. A dark/tinted source window
    can still be real; only a subsequent source-aware check can decide membership.
    Narrow 1–4 pixel glazing and oversized boxes are deliberately left alone.
    """
    if not isinstance(boxes, (list, tuple)) or len(boxes) > 100:
        raise ValueError("At most 100 window boxes are supported.")
    if not boxes:
        return ()
    cv2 = _cv2()
    if cv2 is None:
        return ()
    path = Path(image_path)
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("Raster exceeds the inspection byte limit.")
        with Image.open(path) as image:
            width, height = image.size
            if width * height > MAX_SOURCE_PIXELS:
                raise ValueError("Raster exceeds the inspection pixel limit.")
            if getattr(image,"n_frames",1) != 1 or image.getexif().get(274,1) != 1:
                raise ValueError("Inspection requires one already-upright raster frame.")
            validated = [_box(box,width,height) for box in boxes]
            rgba = image.convert("RGBA")
            white = Image.new("RGBA",rgba.size,"white")
            white.alpha_composite(rgba)
            grey = white.convert("L")
        flagged = []
        for index,(a,b,c,d) in enumerate(validated):
            a,b,c,d = math.floor(a),math.floor(b),math.ceil(c),math.ceil(d)
            w,h = c-a,d-b
            short,long = min(w,h),max(w,h)
            if short < 6 or long < 1.5*short or w*h > 1_000_000 or long > 4096:
                continue
            inset = min(2,max(1,round(short*.2)))
            pixels = np.asarray(grey.crop((a+inset,b+inset,c-inset,d-inset)))
            if not pixels.size:
                continue
            _, dark = cv2.threshold(pixels,100,255,cv2.THRESH_BINARY_INV)
            if float(np.mean(dark > 0)) <= .92:
                continue
            _, bright = cv2.threshold(pixels,150,255,cv2.THRESH_BINARY)
            length = max(3,round((h if h>=w else w)*.5))
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(1,length) if h>=w else (length,1))
            channels = cv2.morphologyEx(bright,cv2.MORPH_OPEN,kernel)
            if not np.any(channels):
                flagged.append(index)
        return tuple(flagged)
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as exc:
        raise ValueError("Could not inspect the source raster.") from exc

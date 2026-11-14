"""Validated polygon arithmetic with explicit per-view calibration and anchors."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
import math
from typing import Iterable

from .quantities import SourceQuantity, UNITS, normalize_unit
from .store import DocumentError


@dataclass(frozen=True)
class GeometryCalibration:
    source_revision: str
    view_id: str
    metres_per_unit: Decimal
    anchor_ids: tuple[str, ...]
    method: str  # native_units, dimension, scale_bar
    estimated: bool = False

    def __post_init__(self):
        if (not self.source_revision or not self.view_id or not self.anchor_ids or
                not self.metres_per_unit.is_finite() or self.metres_per_unit <= 0 or
                self.method not in {"native_units", "dimension", "scale_bar"}):
            raise DocumentError("invalid_calibration", "Geometry needs positive, source-anchored calibration for its exact revision/view.")


@dataclass(frozen=True)
class SourcePolygon:
    id: str
    source_revision: str
    view_id: str
    shell: tuple[tuple[float, float], ...]
    holes: tuple[tuple[tuple[float, float], ...], ...]
    anchor_ids: tuple[str, ...]
    estimated: bool = False


@dataclass(frozen=True)
class AreaCalculation:
    operation: str
    included_polygon_ids: tuple[str, ...]
    excluded_polygon_ids: tuple[str, ...]
    inputs: tuple[dict, ...]
    calibration: GeometryCalibration
    result: SourceQuantity
    geometry: dict


def _polygon(value: SourcePolygon):
    try:
        from shapely.geometry import Polygon
        from shapely.validation import explain_validity
    except ImportError:
        raise DocumentError("geometry_executor_unavailable", "Install the geometry/preprocess dependencies to execute polygon area operations.") from None
    if not value.anchor_ids:
        raise DocumentError("missing_evidence", "Every included/excluded polygon needs source geometry anchors.")
    for ring in (value.shell, *value.holes):
        if len(ring) < 4 or ring[0] != ring[-1] or len(set(ring[:-1])) < 3:
            raise DocumentError("invalid_geometry", "Source polygon rings must be closed with three distinct vertices.")
        if any(len(point) != 2 or not all(math.isfinite(coordinate) for coordinate in point) for point in ring):
            raise DocumentError("invalid_geometry", "Source polygon coordinates must be finite 2D values.")
    polygon = Polygon(value.shell, value.holes)
    if polygon.is_empty or polygon.area <= 0 or not polygon.is_valid:
        raise DocumentError("invalid_geometry", "Source polygon shells/holes intersect, lie outside their shell, or have zero area.")
    return polygon


def calibrated_area(included: Iterable[SourcePolygon], *, calibration: GeometryCalibration,
                    excluded: Iterable[SourcePolygon] = (), basis: str = "net",
                    output_unit: str = "m2", allow_overlap_union: bool = False) -> AreaCalculation:
    """Compute union-minus-exclusions; refuse a guessed raster calibration.

    Geometry is float-based and reported estimated, with every polygon and
    calibration retained. Source-printed exact area remains a separate fact.
    Overlapping included shells require an explicit union request, avoiding a
    silent double count; exclusions must lie within the included union.
    """
    try:
        from shapely.geometry import mapping
        from shapely.ops import unary_union
    except ImportError:
        raise DocumentError("geometry_executor_unavailable", "Install the geometry/preprocess dependencies to execute polygon area operations.") from None
    inputs, omissions = tuple(included), tuple(excluded)
    if not inputs:
        raise DocumentError("missing_geometry", "No supported included geometry was supplied; the area is unknown, not zero.")
    if len(inputs) + len(omissions) > 10000 or sum(len(value.shell) + sum(len(hole) for hole in value.holes) for value in (*inputs, *omissions)) > 200000:
        raise DocumentError("geometry_limit", "The geometry query exceeds its polygon/vertex limit.")
    ids = [value.id for value in (*inputs, *omissions)]
    if len(set(ids)) != len(ids):
        raise DocumentError("duplicate_geometry", "Each contributing polygon must have a distinct source identity.")
    if any(value.source_revision != calibration.source_revision or value.view_id != calibration.view_id for value in (*inputs, *omissions)):
        raise DocumentError("calibration_scope_mismatch", "The geometry and calibration must belong to the same exact source revision and view.")
    shapes = [_polygon(value) for value in inputs]
    removed = [_polygon(value) for value in omissions]
    whole = unary_union(shapes)
    native_sum = sum(shape.area for shape in shapes)
    if not allow_overlap_union and not math.isclose(native_sum, whole.area, rel_tol=1e-10, abs_tol=1e-10):
        raise DocumentError("overlapping_geometry", "Included room shells overlap; resolve membership or request an explicit union.")
    if any(not whole.covers(shape) for shape in removed):
        raise DocumentError("exclusion_outside_scope", "Excluded geometry must lie within the included area scope.")
    result_shape = whole.difference(unary_union(removed)) if removed else whole
    unit = normalize_unit(output_unit)
    if UNITS[unit][0] != (2, 0, 0):
        raise DocumentError("incompatible_dimensions", "An area calculation requires an explicit area unit.")
    with localcontext() as context:
        context.prec = 40
        magnitude = Decimal(str(result_shape.area)) * calibration.metres_per_unit ** 2 / UNITS[unit][1]
    anchors = tuple(dict.fromkeys((*calibration.anchor_ids, *(anchor for value in (*inputs, *omissions) for anchor in value.anchor_ids))))
    result = SourceQuantity(magnitude, unit, "", anchors, basis, "estimated")
    details = tuple({"polygon_id": value.id, "native_area": str(shape.area), "shell": value.shell,
                     "holes": value.holes, "anchor_ids": value.anchor_ids, "role": role}
                    for role, values, geometries in (("included", inputs, shapes), ("excluded", omissions, removed))
                    for value, shape in zip(values, geometries))
    return AreaCalculation("union_minus_exclusions", tuple(value.id for value in inputs),
                           tuple(value.id for value in omissions), details, calibration, result, mapping(result_shape))


def calibration_from_dimension(*, source_revision: str, view_id: str,
                               first: tuple[float, float], second: tuple[float, float],
                               printed: SourceQuantity, dimension_anchor_ids: Iterable[str],
                               crosscheck: tuple[float, float] | None = None,
                               tolerance: Decimal = Decimal("0.02")) -> GeometryCalibration:
    """Tie a physical printed dimension to its measured endpoints in one view.

    A scale label alone supplies no endpoints and cannot call this method.
    Optional crosscheck is (other measured span, other printed metres).
    """
    if printed.dimension != (1, 0, 0) or printed.magnitude <= 0:
        raise DocumentError("invalid_calibration", "A calibration dimension must be a positive supported length.")
    if (len(first) != 2 or len(second) != 2 or
            not all(math.isfinite(value) for value in (*first, *second))):
        raise DocumentError("invalid_calibration", "Dimension endpoints must be finite 2D coordinates.")
    measured = math.dist(first, second)
    if measured <= 0:
        raise DocumentError("invalid_calibration", "Calibration dimension endpoints must differ.")
    ratio = printed.magnitude * UNITS[printed.unit][1] / Decimal(str(measured))
    if crosscheck is not None:
        measured_other, metres_other = map(Decimal, map(str, crosscheck))
        if measured_other <= 0 or metres_other <= 0 or abs(measured_other * ratio - metres_other) / metres_other > tolerance:
            raise DocumentError("calibration_conflict", "The independent dimension cross-check disagrees with the view calibration.")
    anchors = tuple(dict.fromkeys((*printed.anchor_ids, *dimension_anchor_ids)))
    return GeometryCalibration(source_revision, view_id, ratio, anchors, "dimension", True)

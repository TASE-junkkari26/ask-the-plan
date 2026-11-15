"""Bounded regions formed by actual projected boundary and closure geometry."""
from __future__ import annotations

from shapely.geometry import Polygon
from shapely.ops import unary_union

MAX_ENCLOSURE_COORDINATES = 20000


def _polygons(value):
    if value.geom_type == "Polygon":
        yield value
    elif hasattr(value, "geoms"):
        for item in value.geoms:
            yield from _polygons(item)


def enclosed_regions(subject, closures, tolerance_m):
    """Combine source footprints, retaining only subject-associated interiors.

    No closing buffer or convex hull is used. A courtyard made entirely by a
    closure object is not part of the selected wall's enclosed region.
    """
    combined = unary_union([subject, *closures.values()])
    associated, candidates, rejected = [], [], []
    if combined.is_empty or not combined.is_valid:
        return {"status": "unavailable", "reason_code": "invalid_projection_union"}
    for polygon in _polygons(combined):
        for ring in polygon.interiors:
            region = Polygon(ring)
            if region.area <= tolerance_m * tolerance_m or 2 * region.area <= tolerance_m * region.length:
                rejected.append({"area_m2": float(region.area), "reason": "within_physical_tolerance"})
                continue
            contribution = float(region.boundary.intersection(subject).length)
            if contribution <= tolerance_m:
                rejected.append({"area_m2": float(region.area), "reason": "closure_only_courtyard"})
                continue
            refs = {identifier: float(region.boundary.intersection(geometry).length)
                    for identifier, geometry in closures.items()}
            refs = {identifier: length for identifier, length in refs.items() if length > tolerance_m}
            candidates.append({"area_m2": float(region.area), "subject_boundary_length_m": contribution,
                "contributing_references": refs})
            associated.append(region)
    if not associated:
        return {"status": "unavailable", "reason_code": "no_subject_associated_bounded_region",
                "rejected_regions": rejected[:64]}
    # Nested/overlapping associated regions must not be counted twice.
    region = unary_union(associated)
    polygons = list(_polygons(region))
    coordinate_count = sum(len(p.exterior.coords) + sum(len(r.coords) for r in p.interiors) for p in polygons)
    if coordinate_count > MAX_ENCLOSURE_COORDINATES or len(candidates) > 256:
        return {"status": "unavailable", "reason_code": "enclosure_geometry_work_budget"}
    return {"status": "verified", "value": float(region.area), "metadata": {
        "policy": "Union of bounded interiors whose boundary has positive-length support from the selected subject; closure-only courtyards and tolerance-scale slivers are excluded. No artificial gap closing or convex hull is used.",
        "regions": candidates, "rejected_regions": rejected[:64], "coordinate_count": coordinate_count,
        "region_geometry_xy_m": [{"outer": [list(point) for point in polygon.exterior.coords],
            "holes": [[list(point) for point in ring.coords] for ring in polygon.interiors]} for polygon in polygons],
    }}

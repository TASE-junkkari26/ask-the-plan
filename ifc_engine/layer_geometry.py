"""Verify an explicit native layer usage against a uniform closed host solid.

This module establishes geometric prerequisites only. Material selection and
layer-volume allocation belong to the query executor and retain their own proof.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np


class _Unavailable(ValueError):
    def __init__(self, code, metadata=None):
        self.code = code
        self.metadata = metadata or {}


def _usage(element):
    """Effective source association; occurrence assignments override types."""
    associations = [relation for relation in (getattr(element, "HasAssociations", ()) or ())
                    if relation.is_a("IfcRelAssociatesMaterial")]
    typing = []
    if not associations:
        typing = list(getattr(element, "IsTypedBy", ()) or ()) or [relation for relation in
            (getattr(element, "IsDefinedBy", ()) or ()) if relation.is_a("IfcRelDefinesByType")]
        candidates = {relation.RelatingType.id(): relation.RelatingType for relation in typing}
        groups = [[relation for relation in (getattr(native_type, "HasAssociations", ()) or ())
                   if relation.is_a("IfcRelAssociatesMaterial")] for native_type in candidates.values()]
        if groups and any(not group for group in groups):
            raise _Unavailable("material_assignment_ambiguous")
        associations = [relation for group in groups for relation in group]
    assignments = {relation.RelatingMaterial.id(): relation.RelatingMaterial for relation in associations}
    if len(assignments) != 1:
        raise _Unavailable("material_assignment_ambiguous" if assignments else "layer_usage_missing")
    usage = next(iter(assignments.values()))
    if not usage.is_a("IfcMaterialLayerSetUsage"):
        raise _Unavailable("layer_usage_missing")
    return usage, associations, typing


def _cap_polygon(points, faces):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polygons = [Polygon(points[triangle]) for triangle in faces]
    polygons = [polygon for polygon in polygons if polygon.area > 1e-14]
    if not polygons:
        raise _Unavailable("cap_geometry_missing")
    result = unary_union(polygons)
    if result.is_empty or not result.is_valid or result.area <= 1e-12:
        raise _Unavailable("cap_geometry_invalid")
    return result


def verify_layered_host(model, step, tolerance):
    """Strict material prerequisite: actual body and declared layer dimensions agree."""
    return _verify_prism(model, step, tolerance, require_layer_match=True)


def verify_layer_axis_body_host(model, step, tolerance):
    """Actual body prism for one-face area; never authorizes layer allocation."""
    return _verify_prism(model, step, tolerance, require_layer_match=False)


def _verify_prism(model, step, tolerance, *, require_layer_match):
    from ifcopenshell.util.placement import get_local_placement
    from .geometry import _length_scale, _mesh, _solid_volume

    element = model.by_id(step)
    usage, associations, typing = _usage(element)
    scale = _length_scale(model)
    layers = list(usage.ForLayerSet.MaterialLayers)
    if not layers or len(layers) > 256:
        raise _Unavailable("layer_inventory_missing_or_excessive")
    records = []
    for layer in layers:
        thickness = layer.LayerThickness
        if thickness is None or not math.isfinite(float(thickness)) or thickness < 0:
            raise _Unavailable("layer_thickness_unknown")
        material = layer.Material
        records.append({"layer_step_id": layer.id(), "material_step_id": material.id() if material else None,
            "name": material.Name if material else None, "thickness_m": float(thickness) * scale})
    specified = sum(record["thickness_m"] for record in records)
    if not math.isfinite(specified) or specified <= 0:
        raise _Unavailable("layer_thickness_unknown")
    axis_name, sense = usage.LayerSetDirection, usage.DirectionSense
    if axis_name not in {"AXIS1", "AXIS2", "AXIS3"} or sense not in {"POSITIVE", "NEGATIVE"}:
        raise _Unavailable("layer_axis_unknown")
    offset = usage.OffsetFromReferenceLine
    if offset is None or not math.isfinite(float(offset)):
        raise _Unavailable("layer_offset_unknown")
    offset = float(offset) * scale
    placement = element.ObjectPlacement
    matrix = get_local_placement(placement) if placement else np.eye(4)
    rotation = matrix[:3, :3]
    if not np.isfinite(matrix).all() or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-10, rtol=0):
        raise _Unavailable("placement_not_rigid")
    axis_index = int(axis_name[-1]) - 1
    axis, origin = rotation[:, axis_index], matrix[:3, 3] * scale
    transverse = [index for index in range(3) if index != axis_index]
    vertices, faces = _mesh(model, element)
    if len(faces) > 200000:
        raise _Unavailable("geometry_work_budget")
    # This rejects open/nonmanifold or inconsistently wound meshes; the result
    # is an integrated solid volume, never a bounding-box product.
    volume = _solid_volume(vertices, faces)
    local = (vertices - origin) @ rotation
    position = local[:, axis_index]
    low, high = float(np.min(position)), float(np.max(position))
    thickness = high - low
    actual = {"axis_world": axis.tolist(), "axis_interval_m": [low, high],
        "axis_thickness_m": thickness, "specified_total_thickness_m": specified,
        "declared_thickness_residual_m": abs(thickness - specified)}
    if thickness <= 4 * tolerance:
        raise _Unavailable("axis_planes_within_tolerance")
    thickness_error = abs(thickness - specified)
    if require_layer_match and thickness_error > tolerance:
        raise _Unavailable("layer_thickness_geometry_mismatch", actual)
    expected = sorted([offset, offset + (specified if sense == "POSITIVE" else -specified)])
    offset_error = max(abs(low - expected[0]), abs(high - expected[1]))
    if require_layer_match and offset_error > tolerance:
        raise _Unavailable("layer_offset_geometry_mismatch", {**actual, "specified_axis_interval_m": expected,
            "offset_residual_m": offset_error})
    on_low, on_high = np.abs(position - low) <= tolerance, np.abs(position - high) <= tolerance
    if not np.all(on_low | on_high):
        raise _Unavailable("nonuniform_axis_geometry", {**actual,
            "off_endplane_vertex_count": int(np.count_nonzero(~(on_low | on_high))),
            "maximum_off_endplane_distance_m": float(np.max(np.minimum(abs(position - low), abs(position - high))))})
    low_faces = np.all(on_low[faces], axis=1)
    high_faces = np.all(on_high[faces], axis=1)
    if np.any(low_faces & high_faces):
        raise _Unavailable("axis_planes_within_tolerance")
    projected = local[:, transverse]
    a = _cap_polygon(projected, faces[low_faces])
    b = _cap_polygon(projected, faces[high_faces])
    symmetric_difference = float(a.symmetric_difference(b).area)
    hausdorff = float(a.hausdorff_distance(b))
    if hausdorff > tolerance or symmetric_difference > max(1e-10, min(a.length, b.length) * tolerance):
        raise _Unavailable("noncongruent_axis_caps")
    from shapely.geometry import LineString, Polygon
    boundary_band = a.boundary.buffer(tolerance)
    maximum_side_area = 0.
    for triangle in faces[~(low_faces | high_faces)]:
        points = projected[triangle]
        area = float(Polygon(points).area)
        maximum_side_area = max(maximum_side_area, area)
        if area > max(1e-10, tolerance * tolerance) or not boundary_band.covers(LineString(points)):
            raise _Unavailable("nonprismatic_side_geometry")
    predicted = float(a.area) * thickness
    residual = abs(volume - predicted)
    if residual > max(1e-10, volume * 1e-6, a.area * tolerance * 1e-3):
        raise _Unavailable("solid_prism_volume_mismatch")
    source_steps = {step, usage.id(), usage.ForLayerSet.id(), *(relation.id() for relation in associations),
                    *(relation.id() for relation in typing), *(record["layer_step_id"] for record in records),
                    *(record["material_step_id"] for record in records if record["material_step_id"] is not None)}
    units = model.by_type("IfcProject")[0].UnitsInContext
    length_unit = next(unit for unit in units.Units if getattr(unit, "UnitType", None) == "LENGTHUNIT")
    source_steps.update([units.id(), length_unit.id()])
    visited = set()
    while placement is not None:
        if placement.id() in visited or len(visited) >= 32:
            raise _Unavailable("placement_chain_ambiguous")
        visited.add(placement.id())
        source_steps.add(placement.id())
        if not placement.is_a("IfcLocalPlacement"):
            raise _Unavailable("placement_not_local")
        source_steps.add(placement.RelativePlacement.id())
        placement = placement.PlacementRelTo
    representation = element.Representation
    representation_steps = [representation.id(), *(item.id() for item in representation.Representations)]
    polygons = [a] if a.geom_type == "Polygon" else list(a.geoms)
    return {
        "status": "verified", "method": "uniform_layered_prism.v1" if require_layer_match else "uniform_layer_axis_body_prism.v1",
        "frame": "ifc_world", "unit": "m3",
        "volume_m3": volume, "axis_thickness_m": thickness, "specified_total_thickness_m": specified,
        "source_step_ids": sorted(source_steps), "representation_step_ids": sorted(set(representation_steps)),
        "usage_step_id": usage.id(), "layer_set_step_id": usage.ForLayerSet.id(), "layers": records,
        "metadata": {"axis": axis_name, "direction_sense": sense, "offset_m": offset,
            "length_unit_step_id": length_unit.id(), "length_scale_to_m": scale,
            "axis_world": axis.tolist(), "origin_m": origin.tolist(),
            "axis_interval_m": [low, high], "specified_axis_interval_m": expected,
            "declared_thickness_residual_m": thickness_error,
            "declared_thickness_matches_body": thickness_error <= tolerance,
            "declared_interval_matches_body": offset_error <= tolerance,
            "material_allocation_eligible": require_layer_match,
            "offset_residual_m": offset_error, "cap_area_m2": float(a.area), "cap_symdiff_m2": symmetric_difference,
            "cap_hausdorff_m": hausdorff, "maximum_side_projection_area_m2": maximum_side_area,
            "volume_residual_m3": residual, "cap_component_count": len(polygons),
            "cap_hole_count": sum(len(polygon.interiors) for polygon in polygons),
            "cap_geometry_sha256": hashlib.sha256(a.wkb).hexdigest(),
            "vertex_count": len(vertices), "triangle_count": len(faces),
            "quality_basis": (
                "Closed modeled mesh and declared layer usage agree with a uniform prism within the physical tolerance; derived layer volumes remain estimates."
                if require_layer_match else
                "The closed modeled body is a complete uniform prism along the native layer axis. Declared layer thickness/offset agreement is reported separately; this body-only proof cannot authorize material-layer volume allocation." )},
    }


def verify_layered_batch(model, subjects, tolerance):
    """Strict default used exclusively by material-layer allocation."""
    return _verify_batch(model, subjects, tolerance, require_layer_match=True)


def verify_layer_axis_body_batch(model, subjects, tolerance):
    """Face-area geometry with the actual thickness, retaining authored discrepancies."""
    return _verify_batch(model, subjects, tolerance, require_layer_match=False)


def _verify_batch(model, subjects, tolerance, *, require_layer_match):
    records = []
    for subject, step in subjects.items():
        record = {"subject_id": subject, "status": "unavailable",
            "method": "uniform_layered_prism.v1" if require_layer_match else "uniform_layer_axis_body_prism.v1",
            "frame": "ifc_world", "unit": "m3", "volume_m3": None, "source_step_ids": [step],
            "representation_step_ids": [], "metadata": {}}
        try:
            record.update(_verify_prism(model, step, tolerance, require_layer_match=require_layer_match))
        except _Unavailable as error:
            record["metadata"].update(error.metadata)
            record["metadata"]["reason_code"] = error.code
        except Exception:
            # Native errors can include complete STEP dumps and private paths.
            record["metadata"]["reason_code"] = "source_geometry_unavailable"
        records.append(record)
    return {"status": "match" if records and all(record["status"] == "verified" for record in records) else "unknown",
            "records": records, "reason": (
                "Layer allocation requires a uniform closed host solid consistent with its unambiguous native layer usage."
                if require_layer_match else
                "Face area requires a complete closed actual-body prism along the unambiguous native layer axis; authored thickness/offset discrepancies do not establish or authorize layer allocation.")}

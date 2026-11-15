"""Bounded wall-face and terrain-following vertical-span proofs.

The height proof concerns the supplied wall surface, including open-bottom
surface models. It verifies all displayed side patches and top/base vertices;
it neither substitutes a global elevation extent nor infers ground contact.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math

import numpy as np

MAX_VERTICES = 200000
MAX_FACES = 200000
MAX_COLUMNS = 20000
MAX_PATCHES = 2000
MAX_CLUSTER_CHECKS = 2000000


def net_opaque_face_area(prism):
    """One congruent layer-normal cap of an already verified vertical wall."""
    metadata = dict(prism.get("metadata", {}))
    metadata["prism_verification_method"] = prism.get("method")
    metadata["host_volume_m3"] = prism.get("volume_m3")
    metadata["actual_axis_thickness_m"] = prism.get("axis_thickness_m")
    metadata["authored_total_layer_thickness_m"] = prism.get("specified_total_thickness_m")
    result = dict(status="unavailable", value=None, method="uniform_prism_one_face_area.v1", metadata=metadata)
    if (prism.get("status") != "verified" or prism.get("method") not in {
            "uniform_layered_prism.v1", "uniform_layer_axis_body_prism.v1"}
            or prism.get("frame") != "ifc_world" or prism.get("unit") != "m3"):
        metadata["reason_code"] = "uniform_wall_prism_not_verified"
        return result
    axis = metadata.get("axis_world")
    area = metadata.get("cap_area_m2")
    if (not isinstance(axis, (list, tuple)) or len(axis) != 3
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in axis)
            or not math.isclose(sum(v * v for v in axis), 1., abs_tol=1e-8)
            or abs(axis[2]) > 1e-6):
        metadata["reason_code"] = "layer_normal_is_not_horizontal"
        return result
    if not isinstance(area, (int, float)) or isinstance(area, bool) or not math.isfinite(area) or area <= 0:
        metadata["reason_code"] = "verified_cap_area_unavailable"
        return result
    metadata.update(face_basis="net_opaque_face", face_count=1,
        face_definition="One complete modeled vertical layer-normal face; native openings remain subtracted. The verified opposite cap has the same area.",
        exterior_membership="The caller's source-backed occurrence selection determines exterior membership; this geometric method does not classify exposure or orientation.")
    result.update(status="verified", value=float(area))
    return result


def validated_vertical_spans(vertices, faces, tolerance_m=0.001):
    """Prove one local vertical wall height despite varying base elevation.

    Vertices are grouped only when their horizontal positions agree within the
    physical tolerance. Every used column needs exactly a bottom/top pair,
    every vertical patch must completely cover its source ruled quadrilateral,
    and every remaining triangle must consistently belong to the top or base.
    All columns must have one height. Unpaired, tapered, mixed or incomplete
    surfaces retain observations but do not produce a numeric wall height.
    """
    metadata = {"basis": "validated_vertical_spans", "ground_contact": "not_established",
        "horizontal_match_tolerance_m": tolerance_m,
        "definition": "Uniform local vertical span between the complete modeled side-patch bottom and top boundaries; their elevations may vary with terrain."}
    result = dict(status="unavailable", value=None, method="validated_vertical_wall_spans.v1", metadata=metadata)

    def fail(reason):
        metadata["reason_code"] = reason
        return result

    if not math.isfinite(tolerance_m) or not 0 < tolerance_m <= .1:
        return fail("invalid_physical_tolerance")
    vertices, faces = np.asarray(vertices, dtype=float), np.asarray(faces)
    if (vertices.ndim != 2 or vertices.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3
            or not len(vertices) or not len(faces) or not np.isfinite(vertices).all()
            or not np.issubdtype(faces.dtype, np.integer) or np.min(faces) < 0 or np.max(faces) >= len(vertices)):
        return fail("invalid_source_mesh")
    if len(vertices) > MAX_VERTICES or len(faces) > MAX_FACES:
        return fail("geometry_work_budget")
    used = sorted(set(int(i) for i in faces.flat))
    metadata.update(vertex_count=len(vertices), used_vertex_count=len(used), triangle_count=len(faces),
        global_elevation_interval_m=[float(np.min(vertices[used, 2])), float(np.max(vertices[used, 2]))])
    # Hash the complete numeric inputs. Native representation/placement locators
    # are attached by the isolated IFC worker around this pure geometry proof.
    digest = hashlib.sha256(vertices.astype("<f8").tobytes())
    digest.update(faces.astype("<i8").tobytes())
    metadata["mesh_sha256"] = digest.hexdigest()
    cells, columns, assignment = defaultdict(list), [], {}
    checks = 0
    for index in used:
        point = vertices[index, :2]
        cell = tuple(int(math.floor(v / tolerance_m)) for v in point)
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for candidate in cells.get((cell[0] + dx, cell[1] + dy), ()):
                    checks += 1
                    if checks > MAX_CLUSTER_CHECKS:
                        return fail("geometry_work_budget")
                    if float(np.linalg.norm(columns[candidate]["xy"] - point)) <= tolerance_m:
                        candidates.append(candidate)
        if len(candidates) > 1:
            return fail("ambiguous_horizontal_columns")
        if not candidates:
            if len(columns) >= MAX_COLUMNS:
                return fail("geometry_work_budget")
            candidate = len(columns)
            columns.append({"xy": point, "vertices": []})
            cells[cell].append(candidate)
        else:
            candidate = candidates[0]
        columns[candidate]["vertices"].append(index)
        assignment[index] = candidate

    tags, heights, unpaired, intermediate = {}, [], [], []
    for index, column in enumerate(columns):
        values = vertices[column["vertices"], 2]
        low, high = float(np.min(values)), float(np.max(values))
        column.update(low=low, high=high)
        if high - low <= 4 * tolerance_m:
            unpaired.append(index)
            continue
        if np.any((np.abs(values - low) > tolerance_m) & (np.abs(values - high) > tolerance_m)):
            intermediate.append(index)
            continue
        heights.append(high - low)
        for vertex in column["vertices"]:
            tags[vertex] = "bottom" if abs(vertices[vertex, 2] - low) <= tolerance_m else "top"
    metadata.update(horizontal_column_count=len(columns), paired_column_count=len(heights),
        unpaired_column_count=len(unpaired), intermediate_level_column_count=len(intermediate),
        observed_paired_span_interval_m=[min(heights), max(heights)] if heights else None,
        bottom_elevation_interval_m=[min(c["low"] for c in columns), max(c["low"] for c in columns)],
        top_elevation_interval_m=[min(c["high"] for c in columns), max(c["high"] for c in columns)])
    # Keep every unresolved column locator within the bounded input proof.
    metadata["unresolved_column_vertex_ids"] = [columns[i]["vertices"] for i in [*unpaired, *intermediate]]
    patch_triangles, caps, invalid, degenerate = defaultdict(list), defaultdict(list), [], []
    for index, triangle in enumerate(faces):
        points = vertices[triangle]
        area2 = float(np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])))
        if area2 <= tolerance_m * tolerance_m:
            degenerate.append(index)
            continue
        identifiers = tuple(sorted({assignment[int(i)] for i in triangle}))
        if len(identifiers) == 2:
            patch_triangles[identifiers].append(index)
        elif len(identifiers) == 3 and all(int(i) in tags for i in triangle):
            levels = {tags[int(i)] for i in triangle}
            left, right = points[1, :2] - points[0, :2], points[2, :2] - points[0, :2]
            xy_area2 = abs(float(left[0] * right[1] - left[1] * right[0]))
            if len(levels) != 1 or xy_area2 <= tolerance_m * tolerance_m:
                invalid.append(index)
            else:
                caps[next(iter(levels))].append(index)
        else:
            invalid.append(index)
    if len(patch_triangles) > MAX_PATCHES:
        return fail("geometry_work_budget")

    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    patches, unsupported_patches = [], []
    for identifiers, triangles in sorted(patch_triangles.items()):
        a, b = (columns[i] for i in identifiers)
        length = float(np.linalg.norm(b["xy"] - a["xy"]))
        record = {"column_ids": list(identifiers), "source_triangle_ids": triangles,
            "bottom_endpoints_m": [[*a["xy"].tolist(), a["low"]], [*b["xy"].tolist(), b["low"]]],
            "top_endpoints_m": [[*a["xy"].tolist(), a["high"]], [*b["xy"].tolist(), b["high"]]],
            "endpoint_spans_m": [a["high"] - a["low"], b["high"] - b["low"]]}
        if any(vertex not in tags for index in triangles for vertex in faces[index]) or length <= 4 * tolerance_m:
            record.update(status="unavailable", reason_code="incomplete_vertical_endpoints")
            unsupported_patches.append(record)
            continue
        polygons = [Polygon([(0. if assignment[int(vertex)] == identifiers[0] else length, float(vertices[vertex, 2]))
                             for vertex in faces[index]]) for index in triangles]
        observed = unary_union(polygons)
        expected = Polygon([(0., a["low"]), (length, b["low"]), (length, b["high"]), (0., a["high"])])
        residual = float(expected.symmetric_difference(observed).area)
        hausdorff = float(expected.hausdorff_distance(observed))
        record.update(expected_patch_area_m2=float(expected.area), observed_patch_area_m2=float(observed.area),
            area_residual_m2=residual, boundary_residual_m=hausdorff)
        if not observed.is_valid or residual > max(tolerance_m ** 2, expected.length * tolerance_m) or hausdorff > tolerance_m:
            record.update(status="unavailable", reason_code="incomplete_ruled_side_patch")
            unsupported_patches.append(record)
        else:
            record["status"] = "verified"
            patches.append(record)
    metadata.update(verified_side_patch_count=len(patches), unsupported_side_patch_count=len(unsupported_patches),
        vertical_side_patch_proof=[*patches, *unsupported_patches],
        top_triangle_ids=caps["top"], bottom_triangle_ids=caps["bottom"],
        unclassified_triangle_ids=invalid, degenerate_triangle_ids=degenerate)
    if unpaired or intermediate or unsupported_patches or invalid or not patches or not heights:
        return fail("incomplete_vertical_surface_coverage")
    if max(heights) - min(heights) > tolerance_m:
        return fail("nonuniform_local_vertical_spans")
    metadata["coverage"] = "Every used source vertex and nondegenerate triangle belongs to a complete paired side patch or consistently classified top/base surface."
    result.update(status="verified", value=float(np.median(heights)))
    return result

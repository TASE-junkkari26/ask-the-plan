"""Bounded modeled walking paths through native rooms, openings and stairs.

This computes potential routes in the recorded room topology. Door operability,
fire-exit certification, movable obstacles and physical clear width are separate
unknowns; a modeled route never establishes regulatory compliance.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import heapq
import json
import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon, MultiPolygon
from shapely.ops import nearest_points, unary_union

METHOD = "native_room_opening_visibility_route.v1"
MAX_ROOMS = 500
MAX_PORTALS = 2000
MAX_EDGES = 50000
MAX_SAMPLES = 3000


def _polygon(value):
    if isinstance(value, Polygon):
        return value
    pieces = [part for part in getattr(value, "geoms", ()) if isinstance(part, Polygon)]
    if not pieces:
        raise ValueError("No planar modeled room region")
    result = unary_union(pieces)
    if not result.is_valid or result.area <= 1e-8:
        raise ValueError("Invalid modeled room region")
    return result


def _parts(polygon):
    return [polygon] if isinstance(polygon, Polygon) else list(polygon.geoms)


def _covered(region, geometry, tolerance=1e-8):
    """Tolerance is numeric coverage only, never an artificial portal."""
    if geometry.length <= 1e-10 and geometry.geom_type == "LineString":
        geometry = Point(geometry.coords[0])
    return region.covers(geometry) or region.buffer(tolerance).covers(geometry)


def _line_points(geometry):
    lines = [geometry] if geometry.geom_type == "LineString" else [p for p in getattr(geometry, "geoms", ()) if p.geom_type == "LineString"]
    return [line for line in lines if line.length > .02]


def _visibility_vertices(polygon):
    result = []
    for part in _parts(polygon):
        points = list(part.exterior.coords)[:-1]
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
        for i, point in enumerate(points):
            before, after = np.asarray(points[i-1]), np.asarray(points[(i+1)%len(points)])
            a, b = np.asarray(point)-before, after-np.asarray(point)
            cross = a[0]*b[1]-a[1]*b[0]
            if cross * area < -1e-10:
                result.append(tuple(point))
        for hole in part.interiors:
            result.extend(tuple(p) for p in list(hole.coords)[:-1])
    return list(dict.fromkeys(result))


def _inside_path(polygon, start, end, *, vertices=None):
    """Shortest polygon visibility path, preserving concavity and holes."""
    start, end = tuple(start[:2]), tuple(end[:2])
    if not _covered(polygon, Point(start)) or not _covered(polygon, Point(end)):
        return None
    direct = LineString([start, end])
    if _covered(polygon, direct):
        return [start, end]
    if vertices is None:
        vertices = [tuple(p) for part in _parts(polygon) for ring in [part.exterior, *part.interiors] for p in list(ring.coords)[:-1]]
    if len(vertices) > 128:
        raise ValueError("Room visibility vertices exceed work budget")
    points = [start, end, *vertices]
    graph = defaultdict(list)
    for i, a in enumerate(points):
        for j in range(i):
            b = points[j]
            distance = math.dist(a, b)
            if distance <= 1e-10 or _covered(polygon, LineString([a, b])):
                graph[i].append((j, distance)); graph[j].append((i, distance))
    distance, following = _dijkstra(graph, [1])
    if 0 not in distance:
        return None
    result, current = [start], 0
    while current != 1:
        current = following[current]
        result.append(points[current])
    return result


def _dijkstra(graph, targets):
    best = {target: 0. for target in targets}; distance = {}; following = {}
    pending = [(0., target) for target in targets]; heapq.heapify(pending)
    while pending:
        value, node = heapq.heappop(pending)
        if node in distance or value != best[node]:
            continue
        distance[node] = value
        for other, length in graph.get(node, ()):
            candidate = value + length
            if other not in distance and candidate < best.get(other, math.inf) - 1e-10:
                best[other] = candidate; following[other] = node
                heapq.heappush(pending, (candidate, other))
    return distance, following


def _contact(room, opening, tolerance):
    intersection = room.boundary.intersection(opening)
    lines = _line_points(intersection)
    if lines:
        return max(lines, key=lambda p: p.length)
    # Project only a tolerance-scale native round-off discrepancy. A gap cannot
    # become a portal merely because the room is the nearest one.
    if room.distance(opening) <= tolerance:
        intersection = room.boundary.intersection(opening.buffer(min(tolerance, 1e-8), join_style=2))
        lines = _line_points(intersection)
        if lines:
            return max(lines, key=lambda p: p.length)
    return None


def _patch_lines(model, boundary, room, tolerance):
    from ifcopenshell.util.placement import get_local_placement
    from .geometry import _patches, _length_scale
    patches = _patches(model, boundary)
    matrix = get_local_placement(boundary.RelatingSpace.ObjectPlacement) if boundary.RelatingSpace.ObjectPlacement else np.eye(4)
    scale = _length_scale(model)
    options = [("ifc_space_relative", patches)]
    if np.allclose(matrix[:3, :3], np.eye(3), atol=1e-8):
        options += [("source_xy_world_z_relative", [p - np.r_[matrix[:2, 3] * scale, 0.] for p in patches]),
                    ("source_surface_world", [p - matrix[:3, 3] * scale for p in patches])]
    candidates = []
    for basis, items in options:
        for patch in items:
            if np.ptp(patch[:, 2]) < .5:
                continue
            unique = np.unique(patch[:, :2], axis=0)
            if len(unique) < 2:
                continue
            a, b = max(((a, b) for a in unique for b in unique), key=lambda pair: math.dist(*pair))
            line = LineString([a, b])
            # Select the interpretation by the actual room boundary, rather
            # than treating the exporter coordinate defect as a global offset.
            nearby = line.intersection(room["polygon"].boundary.buffer(tolerance * 2))
            support = nearby.length
            zlo, zhi = float(patch[:, 2].min()), float(patch[:, 2].max())
            if support > .05 and zlo <= room["floor"] + .1 <= zhi:
                candidates.append((support, basis, line, zlo, zhi))
    if not candidates:
        return []
    best = max(value[0] for value in candidates)
    chosen = [value for value in candidates if value[0] >= best - tolerance]
    # Numerically equivalent frame candidates are common at the origin. Keep a
    # deterministic native interpretation, but reject distinct equally valid XY.
    selected = chosen[0]
    if any(selected[2].hausdorff_distance(value[2]) > tolerance for value in chosen):
        return []
    return [(selected[2], selected[1], selected[3], selected[4])]


def _overlap_lines(a, b, tolerance):
    av = np.asarray(a.coords[-1]) - a.coords[0]
    av /= np.linalg.norm(av)
    bv = np.asarray(b.coords[-1]) - b.coords[0]
    bv /= np.linalg.norm(bv)
    if abs(float(av @ bv)) < .99999:
        return None
    origin = np.asarray(a.coords[0]); normal = np.array([-av[1], av[0]])
    if max(abs(float((np.asarray(p) - origin) @ normal)) for p in b.coords) > tolerance:
        return None
    aa = sorted(float((np.asarray(p) - origin) @ av) for p in a.coords)
    bb = sorted(float((np.asarray(p) - origin) @ av) for p in b.coords)
    lo, hi = max(aa[0], bb[0]), min(aa[-1], bb[-1])
    if hi - lo <= .05:
        return None
    return LineString([origin + av * lo, origin + av * hi])


def _typed_bool(model, obj, name):
    """Only real boolean/logical values can establish a source flag."""
    import ifcopenshell.util.element
    result = []
    for relationship in getattr(obj, "IsDefinedBy", ()):
        if not relationship.is_a("IfcRelDefinesByProperties"):
            continue
        definition = relationship.RelatingPropertyDefinition
        for prop in getattr(definition, "HasProperties", ()):
            value = getattr(prop, "NominalValue", None)
            if prop.Name == name and value is not None and value.is_a() in {"IfcBoolean", "IfcLogical"} and isinstance(value.wrappedValue, bool):
                result.append((value.wrappedValue, prop.id(), relationship.id()))
    # Type inheritance follows the same no-pick-one ambiguity rule as extraction.
    if not result:
        branches = []
        for relationship in getattr(obj, "IsTypedBy", ()) or getattr(obj, "IsDefinedBy", ()):
            if not relationship.is_a("IfcRelDefinesByType"): continue
            values = []
            for definition in getattr(relationship.RelatingType, "HasPropertySets", ()) or ():
                for prop in getattr(definition, "HasProperties", ()):
                    value = getattr(prop, "NominalValue", None)
                    if prop.Name == name and value is not None and value.is_a() in {"IfcBoolean", "IfcLogical"} and isinstance(value.wrappedValue, bool):
                        values.append((value.wrappedValue, prop.id(), relationship.id()))
            branches.append(values or [(None, relationship.RelatingType.id(), relationship.id())])
        if any(value[0] is not None for values in branches for value in values):
            result = [value for values in branches for value in values]
    return result


def _geometry_inputs(obj):
    steps = {obj.id()}
    placement = getattr(obj, "ObjectPlacement", None)
    seen = set()
    while placement is not None and placement.id() not in seen and len(seen) < 64:
        seen.add(placement.id()); steps.add(placement.id())
        relative = getattr(placement, "RelativePlacement", None)
        if relative:
            steps.add(relative.id())
            for field in ("Location", "Axis", "RefDirection"):
                value = getattr(relative, field, None)
                if value: steps.add(value.id())
        placement = getattr(placement, "PlacementRelTo", None)
    shape = getattr(obj, "Representation", None)
    if shape:
        steps.add(shape.id())
        for rep in shape.Representations:
            steps.add(rep.id())
            steps.update(item.id() for item in rep.Items)
    return sorted(steps)


def _stair_metrics(model, stair, scale):
    values, proof = {}, []
    for relationship in getattr(stair, "IsDefinedBy", ()):
        if not relationship.is_a("IfcRelDefinesByProperties"): continue
        definition = relationship.RelatingPropertyDefinition
        if definition.Name != "Pset_StairFlightCommon": continue
        for prop in getattr(definition, "HasProperties", ()):
            if prop.Name not in {"RiserHeight", "NumberOfRiser"}: continue
            value = getattr(prop, "NominalValue", None)
            if value is None: continue
            if prop.Name in values: raise ValueError("Ambiguous native stair rise")
            number = value.wrappedValue
            if prop.Name == "RiserHeight":
                if value.is_a() not in {"IfcLengthMeasure", "IfcPositiveLengthMeasure"}: raise ValueError("Untyped stair rise")
                native_unit = getattr(prop, "Unit", None)
                if native_unit:
                    from ifcopenshell.util.unit import get_unit_scale
                    number *= get_unit_scale(native_unit); proof.append(native_unit.id())
                else: number *= scale
            values[prop.Name] = number
            proof += [relationship.id(), definition.id(), prop.id()]
    if set(values) == {"RiserHeight", "NumberOfRiser"}:
        return values["RiserHeight"], values["NumberOfRiser"], "Pset_StairFlightCommon", proof
    count = getattr(stair,"NumberOfRiser",getattr(stair,"NumberOfRisers",None))
    return float(stair.RiserHeight)*scale, count, "native_stair_attributes", [stair.id()]


def _native_rooms(model, subjects, failures):
    from .geometry import _mesh_sources, _project_meshes
    rooms = {}
    for identifier, step in subjects.items():
        try:
            obj = model.by_id(step)
            meshes, used, representations = _mesh_sources(model, [step], {}, explicit_roots=[step])
            polygon = _polygon(_project_meshes(meshes))
            vertices = np.concatenate([mesh[0] for mesh in meshes])
            floor = float(vertices[:, 2].min())
            caps = [Polygon(v[face,:2]) for v,faces in meshes for face in faces
                if np.max(np.abs(v[face,2] - floor)) <= .001 and Polygon(v[face,:2]).area > 1e-10]
            floor_region = unary_union(caps)
            if floor_region.is_empty or floor_region.symmetric_difference(polygon).area > .001 * polygon.length:
                raise ValueError("The modeled room has no complete horizontal floor region")
            rooms[identifier] = {"step": step, "polygon": polygon, "floor": floor,
                "top": float(vertices[:, 2].max()), "representations": representations, "source_inputs": _geometry_inputs(obj), "name": obj.Name}
        except Exception:
            failures.append({"entity_id": identifier, "reason": "room_body_unavailable"})
    return rooms


def route_batch(model, options, tolerance):
    """Read only explicitly authorized native objects and emit inspectable paths."""
    from .geometry import _mesh, _project_meshes, _length_scale, _curve, _transform
    from ifcopenshell.util.placement import get_local_placement
    rooms_input = options["rooms"]
    if len(rooms_input) > MAX_ROOMS or len(options["doors"]) > 1000 or len(options.get("stairs", {})) > 64:
        return {"status": "unknown", "records": [], "reason": "The route inventory exceeds its bounded work budget."}
    failures = []
    rooms = _native_rooms(model, rooms_input, failures)
    room_steps = {room["step"]: identifier for identifier, room in rooms.items()}
    door_steps = {step: identifier for identifier, step in options["doors"].items()}
    opening_steps = set(options["openings"].values())
    allowed_boundaries = set(options["boundaries"])
    boundaries, virtual = defaultdict(list), []
    by_boundary = {}
    for step in allowed_boundaries:
        boundary = model.by_id(step)
        room_id = room_steps.get(boundary.RelatingSpace.id())
        if room_id is None:
            continue
        element = boundary.RelatedBuildingElement
        if boundary.PhysicalOrVirtualBoundary == "VIRTUAL":
            try:
                for line, basis, lo, hi in _patch_lines(model, boundary, rooms[room_id], tolerance):
                    virtual.append((room_id, boundary.id(), line, basis, lo, hi))
            except Exception:
                failures.append({"entity_id": room_id, "reason": "virtual_patch_unavailable", "boundary_step_id": step})
        elif element is not None and element.id() in door_steps:
            boundaries[element.id()].append((room_id, boundary))
        by_boundary[step] = boundary
    nodes, graph, edge_paths, edge_proof = [], defaultdict(list), {}, {}
    room_nodes = defaultdict(list)
    targets = set()
    edge_count = 0
    def node(room_id, point):
        if len(nodes) >= 8000:
            raise ValueError("Route portal sample work budget exceeded")
        index = len(nodes); nodes.append({"room": room_id, "point": tuple(float(x) for x in point)})
        if room_id:
            room_nodes[room_id].append(index)
        return index
    def edge(a, b, points, proof):
        nonlocal edge_count
        length = sum(math.dist(x, y) for x, y in zip(points, points[1:]))
        if not math.isfinite(length):
            raise ValueError("Invalid path length")
        if edge_count >= MAX_EDGES:
            raise ValueError("Visibility edge budget exceeded")
        edge_count += 1
        graph[a].append((b, length)); graph[b].append((a, length))
        edge_paths[a, b] = points; edge_paths[b, a] = list(reversed(points))
        edge_proof[a, b] = edge_proof[b, a] = proof
    source_candidates, uncertified, candidate_inputs = [], set(), set()
    for door_step, door_id in door_steps.items():
        values = _typed_bool(model, model.by_id(door_step), "IsExternal")
        if values and {value[0] for value in values} == {True} and not any(b.InternalOrExternalBoundary == "EXTERNAL" for _, b in boundaries[door_step]):
            failures.append({"entity_id": door_id, "reason": "recorded_exterior_door_without_external_room_boundary"})
            candidate_inputs.update([door_step, *[v[1] for v in values]])
    certified_targets = set()
    if options.get("target_basis") == "certified_fire_exit":
        for door_step, related in boundaries.items():
            door_id = door_steps[door_step]
            if options.get("targets") is not None and door_id not in options["targets"]: continue
            door = model.by_id(door_step)
            flags = _typed_bool(model, door, "IsExternal")
            values = _typed_bool(model, door, "IsFireExit")
            if (any(b.InternalOrExternalBoundary == "EXTERNAL" for _,b in related)
                    and not any(v[0] is False for v in flags) and values and {v[0] for v in values} == {True}):
                certified_targets.add(door_id)
    for door_step, related in sorted(boundaries.items()):
        door_id = door_steps[door_step]; door = model.by_id(door_step)
        fill = list(getattr(door, "FillsVoids", ()) or ())
        if len(fill) != 1 or fill[0].RelatingOpeningElement.id() not in opening_steps:
            failures.append({"entity_id": door_id, "reason": "opening_missing_or_outside_scope"}); continue
        opening = fill[0].RelatingOpeningElement
        try:
            opening_mesh = _mesh(model, opening)
            from .geometry import _closed_vertices
            _closed_vertices(*opening_mesh)
            projection = _polygon(_project_meshes([opening_mesh]))
        except Exception:
            failures.append({"entity_id": door_id, "reason": "opening_geometry_unavailable"}); continue
        contacts = {}
        for room_id, boundary in related:
            floor = rooms[room_id]["floor"]
            if opening_mesh[0][:,2].min() > floor + .15 or opening_mesh[0][:,2].max() < floor + 1.5:
                failures.append({"entity_id": door_id, "reason": "opening_not_at_supported_room_floor", "room_id": room_id})
                continue
            contact = _contact(rooms[room_id]["polygon"], projection, tolerance)
            if contact is not None:
                contacts[room_id] = contact
        external = [(r, b) for r, b in related if b.InternalOrExternalBoundary == "EXTERNAL"]
        flags = _typed_bool(model, door, "IsExternal")
        conflicting_external = any(value[0] is False for value in flags)
        if external and conflicting_external:
            failures.append({"entity_id": door_id, "reason": "external_boundary_conflicts_with_typed_IsExternal"})
        certified_values = _typed_bool(model, door, "IsFireExit")
        certified = certified_values and {v[0] for v in certified_values} == {True}
        candidate = bool(external) and not conflicting_external and (options.get("targets") is None or door_id in options["targets"])
        if candidate and certified_targets and door_id not in certified_targets:
            candidate = False
        if candidate:
            candidate_inputs.update([door_step, *[b.id() for _,b in external], *[v[1] for v in flags + certified_values]])
            source_candidates.append(door_id)
            if not certified:
                uncertified.add(door_id)
        nominal = getattr(door, "OverallWidth", None)
        nominal = float(nominal) * _length_scale(model) if nominal is not None else None
        for fraction in (.2, .5, .8):
            indices = {}
            for room_id, contact in contacts.items():
                p = contact.interpolate(fraction, normalized=True)
                # Original room boundary is the authoritative allowed region.
                p = nearest_points(rooms[room_id]["polygon"], p)[0]
                indices[room_id] = node(room_id, [p.x, p.y, rooms[room_id]["floor"]])
            for room_a, a in indices.items():
                for room_b, b in indices.items():
                    if a >= b or abs(rooms[room_a]["floor"] - rooms[room_b]["floor"]) > .1:
                        continue
                    points = [nodes[a]["point"], nodes[b]["point"]]
                    if not _covered(unary_union([rooms[room_a]["polygon"], rooms[room_b]["polygon"], projection]), LineString([p[:2] for p in points])):
                        continue
                    proof = {"kind": "door", "door_id": door_id, "opening_step_id": opening.id(),
                        "source_step_ids": [*_geometry_inputs(door), *_geometry_inputs(opening), fill[0].id(), *[b.id() for r, b in related if r in {room_a, room_b}]],
                        "nominal_width_m": nominal, "geometric_opening_width_m": min(contacts[room_a].length, contacts[room_b].length),
                        "assumption": "Modeled door is potentially operable; lock, swing and hardware clearance are not recorded."}
                    edge(a, b, points, proof)
            if candidate:
                for room_id, a in indices.items():
                    if not any(r == room_id for r, _ in external):
                        continue
                    center = projection.centroid
                    end = node(None, [center.x, center.y, rooms[room_id]["floor"]])
                    if not _covered(projection, LineString([nodes[a]["point"][:2], (center.x, center.y)])):
                        continue
                    proof = {"kind": "door", "door_id": door_id, "opening_step_id": opening.id(),
                        "source_step_ids": [*_geometry_inputs(door), *_geometry_inputs(opening), fill[0].id(), *[b.id() for r, b in external if r == room_id], *[v[1] for v in flags + certified_values]],
                        "nominal_width_m": nominal, "geometric_opening_width_m": contacts[room_id].length,
                        "target": True, "certified": bool(certified), "endpoint_basis": "modeled exterior opening center"}
                    edge(a, end, [nodes[a]["point"], nodes[end]["point"]], proof); targets.add(end)
                    nodes[end]["target"] = door_id
    # Open boundaries need two source VIRTUAL records and an actual shared room
    # boundary. Normals are checked through room interiors because some supplied
    # exporters reverse both source loops in the same direction.
    for i, (room_a, step_a, line_a, basis_a, lo_a, hi_a) in enumerate(virtual):
        for room_b, step_b, line_b, basis_b, lo_b, hi_b in virtual[:i]:
            if room_a == room_b or abs(rooms[room_a]["floor"] - rooms[room_b]["floor"]) > .1:
                continue
            overlap = _overlap_lines(line_a, line_b, tolerance)
            if overlap is None:
                continue
            allowed = unary_union([rooms[room_a]["polygon"], rooms[room_b]["polygon"]])
            for fraction in (.2, .5, .8):
                p = overlap.interpolate(fraction, normalized=True)
                a = nearest_points(rooms[room_a]["polygon"], p)[0]
                b = nearest_points(rooms[room_b]["polygon"], p)[0]
                if a.distance(p) > tolerance or b.distance(p) > tolerance:
                    continue
                tangent = np.asarray(overlap.coords[-1]) - overlap.coords[0]
                tangent /= np.linalg.norm(tangent)
                normal = np.array([-tangent[1], tangent[0]])
                plus, minus = Point(np.asarray(p.coords[0]) + normal*.01), Point(np.asarray(p.coords[0]) - normal*.01)
                side_a = int(rooms[room_a]["polygon"].covers(plus)) - int(rooms[room_a]["polygon"].covers(minus))
                side_b = int(rooms[room_b]["polygon"].covers(plus)) - int(rooms[room_b]["polygon"].covers(minus))
                if side_a * side_b != -1:
                    continue
                points = [(a.x, a.y, rooms[room_a]["floor"]), (b.x, b.y, rooms[room_b]["floor"])]
                if not _covered(allowed, LineString([point[:2] for point in points])):
                    continue
                na, nb = node(room_a, points[0]), node(room_b, points[1])
                edge(na, nb, points, {"kind": "virtual_open_passage", "source_step_ids": [step_a, step_b],
                    "boundary_frame_a": basis_a, "boundary_frame_b": basis_b, "portal_width_m": overlap.length,
                    "overlap_line_xy_m": list(overlap.coords), "room_interior_side_a": side_a, "room_interior_side_b": side_b,
                    "boundary_z_overlap_m": [max(lo_a,lo_b),min(hi_a,hi_b)]})
    if options.get("include_stairs", True):
        _stairs(model, options.get("stairs", {}), rooms, node, edge, failures, tolerance)
    portal_sample_count = len(nodes)
    if portal_sample_count > MAX_PORTALS:
        raise ValueError("Route portal sample work budget exceeded")
    # One visibility graph per room. Polygon corners are shared graph vertices;
    # recomputing a complete corner graph for every portal pair is quadratic
    # work multiplied by another quadratic factor on concave rooms.
    for room_id in list(room_nodes):
        polygon = rooms[room_id]["polygon"]
        vertices = _visibility_vertices(polygon)
        if len(vertices) > 128:
            failures.append({"entity_id": room_id, "reason": "room_visibility_vertex_budget"})
            continue
        for point in vertices:
            node(room_id, [*point, rooms[room_id]["floor"]])
        indices = room_nodes[room_id]
        for ii, a in enumerate(indices):
            for b in indices[:ii]:
                if abs(nodes[a]["point"][2] - nodes[b]["point"][2]) > tolerance:
                    continue
                points = [nodes[a]["point"], nodes[b]["point"]]
                if _covered(polygon, LineString([point[:2] for point in points])):
                    edge(a, b, points, {"kind": "room", "room_id": room_id, "source_step_ids": rooms[room_id]["source_inputs"],
                        "representation_step_ids": rooms[room_id]["representations"]})
    distance, following = _dijkstra(graph, sorted(targets))
    fingerprint = hashlib.sha256(json.dumps({"rooms": options["rooms"], "doors": options["doors"],
        "openings": options["openings"], "stairs": options.get("stairs", {}), "boundaries": sorted(allowed_boundaries),
        "targets": options.get("targets"), "method": METHOD}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    meta = {"method": METHOD, "scope_graph_sha256": fingerprint, "room_inventory_count": len(rooms_input),
        "usable_room_count": len(rooms), "portal_sample_count": portal_sample_count, "visibility_node_count": len(nodes), "visibility_edge_count": sum(len(v) for v in graph.values()) // 2,
        "recorded_outdoor_candidate_ids": sorted(source_candidates), "uncertified_candidate_ids": sorted(uncertified),
        "unresolved_inventory": failures, "portal_sample_fractions": [.2, .5, .8],
        "physical_clearance_verified": False, "required_clearance_m": options.get("clearance_m", 0),
        "requested_target_basis": options.get("target_basis", "recorded_external_boundary"),
        "target_basis_used": "certified_fire_exit" if certified_targets else "recorded_external_boundary",
        "certification_requested_unavailable": options.get("target_basis") == "certified_fire_exit" and not certified_targets,
        "route_basis": "Potential path through modeled room footprints and recorded open passages, door openings and native stair pitch lines; movable obstacles and door operability are unknown."}
    records = []
    sampling_inventory = []
    for subject in options["subjects"]:
        base = {"subject_id": subject, "target_id": None, "method": METHOD, "frame": "ifc_world", "unit": "m",
            "tolerance_m": tolerance, "quality": "estimated", "status": "unavailable", "path_points_m": [],
            "room_ids": [], "door_ids": [], "stair_ids": [], "source_step_ids": [], "metadata": dict(meta)}
        if subject not in rooms:
            records.append(base); continue
        room = rooms[subject]; polygon = room["polygon"]
        if options.get("mode") == "farthest":
            starts, resolution = _samples(polygon, MAX_SAMPLES // max(1, len(options["subjects"])))
        elif options.get("start_point_m") is not None:
            supplied = options["start_point_m"]
            starts, resolution = ([tuple(supplied[:2])] if abs(supplied[2] - room["floor"]) <= tolerance else []), None
        else:
            point = polygon.centroid
            if not polygon.covers(point): point = polygon.representative_point()
            starts, resolution = [(point.x, point.y)], None
        sampling_inventory.append({"room_id": subject, "sample_count": len(starts), "resolution_m": resolution, "bounds_xy_m": list(polygon.bounds)})
        best = None
        for start in starts:
            candidates = []
            for portal in room_nodes.get(subject, ()):
                if portal not in distance: continue
                if not _covered(polygon, Point(start)) or not _covered(polygon, LineString([start, nodes[portal]["point"][:2]])): continue
                prefix = [(*start, room["floor"]), nodes[portal]["point"]]
                length = sum(math.dist(a, b) for a, b in zip(prefix, prefix[1:])) + distance[portal]
                candidates.append((length, portal, prefix))
            if candidates:
                candidate = min(candidates, key=lambda p: p[0])
                if best is None or (candidate[0] > best[0] if options.get("mode") == "farthest" else candidate[0] < best[0]): best = candidate
        if best is None:
            base["metadata"]["reason"] = "No modeled path from this room to an authorized recorded exterior opening was established."
            records.append(base); continue
        length, current, points = best
        proof, route_rooms, doors, stairs = [], [subject], [], []
        while current not in targets:
            other = following[current]
            segment = edge_paths[current, other]
            if points[-1] != segment[0]:
                raise ValueError("Route edge continuity failure")
            points.extend(segment[1:]); proof.append(edge_proof[current, other])
            if nodes[other]["room"] and nodes[other]["room"] != route_rooms[-1]: route_rooms.append(nodes[other]["room"])
            current = other
        for item in proof:
            if item.get("door_id") and item["door_id"] not in doors: doors.append(item["door_id"])
            if item.get("stair_id") and item["stair_id"] not in stairs: stairs.append(item["stair_id"])
        target = nodes[current]["target"]
        nominal = [item["nominal_width_m"] for item in proof if item.get("nominal_width_m") is not None]
        geometric = [item["geometric_opening_width_m"] for item in proof if item.get("geometric_opening_width_m") is not None]
        native_unit_ids = [u.id() for project in model.by_type("IfcProject") for u in project.UnitsInContext.Units if getattr(u,"UnitType",None)=="LENGTHUNIT"]
        base.update(target_id=target, status="partial", path_points_m=points, room_ids=route_rooms, door_ids=doors, stair_ids=stairs,
            source_step_ids=sorted({*rooms[subject]["source_inputs"], *native_unit_ids, *candidate_inputs, *[step for item in proof for step in item.get("source_step_ids", [])]}))
        base["metadata"].update(distance_m=length, segment_lengths_m=[math.dist(a, b) for a, b in zip(points, points[1:])],
            path_checks=proof, nominal_door_width_m=min(nominal) if nominal else None,
            geometric_opening_width_m=min(geometric) if geometric else None, sampled_clearance_m=None,
            start_basis=options.get("start_basis"), requested_start_point_m=options.get("start_point_m"),
            sampled_point_count=len(starts), sampling_resolution_m=resolution,
            certification_status="typed_source_certification" if target not in uncertified else "unavailable",
            nearest_basis="Shortest path among the validated portal samples to authorized recorded exterior opening centers.")
        if len(points) > 2048 or len(base["source_step_ids"]) > 2000:
            raise ValueError("Route proof exceeds bounded output size")
        records.append(base)
    if options.get("mode") == "farthest" and records:
        available = [r for r in records if r["path_points_m"]]
        if available:
            chosen = max(available, key=lambda r: r["metadata"]["distance_m"])
            chosen["metadata"]["farthest_domain_room_ids"] = list(options["subjects"])
            chosen["metadata"]["farthest_sampling_inventory"] = sampling_inventory
            chosen["metadata"]["total_start_sample_count"] = sum(item["sample_count"] for item in sampling_inventory)
            chosen["metadata"]["unreachable_origin_room_ids"] = [r["subject_id"] for r in records if not r["path_points_m"]]
            chosen["metadata"]["farthest_basis"] = "Maximum of sampled shortest paths; a sampled estimate, not an exact continuous-domain maximum."
            records = [chosen]
    return {"status": "match" if records and all(r["path_points_m"] for r in records) else "unknown", "records": records}


def _samples(polygon, limit):
    if limit < 8: return [], None
    area = polygon.area
    minx, miny, maxx, maxy = polygon.bounds
    result = []
    for part in _parts(polygon):
        result.extend(tuple(p) for ring in [part.exterior, *part.interiors] for p in list(ring.coords)[:-1])
        p = part.representative_point(); result.append((p.x, p.y))
    resolution = max(.25, math.sqrt(area / max(1, limit - len(result))))
    for x in np.arange(minx + resolution / 2, maxx, resolution):
        for y in np.arange(miny + resolution / 2, maxy, resolution):
            if polygon.covers(Point(x, y)): result.append((float(x), float(y)))
            if len(result) >= limit: return result[:limit], resolution
    return result[:limit], resolution


def _stairs(model, candidates, rooms, node, edge, failures, tolerance):
    """Native straight walking lines, checked against body rise and room floors."""
    from .geometry import _curve, _transform, _length_scale, _mesh
    from ifcopenshell.util.placement import get_local_placement
    import ifcopenshell.util.element
    scale = _length_scale(model)
    for identifier, step in candidates.items():
        stair = model.by_id(step)
        phase = "walking_line"
        try:
            reps = [r for r in stair.Representation.Representations if r.RepresentationIdentifier == "WalkingLine"]
            if len(reps) != 1 or len(reps[0].Items) != 1: raise ValueError("Ambiguous walking line")
            raw = _curve(reps[0].Items[0]); matrix = get_local_placement(stair.ObjectPlacement) if stair.ObjectPlacement else np.eye(4)
            points = _transform(raw, matrix, scale)
            if len(points) != 2: raise ValueError("Only a native straight flight line is supported")
            phase = "stair_body"
            vertices, faces = _mesh(model, stair)
            projection = _polygon(__import__("ifc_engine.geometry", fromlist=["_project_meshes"])._project_meshes([(vertices, faces)]))
            line = LineString(points[:, :2])
            if not projection.covers(line):
                # Stair body tread nosings can differ by a small native chord;
                # require its line to remain within the actual 1 mm tolerance.
                if not projection.buffer(tolerance).covers(line): raise ValueError("Walking line outside stair body")
            phase = "native_rise"
            rise, count, rise_basis, rise_proof = _stair_metrics(model, stair, scale)
            if not isinstance(count, int) or isinstance(count, bool) or count <= 0 or not math.isfinite(rise) or rise <= 0: raise ValueError("Invalid native stair rise")
            total = float(rise) * count
            body_rise = float(np.ptp(vertices[:, 2]))
            if not math.isfinite(total) or abs(body_rise - total) > max(.12, total * .05): raise ValueError("Native rise and stair body disagree")
            # Upper treads identify the rising direction without relying on
            # arbitrary polyline order; native rise then locates the top floor.
            phase = "endpoint_direction"
            z = []
            for p in points:
                direction = (points[-1, :2] - points[0, :2]) / line.length
                longitudinal = np.abs((vertices[:, :2] - p[:2]) @ direction)
                nearby = vertices[longitudinal <= max(.15, 1.2 * line.length / max(count, 1)), 2]
                if not len(nearby): raise ValueError("Stair line endpoint not on its body")
                z.append(float(nearby.max()))
            if abs(z[0] - z[1]) < .3: raise ValueError("Stair body does not establish walking-line rise direction")
            if z[0] > z[1]: points = points[::-1]
            lo = float(vertices[:, 2].min())
            phase = "room_endpoints"
            lower = [(rid, room) for rid, room in rooms.items() if room["polygon"].distance(Point(points[0, :2])) <= tolerance and abs(room["floor"] - lo) <= .12]
            pairs = []
            for low_id, low in lower:
                top = low["floor"] + total
                upper = [(rid, room) for rid, room in rooms.items() if room["polygon"].distance(Point(points[-1, :2])) <= tolerance and abs(room["floor"] - top) <= .03 and room["floor"] > low["floor"] + .3]
                for high_id, high in upper:
                    axy = nearest_points(low["polygon"], Point(points[0, :2]))[0]
                    bxy = nearest_points(high["polygon"], Point(points[-1, :2]))[0]
                    path = [(axy.x, axy.y, low["floor"]), (bxy.x, bxy.y, high["floor"])]
                    if projection.buffer(tolerance).covers(LineString([p[:2] for p in path])):
                        a, b = node(low_id, path[0]), node(high_id, path[1])
                        proof = {"kind": "stair", "stair_id": identifier, "source_step_ids": [*_geometry_inputs(stair), *rise_proof],
                            "rise_m": total, "riser_count": count, "rise_basis": rise_basis,
                            "native_attribute_rise_m": float(stair.RiserHeight)*getattr(stair,"NumberOfRiser",getattr(stair,"NumberOfRisers",0))*scale, "body_vertical_extent_m": body_rise,
                            "representation_step_ids": [r.id() for r in stair.Representation.Representations],
                            "basis": "Native walking-line pitch approximation with authored rise, verified against stair body and endpoint room floors; tread-by-tread walking distance is not asserted."}
                        edge(a, b, path, proof); pairs.append((low_id, high_id))
            if not pairs: raise ValueError("No supported lower and upper room endpoints")
        except Exception:
            failures.append({"entity_id": identifier, "reason": "native_stair_connector_unresolved", "phase": phase})

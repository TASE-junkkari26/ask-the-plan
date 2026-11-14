"""Bounded, revision-bound spatial checks; native geometry runs in a subprocess.

Only finite planar boundary patches and convex, closed room solids are accepted.
Unsupported/invalid shapes and tolerance-edge cases remain unknown. Bounding
boxes prune candidates; they never establish a positive spatial relationship.
"""
from __future__ import annotations

from collections import OrderedDict
import math
import multiprocessing
from pathlib import Path

import numpy as np

VERSION = "ifc-spatial-geometry-v2"
MAX_VERTICES = 100000
MAX_PATCHES = 256


class GeometryProvider:
    def __init__(self, path, source_sha256, *, timeout_seconds=10, max_items=2000):
        self.path = Path(path)
        self.source_sha256 = source_sha256
        self.timeout_seconds = timeout_seconds
        self.max_items = max_items
        self._cache = OrderedDict()

    def compare_boundaries(self, a_step, b_step, tolerance_m=0.01, *, timeout_seconds=None):
        return self._request("boundary_patch_overlap.v1", [a_step, b_step], tolerance_m, timeout_seconds)

    def locate_in_spaces(self, object_step, space_steps, tolerance_m=0.01, *, timeout_seconds=None):
        return self._request("convex_room_containment.v1", [object_step, *sorted(set(space_steps))], tolerance_m, timeout_seconds)

    def _request(self, method, steps, tolerance, timeout_seconds=None):
        result = dict(status="unknown", method=method, unit="m", frame="ifc_world",
                      source_sha256=self.source_sha256, geometry_version=VERSION,
                      tolerance_m=tolerance, source_step_ids=steps, reason="Geometry is unavailable.")
        if method == "convex_room_containment.v1":
            result.update(matched_step_ids=[], unresolved_step_ids=steps[1:])
        if not math.isfinite(tolerance) or not 0 < tolerance <= 0.1:
            return {**result, "reason": "Tolerance must be positive and at most 0.1 metre."}
        timeout = self.timeout_seconds if timeout_seconds is None else min(self.timeout_seconds,timeout_seconds)
        if timeout <= 0:
            return {**result, "reason": "The geometry execution budget is exhausted."}
        if len(steps) > self.max_items or not self.path.is_file():
            return {**result, "reason": "The bounded source geometry is unavailable or exceeds the object limit."}
        from .ingest import file_sha256
        try:
            if file_sha256(self.path) != self.source_sha256:
                return {**result, "reason": "The source bytes differ from the extracted IFC revision."}
        except OSError:
            return {**result, "reason": "The source revision is unavailable."}
        # The cache never outlives its immutable source/settings identity.
        key = (self.source_sha256, VERSION, method, tuple(steps), tolerance)
        if key in self._cache:
            self._cache.move_to_end(key)
            return dict(self._cache[key])
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        worker = context.Process(target=_worker, args=(sender, str(self.path), self.source_sha256, result))
        try:
            worker.start()
            sender.close()
            if receiver.poll(timeout):
                try:
                    result = receiver.recv()
                except (EOFError, OSError):
                    result["reason"] = "The native geometry worker could not complete this check."
            else:
                result["reason"] = "The geometry check exceeded its bounded execution deadline."
        except (OSError, RuntimeError):
            result["reason"] = "The isolated geometry worker is unavailable."
        finally:
            sender.close()
            receiver.close()
            if worker.pid is not None:
                if worker.is_alive():
                    worker.terminate()
                worker.join(timeout=1)
                if worker.is_alive():
                    worker.kill()
                    worker.join(timeout=1)
                worker.close()
        # A short earlier query budget must not permanently poison this source.
        if result["status"] in {"match", "no_match"}:
            self._cache[key] = result
            while len(self._cache) > 256:
                self._cache.popitem(last=False)
        return dict(result)


def _worker(sender, path, source_sha256, result):
    try:
        from .ingest import file_sha256
        import ifcopenshell
        if file_sha256(Path(path)) != source_sha256:
            result["reason"] = "The source bytes differ from the extracted IFC revision."
        else:
            model = ifcopenshell.open(path)
            if result["method"] == "boundary_patch_overlap.v1":
                result.update(_compare_boundaries(model, *result["source_step_ids"], result["tolerance_m"]))
            else:
                result.update(_locate(model, result["source_step_ids"][0], result["source_step_ids"][1:], result["tolerance_m"]))
            # Detect edits during native processing before publishing a claim.
            if file_sha256(Path(path)) != source_sha256:
                result.update(status="unknown", reason="The source changed during geometry processing.")
                if "matched_step_ids" in result:
                    result.update(matched_step_ids=[], unresolved_step_ids=result["source_step_ids"][1:])
    except Exception:
        # Native error text can contain source paths or huge STEP dumps.
        result.update(status="unknown", reason="This source geometry could not be processed by the bounded geometry method.")
    try:
        sender.send(result)
    finally:
        sender.close()


def _point(value):
    coords = list(value.Coordinates)
    return np.asarray([*coords, *([0.] * (3 - len(coords)))], dtype=float)


def _curve(curve):
    if curve.is_a("IfcPolyline"):
        return [_point(p) for p in curve.Points]
    if curve.is_a("IfcIndexedPolyCurve") and not curve.Segments:
        return [np.asarray([*p, *([0.] * (3 - len(p)))], dtype=float) for p in curve.Points.CoordList]
    raise ValueError("Only explicit straight boundary segments are supported")


def _placement(position):
    from ifcopenshell.util.placement import get_axis2placement
    return get_axis2placement(position) if position else np.eye(4)


def _transform(points, matrix, scale):
    result = np.asarray([(matrix @ np.r_[p, 1.])[:3] * scale for p in points])
    if len(result) > 2048 or not np.isfinite(result).all():
        raise ValueError("Invalid or excessive patch coordinates")
    return result


def _length_scale(model):
    from ifcopenshell.util.unit import get_unit_scale
    projects=model.by_type("IfcProject")
    assignment=projects[0].UnitsInContext if len(projects)==1 else None
    units=[u for u in assignment.Units if getattr(u,"UnitType",None)=="LENGTHUNIT"] if assignment else []
    if len(units)!=1:
        raise ValueError("A unique explicit source length unit is required")
    unit=units[0]
    visited=set()
    while unit.is_a("IfcConversionBasedUnit"):
        if unit.id() in visited or len(visited)>=32 or unit.is_a("IfcConversionBasedUnitWithOffset"):
            raise ValueError("Unsupported source length-unit chain")
        visited.add(unit.id())
        factor=float(unit.ConversionFactor.ValueComponent.wrappedValue)
        if not math.isfinite(factor) or factor<=0:
            raise ValueError("Invalid source length conversion")
        unit=unit.ConversionFactor.UnitComponent
    if not unit.is_a("IfcSIUnit") or unit.Name!="METRE":
        raise ValueError("Source length unit cannot be resolved to metres")
    scale=get_unit_scale(units[0])
    if not math.isfinite(scale) or scale<=0:
        raise ValueError("Invalid metre conversion")
    return scale


def _patches(model, boundary):
    from ifcopenshell.util.placement import get_local_placement
    connection = boundary.ConnectionGeometry
    if not connection or not connection.is_a("IfcConnectionSurfaceGeometry"):
        raise ValueError("Missing native connection surface")
    surface = connection.SurfaceOnRelatingElement
    if surface is None:
        raise ValueError("Missing relating-space surface")
    placement = getattr(boundary.RelatingSpace, "ObjectPlacement", None)
    world = get_local_placement(placement) if placement else np.eye(4)
    scale = _length_scale(model)
    patches = []
    if surface.is_a("IfcSurfaceOfLinearExtrusion"):
        profile = surface.SweptCurve
        if not profile.is_a("IfcArbitraryOpenProfileDef"):
            raise ValueError("Only open, explicit boundary profiles are supported")
        points = _curve(profile.Curve)
        vector = np.asarray(surface.ExtrudedDirection.DirectionRatios, dtype=float)
        vector = vector / np.linalg.norm(vector) * surface.Depth
        matrix = world @ _placement(surface.Position)
        patches = [_transform([a, b, b + vector, a + vector], matrix, scale)
                   for a, b in zip(points, points[1:])]
    elif surface.is_a("IfcCurveBoundedPlane"):
        if surface.InnerBoundaries:
            raise ValueError("Boundary patch holes need a separate evaluated method")
        points = _curve(surface.OuterBoundary)
        patches = [_transform(points, world @ _placement(surface.BasisSurface.Position), scale)]
    elif surface.is_a("IfcRectangularTrimmedSurface") and surface.BasisSurface.is_a("IfcPlane"):
        u1, v1, u2, v2 = surface.U1, surface.V1, surface.U2, surface.V2
        patches = [_transform([np.array(p) for p in [(u1,v1,0.), (u2,v1,0.), (u2,v2,0.), (u1,v2,0.)]],
                              world @ _placement(surface.BasisSurface.Position), scale)]
    else:
        raise ValueError("Unsupported finite boundary surface")
    if not patches or len(patches) > MAX_PATCHES:
        raise ValueError("Empty or excessive patch collection")
    return patches


def _cross2(a, b):
    return float(a[0]*b[1]-a[1]*b[0])


def _area(points):
    return .5 * sum(_cross2(a, b) for a, b in zip(points, np.roll(points, -1, axis=0)))


def _plane(patch, tolerance):
    if np.linalg.norm(patch[0] - patch[-1]) < 1e-10:
        patch = patch[:-1]
    if len(patch) < 3:
        raise ValueError("Degenerate patch")
    normal = sum((np.cross(a, b) for a, b in zip(patch, np.roll(patch, -1, axis=0))), np.zeros(3))
    if np.linalg.norm(normal) < 1e-12:
        raise ValueError("Zero-area patch")
    normal /= np.linalg.norm(normal)
    if np.max(np.abs((patch - patch[0]) @ normal)) > tolerance / 10:
        raise ValueError("Nonplanar patch")
    u = patch[1] - patch[0]
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    points = np.array([[(p - patch[0]) @ u, (p - patch[0]) @ v] for p in patch])
    if _area(points) < 0:
        points = points[::-1]
    return patch[0], normal, u, v, points


def _triangles(points):
    # Ear clipping supports simple concave rings. Ambiguous/invalid rings fail.
    for i, (a,b) in enumerate(zip(points,np.roll(points,-1,axis=0))):
        for j, (c,d) in enumerate(zip(points,np.roll(points,-1,axis=0))):
            if j <= i or j in {(i+1)%len(points),(i-1)%len(points)}:
                continue
            orientations=(_cross2(b-a,c-a),_cross2(b-a,d-a),_cross2(d-c,a-c),_cross2(d-c,b-c))
            if orientations[0]*orientations[1] <= 0 and orientations[2]*orientations[3] <= 0 and (
                    np.all(np.maximum(np.minimum(a,b),np.minimum(c,d)) <= np.minimum(np.maximum(a,b),np.maximum(c,d))+1e-12)):
                raise ValueError("Self-intersecting boundary polygon")
    indices = list(range(len(points)))
    triangles = []
    while len(indices) > 3:
        for k, current in enumerate(indices):
            a, b, c = (points[indices[(k - 1) % len(indices)]], points[current], points[indices[(k + 1) % len(indices)]])
            if _cross2(b - a, c - b) <= 1e-12:
                continue
            def inside(p):
                return all(_cross2(y - x, p - x) >= -1e-12 for x,y in [(a,b),(b,c),(c,a)])
            if any(inside(points[j]) for j in indices if j not in {indices[k - 1], current, indices[(k + 1) % len(indices)]}):
                continue
            triangles.append(np.array([a,b,c]))
            indices.pop(k)
            break
        else:
            raise ValueError("Invalid or unsupported boundary polygon")
    triangles.append(points[indices])
    return triangles


def _clip(subject, clip):
    output = list(subject)
    for a,b in zip(clip, np.roll(clip, -1, axis=0)):
        source, output = output, []
        if not source:
            break
        previous = source[-1]
        for current in source:
            d0, d1 = _cross2(b-a, previous-a), _cross2(b-a, current-a)
            if (d0 >= 0) != (d1 >= 0):
                output.append(previous + (current-previous) * (d0 / (d0-d1)))
            if d1 >= 0:
                output.append(current)
            previous = current
    return np.asarray(output)


def _minimum_width(points):
    """Minimum support width of a convex clipped polygon, in physical metres."""
    widths = []
    for a, b in zip(points, np.roll(points, -1, axis=0)):
        edge = b - a
        length = np.linalg.norm(edge)
        if length <= 1e-12:
            continue
        normal = np.array([-edge[1], edge[0]]) / length
        projected = points @ normal
        widths.append(float(np.max(projected) - np.min(projected)))
    return min(widths) if widths else 0.


def _mesh(model, element):
    import ifcopenshell.geom
    _length_scale(model)  # Native geometry must not silently assume metres.
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("convert-back-units", False)
    shape = ifcopenshell.geom.create_shape(settings, element)
    vertices = np.asarray(shape.geometry.verts).reshape((-1,3))
    faces = np.asarray(shape.geometry.faces).reshape((-1,3))
    if not len(vertices) or len(vertices) > MAX_VERTICES or not len(faces) or not np.isfinite(vertices).all():
        raise ValueError("Missing or excessive solid geometry")
    return vertices, faces


def _closed_vertices(vertices, faces):
    """Check closed manifold topology after welding physical-metre seam vertices."""
    rounded = np.round(vertices, 8)
    unique, indices = np.unique(rounded, axis=0, return_inverse=True)
    edges = {}
    links = {}
    for triangle in indices[faces]:
        if len(set(triangle)) != 3:
            raise ValueError("Degenerate mesh face")
        for a,b in zip(triangle, np.roll(triangle,-1)):
            key = tuple(sorted((int(a),int(b))))
            edges[key] = edges.get(key,0) + 1
        for vertex, a, b in (triangle, np.roll(triangle, 1), np.roll(triangle, 2)):
            graph = links.setdefault(int(vertex), {})
            graph.setdefault(int(a), set()).add(int(b))
            graph.setdefault(int(b), set()).add(int(a))
    if not edges or any(count != 2 for count in edges.values()):
        raise ValueError("Shape is not a closed manifold")
    for graph in links.values():
        if any(len(neighbors) != 2 for neighbors in graph.values()):
            raise ValueError("Nonmanifold mesh vertex")
        visited, pending = set(), [next(iter(graph))]
        while pending:
            item = pending.pop()
            if item not in visited:
                visited.add(item)
                pending.extend(graph[item] - visited)
        if len(visited) != len(graph):
            raise ValueError("Disconnected mesh vertex link")
    return unique


def _convex_planes(vertices, faces, tolerance):
    unique = _closed_vertices(vertices, faces)
    center = np.mean(unique, axis=0)
    planes = []
    for triangle in faces:
        a,b,c = vertices[triangle]
        normal = np.cross(b-a,c-a)
        if np.linalg.norm(normal) < 1e-12:
            raise ValueError("Degenerate mesh triangle")
        normal /= np.linalg.norm(normal)
        if (center-a) @ normal > 0:
            normal *= -1
        if np.max((vertices-a) @ normal) > min(tolerance/10,1e-5):
            raise ValueError("Only convex room/host solids are supported")
        planes.append((a,normal))
    if any(abs((center-a) @ n) < 1e-8 for a,n in planes):
        raise ValueError("Solid has no established interior")
    return planes


def _point_inside(point, planes, tolerance):
    distances = np.asarray([(point-a) @ n for a,n in planes])
    return bool(np.max(distances) <= tolerance)


def _compare_boundaries(model, a_step, b_step, tolerance):
    a, b = model.by_id(a_step), model.by_id(b_step)
    if not a.is_a("IfcRelSpaceBoundary") or not b.is_a("IfcRelSpaceBoundary"):
        raise ValueError("Expected native space boundary records")
    if not a.RelatedBuildingElement or a.RelatedBuildingElement != b.RelatedBuildingElement:
        return dict(status="unknown",reason="Patches do not refer to the same native boundary element.")
    patches_a, patches_b = _patches(model,a), _patches(model,b)
    uncertain = False
    for patch_a in patches_a:
        origin, normal, u, v, points_a = _plane(patch_a,tolerance)
        for patch_b in patches_b:
            _, normal_b, _, _, _ = _plane(patch_b,tolerance)
            if abs(normal @ normal_b) < 1-1e-8:
                continue  # Nonparallel patches cannot share positive face area.
            points_b = np.array([[(p-origin)@u,(p-origin)@v] for p in patch_b])
            if np.linalg.norm(points_b[0]-points_b[-1]) < 1e-10:
                points_b=points_b[:-1]
            if _area(points_b)<0:
                points_b=points_b[::-1]
            # Disjoint projected extents have no positive patch overlap.
            gaps=np.maximum(np.min(points_a,axis=0)-np.max(points_b,axis=0), np.min(points_b,axis=0)-np.max(points_a,axis=0))
            if np.max(gaps)>tolerance:
                continue
            intersections=[_clip(x,y) for x in _triangles(points_a) for y in _triangles(points_b)]
            intersections=[p for p in intersections if len(p)>=3 and abs(_area(p))>tolerance*tolerance
                           and _minimum_width(p)>tolerance]
            if not intersections:
                uncertain=True
                continue
            if normal @ normal_b > 0:
                uncertain=True  # Same-facing coincident patches do not prove opposing rooms.
                continue
            separation=float(np.mean((patch_b-origin)@normal))
            if abs(separation)>tolerance:
                # Opposing room faces may be separated by wall thickness. Only
                # accept this when a closed convex host bridges that segment.
                try:
                    host_vertices,host_faces=_mesh(model,a.RelatedBuildingElement)
                    planes=_convex_planes(host_vertices,host_faces,tolerance)
                    projected=np.mean(intersections[0],axis=0)
                    start=origin+projected[0]*u+projected[1]*v
                    if not all(_point_inside(start+normal*separation*t,planes,tolerance) for t in (0.,.25,.5,.75,1.)):
                        uncertain=True
                        continue
                except Exception:
                    uncertain=True
                    continue
            return dict(status="match",reason="Finite native boundary patches overlap across the same boundary element.",
                        overlap_area_m2=float(sum(abs(_area(p)) for p in intersections)),
                        plane_separation_m=abs(separation), patch_a_m=patch_a.tolist(),patch_b_m=patch_b.tolist(),
                        normal_a=normal.tolist(),normal_b=normal_b.tolist(),host_step_id=a.RelatedBuildingElement.id(),
                        connection_geometry_step_ids=[a.ConnectionGeometry.id(),b.ConnectionGeometry.id()])
    return dict(status="unknown" if uncertain else "no_match",reason=(
        "Boundary overlap is within tolerance or the intervening host geometry is unverified." if uncertain else
        "Finite native boundary patches have disjoint face extents."))


def _locate(model, object_step, space_steps, tolerance):
    matches, unresolved = [], []
    try:
        object_vertices,object_faces = _mesh(model,model.by_id(object_step))
        _closed_vertices(object_vertices, object_faces)
    except Exception:
        return dict(status="unknown",matched_step_ids=[],unresolved_step_ids=space_steps,
                    reason="The requested object's closed solid geometry is unavailable; its placement alone does not prove room containment.")
    for step in space_steps:
        try:
            space=model.by_id(step)
            if not space.is_a("IfcSpace"):
                raise ValueError("Expected room solid")
            vertices,faces=_mesh(model,space)
            # Negative pruning remains valid even for nonconvex room shapes.
            if np.any(np.min(object_vertices,axis=0)>np.max(vertices,axis=0)+tolerance) or np.any(np.max(object_vertices,axis=0)<np.min(vertices,axis=0)-tolerance):
                continue
            planes=_convex_planes(vertices,faces,tolerance)
            distances=np.asarray([np.max((object_vertices-a)@n) for a,n in planes])
            if np.max(distances)<-tolerance:
                matches.append(step)
            elif np.max(distances)<=tolerance:
                unresolved.append(step)  # Touching/near a face is ambiguous.
        except Exception:
            unresolved.append(step)
    return dict(status="unknown" if unresolved else "match" if matches else "no_match",
                matched_step_ids=matches,unresolved_step_ids=unresolved,
                reason="Whole-object geometry was tested against closed convex room solids; touching or unsupported solids remain unresolved.")

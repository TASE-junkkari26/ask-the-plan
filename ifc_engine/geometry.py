"""Bounded, revision-bound spatial checks; native geometry runs in a subprocess.

Only finite planar boundary patches and convex, closed room solids are accepted.
Unsupported/invalid shapes and tolerance-edge cases remain unknown. Bounding
boxes prune candidates; they never establish a positive spatial relationship.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import json
import hashlib
import math
import multiprocessing
from pathlib import Path
import sys

import numpy as np

VERSION = "ifc-spatial-geometry-v5-body-face-proof"
MAX_VERTICES = 100000
MAX_PATCHES = 256


def _record_cache_size(key, record):
    """Conservative Python-object budget, including native group keys."""
    total, seen, pending = 128, set(), [key, record]
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        total += sys.getsizeof(value)
        if isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, (tuple, list, set, frozenset)):
            pending.extend(value)
    return total


class GeometryProvider:
    def __init__(self, path, source_sha256, *, timeout_seconds=10, max_items=2000):
        self.path = Path(path)
        self.source_sha256 = source_sha256
        self.timeout_seconds = timeout_seconds
        self.max_items = max_items
        self._cache = OrderedDict()
        self._measurement_cache = OrderedDict()
        self._measurement_cache_bytes = 0
        self._measurement_cache_max_records = 2048
        self._measurement_cache_max_bytes = 16 * 1024 * 1024
        self._closed = False

    def close(self):
        self._closed = True
        self._cache.clear()
        self._measurement_cache.clear()
        self._measurement_cache_bytes = 0

    def _remember_record(self, key, record):
        size = _record_cache_size(key, record)
        if key in self._measurement_cache:
            _, previous_size = self._measurement_cache.pop(key)
            self._measurement_cache_bytes -= previous_size
        if size <= self._measurement_cache_max_bytes:
            self._measurement_cache[key] = deepcopy(record), size
            self._measurement_cache_bytes += size
            while len(self._measurement_cache) > self._measurement_cache_max_records or self._measurement_cache_bytes > self._measurement_cache_max_bytes:
                _, (_, previous_size) = self._measurement_cache.popitem(last=False)
                self._measurement_cache_bytes -= previous_size

    def compare_boundaries(self, a_step, b_step, tolerance_m=0.01, *, timeout_seconds=None):
        return self._request("boundary_patch_overlap.v1", [a_step, b_step], tolerance_m, timeout_seconds)

    def locate_in_spaces(self, object_step, space_steps, tolerance_m=0.01, *, timeout_seconds=None):
        return self._request("convex_room_containment.v1", [object_step, *sorted(set(space_steps))], tolerance_m, timeout_seconds)

    def route_many(self, options, *, tolerance_m=.001, timeout_seconds=None):
        """Route over an explicitly authorized native room/portal inventory."""
        if self._closed or not self._measurement_source_matches():
            return dict(status="unknown", records=[], reason="The immutable route source is unavailable.")
        steps = sorted({step for group in ("rooms", "doors", "openings", "stairs")
            for step in options.get(group, {}).values()})
        signature = hashlib.sha256(json.dumps(options, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        key = self.source_sha256, VERSION, "native_room_opening_visibility_route.v1", tolerance_m, signature
        if key in self._measurement_cache:
            self._measurement_cache.move_to_end(key)
            return deepcopy(self._measurement_cache[key][0])
        result = self._request("native_room_opening_visibility_route.v1", steps,
            tolerance_m, timeout_seconds, options=options)
        if result.get("status") == "match" and result.get("records") and all(record.get("path_points_m") for record in result["records"]):
            self._remember_record(key, result)
        return result

    def measure_many(self, metric, subjects, references=None, *, basis,
                     tolerance_m=0.001, timeout_seconds=None, incomplete_groups=(), explicit_root_steps=()):
        """Measure a bounded batch in one source-opening native worker.

        Groups are already expanded to authorized source objects by the executor;
        this method never follows hidden native containment relationships.
        """
        references = references or {}
        options = {"metric": metric, "basis": basis,
                   "subjects": {key: list(dict.fromkeys(values)) for key, values in subjects.items()},
                   "references": {key: list(dict.fromkeys(values)) for key, values in references.items()},
                   "incomplete_groups": sorted(set(incomplete_groups)),
                   "explicit_root_steps": sorted(set(explicit_root_steps))}
        steps = sorted({step for groups in (subjects, references) for values in groups.values() for step in values})
        result = dict(status="unknown", method="mesh_measurement.v1", unit="m", frame="ifc_world",
            source_sha256=self.source_sha256, geometry_version=VERSION, tolerance_m=tolerance_m,
            source_step_ids=steps, records=[], reason="The bounded native measurement source is unavailable.")
        if self._closed or len(steps) > self.max_items or not self._measurement_source_matches():
            return result
        combined_references = metric == "enclosed_area"
        if combined_references and (len(subjects) > 64 or len(references) > 32):
            return {**result, "reason": "Enclosure groups exceed the bounded work budget."}
        if not combined_references and len(subjects) * max(1, len(references)) > 10000:
            return {**result, "reason": "Measurement pairs exceed the bounded work budget."}
        if not math.isfinite(tolerance_m) or not 0 < tolerance_m <= .1:
            return {**result, "reason": "Tolerance must be positive and at most 0.1 metre."}
        pairs = [(subject, reference) for subject in subjects for reference in ([None] if combined_references else references or [None])]
        keys, records, missing = {}, {}, []
        incomplete = set(options["incomplete_groups"])
        explicit = set(options["explicit_root_steps"])
        for subject, reference in pairs:
            source_steps = options["subjects"][subject]
            reference_steps = ([step for values in options["references"].values() for step in values]
                               if combined_references else options["references"].get(reference, []))
            relevant = set(source_steps + reference_steps)
            key = (self.source_sha256, VERSION, metric, basis, tolerance_m,
                tuple(source_steps),
                tuple((identifier, tuple(values), identifier in incomplete) for identifier, values in sorted(options["references"].items())) if combined_references else tuple(reference_steps),
                subject in incomplete, any(identifier in incomplete for identifier in references) if combined_references else reference in incomplete if reference else False,
                tuple(sorted(explicit & relevant)))
            keys[subject, reference] = key
            if key in self._measurement_cache:
                self._measurement_cache.move_to_end(key)
                raw, _ = self._measurement_cache[key]
                record = deepcopy(raw)
                record.update(subject_id=subject, reference_entity_ids=list(references) if combined_references else [reference] if reference else [])
                records[subject, reference] = record
            else:
                missing.append((subject, reference))
        if missing:
            pending_subjects = {subject for subject, _ in missing}
            pending_references = set(references) if combined_references else {reference for _, reference in missing if reference is not None}
            pending = {**options,
                "subjects": {key: value for key, value in options["subjects"].items() if key in pending_subjects},
                "references": {key: value for key, value in options["references"].items() if key in pending_references}}
            pending_steps = sorted({step for groups in (pending["subjects"], pending["references"])
                for values in groups.values() for step in values})
            observed = self._request("mesh_measurement.v1", pending_steps, tolerance_m, timeout_seconds, options=pending)
            # A changed source invalidates both newly measured and previously
            # cached records for this request. Failures/timeouts are not cached.
            if not self._measurement_source_matches():
                return {**result, "reason": "The source bytes differ from the extracted IFC revision."}
            for record in observed.get("records", []):
                reference = None if combined_references else next(iter(record.get("reference_entity_ids", [])), None)
                pair = record.get("subject_id"), reference
                if pair not in keys:
                    continue
                if pair not in records or record.get("status") == "verified":
                    records[pair] = deepcopy(record)
                if record.get("status") == "verified" and isinstance(record.get("value"), (int, float)) and math.isfinite(record["value"]):
                    self._remember_record(keys[pair], record)
        for subject, reference in pairs:
            if (subject, reference) not in records:
                records[subject, reference] = dict(subject_id=subject,
                    reference_entity_ids=list(references) if combined_references else [reference] if reference else [], metric=metric, basis=basis,
                    status="unavailable", value=None, source_step_ids=sorted(set(options["subjects"][subject] +
                        ([step for values in options["references"].values() for step in values] if combined_references else options["references"].get(reference, [])))),
                    representation_step_ids=[], method="native_mesh_" + metric + ".v1", frame="ifc_world",
                    unit="m2" if metric in {"area", "union_area", "enclosed_area"} else "m3" if metric == "volume" else "m",
                    tolerance_m=tolerance_m, metadata={"basis": basis, "geometry_version": VERSION,
                        "reason": "The required source geometry could not be measured within this request's work/deadline budget."})
        result["records"] = [records[pair] for pair in pairs]
        result["status"] = "match" if pairs and all(record["status"] == "verified" for record in result["records"]) else "unknown"
        result["reason"] = "Source-revision-bound native measurements; cached records retain the original method and numeric inputs."
        return result

    def _measurement_source_matches(self):
        from .ingest import file_sha256
        try:
            return self.path.is_file() and file_sha256(self.path) == self.source_sha256
        except OSError:
            return False

    def verify_layered_volumes(self, subjects, *, tolerance_m=0.001, timeout_seconds=None):
        """Verify native layer usages against bounded, uniform host prisms."""
        result = dict(status="unknown", method="uniform_layered_volumes.v1", frame="ifc_world", unit="m3",
            source_sha256=self.source_sha256, geometry_version=VERSION, tolerance_m=tolerance_m,
            source_step_ids=sorted(set(subjects.values())), records=[],
            reason="A uniform closed source solid and unambiguous native layer usage are required.")
        if self._closed or len(subjects) > self.max_items or not self._measurement_source_matches():
            return result
        if not math.isfinite(tolerance_m) or not 0 < tolerance_m <= .1:
            return result
        records, pending, keys = {}, {}, {}
        for subject, step in subjects.items():
            key = self.source_sha256, VERSION, "uniform_layered_prism.v1", tolerance_m, step
            keys[subject] = key
            if key in self._measurement_cache:
                self._measurement_cache.move_to_end(key)
                record = deepcopy(self._measurement_cache[key][0])
                record["subject_id"] = subject
                records[subject] = record
            else:
                pending[subject] = step
        if pending:
            observed = self._request("uniform_layered_volumes.v1", sorted(set(pending.values())), tolerance_m,
                timeout_seconds, options={"subjects": pending})
            if not self._measurement_source_matches():
                return result
            for record in observed.get("records", []):
                subject = record.get("subject_id")
                if subject not in keys:
                    continue
                records[subject] = deepcopy(record)
                if record.get("status") == "verified":
                    self._remember_record(keys[subject], record)
        result["records"] = [records.get(subject, {"subject_id": subject, "status": "unavailable",
            "method": "uniform_layered_prism.v1", "frame": "ifc_world", "unit": "m3", "volume_m3": None,
            "source_step_ids": [step], "representation_step_ids": [], "metadata": {"reason_code": "geometry_work_budget"}})
            for subject, step in subjects.items()]
        result["status"] = "match" if result["records"] and all(record["status"] == "verified" for record in result["records"]) else "unknown"
        return result

    def _request(self, method, steps, tolerance, timeout_seconds=None, *, options=None):
        result = dict(status="unknown", method=method, unit="m", frame="ifc_world",
                      source_sha256=self.source_sha256, geometry_version=VERSION,
                      tolerance_m=tolerance, source_step_ids=steps, reason="Geometry is unavailable.")
        if options is not None:
            result["options"] = options
            result["records"] = []
        if method == "convex_room_containment.v1":
            result.update(matched_step_ids=[], unresolved_step_ids=steps[1:])
        if not math.isfinite(tolerance) or not 0 < tolerance <= 0.1:
            return {**result, "reason": "Tolerance must be positive and at most 0.1 metre."}
        timeout = self.timeout_seconds if timeout_seconds is None else min(self.timeout_seconds,timeout_seconds)
        if timeout <= 0:
            return {**result, "reason": "The geometry execution budget is exhausted."}
        if self._closed or len(steps) > self.max_items or not self.path.is_file():
            return {**result, "reason": "The bounded source geometry is unavailable or exceeds the object limit."}
        from .ingest import file_sha256
        try:
            if file_sha256(self.path) != self.source_sha256:
                return {**result, "reason": "The source bytes differ from the extracted IFC revision."}
        except OSError:
            return {**result, "reason": "The source revision is unavailable."}
        # The cache never outlives its immutable source/settings identity.
        key = (self.source_sha256, VERSION, method, tuple(steps), tolerance,
               json.dumps(options, sort_keys=True) if options is not None else "")
        if method not in {"mesh_measurement.v1", "uniform_layered_volumes.v1", "native_room_opening_visibility_route.v1"} and key in self._cache:
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
        if method not in {"mesh_measurement.v1", "uniform_layered_volumes.v1", "native_room_opening_visibility_route.v1"} and result["status"] in {"match", "no_match"}:
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
            if result["method"] == "mesh_measurement.v1":
                result.update(_measure_batch(model, result["options"], result["tolerance_m"]))
                result.pop("options", None)
            elif result["method"] == "uniform_layered_volumes.v1":
                from .layer_geometry import verify_layered_batch
                result.update(verify_layered_batch(model, result["options"]["subjects"], result["tolerance_m"]))
                result.pop("options", None)
            elif result["method"] == "native_room_opening_visibility_route.v1":
                from .route_geometry import route_batch
                result.update(route_batch(model, result["options"], result["tolerance_m"]))
                result.pop("options", None)
            elif result["method"] == "boundary_patch_overlap.v1":
                result.update(_compare_boundaries(model, *result["source_step_ids"], result["tolerance_m"]))
            else:
                result.update(_locate(model, result["source_step_ids"][0], result["source_step_ids"][1:], result["tolerance_m"]))
            # Detect edits during native processing before publishing a claim.
            if file_sha256(Path(path)) != source_sha256:
                result.update(status="unknown", reason="The source changed during geometry processing.")
                if "records" in result:
                    result["records"] = []
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


def _mesh_sources(model, steps, cache, *, prefer_root=True, explicit_roots=()):
    """Read only the explicitly authorized representation-bearing records."""
    meshes, used, representations = [], [], []
    required_roots = set(explicit_roots)
    if prefer_root and steps:
        required_roots.add(steps[0])
    for step in required_roots:
        if step in steps:
            selected = model.by_id(step)
            if selected.is_a("IfcSpace") and getattr(selected, "Representation", None) is None:
                raise ValueError("A room's contents do not establish the missing room-volume footprint")
    if prefer_root and steps and getattr(model.by_id(steps[0]), "Representation", None) is not None:
        steps = steps[:1]
    for step in steps:
        element = model.by_id(step)
        # Spatial parents have no shape of their own. The caller supplies all
        # authorized descendants; never follow native inverses in this worker.
        representation = getattr(element, "Representation", None)
        if representation is None:
            continue
        # Voids and room volumes are not physical building-envelope components.
        # They are still measurable when explicitly selected as the sole source.
        if len(steps) > 1 and step not in explicit_roots and (element.is_a("IfcOpeningElement") or element.is_a("IfcSpace")):
            continue
        if step not in cache:
            cache[step] = _mesh(model, element)
        vertices, faces = cache[step]
        if element.is_a("IfcSpace") and np.ptp(vertices[:, 2]) > 1e-8:
            # A nonplanar partial room shell can project to a plausible area
            # (or a false zero). Require a closed modeled room solid before
            # using its projection as a room-footprint measurement.
            _closed_vertices(vertices, faces)
        meshes.append((vertices, faces))
        used.append(step)
        representations.append(representation.id())
        representations.extend(item.id() for item in representation.Representations)
    if not meshes:
        raise ValueError("No usable source mesh representation")
    if sum(len(vertices) for vertices, _ in meshes) > 500000:
        raise ValueError("The combined mesh exceeds the bounded vertex budget")
    return meshes, used, sorted(set(representations))


def _project_meshes(meshes):
    """Exact union of mesh-triangle XY projections, retaining concave outlines."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    triangles = []
    if sum(len(faces) for _, faces in meshes) > 250000:
        raise ValueError("Projected triangles exceed the bounded work budget")
    for vertices, faces in meshes:
        for points in vertices[faces, :2]:
            polygon = Polygon(points)
            if polygon.area > 1e-16:
                triangles.append(polygon)
            else:
                # A vertical surface still has a meaningful projected line for
                # distance, but contributes no projected area.
                unique = np.unique(points, axis=0)
                if len(unique) > 1:
                    triangles.append(LineString(unique))
    if not triangles:
        raise ValueError("No finite projected geometry")
    result = unary_union(triangles)
    if result.is_empty or not result.is_valid:
        raise ValueError("Projected geometry is invalid")
    return result


def _surface_area(meshes):
    return float(sum(np.sum(np.linalg.norm(np.cross(
        vertices[faces[:, 1]] - vertices[faces[:, 0]],
        vertices[faces[:, 2]] - vertices[faces[:, 0]]), axis=1)) / 2
        for vertices, faces in meshes))


def _solid_volume(vertices, faces):
    """Oriented tetrahedron integration over a closed, consistently wound mesh.

    Separate nested shells retain their sign (cavities subtract). A conflicting
    orientation among disjoint shells is rejected rather than cancelling solid
    volumes into a plausible but wrong answer.
    """
    _closed_vertices(vertices, faces)
    _, welded = np.unique(np.round(vertices, 8), axis=0, return_inverse=True)
    triangles = welded[faces]
    directed = {}
    vertex_faces = {}
    for index, triangle in enumerate(triangles):
        for a, b in zip(triangle, np.roll(triangle, -1)):
            key = tuple(sorted((int(a), int(b))))
            directed[key] = directed.get(key, 0) + (1 if a < b else -1)
        for vertex in triangle:
            vertex_faces.setdefault(int(vertex), []).append(index)
    if any(directed.values()):
        raise ValueError("Closed faces have inconsistent winding")
    pending = set(range(len(faces)))
    components = []
    while pending:
        frontier, component = [pending.pop()], set()
        while frontier:
            index = frontier.pop()
            if index in component:
                continue
            component.add(index)
            pending.discard(index)
            frontier.extend(other for vertex in triangles[index]
                            for other in vertex_faces[int(vertex)] if other not in component)
        components.append(np.asarray(sorted(component), dtype=int))
    origin = np.mean(vertices, axis=0)
    signed = []
    bounds = []
    for component in components:
        points = vertices[faces[component]] - origin
        signed.append(float(np.sum(np.einsum("ij,ij->i", points[:, 0],
            np.cross(points[:, 1], points[:, 2]))) / 6))
        points = vertices[faces[component]].reshape((-1, 3))
        bounds.append((np.min(points, axis=0), np.max(points, axis=0)))
    if any(abs(value) < 1e-12 for value in signed):
        raise ValueError("A shell has no established enclosed volume")
    # A native disconnected compound may have independently wound outer shells.
    # Summing their absolute values is valid only when their bounds are disjoint.
    if len(components) > 1:
        disjoint = all(np.any(a_max < b_min) or np.any(b_max < a_min)
            for i, (a_min, a_max) in enumerate(bounds)
            for b_min, b_max in bounds[i + 1:])
        if disjoint:
            return float(sum(abs(value) for value in signed))
        # With nested/intersecting shells, source winding must consistently
        # describe a signed solid. Reject ambiguous compound orientation.
        if len({value > 0 for value in signed}) > 1:
            raise ValueError("Nested or overlapping compound shells require explicit solid validation")
        raise ValueError("Overlapping compound shells cannot establish a union volume")
    return abs(signed[0])


def _curve_length_sources(model, steps):
    from ifcopenshell.util.placement import get_local_placement
    scale = _length_scale(model)
    used, representations, total = [], [], 0.
    for step in steps:
        element = model.by_id(step)
        representation = getattr(element, "Representation", None)
        if representation is None:
            continue
        matrix = get_local_placement(element.ObjectPlacement) if element.ObjectPlacement else np.eye(4)
        accepted = []
        for shape in representation.Representations:
            if shape.RepresentationIdentifier not in {"Axis", "FootPrint"}:
                continue
            for item in shape.Items:
                if item.is_a("IfcGeometricCurveSet"):
                    curves = item.Elements
                else:
                    curves = [item]
                for curve in curves:
                    points = _transform(_curve(curve), matrix, scale)
                    total += float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)))
                    accepted.append(curve.id())
            representations.append(shape.id())
        if not accepted:
            raise ValueError("No explicit straight Axis/FootPrint curve is available")
        used.append(step)
        representations.extend([representation.id(), *accepted])
    if not used:
        raise ValueError("No modeled curve length is available")
    return total, used, sorted(set(representations))


def _measure_batch(model, options, tolerance):
    """Return finite source-derived measurements, never physical-room claims."""
    metric, basis = options["metric"], options["basis"]
    supported = {
        "height": {"world_z_extent", "validated_vertical_spans"}, "base_elevation": {"world_min_z"},
        "area": {"surface", "footprint", "net_opaque_face"}, "union_area": {"footprint"},
        "volume": {"solid"}, "length": {"axis"}, "perimeter": {"footprint"},
        "horizontal_distance": {"minimum_projected_separation"},
        "distance": {"surface_centroids"},
        "enclosed_area": {"bounded_regions"},
    }
    records = []
    if metric not in supported or basis not in supported[metric]:
        return {"status": "unknown", "records": [],
                "reason": "This metric requires an explicit supported mesh/curve measurement basis."}
    references = options["references"]
    pair = metric in {"distance", "horizontal_distance"}
    enclosed = metric == "enclosed_area"
    if not enclosed and pair != bool(references):
        return {"status": "unknown", "records": [],
                "reason": "Distance measurements require explicit reference objects; other metrics do not."}
    if enclosed and (len(options["subjects"]) > 64 or len(references) > 32):
        return {"status": "unknown", "records": [], "reason": "Enclosure groups exceed the bounded work budget."}
    if not enclosed and len(options["subjects"]) * max(1, len(references)) > 10000:
        return {"status": "unknown", "records": [], "reason": "Measurement pairs exceed the bounded work budget."}
    cache, group_cache = {}, {}

    def geometry(steps):
        key = tuple(steps)
        if key not in group_cache:
            group_cache[key] = _mesh_sources(model, steps, cache, prefer_root=metric != "union_area",
                explicit_roots=options.get("explicit_root_steps", ()))
        return group_cache[key]

    for subject, steps in options["subjects"].items():
        grouped_references = list(references.items()) if enclosed else []
        combined_steps = [step for _, values in grouped_references for step in values]
        for reference, reference_steps in (references.items() if pair else [(None, combined_steps)]):
            record = {"subject_id": subject, "reference_entity_ids": list(references) if enclosed else [reference] if reference else [],
                "metric": metric, "basis": basis, "status": "unavailable", "value": None,
                "source_step_ids": sorted(set(steps + reference_steps)), "representation_step_ids": [],
                "method": "native_axis_polyline_length.v1" if metric == "length" else "native_mesh_" + metric + ".v1",
                "frame": "ifc_world", "unit": "m2" if metric in {"area", "union_area", "enclosed_area"} else "m3" if metric == "volume" else "m",
                "tolerance_m": tolerance, "metadata": {"basis": basis, "geometry_version": VERSION}}
            try:
                for identifier, group in [(subject, steps), *(grouped_references if enclosed else [(reference, reference_steps)] if reference else [])]:
                    if identifier in options.get("incomplete_groups", ()) and (
                            metric == "union_area" or getattr(model.by_id(group[0]), "Representation", None) is None):
                        record["metadata"]["issue_code"] = "incomplete_coverage"
                        raise ValueError("The aggregate geometry requires objects outside the captured scope")
                if metric == "length":
                    value, used, representations = _curve_length_sources(model, steps)
                    record.update(source_step_ids=used, representation_step_ids=representations)
                elif metric == "area" and basis == "net_opaque_face":
                    from .layer_geometry import verify_layer_axis_body_batch
                    from .wall_geometry import net_opaque_face_area
                    if not steps or getattr(model.by_id(steps[0]), "Representation", None) is None:
                        raise ValueError("One represented source occurrence is required for a single opaque face")
                    evaluated = verify_layer_axis_body_batch(model, {subject: steps[0]}, tolerance)["records"][0]
                    face = net_opaque_face_area(evaluated)
                    record["method"] = face["method"]
                    record["metadata"].update(face["metadata"])
                    if evaluated["metadata"].get("reason_code"):
                        record["metadata"]["host_prism_reason_code"] = evaluated["metadata"]["reason_code"]
                    record["metadata"]["native_input_step_ids"] = evaluated["source_step_ids"]
                    record.update(source_step_ids=[steps[0]], representation_step_ids=evaluated["representation_step_ids"])
                    if face["status"] != "verified":
                        raise ValueError("The source does not establish a uniform layered host face")
                    value = float(face["value"])
                    record["metadata"]["face_counting_basis"] = "One verified cap normal to the native horizontal layer axis; modeled holes and edge-opening cutouts remain subtracted."
                else:
                    meshes, used, representations = geometry(steps)
                    record.update(source_step_ids=used, representation_step_ids=representations)
                    vertices = np.concatenate([vertices for vertices, _ in meshes])
                    record["metadata"].update(vertex_count=len(vertices), triangle_count=sum(len(faces) for _, faces in meshes),
                        minimum_m=np.min(vertices, axis=0).tolist(), maximum_m=np.max(vertices, axis=0).tolist())
                    if metric == "height":
                        if basis == "validated_vertical_spans":
                            from .wall_geometry import validated_vertical_spans
                            offset, combined_faces = 0, []
                            for points, faces in meshes:
                                combined_faces.append(faces + offset)
                                offset += len(points)
                            evaluated = validated_vertical_spans(vertices, np.concatenate(combined_faces), tolerance)
                            record["method"] = evaluated["method"]
                            record["metadata"].update(evaluated["metadata"])
                            if evaluated["status"] != "verified":
                                raise ValueError("The full source mesh does not establish a uniform standing height")
                            value = float(evaluated["value"])
                        else:
                            value = float(np.ptp(vertices[:, 2]))
                    elif metric == "base_elevation":
                        value = float(np.min(vertices[:, 2]))
                    elif metric == "volume":
                        if len(meshes) != 1:
                            raise ValueError("A combined set of overlapping components cannot establish solid union volume")
                        value = _solid_volume(*meshes[0])
                    elif metric == "area" and basis == "surface":
                        value = _surface_area(meshes)
                    elif enclosed:
                        from .enclosure import enclosed_regions
                        closures, closure_steps, closure_representations = {}, [], []
                        for identifier, group in references.items():
                            other, other_used, other_representations = geometry(group)
                            closures[identifier] = _project_meshes(other)
                            closure_steps.extend(other_used)
                            closure_representations.extend(other_representations)
                        enclosed_result = enclosed_regions(_project_meshes(meshes), closures, tolerance)
                        if enclosed_result["status"] != "verified":
                            record["metadata"].update(enclosed_result)
                            raise ValueError("The selected source parts do not establish a bounded enclosure")
                        value = enclosed_result["value"]
                        record["metadata"].update(enclosed_result["metadata"])
                        record["metadata"]["reference_source_step_ids"] = {identifier: geometry(group)[1] for identifier, group in references.items()}
                        record["source_step_ids"] = sorted(set(used + closure_steps))
                        record["representation_step_ids"] = sorted(set(representations + closure_representations))
                    elif metric in {"area", "union_area", "perimeter"}:
                        projected = _project_meshes(meshes)
                        value = float(projected.length if metric == "perimeter" else projected.area)
                    else:
                        other, other_used, other_representations = geometry(reference_steps)
                        record["source_step_ids"] = sorted(set(used + other_used))
                        record["representation_step_ids"] = sorted(set(representations + other_representations))
                        if metric == "horizontal_distance":
                            from shapely.ops import nearest_points
                            a, b = _project_meshes(meshes), _project_meshes(other)
                            value = float(a.distance(b))
                            record["metadata"]["nearest_points_xy_m"] = [list(point.coords[0]) for point in nearest_points(a, b)]
                        else:
                            def centroid(items):
                                numerator, weight = np.zeros(3), 0.
                                for points, faces in items:
                                    triangles = points[faces]
                                    areas = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1) / 2
                                    numerator += np.sum(np.mean(triangles, axis=1) * areas[:, None], axis=0)
                                    weight += float(np.sum(areas))
                                if weight <= 0:
                                    raise ValueError("Surface centroid has no established area")
                                return numerator / weight
                            a, b = centroid(meshes), centroid(other)
                            value = float(np.linalg.norm(a - b))
                            record["metadata"]["surface_centroids_m"] = [a.tolist(), b.tolist()]
                if not math.isfinite(value) or metric != "base_elevation" and value < 0:
                    raise ValueError("A finite geometric measurement could not be established")
                record.update(status="verified", value=value)
                record["metadata"]["quality_basis"] = "Calculated from the source tessellation; geometric tolerance and source modeling accuracy apply."
            except Exception:
                # Native error text can include entire source records/paths.
                record["metadata"]["reason"] = "The required finite source geometry is missing, invalid, ambiguous or exceeds the bounded method's work limits."
            records.append(record)
    return {"status": "match" if records and all(record["status"] == "verified" for record in records) else "unknown",
            "records": records, "reason": "Measurements use native source geometry in physical metre coordinates; they do not establish a navigable route or regulatory compliance."}


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

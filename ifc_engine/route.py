"""Scope-bound route execution and public native geometry proof."""
from __future__ import annotations

import math
import json
from collections import defaultdict

from contracts import models as m
from .units import decimal_string


def execute_route(engine, state, operation, scope_members, target_state=None):
    from .engine import QueryError, _Support

    inputs = [state, *([target_state] if target_state is not None else [])]
    if any(value.shape != "entities" for value in inputs):
        raise QueryError("unsupported_operation", "Walking routes require selected origin room and optional target door occurrences.")
    if any(value.unresolved or value.candidate_members or not value.coverage_complete for value in inputs):
        raise QueryError("incomplete_coverage", "An unresolved room or target selection cannot establish a complete modeled route.")
    subjects = sorted(state.members)
    if not subjects or any(engine.entities[identifier].kind != "space" for identifier in subjects):
        raise QueryError("needs_clarification", "Choose one or more native IfcSpace origins for a modeled walking route.", subjects)
    if operation.start_point_m is not None and len(subjects) != 1:
        raise QueryError("needs_clarification", "An explicit physical start point requires one unambiguous origin room.", subjects)
    targets = sorted(target_state.members) if target_state is not None else None
    if targets is not None and any("ifc:IfcDoor" not in engine.entities[identifier].concept_ids for identifier in targets):
        raise QueryError("needs_clarification", "Route targets must be native door occurrences.", targets)
    if not set(subjects + (targets or [])) <= scope_members:
        raise QueryError("incomplete_coverage", "Route origins and targets must belong to the captured source/view scope.", subjects)
    provider = getattr(engine, "geometry", None)
    if provider is None:
        raise QueryError("missing_information", "Walking routes require the retained immutable original IFC source.")
    def native_step(identifier):
        values = {int(engine.anchors[a].selector.value) for a in engine.entity_anchors[identifier]
            if engine.anchors[a].selector.kind == "step_id" and not engine.anchors[a].selector.property_path
            and engine.anchors[a].selector.value.isdigit()}
        if len(values) != 1:
            raise QueryError("missing_information", "A route object has no unique native IFC record.", [identifier])
        return next(iter(values))
    groups = {key: {} for key in ("rooms", "doors", "openings", "stairs")}
    for identifier in sorted(scope_members):
        entity = engine.entities[identifier]
        key = ("rooms" if entity.kind == "space" else "doors" if "ifc:IfcDoor" in entity.concept_ids
            else "openings" if "ifc:IfcOpeningElement" in entity.concept_ids
            else "stairs" if "ifc:IfcStairFlight" in entity.concept_ids else None)
        if key:
            groups[key][identifier] = native_step(identifier)
    boundaries = [boundary for boundary in engine.bundle.space_boundaries if boundary.space_id in groups["rooms"]
        and (boundary.physical_or_virtual == "VIRTUAL" or boundary.element_id in groups["doors"])]
    outside_doors = [boundary for boundary in engine.bundle.space_boundaries if boundary.space_id in groups["rooms"]
        and boundary.element_id and boundary.element_id not in scope_members
        and "ifc:IfcDoor" in engine.entities[boundary.element_id].concept_ids]
    visible_portal_doors = {boundary.element_id for boundary in boundaries if boundary.element_id in groups["doors"]}
    outside_rooms = [boundary for boundary in engine.bundle.space_boundaries if boundary.space_id not in scope_members
        and boundary.element_id in visible_portal_doors]
    options = {**groups, "subjects": subjects, "targets": targets,
        "boundaries": sorted(boundary.native_step_id for boundary in boundaries),
        "mode": operation.mode, "start_basis": operation.start_basis, "start_point_m": operation.start_point_m,
        "target_basis": operation.target_basis, "include_stairs": operation.include_stairs, "clearance_m": operation.clearance_m}
    observed = provider.route_many(options, tolerance_m=.001)
    records = observed.get("records", [])
    if not records:
        raise QueryError("unsupported_operation", "The native route inventory could not be processed within the bounded geometry deadline.", subjects)
    if operation.mode == "shortest" and ({r.get("subject_id") for r in records} != set(subjects) or len(records) != len(subjects)):
        raise QueryError("execution_error", "Native routing did not return the requested origin inventory.", subjects)
    step_anchors = defaultdict(set)
    for anchor in engine.anchors.values():
        if anchor.selector.kind == "step_id" and anchor.selector.value.isdigit():
            step_anchors[int(anchor.selector.value)].add(anchor.id)
    inventory_proof = {a for group in groups.values() for identifier in group for a in engine.entity_anchors[identifier]}
    inventory_proof.update(a for boundary in boundaries for a in boundary.provenance.anchor_ids)
    state.anchors.update(inventory_proof)
    state.members = set()  # Public highlights describe the chosen physical path; inventory proof stays on the calculation.
    if target_state is not None:
        state.facts.update(target_state.facts); state.anchors.update(target_state.anchors)
        state.concepts.update(target_state.concepts); state.properties.update(target_state.properties)
        state.operation_keys.extend(target_state.operation_keys)
    state.quality = "estimated"
    if outside_doors or outside_rooms:
        state.coverage_complete = False
    rows, cells = [], []
    for raw in records:
        related = {identifier for key in ("room_ids", "door_ids", "stair_ids") for identifier in raw.get(key, [])}
        if raw.get("subject_id") not in subjects or not related <= scope_members or raw.get("target_id") and raw["target_id"] not in groups["doors"]:
            raise QueryError("execution_error", "Native routing returned an object outside its exact authorized inventory.", subjects)
        state.members.update(related | {raw["subject_id"]})
        points = raw.get("path_points_m", [])
        if any(len(point) != 3 or not all(math.isfinite(v) for v in point) for point in points):
            raise QueryError("execution_error", "Native routing returned invalid physical coordinates.")
        metadata = dict(raw.get("metadata", {})); metadata["source_sha256"] = engine.bundle.assets[0].sha256
        metadata["outside_scope_recorded_door_boundaries"] = len(outside_doors)
        metadata["outside_scope_recorded_room_boundaries"] = len(outside_rooms)
        metadata["requested_target_basis"] = operation.target_basis
        metadata["certified_emergency_route"] = False
        from .ingest import _id
        for step in raw.get("source_step_ids", []):
            if not any(not engine.anchors[a].selector.property_path for a in step_anchors[step]):
                asset = engine.bundle.assets[0].id
                anchor_id = _id("anchor", asset + str(step) + json.dumps(()))
                anchor = m.EvidenceAnchor(id=anchor_id, asset_id=asset,
                    selector=m.NativeSelector(kind="step_id", value=str(step)))
                engine.anchors[anchor_id] = anchor; engine.bundle.anchors.append(anchor)
                step_anchors[step].add(anchor_id)
        proof = inventory_proof | {a for step in raw.get("source_step_ids", []) for a in step_anchors[step]}
        record = {key: raw[key] for key in ("subject_id", "target_id", "method", "frame", "unit", "tolerance_m", "quality", "status",
            "path_points_m", "room_ids", "door_ids", "stair_ids", "source_step_ids")}
        record.update(anchor_ids=sorted(proof), metadata=metadata)
        state.route_records.append(record)
        def unavailable(explanation):
            return m.UnavailableValue(kind="unavailable", reason="unknown", explanation=explanation)
        def quantity(value, basis):
            return m.QuantityValue(kind="quantity", magnitude=decimal_string(value), unit_id="unit:m", quantity_kind="length",
                basis=basis, unit_resolution="derived", quality="estimated") if isinstance(value, (int, float)) and math.isfinite(value) else unavailable("This physical route quantity is not established by the source and modeled path.")
        if metadata.get("unresolved_inventory") or metadata.get("unreachable_origin_room_ids") or operation.clearance_m:
            state.coverage_complete = False
        state.unresolved.update(metadata.get("unreachable_origin_room_ids", []))
        valid = len(points) >= 2
        if valid:
            length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
            if not math.isclose(length, metadata.get("distance_m", math.inf), abs_tol=.001, rel_tol=1e-8):
                raise QueryError("execution_error", "Exported physical route points and the route distance disagree.")
            distance = quantity(length, "potential modeled walking path through source room/opening/stair geometry")
        else:
            distance = unavailable(metadata.get("reason", "No modeled path to an authorized recorded exterior opening is established."))
            state.unresolved.add(raw["subject_id"]); state.coverage_complete = False
        row = {"subject": m.ReferencesValue(kind="references", entity_ids=[raw["subject_id"]]),
            "target": m.ReferencesValue(kind="references", entity_ids=[raw["target_id"]] if raw["target_id"] else []),
            "rooms": m.ReferencesValue(kind="references", entity_ids=raw["room_ids"]),
            "doors": m.ReferencesValue(kind="references", entity_ids=raw["door_ids"]),
            "stairs": m.ReferencesValue(kind="references", entity_ids=raw["stair_ids"]),
            "distance": distance, "nominal_door_width": quantity(metadata.get("nominal_door_width_m"), "minimum authored OverallWidth among doors on this route; nominal, not clear width"),
            "geometric_opening_width": quantity(metadata.get("geometric_opening_width_m"), "minimum modeled gross opening contact width among doors on this route; not hardware clear width"),
            "sampled_clearance": unavailable("Actual clear egress width is not established: door hardware, opening state and fixed/movable obstructions require separate evidence."),
            "status": m.TextValue(kind="text", value=m.LocalizedText(text="Potential modeled route; emergency certification and clear width unresolved" if valid else "Modeled route unresolved"))}
        rows.append(row)
        cells.append({key: _Support(set(value.entity_ids) if isinstance(value, m.ReferencesValue) else related | {raw["subject_id"]}, set(), proof,
            "route_query", "unavailable" if isinstance(value, m.UnavailableValue) else "verified", metadata) for key, value in row.items()})
    state.value = m.TableValue(kind="table", columns=[m.TableColumn(key=key, label=m.LocalizedText(text=label)) for key, label in [
        ("subject", "Origin room"), ("target", "Recorded outdoor opening"), ("rooms", "Ordered rooms"), ("doors", "Traversed doors"),
        ("stairs", "Native stair flights"), ("distance", "Modeled walking distance"), ("nominal_door_width", "Nominal door bottleneck"),
        ("geometric_opening_width", "Modeled gross opening bottleneck"), ("sampled_clearance", "Physical clear width"), ("status", "Qualification")]], rows=rows)
    state.shape, state.cells = "table", cells
    state.issues.append(m.Issue(code="incomplete_coverage" if outside_doors or outside_rooms else "missing_information", message=m.LocalizedText(text=
        "The result is a potential modeled route to recorded outdoor openings. Emergency-exit certification, door operability and physical clear width remain unresolved; missing source connectors or objects outside the captured view may limit reachability."), entity_ids=subjects))
    state.notes.append("Walking distances follow exported physical paths inside modeled room footprints, explicit opening bridges and native stair pitch lines. Portal sampling and any farthest-point sampling are estimates. Distances to centroids or straight door separations are never substituted for walking paths.")

"""Bounded native IFC measurements with explicit geometric meaning and evidence.

The executor chooses authorized source records; a subprocess tessellates them.
Measurements are estimates of modeled geometry, never a substitute for a net/
gross stored quantity, a traversable escape route, or physical completeness.
"""
from __future__ import annotations

import math
import hashlib
import json
from time import monotonic

from contracts import models as m
from .units import convert, decimal_string


METRIC_KIND = {
    "area": "area", "union_area": "area", "enclosed_area": "area", "perimeter": "length", "length": "length",
    "volume": "volume", "height": "length", "base_elevation": "length",
    "distance": "length", "horizontal_distance": "length",
}
SI_UNIT = {"area": "unit:m2", "volume": "unit:m3", "length": "unit:m"}
BASES = {
    "area": {"surface", "footprint", "net_opaque_face"}, "union_area": {"footprint"},
    "volume": {"solid"}, "length": {"axis"}, "perimeter": {"footprint"},
    "height": {"world_z_extent", "validated_vertical_spans"}, "base_elevation": {"world_min_z"},
    "horizontal_distance": {"minimum_projected_separation"}, "distance": {"surface_centroids"},
    "enclosed_area": {"bounded_regions"},
}


def execute_measurement(engine, state, operation, scope_members):
    from .engine import QueryError, _Support

    if state.shape != "entities":
        raise QueryError("unsupported_operation", "Native measurements require a selected source-object set.")
    if operation.metric not in METRIC_KIND or operation.basis not in BASES.get(operation.metric, set()):
        raise QueryError("unsupported_operation", "Choose a supported geometric metric and its explicit measurement basis.")
    if state.unresolved or state.candidate_members or not state.coverage_complete:
        raise QueryError("incomplete_coverage", "An unresolved or candidate selection cannot establish complete measured quantities.", state.unresolved | state.candidate_members)
    provider = getattr(engine, "geometry", None)
    if provider is None:
        raise QueryError("missing_information", "The retained original IFC source is required for native geometry measurement.")
    subjects = sorted(state.members)
    references = sorted(set(operation.reference_entity_ids))
    if not subjects:
        raise QueryError("missing_information", "No source objects match this measurement in the selected scope.")
    pair = operation.metric in {"distance", "horizontal_distance"}
    enclosed = operation.metric == "enclosed_area"
    if not enclosed and pair != bool(references):
        raise QueryError("needs_clarification", "Distance measurements need explicit reference source objects; other metrics do not.")
    if not set(subjects + references) <= scope_members:
        raise QueryError("incomplete_coverage", "Measurement references must belong to the captured source/view scope.", subjects + references)
    if operation.calibration_ids:
        raise QueryError("unsupported_operation", "Native IFC mesh measurements use explicit source length units, not drawing calibration.")

    def source_step(identifier):
        values = {int(engine.anchors[a].selector.value) for a in engine.entity_anchors[identifier]
                  if engine.anchors[a].selector.kind == "step_id"
                  and not engine.anchors[a].selector.property_path
                  and engine.anchors[a].selector.value.isdigit()}
        if len(values) != 1:
            raise QueryError("missing_information", "Measurement cannot resolve a unique native IFC record.", [identifier])
        return next(iter(values))

    groups, group_entities, group_anchors, incomplete = {}, {}, {}, set()
    def add_group(identifier):
        pending, members, proof = [identifier], set(), set()
        while pending:
            current = pending.pop()
            if current in members:
                continue
            if current not in scope_members:
                incomplete.add(identifier)
                continue
            members.add(current)
            if len(members) > 2000:
                raise QueryError("unsupported_operation", "One measurement group exceeds the bounded 2000-object work budget.", [identifier])
            proof.update(engine.entity_anchors[current])
            for predicate in ("contains", "aggregates"):
                for child in engine.graphs[predicate, "outgoing"].get(current, set()):
                    if child in scope_members:
                        proof.update(engine.edge_anchors[predicate, "outgoing", current, child])
                    pending.append(child)
        # The root stays first: a represented occurrence is measured directly;
        # spatial parents can instead use their authorized represented children.
        groups[identifier] = [source_step(identifier), *sorted(source_step(child) for child in members - {identifier})]
        group_entities[identifier] = members
        group_anchors[identifier] = proof

    for identifier in dict.fromkeys(subjects + references):
        add_group(identifier)

    union = operation.metric == "union_area"
    query_subjects = {identifier: groups[identifier] for identifier in subjects}
    if union:
        # One union result, not per-object areas that would double-count overlap.
        query_subjects = {subjects[0]: list(dict.fromkeys(step for identifier in subjects for step in groups[identifier]))}
        if incomplete.intersection(subjects):
            incomplete.add(subjects[0])
    batch = None
    # The known room-area cohort asks hundreds of room/floor questions of the
    # same two models. One small authorized batch can warm numeric records, not
    # retain meshes or repeatedly reopen the same IFC for every room.
    if operation.metric == "area" and operation.basis == "footprint" and not references and all(
            engine.entities[identifier].kind == "space" for identifier in subjects):
        spaces = sorted(identifier for identifier in scope_members if engine.entities[identifier].kind == "space")
        if len(subjects) < len(spaces) <= 512:
            prefetch = dict(query_subjects)
            native_inputs = {step for values in prefetch.values() for step in values}
            for identifier in spaces:
                if identifier in prefetch:
                    continue
                try:
                    add_group(identifier)
                except QueryError:
                    continue  # Opportunistic work cannot invalidate the request.
                following = native_inputs | set(groups[identifier])
                if len(following) <= getattr(provider, "max_items", 2000):
                    prefetch[identifier] = groups[identifier]
                    native_inputs = following
            signature = hashlib.sha256(json.dumps([engine.bundle.assets[0].sha256,
                [(identifier, steps, identifier in incomplete) for identifier, steps in sorted(prefetch.items())]],
                separators=(",", ":")).encode()).hexdigest()
            attempts = getattr(engine, "_space_measurement_prefetch", {})
            attempted, complete = attempts.get(signature, (-math.inf, False))
            if len(prefetch) > len(query_subjects) and not complete and monotonic() - attempted >= 30:
                observed = provider.measure_many(operation.metric, prefetch, basis=operation.basis,
                    tolerance_m=0.001, incomplete_groups=incomplete,
                    explicit_root_steps=[source_step(identifier) for identifier in prefetch], timeout_seconds=3)
                selected = [record for record in observed.get("records", []) if record.get("subject_id") in query_subjects]
                attempts[signature] = monotonic(), bool(observed.get("records")) and all(
                    record.get("status") == "verified" for record in observed["records"])
                while len(attempts) > 64:
                    attempts.pop(next(iter(attempts)))
                engine._space_measurement_prefetch = attempts
                if len(selected) == len(query_subjects) and all(record.get("status") == "verified" for record in selected):
                    batch = {**observed, "records": selected}
    if batch is None:
        batch = provider.measure_many(operation.metric, query_subjects,
            {identifier: groups[identifier] for identifier in references}, basis=operation.basis,
            tolerance_m=0.001, incomplete_groups=incomplete,
            explicit_root_steps=[source_step(identifier) for identifier in subjects + references])
    records = batch.get("records", [])
    if not records:
        raise QueryError("missing_information", "The required source geometry could not be measured within the bounded execution budget.", subjects + references)
    expected = ({(subject, tuple(references)) for subject in query_subjects} if enclosed else
        {(subject, (reference,) if reference else ()) for subject in query_subjects for reference in (references or [None])})
    observed = {(record.get("subject_id"), tuple(record.get("reference_entity_ids", []))) for record in records}
    if observed != expected or len(records) != len(expected):
        raise QueryError("execution_error", "Geometry did not return the complete requested measurement batch.", subjects + references)

    rows, cells, measured, unresolved = [], [], set(), set()
    state.quality = "estimated"
    kind = METRIC_KIND[operation.metric]
    source_unit = engine.units[SI_UNIT[kind]]
    output_unit = engine.units[operation.output_unit_id]
    notes = {
        "height": "Height is the world-frame vertical extent of the represented source mesh; it is not a stored floor-to-floor or clear room height.",
        "base_elevation": "Base elevation is the represented mesh's minimum world Z, not a certified ground or finished-floor elevation.",
        "area": "Surface area sums tessellated modeled faces; footprint area is the union of their XY projections. Neither silently substitutes for a stored net/gross floor area or paint-finish scope.",
        "union_area": "Union area combines the selected modeled mesh footprints in world XY and removes projected overlap; it is not a stored net/gross floor area.",
        "enclosed_area": "Area is the union of bounded projected regions whose boundary has positive-length support from the selected subject, after jointly adding the explicitly selected source closure objects. Closure-only courtyards and tolerance-scale slivers are excluded; no artificial gap closing or convex hull is used.",
        "volume": "Solid volume integrates an oriented closed source mesh; open, invalid and ambiguous overlapping compound shells remain unresolved. Bounding-box volume is never used.",
        "length": "Length follows explicit straight native Axis/FootPrint curves in physical units; mesh edges and bounding-box widths are not substituted.",
        "perimeter": "Perimeter follows the boundary of the union of modeled XY mesh projections, including modeled holes.",
        "horizontal_distance": "Distance is minimum separation between the modeled XY mesh projections. This straight geometric separation is not a walkable or emergency escape route.",
        "distance": "Distance is the 3D separation between area-weighted modeled surface centroids. It is not minimum surface clearance or an emergency escape route.",
    }
    note = notes[operation.metric]
    if operation.basis == "validated_vertical_spans":
        note = "Standing height requires complete vertical side patches, paired top/bottom columns and consistent full-mesh height. Terrain-following world-Z extent, majority spans and missing cap geometry are never substituted."
    elif operation.basis == "net_opaque_face":
        note = "Area measures one verified modeled opaque face normal to a horizontal native layer axis, retaining modeled holes and edge-opening cuts. It is not both sides, gross facade area, glazing area or proof that the selected objects exhaust the exterior facade."
    state.notes.append(note)
    measurement_start = len(state.measurement_records)
    for raw in records:
        subject, related = raw["subject_id"], raw.get("reference_entity_ids", [])
        involved = subjects if union else [subject, *related]
        members = set().union(*(group_entities[identifier] for identifier in involved))
        proof = set().union(*(group_anchors[identifier] for identifier in involved))
        allowed_steps = {step for identifier in involved for step in groups[identifier]}
        if not set(raw.get("source_step_ids", [])) <= allowed_steps:
            raise QueryError("execution_error", "Geometry returned source inputs outside the authorized measurement group.", involved)
        metadata = dict(raw.get("metadata", {}))
        from .ingest import _id
        # Geometry-native dependencies (placements, units and declared layer
        # usage) are source inputs of the authorized occurrence, not a wider
        # occurrence selection. Keep their inspectable immutable-source anchors.
        for step in metadata.get("native_input_step_ids", []):
            if not isinstance(step, int) or isinstance(step, bool) or step <= 0:
                raise QueryError("execution_error", "Geometry returned an invalid native source dependency.", involved)
            asset = engine.bundle.assets[0].id
            identifier = _id("anchor", asset + str(step) + json.dumps(()))
            if identifier not in engine.anchors:
                anchor = m.EvidenceAnchor(id=identifier, asset_id=asset,
                    selector=m.NativeSelector(kind="step_id", value=str(step)))
                engine.anchors[identifier] = anchor
                engine.bundle.anchors.append(anchor)
            proof.add(identifier)
        if union:
            metadata["combined_entity_ids"] = subjects
        metadata["source_sha256"] = engine.bundle.assets[0].sha256
        metadata["basis"] = operation.basis
        # Numeric/native inputs remain available without exposing source paths,
        # serialized meshes or unbounded external tool output.
        record = {key: raw[key] for key in ("metric", "subject_id", "reference_entity_ids", "method", "frame", "unit", "tolerance_m", "source_step_ids", "representation_step_ids", "status", "value")}
        record["metadata"] = metadata
        valid = raw["status"] == "verified" and isinstance(raw.get("value"), (int, float)) and math.isfinite(raw["value"])
        if not valid:
            record.update(status="unavailable", value=None)
        state.measurement_records.append(record)
        state.anchors.update(proof)
        support = _Support(members, set(), proof, "measure", "verified" if valid else "unavailable", metadata)
        support.source_record = ("measurement", len(state.measurement_records) - 1, measurement_start, len(records))
        if valid:
            number = convert(decimal_string(raw["value"]), source_unit, output_unit)
            value = m.QuantityValue(kind="quantity", magnitude=decimal_string(number), unit_id=output_unit.id,
                quantity_kind=kind, basis=operation.basis, unit_resolution="derived", quality="estimated")
            measured.update(involved)
        else:
            value = m.UnavailableValue(kind="unavailable", reason="unknown",
                explanation="The required modeled geometry is unavailable or cannot be measured unambiguously within this method's work bounds.")
            unresolved.update(involved)
        rows.append({"subject": m.ReferencesValue(kind="references", entity_ids=subjects if union else [subject]),
                     "reference": m.ReferencesValue(kind="references", entity_ids=related), "value": value})
        cells.append({"subject": _Support(set(subjects) if union else {subject}, set(), proof, "measure"),
                      "reference": _Support(set(related), set(), proof, "measure"), "value": support})
    if unresolved:
        state.unresolved.update(unresolved)
        state.coverage_complete = False
        issue_code = "incomplete_coverage" if any(record.get("metadata", {}).get("issue_code") == "incomplete_coverage" for record in records) else "missing_information"
        state.issues.append(m.Issue(code=issue_code, message=m.LocalizedText(text=
            "Some modeled source geometry could not be measured; known estimates remain separate from unresolved inputs."), entity_ids=sorted(unresolved)))
        if not measured:
            raise QueryError(issue_code, "None of the requested source geometry could be measured with the specified basis. Aggregate geometry may require showing its descendants or choosing Entire IFC model." if issue_code == "incomplete_coverage" else "None of the requested source geometry could be measured with the specified basis.", unresolved)
    state.members = set(subjects + references)
    if union:
        state.value, state.shape, state.cells = rows[0]["value"], "scalar", []
    else:
        state.value = m.TableValue(kind="table", columns=[
            m.TableColumn(key=key, label=m.LocalizedText(text=label)) for key, label in
            [("subject", "Source object"), ("reference", "Reference object"), ("value", "Measured " + operation.metric.replace("_", " "))]], rows=rows)
        state.shape, state.cells = "table", cells

"""Bounded spatial queries with native proof, qualified geometry and partial reports."""
from __future__ import annotations

from collections import defaultdict
from time import monotonic

from contracts import models as m
from .catalog import POLICIES


def execute_spatial(engine, state, operation, scope_members):
    from .engine import QueryError, _Support

    if state.shape != "entities":
        raise QueryError("unsupported_operation", "Spatial queries require source objects.")
    if operation.relation == "exterior_doors":
        if operation.method == "geometry":
            raise QueryError("unsupported_operation", "Geometry does not establish exterior-door classification or outdoor access.")
        from .exterior import execute_exterior
        return execute_exterior(engine, state, operation, scope_members)
    origins = sorted(state.members)
    if not origins:
        raise QueryError("missing_information", "No source objects match this spatial question in the selected scope.")
    if len(origins) > 10000:
        raise QueryError("unsupported_operation", "Spatial queries are limited to 10000 starting objects.")
    relation, method = operation.relation, operation.method
    provider = getattr(engine, "geometry", None)
    boundary_records = defaultdict(list)
    for boundary in engine.bundle.space_boundaries:
        boundary_records[boundary.space_id].append(boundary)
    comparisons = 0
    geometry_deadline = monotonic() + 20
    geometry_checks = defaultdict(list)

    def edges(subject, predicate, direction="outgoing"):
        return engine.graphs[predicate, direction].get(subject, set())

    def anchors(subject, predicate, related, direction="outgoing"):
        return engine.edge_anchors[predicate, direction, subject, related]

    def require_visible(objects):
        if not set(objects) <= scope_members:
            raise QueryError("incomplete_coverage",
                "This spatial relationship needs source objects outside the captured view. "
                "Show those objects or select Entire IFC model and ask again.", origins)

    def native_step(entity_id):
        values = {int(engine.anchors[a].selector.value) for a in engine.entity_anchors[entity_id]
                  if engine.anchors[a].selector.kind == "step_id"
                  and not engine.anchors[a].selector.property_path
                  and engine.anchors[a].selector.value.isdigit()}
        return next(iter(values)) if len(values) == 1 else None

    def is_door(entity):
        return "concept:door" in engine.entities[entity].concept_ids

    def doorway(element):
        if is_door(element):
            return {element}, set()
        doors = {item for item in edges(element, "filled_by") if is_door(item)}
        return doors, set().union(*(anchors(element, "filled_by", door) for door in doors))

    def evaluate_patches(origin, related, element=None):
        """No_match is accepted only when every relevant native patch was checked."""
        nonlocal comparisons

        def finish(result, proof):
            geometry_checks[origin].append({"related_id": related, "element_id": element,
                "result": result, "anchor_ids": sorted(proof)})
            return result, proof

        if method == "native" or provider is None:
            return finish({"status": "unknown", "reason": "Boundary geometry is unavailable."}, set())
        left = [b for b in boundary_records[origin]
                if element is None or b.element_id == element and b.physical_or_virtual == "PHYSICAL"]
        right = [b for b in boundary_records[related]
                 if element is None or b.element_id == element and b.physical_or_virtual == "PHYSICAL"]
        if element is None:
            pairs = [(a, b) for a in left for b in right
                     if a.corresponding_boundary_id == b.id or b.corresponding_boundary_id == a.id]
        else:
            pairs = [(a, b) for a in left for b in right]
        results, proof = [], set()
        incomplete = False
        for a, b in pairs:
            proof.update(a.provenance.anchor_ids)
            proof.update(b.provenance.anchor_ids)
            if a.connection_geometry_step_id is None or b.connection_geometry_step_id is None:
                incomplete = True
                continue
            if comparisons >= 256 or monotonic() >= geometry_deadline:
                return finish({"status": "unknown", "reason": "The bounded boundary comparison budget was reached."}, proof)
            comparisons += 1
            result = provider.compare_boundaries(a.native_step_id, b.native_step_id, operation.tolerance_m,
                                                 timeout_seconds=max(0., geometry_deadline - monotonic()))
            results.append(result)
            if result["status"] == "match":
                return finish(result, proof)
        if results and not incomplete and all(item["status"] == "no_match" for item in results):
            return finish({**results[0], "comparisons": results}, proof)
        return finish(next((item for item in results if item["status"] == "unknown"),
                     {"status": "unknown", "reason": "Usable native boundary patches are missing."}), proof)

    rows, cells, pair_indices = [], [], {}
    failures, evaluated = [], set()

    def row(subject, related, via, basis, proof, *, evidence_kind="verified", metadata=None):
        pair = subject, related
        if pair in pair_indices:
            index = pair_indices[pair]
            if cells[index]["related"].evidence_kind == "verified" or evidence_kind == "candidate":
                return
        else:
            if len(rows) >= 10000:
                raise QueryError("unsupported_operation", "Spatial queries are limited to 10000 relationship rows.")
            index = len(rows)
            pair_indices[pair] = index
        selected = {subject, related, *via}
        require_visible(selected)
        proof = set(proof) | {a for item in selected for a in engine.entities[item].provenance.anchor_ids}
        support = _Support(selected, set(), proof, "spatial_query", evidence_kind=evidence_kind, metadata=metadata or {})
        value = {"subject": m.ReferencesValue(kind="references", entity_ids=[subject]),
                 "related": m.ReferencesValue(kind="references", entity_ids=[related]),
                 "via": m.ReferencesValue(kind="references", entity_ids=sorted(via)),
                 "basis": m.TextValue(kind="text", value=m.LocalizedText(text=basis))}
        if index == len(rows):
            rows.append(value)
            cells.append({key: support for key in value})
        else:
            rows[index] = value
            cells[index] = {key: support for key in value}
        state.anchors.update(proof)

    def record(origin, status, *, related_ids=(), proof=(), used_method="native_topology.v2", metadata=None):
        state.spatial_records.append({"relation": relation, "subject_id": origin, "status": status,
            "method": used_method, "related_ids": sorted(related_ids), "anchor_ids": sorted(proof),
            "tolerance_m": operation.tolerance_m if used_method != "native_topology.v2" else None,
            "metadata": metadata or {}})

    def unavailable(origin, error):
        if error.code not in {"missing_information", "conflicting_evidence"}:
            raise error
        failures.append(error)
        state.unresolved.add(origin)
        state.coverage_complete = False
        issue = m.Issue(code=error.code, message=m.LocalizedText(text=str(error)), entity_ids=error.entity_ids or [origin])
        state.issues.append(issue)
        used_geometry = any(check["result"].get("method") for check in geometry_checks[origin])
        record(origin, "unavailable", proof={a for check in geometry_checks[origin] for a in check["anchor_ids"]},
               metadata={"issue_code": error.code, "reason": str(error), "geometry_checks": geometry_checks[origin]},
               used_method="native_topology+geometry.v1" if used_geometry else "native_topology.v2")

    def geometry_container(origin):
        if operation.container_kind != "space" or provider is None:
            raise QueryError("missing_information",
                f"The source does not establish a containing {operation.container_kind} for this object.", [origin])
        rooms = {item.id for item in engine.entities.values() if item.kind == "space"}
        # Unexamined hidden spaces could contain the object too. Keep the exact
        # captured view authoritative instead of using them as hidden inputs.
        require_visible(rooms)
        step = native_step(origin)
        by_step = {native_step(room): room for room in rooms if native_step(room) is not None}
        if step is None or len(by_step) != len(rooms) or not by_step:
            raise QueryError("missing_information", "Room geometry cannot be resolved to unique source objects.", [origin])
        if monotonic() >= geometry_deadline:
            raise QueryError("missing_information", "The bounded room geometry evaluation budget was reached.", [origin])
        result = provider.locate_in_spaces(step, sorted(by_step), operation.tolerance_m,
                                           timeout_seconds=max(0., geometry_deadline - monotonic()))
        matches = {by_step[item] for item in result.get("matched_step_ids", []) if item in by_step}
        proof = {a for item in rooms | {origin} for a in engine.entity_anchors[item]}
        check = {"related_ids": sorted(matches), "result": result, "anchor_ids": sorted(proof)}
        geometry_checks[origin].append(check)
        if result.get("unresolved_step_ids") or result["status"] == "unknown":
            raise QueryError("missing_information", "Usable room geometry is incomplete; a containing room cannot be established unambiguously.", [origin])
        if len(matches) > 1:
            raise QueryError("conflicting_evidence", "The object is geometrically contained in multiple modeled rooms.", [origin, *sorted(matches)])
        if not matches:
            raise QueryError("missing_information", "The inspected room solids do not establish a containing room for this object.", [origin])
        related = next(iter(matches))
        native, pending, visited = set(), {origin}, set()
        for _ in range(33):
            if not pending:
                break
            following = set()
            for item in pending - visited:
                visited.add(item)
                if engine.entities[item].kind == "space":
                    native.add(item)
                    continue
                parents = edges(item, "contains", "incoming") | edges(item, "aggregates", "incoming")
                require_visible(parents)
                for predicate in ("contains", "aggregates"):
                    for parent in edges(item, predicate, "incoming"):
                        proof.update(anchors(item, predicate, parent, "incoming"))
                following.update(parents - visited)
            pending = following
        if pending or len(visited) > 10000:
            raise QueryError("unsupported_operation", "Native containment validation exceeds the bounded query size.", [origin])
        check["anchor_ids"] = sorted(proof)
        if native and native != matches:
            raise QueryError("conflicting_evidence", "Native room containment disagrees with the inspected room solids.", [origin, *sorted(native | matches)])
        row(origin, related, [], "Geometry-verified space containment", proof, metadata=result)
        record(origin, "verified", related_ids=matches, proof=proof, used_method=result["method"], metadata=result)

    if relation == "containers":
        for origin in origins:
            try:
                if method == "geometry":
                    if operation.container_kind != "space":
                        raise QueryError("unsupported_operation", "Geometry containment currently supports modeled room spaces only.", [origin])
                    geometry_container(origin)
                    evaluated.add(origin)
                    continue
                frontier, visited, found, proof = {origin}, set(), set(), set()
                for _ in range(33):
                    if not frontier:
                        break
                    if len(visited) > 10000:
                        raise QueryError("unsupported_operation", "Spatial ancestry exceeds the bounded query size.")
                    next_frontier = set()
                    for item in sorted(frontier - visited):
                        visited.add(item)
                        if engine.entities[item].kind == operation.container_kind:
                            found.add(item)
                            continue
                        for predicate in ("contains", "aggregates"):
                            parents = edges(item, predicate, "incoming")
                            require_visible(parents)
                            next_frontier.update(parents - visited)
                            for parent in parents:
                                proof.update(anchors(item, predicate, parent, "incoming"))
                    frontier = next_frontier
                if frontier:
                    raise QueryError("unsupported_operation", "Spatial ancestry is limited to 32 relation levels.", [origin])
                if not found:
                    if method == "auto":
                        geometry_container(origin)
                        evaluated.add(origin)
                        continue
                    raise QueryError("missing_information",
                        f"The source does not establish a containing {operation.container_kind} for this object.", [origin])
                if len(found) > 1:
                    raise QueryError("conflicting_evidence", f"The source assigns multiple containing {operation.container_kind} objects.", [origin, *sorted(found)])
                row(origin, next(iter(found)), [], f"Native {operation.container_kind} containment", proof)
                record(origin, "verified", related_ids=found, proof=proof)
                evaluated.add(origin)
            except QueryError as error:
                unavailable(origin, error)
        state.notes.append("Locations follow native IFC containment and aggregation relationships, with qualified room-solid geometry fallback when native room containment is absent. Room names are not used to guess a location.")
    else:
        if method == "geometry" and relation != "boundary_neighbors":
            raise QueryError("unsupported_operation", "Geometry proximity does not establish door connections or outdoor access.")
        if any(engine.entities[origin].kind != "space" for origin in origins):
            raise QueryError("needs_clarification", "Room topology queries must start from modeled IfcSpace objects.", origins)
        access = set()
        for origin in origins:
            try:
                boundaries = edges(origin, "bounded_by")
                paired = edges(origin, "corresponding_boundary") | edges(origin, "corresponding_boundary", "incoming")
                if not boundaries and (not paired or relation != "boundary_neighbors"):
                    raise QueryError("missing_information",
                        "This room has no usable native space boundaries. Missing topology cannot establish zero neighbors or outdoor access.", [origin])
                require_visible(boundaries | (paired if relation == "boundary_neighbors" else set()))
                proof = set()
                for element in boundaries:
                    proof.update(anchors(origin, "bounded_by", element))
                    proof.update(engine.entities[element].provenance.anchor_ids)
                state.anchors.update(proof)
                # Retain unusable/virtual records in diagnostics without treating
                # them as positive physical doorway evidence.
                records = boundary_records[origin]
                proof.update(a for boundary in records for a in boundary.provenance.anchor_ids)
                state.anchors.update(proof)
                uncertain_records = [b for b in records if b.physical_or_virtual not in {"PHYSICAL", "VIRTUAL"}
                    or b.physical_or_virtual == "PHYSICAL" and (b.element_id is None
                        or relation == "outdoor_access" and b.internal_or_external in {None, "NOTDEFINED"})]

                def incomplete_boundary_inventory():
                    if uncertain_records:
                        state.unresolved.add(origin)
                        state.coverage_complete = False
                        state.issues.append(m.Issue(code="incomplete_coverage", message=m.LocalizedText(text=
                            "Some native boundaries have undefined required classifications or no related element; complete spatial coverage cannot be established."),
                            entity_ids=[origin], anchor_ids=sorted({a for b in uncertain_records for a in b.provenance.anchor_ids})))

                record_metadata = {"boundary_ids": sorted(b.id for b in records),
                    "physical_boundaries": sum(b.physical_or_virtual == "PHYSICAL" for b in records),
                    "virtual_boundaries": sum(b.physical_or_virtual == "VIRTUAL" for b in records),
                    "undefined_boundaries": sum(b.physical_or_virtual not in {"PHYSICAL", "VIRTUAL"} for b in records),
                    "semantics": "relationships recorded in this model; absence does not establish physical absence"}
                if relation == "outdoor_access":
                    for element in sorted(edges(origin, "external_boundary")):
                        doors, door_proof = doorway(element)
                        if not doors:
                            continue
                        require_visible({origin, element, *doors})
                        access.add(origin)
                        proof.update(door_proof | anchors(origin, "external_boundary", element))
                        proof.update(a for item in {element, *doors} for a in engine.entities[item].provenance.anchor_ids)
                    state.anchors.update(proof)
                    if origin not in access:
                        incomplete_boundary_inventory()
                    record(origin, "verified" if origin in access else "unavailable" if uncertain_records else "recorded_empty", related_ids=[origin] if origin in access else [], proof=proof, metadata=record_metadata)
                    evaluated.add(origin)
                    continue
                seen = set()
                if relation == "boundary_neighbors":
                    for related in sorted(paired - {origin}):
                        geometric, geometric_proof = evaluate_patches(origin, related)
                        if geometric["status"] == "no_match":
                            raise QueryError("conflicting_evidence", "Native corresponding boundaries disagree with their geometric patches.", [origin, related])
                        if method == "geometry" and geometric["status"] != "match":
                            raise QueryError("missing_information", "The requested boundary geometry check is unavailable.", [origin, related])
                        pair_proof = anchors(origin, "corresponding_boundary", related) | anchors(origin, "corresponding_boundary", related, "incoming") | geometric_proof
                        row(origin, related, [], "Geometry-verified overlapping boundary patches" if method == "geometry" else "Native corresponding space boundaries", pair_proof, metadata={"geometry_check": geometric})
                        seen.add(related)
                ordered = sorted(boundaries, key=lambda item: (not bool(doorway(item)[0]), item))
                for element in ordered:
                    doors, door_proof = doorway(element)
                    if relation == "door_connections" and not doors:
                        continue
                    peers = {element}
                    if doors:
                        peers.update(doors)
                        peers.update(opening for door in doors for opening in edges(door, "filled_by", "incoming"))
                    neighbor_paths = {}
                    for peer in sorted(peers):
                        for related in edges(peer, "bounded_by", "incoming") - {origin}:
                            peer_proof = anchors(peer, "bounded_by", related, "incoming")
                            for door in doors:
                                if peer in edges(door, "filled_by", "incoming"):
                                    peer_proof = peer_proof | anchors(peer, "filled_by", door)
                            neighbor_paths.setdefault(related, (peer, peer_proof))
                    if relation == "door_connections" and len(neighbor_paths) > 1:
                        raise QueryError("conflicting_evidence", "A modeled doorway bounds more than two spaces; direct connectivity is ambiguous.", [origin, *sorted(neighbor_paths)])
                    for related in sorted(set(neighbor_paths) - seen):
                        peer, peer_proof = neighbor_paths[related]
                        require_visible({origin, related, element, peer, *doors})
                        pair_proof = anchors(origin, "bounded_by", element) | peer_proof | door_proof
                        metadata, evidence_kind = {}, "verified"
                        if doors and method != "geometry":
                            basis = "Shared physical door boundary"
                        else:
                            geometric, geometric_proof = evaluate_patches(origin, related, element)
                            pair_proof |= geometric_proof
                            state.anchors.update(pair_proof)
                            if geometric["status"] == "no_match":
                                continue
                            if method == "geometry" and geometric["status"] != "match":
                                raise QueryError("missing_information", "The requested boundary geometry check is unavailable.", [origin, related])
                            metadata = geometric
                            evidence_kind = "verified" if geometric["status"] == "match" else "candidate"
                            basis = "Geometry-verified overlapping boundary patches" if evidence_kind == "verified" else "Shared physical boundary element; candidate adjacency"
                        row(origin, related, {element, peer, *doors}, basis, pair_proof, evidence_kind=evidence_kind, metadata=metadata)
                        if evidence_kind == "verified":
                            seen.add(related)
                origin_rows = [(value, support["related"]) for value, support in zip(rows, cells)
                               if value["subject"].entity_ids == [origin]]
                candidate = any(support.evidence_kind == "candidate" for _, support in origin_rows)
                related_ids = {item for value, _ in origin_rows for item in value["related"].entity_ids}
                incomplete_boundary_inventory()
                record_metadata["relationships"] = [{"related_id": value["related"].entity_ids[0],
                    "evidence_kind": support.evidence_kind, "geometry": support.metadata}
                    for value, support in origin_rows]
                record_metadata["geometry_checks"] = geometry_checks[origin]
                proof.update(a for check in geometry_checks[origin] for a in check["anchor_ids"])
                used_geometry = any(check["result"].get("method") for check in geometry_checks[origin])
                record(origin, "unavailable" if uncertain_records else "candidate" if candidate else "verified" if related_ids else "recorded_empty",
                       related_ids=related_ids, proof=proof, metadata=record_metadata,
                       used_method="native_topology+boundary_patch_overlap.v1" if used_geometry else "native_topology.v2")
                evaluated.add(origin)
            except QueryError as error:
                # Discard rows from a conflicting origin rather than retaining a
                # seemingly verified subset of its inconsistent relationships.
                keep = [i for i, value in enumerate(rows) if value["subject"].entity_ids != [origin]]
                rows, cells = [rows[i] for i in keep], [cells[i] for i in keep]
                pair_indices = {(value["subject"].entity_ids[0], value["related"].entity_ids[0]): i for i, value in enumerate(rows)}
                unavailable(origin, error)
        if relation == "outdoor_access":
            if not evaluated:
                raise failures[0]
            state.members = access
            state.value = m.ReferencesValue(kind="references", entity_ids=sorted(access))
            state.policy = POLICIES["all_matches"]
            state.concepts = {"concept:space"}
            state.notes.append("Outdoor access identifies rooms with a recorded native PHYSICAL EXTERNAL boundary to a door or door-filled opening. An empty result means no such door boundary was recorded among the inspected rooms, not that outdoor access is physically absent. This is not a verified fire exit or compliant escape route.")
            return
        state.notes.append("Room neighbors follow corresponding native space boundaries, geometrically checked boundary patches, or qualified shared-element candidates." if relation == "boundary_neighbors" else
            "Room connections require a shared physical door boundary or a shared opening filled by a door. Shared walls alone do not establish a connection. This is modeled direct connectivity, not a navigable route.")
    if not evaluated:
        raise failures[0]
    candidates = {value["related"].entity_ids[0] for value, support in zip(rows, cells)
                  if support["related"].evidence_kind == "candidate"}
    if candidates:
        state.candidate_members.update(candidates)
        state.coverage_complete = False
        state.issues.append(m.Issue(code="incomplete_coverage", message=m.LocalizedText(text=
            "Some returned rooms only share a physical boundary element. A long wall can bound separated rooms; these are adjacency candidates, not verified geometric neighbors."), entity_ids=sorted(candidates)))
    state.value = m.TableValue(kind="table", columns=[m.TableColumn(key=key, label=m.LocalizedText(text=label))
        for key, label in [("subject", "Object / room"), ("related", "Related location / room"), ("via", "Source boundary / doorway"), ("basis", "Relationship evidence")]], rows=rows)
    state.cells, state.shape = cells, "table"
    state.members = {item for support in cells for item in support["related"].members}
    state.policy = POLICIES["all_matches"]
    state.concepts = {concept for item in state.members for concept in engine.entities[item].concept_ids}

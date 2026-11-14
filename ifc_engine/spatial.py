"""Source topology queries. No meshes, distance guesses or route assumptions."""
from __future__ import annotations

from contracts import models as m
from .catalog import POLICIES


def execute_spatial(engine, state, operation, scope_members):
    # Imported at execution time to keep the engine's state/evidence types local.
    from .engine import QueryError, _Support

    if state.shape != "entities":
        raise QueryError("unsupported_operation", "Native spatial queries require source objects.")
    origins = sorted(state.members)
    if not origins:
        raise QueryError("missing_information", "No source objects match this spatial question in the selected scope.")
    if len(origins) > 10000:
        raise QueryError("unsupported_operation", "Native spatial queries are limited to 10000 starting objects.")

    def edges(subject, predicate, direction="outgoing"):
        return engine.graphs[predicate, direction].get(subject, set())

    def anchors(subject, predicate, related, direction="outgoing"):
        return engine.edge_anchors[predicate, direction, subject, related]

    def require_visible(members):
        if not set(members) <= scope_members:
            raise QueryError("incomplete_coverage",
                "This spatial relationship needs source objects outside the captured view. "
                "Show those objects or select Entire IFC model and ask again.", origins)

    def is_door(entity):
        return "concept:door" in engine.entities[entity].concept_ids

    def doorway(element):
        """An explicit door boundary or opening filled by a door, never a host wall."""
        if is_door(element):
            return {element}, set()
        doors = {item for item in edges(element, "filled_by") if is_door(item)}
        return doors, set().union(*(anchors(element, "filled_by", door) for door in doors))

    rows, cells, members = [], [], set()

    def row(subject, related, via, basis, proof):
        if len(rows) >= 10000:
            raise QueryError("unsupported_operation", "Native spatial queries are limited to 10000 relationship rows.")
        selected = {subject, related, *via}
        require_visible(selected)
        proof = set(proof) | {a for item in selected for a in engine.entities[item].provenance.anchor_ids}
        support = _Support(selected, set(), proof, "spatial_query")
        rows.append({"subject": m.ReferencesValue(kind="references", entity_ids=[subject]),
            "related": m.ReferencesValue(kind="references", entity_ids=[related]),
            "via": m.ReferencesValue(kind="references", entity_ids=sorted(via)),
            "basis": m.TextValue(kind="text", value=m.LocalizedText(text=basis))})
        cells.append({key: support for key in rows[-1]})
        members.update(selected)
        state.anchors.update(proof)

    if operation.relation == "containers":
        for origin in origins:
            # Preserve every relation in the ancestry proof, including assembly
            # containment; a floor name is never inferred from an object label.
            frontier, visited, found, proof = {origin}, set(), set(), set()
            for _ in range(33):
                if not frontier:
                    break
                if visited and len(visited) > 10000:
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
                raise QueryError("missing_information",
                    f"The source does not establish a containing {operation.container_kind} for this object.", [origin])
            if len(found) > 1:
                raise QueryError("conflicting_evidence", f"The source assigns multiple containing {operation.container_kind} objects.", [origin, *sorted(found)])
            row(origin, next(iter(found)), [], f"Native {operation.container_kind} containment", proof)
        state.notes.append("Locations follow native IFC containment and aggregation relationships; object placements and room names are not used to guess a location.")
    else:
        if any(engine.entities[origin].kind != "space" for origin in origins):
            raise QueryError("needs_clarification", "Room topology queries must start from modeled IfcSpace objects.", origins)
        fallback = False
        access = set()
        for origin in origins:
            boundaries = edges(origin, "bounded_by")
            paired = edges(origin, "corresponding_boundary") | edges(origin, "corresponding_boundary", "incoming")
            if not boundaries and (not paired or operation.relation != "boundary_neighbors"):
                raise QueryError("missing_information",
                    "This room has no usable native space boundaries. Missing topology cannot establish zero neighbors or outdoor access.", [origin])
            require_visible(boundaries | (paired if operation.relation == "boundary_neighbors" else set()))
            # Retain inspected negative candidates as well as positive paths so
            # that an empty modeled result can be checked against the source.
            for element in boundaries:
                state.anchors.update(anchors(origin, "bounded_by", element))
                state.anchors.update(engine.entities[element].provenance.anchor_ids)
            if operation.relation == "outdoor_access":
                for element in sorted(edges(origin, "external_boundary")):
                    doors, proof = doorway(element)
                    if not doors:
                        continue
                    require_visible({origin, element, *doors})
                    access.add(origin)
                    state.anchors.update(proof | anchors(origin, "external_boundary", element))
                    state.anchors.update(a for item in {element, *doors} for a in engine.entities[item].provenance.anchor_ids)
                continue
            seen = set()
            if operation.relation == "boundary_neighbors":
                for related in sorted(paired - {origin}):
                    row(origin, related, [], "Native corresponding space boundaries",
                        anchors(origin, "corresponding_boundary", related) | anchors(origin, "corresponding_boundary", related, "incoming"))
                    seen.add(related)
            # Prefer an explicit doorway over a shared wall when several
            # boundaries describe the same pair of rooms.
            ordered_boundaries = sorted(boundaries, key=lambda item: (not bool(doorway(item)[0]), item))
            for element in ordered_boundaries:
                doors, door_proof = doorway(element)
                if operation.relation == "door_connections" and not doors:
                    continue
                # IFC exporters may attach one room boundary to the door and
                # the other to its filled opening. Normalize only that explicit
                # doorway identity, without traversing a shared host wall.
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
                neighbors = set(neighbor_paths)
                # A shared door attributed to >2 spaces cannot identify a single
                # direct connection unambiguously (e.g. a reused modeled door).
                if operation.relation == "door_connections" and len(neighbors) > 1:
                    raise QueryError("conflicting_evidence", "A modeled doorway bounds more than two spaces; direct connectivity is ambiguous.", [origin, *sorted(neighbors)])
                for related in sorted(neighbors - seen):
                    peer, peer_proof = neighbor_paths[related]
                    proof = anchors(origin, "bounded_by", element) | peer_proof | door_proof
                    basis = "Shared physical door boundary" if doors else "Shared physical boundary element; candidate adjacency"
                    row(origin, related, {element, peer, *doors}, basis, proof)
                    seen.add(related)
                    if not doors:
                        fallback = True
        if operation.relation == "outdoor_access":
            state.members = access
            state.value = m.ReferencesValue(kind="references", entity_ids=sorted(access))
            state.policy = POLICIES["all_matches"]
            state.concepts = {"concept:space"}
            state.notes.append("Outdoor access identifies rooms with a recorded native PHYSICAL EXTERNAL boundary to a door or door-filled opening. An empty result means no such door boundary was recorded among the inspected rooms, not that outdoor access is physically absent. This is not a verified fire exit or compliant escape route.")
            return
        if fallback:
            state.issues.append(m.Issue(code="incomplete_coverage", message=m.LocalizedText(text=
                "Some returned rooms only share a physical boundary element. A long wall can bound separated rooms; these are adjacency candidates, not verified geometric neighbors.")))
        state.notes.append("Room neighbors follow corresponding native space boundaries or shared physical boundary elements; shared-element candidates are explicitly qualified." if operation.relation == "boundary_neighbors" else
            "Room connections require a shared physical door boundary or a shared opening filled by a door. Shared walls alone do not establish a connection. This is modeled direct connectivity, not a navigable route.")
    state.value = m.TableValue(kind="table", columns=[m.TableColumn(key=key, label=m.LocalizedText(text=label))
        for key, label in [("subject", "Object / room"), ("related", "Related location / room"), ("via", "Source boundary / doorway"), ("basis", "Relationship evidence")]], rows=rows)
    state.cells, state.members, state.shape = cells, members, "table"
    state.policy = POLICIES["all_matches"]
    state.concepts = {concept for item in members for concept in engine.entities[item].concept_ids}

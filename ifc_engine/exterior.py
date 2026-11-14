"""Source-backed exterior-door membership, distinct from outdoor room counts."""
from __future__ import annotations

from contracts import models as m
from .catalog import property_key


EXTERNAL_KEY = property_key("Pset_DoorCommon", "IsExternal")


def execute_exterior(engine, state, operation, scope_members):
    from .engine import QueryError

    origins = sorted(state.members)
    if len(origins) > 10000:
        raise QueryError("unsupported_operation", "Exterior-door queries are limited to 10000 door occurrences.")
    if any("concept:door" not in engine.entities[door].concept_ids or
           engine.entities[door].kind == "type" for door in origins):
        raise QueryError("needs_clarification", "Exterior-door queries must start from selected IfcDoor occurrences, not rooms or door types.", origins)

    basis = operation.exterior_basis
    state.concepts = {"concept:door"}
    state.policy = m.CountPolicy(grain="occurrence", hierarchy="all_matches",
        rule_key="ifc.exterior-door." + basis + ".v1")
    state.coverage_explanation = {
        "combined": "Door occurrences evaluated using recorded IsExternal classification and explicit physical external door/filled-opening boundaries. A positive boundary can resolve an absent classification; absence of a boundary alone is not an interior classification.",
        "classification": "Door occurrences evaluated only against recorded Pset_DoorCommon.IsExternal boolean classifications, including source occurrence/type precedence.",
        "boundary": "Complete enumeration of recorded PHYSICAL EXTERNAL boundary paths to selected doors or openings explicitly filled by them. This counts supported source relationships, not the physical completeness of outdoor access.",
    }[basis] + " Physical-building completeness, traversability and fire-exit compliance are unverified."
    state.notes.append(state.coverage_explanation)

    def edges(subject, predicate, direction="outgoing"):
        return engine.graphs[predicate, direction].get(subject, set())

    def proof(subject, predicate, related, direction="outgoing"):
        return engine.edge_anchors[predicate, direction, subject, related]

    def require_visible(members):
        if not set(members) <= scope_members:
            raise QueryError("incomplete_coverage", "Exterior-door boundary evidence needs source rooms or openings outside the captured view. Show those objects or select Entire IFC model and ask again.",
                sorted(set(members) & scope_members))

    # A source with no boundaries cannot support a boundary-only negative result.
    if origins and basis == "boundary" and not engine.graphs["bounded_by", "outgoing"]:
        raise QueryError("missing_information", "The source contains no usable physical space boundaries; missing topology cannot establish zero exterior doors.", origins)

    included, excluded, unknown, conflicting = set(), set(), set(), set()
    unknown_facts, conflict_facts = set(), set()
    inspected_anchors = set()
    inspected_paths = 0
    if basis != "boundary" and EXTERNAL_KEY in engine.properties:
        state.properties.add(EXTERNAL_KEY)

    for door in origins:
        anchor_ids = set(engine.entities[door].provenance.anchor_ids) | engine.entity_anchors[door]
        flag = None
        facts = engine.facts[door, EXTERNAL_KEY] if basis != "boundary" else []
        values = {fact.value.value for fact in facts if fact.status == "present" and isinstance(fact.value, m.BooleanValue)}
        # The extractor can mark an entire property path ambiguous after mixed
        # source datatypes. That is unknown classification, not proof of two
        # contradictory booleans on this particular occurrence.
        flag_conflict = len(values) > 1
        if len(values) == 1 and all(fact.status == "present" and isinstance(fact.value, m.BooleanValue) for fact in facts):
            flag = next(iter(values))
            state.facts.update(fact.id for fact in facts)
        for fact in facts:
            anchor_ids.update(fact.provenance.anchor_ids)
        if flag_conflict:
            conflicting.add(door)
            conflict_facts.update(fact.id for fact in facts)

        paths = []
        if basis != "classification":
            # Both direct door boundaries and opening->door boundaries normalize
            # to this same door occurrence; repeated boundaries never add doors.
            elements = {door, *edges(door, "filled_by", "incoming")}
            for element in sorted(elements):
                for room in sorted(edges(element, "external_boundary", "incoming")):
                    inspected_paths += 1
                    if inspected_paths > 20000:
                        raise QueryError("unsupported_operation", "Exterior-door inspection is limited to 20000 native boundary paths.")
                    require_visible({door, element, room})
                    path_proof = set(proof(element, "external_boundary", room, "incoming"))
                    if element != door:
                        path_proof.update(proof(element, "filled_by", door))
                    path_proof.update(a for item in {element, room} for a in engine.entities[item].provenance.anchor_ids)
                    anchor_ids.update(path_proof)
                    paths.append((room, element))
                # Retain in-scope physical-boundary inspections even for doors
                # without an external path. They do not turn unknown into false.
                for room in sorted(edges(element, "bounded_by", "incoming")):
                    inspected_paths += 1
                    if inspected_paths > 20000:
                        raise QueryError("unsupported_operation", "Exterior-door inspection is limited to 20000 native boundary paths.")
                    if {door, element, room} <= scope_members:
                        anchor_ids.update(proof(element, "bounded_by", room, "incoming"))
        inspected_anchors.update(anchor_ids)

        if basis == "boundary":
            (included if paths else excluded).add(door)
        elif flag_conflict or flag is False and paths:
            conflicting.add(door)
            conflict_facts.update(fact.id for fact in facts)
        elif flag is True or paths:
            included.add(door)
        elif flag is False:
            excluded.add(door)
        else:
            unknown.add(door)
            unknown_facts.update(fact.id for fact in facts)

    state.anchors.update(inspected_anchors)
    if conflicting:
        raise QueryError("conflicting_evidence", "Exterior-door membership has conflicting source classifications or an IsExternal=false classification with a recorded physical external door boundary. No complete total can be established.",
            sorted(conflicting), sorted(conflict_facts), anchor_ids=sorted(inspected_anchors))
    if unknown:
        message = f"Exterior-door classification is unknown for {len(unknown)} selected door occurrence(s). Missing/null/non-boolean IsExternal values and absent positive boundary paths do not establish interior doors or zero outdoor access."
        if not included:
            raise QueryError("missing_information", message, sorted(unknown), sorted(unknown_facts), anchor_ids=sorted(inspected_anchors))
        state.issues.append(m.Issue(code="incomplete_coverage", message=m.LocalizedText(text=message),
            entity_ids=sorted(unknown), fact_ids=sorted(unknown_facts), anchor_ids=sorted(inspected_anchors)))
        state.quality, state.completeness = "lower_bound", "partial"
        state.coverage_explanation += " Unresolved door occurrences remain; the returned membership/count is a lower bound."
        state.notes.append("The answer is a lower bound over the resolved doors; inspect unresolved door occurrences separately.")
    state.members, state.excluded = included, excluded
    state.value = m.ReferencesValue(kind="references", entity_ids=sorted(included))

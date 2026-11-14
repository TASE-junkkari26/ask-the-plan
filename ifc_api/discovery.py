"""Bounded, source-only metadata discovery shared by IFC planner providers.

Search results are suggestions, never the inventory for a count. Execution still
evaluates a concrete source predicate across the authorized scope.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts import models as m
from ifc_engine.catalog import attribute_key, property_key

DISCOVERY_VERSION = "ifc-discovery-v1"
MAX_RESULT_CHARS = 24000
TEXT_FIELDS = {attribute_key(name) for name in (
    "Name", "LongName", "Description", "Tag", "ObjectType", "PredefinedType",
)}


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    action: Literal["search", "inspect", "facets", "properties"]
    query: str = Field(default="", max_length=200)
    entity_ids: list[str] = Field(default_factory=list, max_length=12)
    property_keys: list[str] = Field(default_factory=list, max_length=8)
    concept_ids: list[str] = Field(default_factory=list, max_length=8)
    limit: int = Field(default=12, ge=1, le=20, strict=True)

    @model_validator(mode="after")
    def relevant_arguments(self):
        if self.action == "inspect" and not self.entity_ids:
            raise ValueError("inspection needs source entity IDs")
        if self.action == "facets" and not self.property_keys:
            raise ValueError("facets needs source property keys")
        if self.action in {"search", "properties"} and not self.query.strip() and not self.concept_ids:
            raise ValueError("search needs text or source concepts")
        if self.action != "inspect" and self.entity_ids:
            raise ValueError("entity IDs are only accepted by inspect")
        return self


def _text(value):
    if isinstance(value, m.TextValue):
        return value.value.text
    if isinstance(value, m.BooleanValue):
        return "true" if value.value else "false"
    if isinstance(value, m.CountValue):
        return str(value.value)
    if isinstance(value, m.QuantityValue):
        return value.magnitude + " " + (value.unit_id or "")
    return ""


def scope_fingerprint(source_hash: str, members: set[str]) -> str:
    encoded = json.dumps([source_hash, sorted(members)], separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class SourceDiscovery:
    """One immutable label index per extracted model; facts stay in the engine."""

    def __init__(self, engine, elements):
        self.engine, self.elements = engine, elements
        self.text = {}
        for identifier, element in elements.items():
            values = [element.name, element.ifc_class, element.guid or "",
                      f"#{element.step_id}" if element.step_id else ""]
            for key in TEXT_FIELDS:
                values.extend(_text(fact.value)[:1000] for fact in engine.facts.get((identifier, key), [])
                              if fact.status == "present")
            self.text[identifier] = " ".join(values).casefold()

    def _members(self, members, concepts):
        unknown = set(concepts) - self.engine.concept_ids
        if unknown:
            raise ValueError("Use only concepts from the source catalog.")
        if not concepts:
            return set(members)
        # Use the same concept inheritance as native source selection.
        descendants, frontier = set(concepts), set(concepts)
        while frontier:
            next_level = set().union(*(self.engine.concept_children.get(c, set()) for c in frontier))
            frontier = next_level - descendants
            descendants.update(frontier)
        return {identifier for identifier in members
                if descendants.intersection(self.engine.entities[identifier].concept_ids)}

    def _record(self, identifier, keys, members):
        record = self.elements[identifier].model_dump()
        facts = []
        selected_keys = keys or sorted(TEXT_FIELDS)
        for key in selected_keys:
            for fact in self.engine.facts.get((identifier, key), [])[:3]:
                facts.append({"property_key": key, "status": fact.status,
                    "value": fact.value.model_dump(mode="json") if fact.value else None,
                    "fact_id": fact.id, "anchor_ids": fact.provenance.anchor_ids})
        record["facts"] = facts
        relations, omitted = [], 0
        for predicate in self.engine.capabilities.relation_predicates:
            for direction in ("outgoing", "incoming"):
                related = self.engine.graphs[predicate, direction].get(identifier, set())
                in_scope = sorted(related & members)
                omitted += len(related - members)
                if in_scope:
                    selected = in_scope[:12]
                    relations.append({"predicate": predicate, "direction": direction,
                        "entity_ids": selected, "total": len(in_scope),
                        "truncated": len(in_scope) > len(selected),
                        "anchor_ids": sorted({anchor for other in selected for anchor in
                            self.engine.edge_anchors[predicate, direction, identifier, other]})[:24]})
        record["relations"] = relations
        record["relationships_outside_scope"] = omitted
        return record

    def execute(self, request: DiscoveryRequest, members: set[str]) -> dict:
        keys = request.property_keys
        if set(keys) - set(self.engine.properties):
            raise ValueError("Use only property keys from the source catalog.")
        eligible = self._members(members, request.concept_ids)
        if request.action == "inspect":
            if set(request.entity_ids) - eligible:
                raise ValueError("An inspection ID is unknown or outside the captured scope.")
            rows = [self._record(identifier, keys, members) for identifier in request.entity_ids]
            result = {"action": "inspect", "records": rows, "truncated": False}
        elif request.action == "properties":
            tokens = re.findall(r"\w+", request.query.casefold())
            matches = [definition for definition in self.engine.bundle.properties if any(
                token in (definition.key + " " + " ".join(v.text for v in definition.labels)).casefold()
                for token in tokens)]
            result = {"action": "properties", "records": [
                {"key": definition.key, "kind": definition.value_kind,
                 "labels": [label.text for label in definition.labels]} for definition in matches[:request.limit]],
                "matching_total": len(matches), "truncated": len(matches) > request.limit}
        elif request.action == "search":
            stop = {"how", "many", "the", "are", "there", "which", "show", "what", "this", "model", "and", "of", "in"}
            aliases = {"doors": "door", "windows": "window", "rooms": "space",
                       "ovet": "door", "ikkunat": "window"}
            tokens = [aliases.get(token, token) for token in re.findall(r"\w+", request.query.casefold()) if token not in stop]
            # Partial names remain suggestions. Do not translate literal IDs or
            # turn a ranked sample into exhaustive answer membership.
            scored = []
            for identifier in eligible:
                haystack = self.text[identifier]
                score = sum(token in haystack for token in tokens)
                if not tokens or score:
                    scored.append((score, identifier))
            scored.sort(key=lambda pair: (-pair[0], pair[1]))
            rows = [self._record(identifier, keys, members)
                    for _, identifier in scored[:request.limit]]
            result = {"action": "search", "records": rows, "matching_total": len(scored),
                "truncated": len(scored) > len(rows), "inventory_completeness": "candidate_search",
                "rule": "Ranked suggestions only. Count/sum an exhaustive native predicate, never this sample."}
        else:
            rows = []
            for key in keys:
                values, statuses, missing, nulls, omitted = Counter(), Counter(), 0, 0, 0
                for identifier in sorted(eligible):
                    facts = self.engine.facts.get((identifier, key), [])
                    statuses.update(sorted({fact.status for fact in facts} or {"not_in_source"}))
                    present = [fact for fact in facts if fact.status == "present" and fact.value is not None]
                    if not present:
                        nulls += any(fact.status == "explicit_null" for fact in facts)
                        missing += not any(fact.status == "explicit_null" for fact in facts)
                    for fact in present:
                        # A facet counts source facts, not distinct physical objects.
                        encoded = json.dumps(fact.value.model_dump(mode="json"), sort_keys=True)
                        if len(encoded) > 2000 or len(values) >= 512 and encoded not in values:
                            omitted += 1
                        else:
                            values[encoded] += 1
                sample = values.most_common(request.limit)
                rows.append({"property_key": key, "eligible_entities": len(eligible),
                    "missing_entities": missing, "explicit_null_entities": nulls,
                    "source_status_entity_counts": dict(statuses),
                    "distinct_values_observed": len(values), "omitted_source_facts": omitted, "values": [
                        {"value": json.loads(value), "source_fact_count": count} for value, count in sample],
                    "truncated": bool(omitted) or len(values) > len(sample)})
            result = {"action": "facets", "facets": rows, "truncated": any(row["truncated"] for row in rows)}
        # Trim whole records/facets rather than emitting broken JSON or clipping
        # source identifiers into invented matches.
        field = "records" if "records" in result else "facets"
        while len(json.dumps(result, ensure_ascii=False)) > MAX_RESULT_CHARS and result[field]:
            result[field].pop()
            result["truncated"] = True
        return result

    def initial(self, question, members):
        search = self.execute(DiscoveryRequest(action="search", query=question, limit=8), members)
        facets = []
        for key, concept in ((property_key("Pset_DoorCommon", "IsExternal"), "concept:door"),
                             (attribute_key("LongName"), "concept:space")):
            if key in self.engine.properties and concept in self.engine.concept_ids:
                result = self.execute(DiscoveryRequest(action="facets", property_keys=[key],
                    concept_ids=[concept], limit=8), members)
                facets.append({"concept_id": concept, **result})
        return {"version": DISCOVERY_VERSION, "search": search, "facets": facets,
            "allowed_actions": ["search", "inspect", "facets", "properties"],
            "note": "Discovery observes only this captured scope; samples never establish inventory completeness."}

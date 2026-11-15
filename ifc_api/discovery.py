"""Bounded, source-only metadata discovery shared by IFC planner providers.

Search results are suggestions, never the inventory for a count. Execution still
evaluates a concrete source predicate across the authorized scope.

Search/property pages use offset/next_offset; cursors advance by the actual
retained records after the response budget is applied. Facets have independent
per-property cursors: follow each using a single-property request. An unpageable
page is an explicit incomplete result, never an empty source inventory.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts import models as m
from ifc_engine.catalog import attribute_key, property_key

DISCOVERY_VERSION = "ifc-discovery-v4-bounded-pagination"
MAX_RESULT_CHARS = 24000
MAX_QUERY_CHARS = 200
MAX_OFFSET = 1000
MAX_FACET_VALUES = MAX_OFFSET + 21
TEXT_FIELDS = {attribute_key(name) for name in (
    "Name", "LongName", "Description", "Tag", "ObjectType", "PredefinedType",
)}
TEXT_FIELDS.update(property_key("SourceContext", name) for name in ("TypeId", "TypeName", "StoreyId", "StoreyName", "BuildingId", "BuildingName"))
TEXT_FIELDS.add(property_key("SourceMaterial", "Names"))


def _normalized(value):
    return unicodedata.normalize("NFKC", value).casefold()


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    action: Literal["search", "inspect", "facets", "properties"]
    query: str = Field(default="", max_length=MAX_QUERY_CHARS)
    entity_ids: list[str] = Field(default_factory=list, max_length=12)
    property_keys: list[str] = Field(default_factory=list, max_length=8)
    concept_ids: list[str] = Field(default_factory=list, max_length=8)
    limit: int = Field(default=12, ge=1, le=20, strict=True)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET, strict=True)

    @model_validator(mode="after")
    def relevant_arguments(self):
        if self.action == "inspect" and not self.entity_ids:
            raise ValueError("inspection needs source entity IDs")
        if self.action == "inspect" and self.offset:
            raise ValueError("inspection does not support an offset")
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


def _page_info(page, offset, returned, observed_total, *, complete=True, blocked_reason="response_budget"):
    end = offset + returned
    remaining = end < observed_total or not complete
    blocked = remaining and (not returned or end > MAX_OFFSET or end >= observed_total and not complete)
    page.update(offset=offset, returned_count=returned, next_offset=end if remaining and not blocked else None,
                truncated=remaining, unpageable=blocked,
                unpageable_reason=("offset_limit" if end > MAX_OFFSET else "value_inventory_limit" if end >= observed_total and not complete
                                   else blocked_reason) if blocked else None,
                blocked_offset=end if blocked else None)


def _bounded_records(result, request):
    while True:
        _page_info(result, request.offset, len(result["records"]), result["matching_total"], blocked_reason="oversized_record")
        if len(json.dumps(result, ensure_ascii=False)) <= MAX_RESULT_CHARS:
            return result
        if result["records"]:
            result["records"].pop()
        else:
            return {"action": request.action, "records": [], "matching_total": result["matching_total"],
                    "offset": request.offset, "returned_count": 0, "next_offset": None, "truncated": True,
                    "unpageable": True, "unpageable_reason": "oversized_metadata", "blocked_offset": request.offset}


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
            self.text[identifier] = _normalized(" ".join(values))

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
        self.engine.ensure_fields([identifier], set(selected_keys) & self.engine.properties.keys())
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
            tokens = re.findall(r"\w+", _normalized(request.query))
            deferred = self.engine.hydrator is not None
            eligible_keys = set(self.engine.properties) if deferred else {
                key for (identifier, key), facts in self.engine.facts.items() if identifier in eligible and facts}
            matches = [definition for definition in self.engine.bundle.properties if definition.key in eligible_keys and (not tokens or any(
                token in _normalized(definition.key + " " + " ".join(v.text for v in definition.labels))
                for token in tokens))]
            matches.sort(key=lambda definition: definition.key)
            result = {"action": "properties", "records": [
                {"key": definition.key, "kind": definition.value_kind,
                 "labels": [label.text for label in definition.labels]} for definition in matches[request.offset:request.offset + request.limit]],
                "matching_total": len(matches), "truncated": len(matches) > request.limit}
            if deferred:
                result["availability"] = "Source vocabulary only; per-object values are checked on demand, not asserted by catalog presence."
        elif request.action == "search":
            stop = {"how", "many", "the", "are", "there", "which", "show", "what", "this", "model", "and", "of", "in"}
            aliases = {"doors": "door", "windows": "window", "rooms": "space",
                       "ovet": "door", "ikkunat": "window"}
            tokens = [aliases.get(token, token) for token in re.findall(r"\w+", _normalized(request.query)) if token not in stop]
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
                    for _, identifier in scored[request.offset:request.offset + request.limit]]
            result = {"action": "search", "records": rows, "matching_total": len(scored),
                "truncated": len(scored) > len(rows), "inventory_completeness": "candidate_search",
                "rule": "Ranked suggestions only. Count/sum an exhaustive native predicate, never this sample."}
        else:
            rows = []
            oversized_offsets = {}
            self.engine.ensure_fields(eligible, keys)
            for key in keys:
                values, statuses, missing, nulls, omitted = {}, Counter(), 0, 0, 0
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
                        identity = hashlib.sha256(encoded.encode()).hexdigest()
                        if identity not in values and len(values) >= MAX_FACET_VALUES:
                            omitted += 1
                        else:
                            value = values.setdefault(identity, {"count": 0,
                                "encoded": encoded if len(encoded) <= MAX_RESULT_CHARS else None})
                            value["count"] += 1
                ordered = sorted(values.items(), key=lambda item: (-item[1]["count"], item[0]))
                oversized_offsets[key] = {index for index, (_, value) in enumerate(ordered) if value["encoded"] is None}
                sample = []
                for _, value in ordered[request.offset:request.offset + request.limit]:
                    if value["encoded"] is None:
                        break  # This pending value cannot be clipped or skipped.
                    sample.append({"value": json.loads(value["encoded"]), "source_fact_count": value["count"]})
                rows.append({"property_key": key, "eligible_entities": len(eligible),
                    "missing_entities": missing, "explicit_null_entities": nulls,
                    "source_status_entity_counts": dict(statuses),
                    "distinct_values_observed": len(values), "matching_total": len(values) if not omitted else None,
                    "value_inventory_complete": not bool(omitted), "omitted_source_facts": omitted,
                    "oversized_source_values": sum(value["encoded"] is None for value in values.values()),
                    "values": sample,
                    "ordering": "source_fact_count_desc_then_canonical_value_sha256"})
            result = {"action": "facets", "facets": rows,
                "pagination": "Offsets apply independently to each property. Follow its next_offset using a single-property request; no shared facet cursor."}
            while True:
                for row in rows:
                    _page_info(row, request.offset, len(row["values"]), row["distinct_values_observed"],
                               complete=row["value_inventory_complete"],
                               blocked_reason="oversized_value" if request.offset in oversized_offsets[row["property_key"]] else "response_budget")
                result["truncated"] = any(row["truncated"] for row in rows)
                result["unpageable"] = any(row["unpageable"] for row in rows)
                result["next_offsets"] = {row["property_key"]: row["next_offset"] for row in rows}
                if len(json.dumps(result, ensure_ascii=False)) <= MAX_RESULT_CHARS:
                    return result
                available = [(len(row["values"]), index) for index, row in enumerate(rows) if row["values"]]
                if not available:
                    return {"action": "facets", "facets": [], "truncated": True, "unpageable": True,
                            "unpageable_reason": "oversized_metadata", "blocked_offset": request.offset,
                            "requested_property_count": len(keys),
                            "matching_totals_by_property_index": [row["matching_total"] for row in rows]}
                _, index = max(available)
                rows[index]["values"].pop()
        if request.action in {"search", "properties"}:
            return _bounded_records(result, request)
        # Trim whole records/facets rather than emitting broken JSON or clipping
        # source identifiers into invented matches.
        field = "records" if "records" in result else "facets"
        while len(json.dumps(result, ensure_ascii=False)) > MAX_RESULT_CHARS and result[field]:
            result[field].pop()
            result["truncated"] = True
        if result["truncated"] and not result[field]:
            result.update(unpageable=True, unpageable_reason="oversized_record")
        return result

    def initial(self, question, members):
        # The complete question remains in the planner payload. Its initial
        # candidate search obeys the narrower tool limit without splitting a
        # literal token or rejecting an otherwise valid long question.
        query, truncated = question, len(question) > MAX_QUERY_CHARS
        if truncated:
            prefix = question[:MAX_QUERY_CHARS + 1]
            query = prefix[:MAX_QUERY_CHARS] if prefix[-1].isspace() else prefix.rsplit(None, 1)[0]
            if len(query) > MAX_QUERY_CHARS:
                query = ""
        if query.strip():
            search = self.execute(DiscoveryRequest(action="search", query=query, limit=8), members)
        else:
            search = {"action": "search", "records": [], "matching_total": None, "truncated": True,
                "offset": 0, "returned_count": 0, "next_offset": None, "unpageable": True,
                "unpageable_reason": "initial_query_token_limit", "blocked_offset": 0,
                "note": "No initial search ran: the first literal query token exceeds the bounded tool limit. Use source catalog references or a shorter discovery query."}
        search["query_truncated"] = truncated
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

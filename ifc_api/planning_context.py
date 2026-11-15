"""Compact entity references at the model boundary without changing public IDs.

Only schema-known operational reference slots are translated. Native source
identifiers, text, property keys, program-step IDs and arbitrary record field
names remain literal. Raw discovery/proof records are never modified.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

VERSION = "ifc-planning-context-v1"
OUTSIDE_SCOPE = "e#outside-scope"
UNAVAILABLE = "e#unavailable"


def _get(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


class PlanningContext:
    def __init__(self, engine, elements, allowed_ids):
        self.engine = engine
        self.allowed = frozenset(allowed_ids)
        if not self.allowed <= engine.entities.keys():
            raise ValueError("Planning scope contains unknown source entities.")
        self._elements = elements
        by_step = defaultdict(list)
        # Native STEP addresses must be unique in the entire source, including
        # records outside this scope. Never invent aliases for ambiguous/missing
        # locators or use a global alias cache across revisions/questions.
        for identifier, element in elements.items():
            step = _get(element, "step_id")
            if identifier in engine.entities and type(step) is int and step > 0:
                by_step[step].append(identifier)
        self._encode = {identifiers[0]: f"e#{step}" for step, identifiers in by_step.items()
                        if len(identifiers) == 1 and identifiers[0] in self.allowed
                        and f"e#{step}" not in engine.entities}
        self._decode = {alias: identifier for identifier, alias in self._encode.items()}
        self._exposed = set()

    @property
    def alias_count(self):
        return len(self._encode)

    def _encode_id(self, identifier):
        if identifier in self.allowed:
            alias = self._encode.get(identifier, identifier)
            if alias in self._decode:
                self._exposed.add(alias)
            return alias
        if identifier in self.engine.entities:
            return OUTSIDE_SCOPE
        # Preserve an unknown model-authored alias so a failed inspection can
        # explain/repair it. It can never acquire a hidden canonical identity.
        if isinstance(identifier, str) and identifier.startswith("e#"):
            return identifier
        return UNAVAILABLE

    def _decode_id(self, identifier):
        # In particular, do not resolve arbitrary native STEP numbers against
        # the full model. Unknown and out-of-scope aliases remain invalid IDs.
        return self._decode.get(identifier, identifier) if identifier in self._exposed else identifier

    def _value(self, value, translate):
        if not isinstance(value, dict):
            return
        kind = value.get("kind")
        if kind == "references" and isinstance(value.get("entity_ids"), list):
            value["entity_ids"] = [translate(identifier) for identifier in value["entity_ids"]]
        elif kind == "list" and isinstance(value.get("items"), list):
            for item in value["items"]:
                self._value(item, translate)
        elif kind == "record" and isinstance(value.get("fields"), dict):
            for item in value["fields"].values():
                self._value(item, translate)
        elif kind == "table" and isinstance(value.get("rows"), list):
            for row in value["rows"]:
                if isinstance(row, dict):
                    for item in row.values():
                        self._value(item, translate)
        # TextValue.value, native quantities/units and every other scalar stay
        # verbatim even if their strings look exactly like canonical IDs/aliases.

    def _proof(self, record, owner=None):
        """Replace known metadata proof tokens with compact native record hints."""
        anchors = list(record.pop("anchor_ids", []))
        fact_id = record.pop("fact_id", None)
        if fact_id and owner in self.allowed and record.get("property_key"):
            for fact in self.engine.facts.get((owner, record["property_key"]), ()):
                if fact.id == fact_id:
                    anchors.extend(fact.provenance.anchor_ids)
        hints, seen = [], set()
        for identifier in anchors:
            anchor = self.engine.anchors.get(identifier)
            selector = _get(anchor, "selector")
            if selector is None:
                continue
            kind, value = _get(selector, "kind"), _get(selector, "value")
            if kind == "step_id" and isinstance(value, str) and value.isdecimal():
                hint = {"step": int(value)}
            elif kind == "ifc_guid":
                hint = {"guid": value}
            elif kind == "file_metadata":
                hint = {"header": value}
            else:
                hint = {"kind": kind, "value": value}
            marker = tuple(hint.items())
            if marker not in seen:
                seen.add(marker)
                hints.append(hint)
        if not hints and owner in self.allowed:
            step = _get(self._elements.get(owner), "step_id")
            if type(step) is int and step > 0:
                hints.append({"step": step})
        if anchors or fact_id:
            record["source_hints"] = hints

    def _metadata(self, record, owner):
        self._proof(record, owner)
        if "value" in record:
            self._value(record["value"], self._encode_id)

    def _record(self, record):
        owner = record["entity_id"]
        record["entity_id"] = self._encode_id(owner)
        for fact in record.get("facts", []):
            self._metadata(fact, owner)
        for field in record.get("matched_fields", []):
            self._metadata(field, owner)
        for relation in record.get("relations", []):
            if isinstance(relation.get("entity_ids"), list):
                relation["entity_ids"] = [self._encode_id(identifier) for identifier in relation["entity_ids"]]
            self._proof(relation, owner)

    def _request(self, request, translate):
        if isinstance(request, dict) and isinstance(request.get("entity_ids"), list):
            request["entity_ids"] = [translate(identifier) for identifier in request["entity_ids"]]

    def _discovery(self, result):
        if not isinstance(result, dict):
            return
        if result.get("action") in {"inspect", "search"} and isinstance(result.get("records"), list):
            result["records"] = [record for record in result["records"]
                                 if isinstance(record, dict) and record.get("entity_id") in self.allowed]
            for record in result["records"]:
                self._record(record)
        elif result.get("action") == "facets":
            for facet in result.get("facets", []):
                for item in facet.get("values", []):
                    self._value(item.get("value"), self._encode_id)

    def encode_payload(self, rawcanonicalpayload):
        """Return an encoded copy; source facts and local proof IDs stay intact."""
        payload = deepcopy(rawcanonicalpayload)
        catalog = payload.get("catalog")
        if isinstance(catalog, dict):
            if isinstance(catalog.get("entities"), list):
                catalog["entities"] = [row for row in catalog["entities"]
                                       if isinstance(row, dict) and row.get("id") in self.allowed]
                for row in catalog["entities"]:
                    row["id"] = self._encode_id(row["id"])
            if isinstance(catalog.get("matching_elements"), list):
                catalog["matching_elements"] = [row for row in catalog["matching_elements"]
                                               if isinstance(row, dict) and row.get("entity_id") in self.allowed]
                for row in catalog["matching_elements"]:
                    self._record(row)
            if isinstance(catalog.get("source_metadata"), list):
                catalog["source_metadata"] = [row for row in catalog["source_metadata"]
                                             if isinstance(row, dict) and row.get("entity_id") in self.allowed]
                for row in catalog["source_metadata"]:
                    owner = row["entity_id"]
                    row["entity_id"] = self._encode_id(owner)
                    self._metadata(row, owner)
        discovery = payload.get("discovery")
        if isinstance(discovery, dict):
            self._discovery(discovery.get("search"))
            for result in discovery.get("facets", []):
                self._discovery(result)
        for inspection in payload.get("inspection_history", []):
            self._request(inspection.get("request"), self._encode_id)
            self._discovery(inspection.get("result"))
        return payload

    def _predicate(self, predicate):
        if not isinstance(predicate, dict):
            return
        kind = predicate.get("kind")
        if kind == "related_to":
            predicate["entity_ids"] = [self._decode_id(identifier) for identifier in predicate["entity_ids"]]
        elif kind == "compare":
            self._value(predicate.get("value"), self._decode_id)
        elif kind in {"all", "any", "not"}:
            for operand in predicate["operands"]:
                self._predicate(operand)

    def decode_proposal(self, validatedPlanProposal):
        """Translate only executable ID operands, retaining the proposal type."""
        data = validatedPlanProposal.model_dump(mode="json")
        for step in data.get("steps", []):
            operation = step["operation"]
            if operation["kind"] == "select":
                self._predicate(operation.get("where"))
                self._predicate(operation.get("exclude"))
            elif operation["kind"] == "measure":
                operation["reference_entity_ids"] = [self._decode_id(identifier)
                                                     for identifier in operation.get("reference_entity_ids", [])]
        for request in data.get("requests", []):
            self._request(request, self._decode_id)
        return type(validatedPlanProposal).model_validate(data)

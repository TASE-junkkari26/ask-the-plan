"""Model-only aliases preserve literal source data and canonical execution IDs."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from contracts import models as m
from contracts.validation import validate_plan
from ifc_api.config import IfcSettings
from ifc_api.discovery import DiscoveryRequest
from ifc_api.planning_context import OUTSIDE_SCOPE, PlanningContext
from ifc_api.service import IfcService, PlanProposal
from tests.test_ifc_engine import sample_model


class PlanningContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "fixture.ifc"
        source, doors, rooms, *_ = sample_model(cls.path)
        cls.service = IfcService(None, settings=IfcSettings(fast_plans=False))
        raw = cls.path.read_bytes()
        response = cls.service._load(cls.path, hashlib.sha256(raw).hexdigest(), len(raw))
        cls.model = cls.service._model(response.model_id, response.source_sha256)
        cls.engine = cls.model.engine
        cls.door = cls.engine.resolve_entity(doors[0].GlobalId)
        cls.other = cls.engine.resolve_entity(doors[1].GlobalId)
        cls.hidden = cls.engine.resolve_entity(doors[2].GlobalId)
        cls.room = cls.engine.resolve_entity(rooms[0].GlobalId)

    @classmethod
    def tearDownClass(cls):
        cls.service.close()
        cls.directory.cleanup()

    def context(self, allowed=None):
        return PlanningContext(self.engine, self.model.elements,
                               set(self.engine.entities) if allowed is None else allowed)

    def alias(self, identifier):
        return f"e#{self.model.elements[identifier].step_id}"

    def expose(self, context, *identifiers):
        return context.encode_payload({"catalog": {"entities": [{"id": identifier} for identifier in identifiers]}})

    def proposal(self, where, *, measure=False):
        steps = [{"id": self.alias(self.door), "operation": {"kind": "select", "concept_ids": ["concept:door"],
                  "where": where, "count_policy": {"grain": "occurrence", "hierarchy": "all_matches", "rule_key": "ifc.occurrence.v1"}}}]
        if measure:
            steps.append({"id": "measured", "operation": {"kind": "measure", "input_step_id": self.alias(self.door),
                          "metric": "distance", "reference_entity_ids": [self.alias(self.room)], "output_unit_id": "unit:m", "basis": "surface_centroids"}})
        return PlanProposal(status="ready", interpretation=f"literal {self.alias(self.door)} {self.door}",
                            explicitly_requests_entire_model=False, steps=steps,
                            output_step_id="measured" if measure else self.alias(self.door))

    def test_actual_source_discovery_and_matching_compact_without_mutating_proofs(self):
        context = self.context()
        initial = self.model.discovery.initial("What is the width of D1?", set(self.engine.entities))
        request = DiscoveryRequest(action="inspect", entity_ids=[self.door], limit=2)
        inspected = self.model.discovery.execute(request, set(self.engine.entities))
        raw = {"question": f"Quote '{self.door}' literally", "catalog": self.service._catalog(self.model, "What is the width of D1?"),
               "discovery": initial, "inspection_history": [{"request": request.model_dump(mode="json"), "result": inspected}]}
        before = deepcopy(raw)
        encoded = context.encode_payload(raw)
        self.assertEqual(raw, before)
        self.assertEqual(encoded["question"], raw["question"])
        self.assertEqual(encoded["inspection_history"][0]["request"]["entity_ids"], [self.alias(self.door)])
        record = encoded["inspection_history"][0]["result"]["records"][0]
        self.assertEqual(record["entity_id"], self.alias(self.door))
        self.assertEqual(record["guid"], self.model.elements[self.door].guid)
        self.assertEqual(record["step_id"], self.model.elements[self.door].step_id)
        self.assertTrue(any("source_hints" in fact for fact in record["facts"]))
        for fact in record["facts"]:
            self.assertNotIn("fact_id", fact)
            self.assertNotIn("anchor_ids", fact)
        self.assertTrue(any("fact_id" in fact and "anchor_ids" in fact for fact in inspected["records"][0]["facts"]))
        raw_bytes = len(json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode())
        encoded_bytes = len(json.dumps(encoded, ensure_ascii=False, separators=(",", ":")).encode())
        self.assertLess(encoded_bytes, raw_bytes * 0.85)

    def test_nested_typed_references_preserve_text_record_keys_columns_and_native_names(self):
        context = self.context({self.door, self.room})
        literal = self.alias(self.room)
        typed = {"kind": "record", "fields": {
            "anchor_ids": {"kind": "text", "value": {"text": self.door}},
            self.door: {"kind": "list", "items": [
                {"kind": "text", "value": {"text": literal}},
                {"kind": "references", "entity_ids": [self.room]}]},
            "table": {"kind": "table", "columns": [{"key": self.door, "label": {"text": literal}}],
                      "rows": [{self.door: {"kind": "references", "entity_ids": [self.door]}}]}}}
        raw = {"question": self.door, "user_record": {"anchor_ids": [self.door], "entity_id": self.door},
               "catalog": {"source_metadata": [{"entity_id": self.door, "property_key": self.door, "value": typed}],
                           "properties": [{"key": self.door, "labels": [literal]}]}}
        encoded = context.encode_payload(raw)
        value = encoded["catalog"]["source_metadata"][0]["value"]
        self.assertEqual(encoded["user_record"], raw["user_record"])
        self.assertEqual(encoded["catalog"]["properties"], raw["catalog"]["properties"])
        self.assertEqual(encoded["catalog"]["source_metadata"][0]["property_key"], self.door)
        self.assertEqual(value["fields"]["anchor_ids"], typed["fields"]["anchor_ids"])
        self.assertEqual(value["fields"][self.door]["items"][0], typed["fields"][self.door]["items"][0])
        self.assertEqual(value["fields"][self.door]["items"][1]["entity_ids"], [literal])
        self.assertEqual(value["fields"]["table"]["columns"], typed["fields"]["table"]["columns"])
        proposal = self.proposal({"kind": "compare", "field": {"kind": "entity_id", "key": self.door}, "operator": "eq", "value": value})
        original = proposal.model_dump(mode="json")
        decoded = context.decode_proposal(proposal)
        self.assertIs(type(decoded), type(proposal))
        self.assertIsNot(decoded, proposal)
        self.assertEqual(proposal.model_dump(mode="json"), original)
        self.assertEqual(decoded.steps[0].operation.where.value.model_dump(mode="json"), m.RecordValue.model_validate(typed).model_dump(mode="json"))
        self.assertEqual(decoded.steps[0].id, self.alias(self.door))
        self.assertEqual(decoded.output_step_id, self.alias(self.door))
        self.assertEqual(decoded.steps[0].operation.where.field.key, self.door)
        self.assertEqual(decoded.interpretation, proposal.interpretation)

    def test_decode_boolean_predicates_exclusions_measurements_and_inspection_ids(self):
        context = self.context()
        self.expose(context, self.door, self.room)
        condition = {"kind": "all", "operands": [
            {"kind": "related_to", "predicate": "contained_in", "direction": "outgoing", "entity_ids": [self.alias(self.room)]},
            {"kind": "not", "operands": [{"kind": "compare", "field": {"kind": "entity_id", "key": "id"},
                "operator": "eq", "value": {"kind": "references", "entity_ids": [self.alias(self.door)]}}]}]}
        proposal = self.proposal(condition, measure=True)
        proposal.steps[0].operation.exclude = m.RelationPredicate(kind="related_to", predicate="contained_in", direction="incoming", entity_ids=[self.alias(self.room)])
        decoded = context.decode_proposal(proposal)
        op = decoded.steps[0].operation
        self.assertEqual(op.where.operands[0].entity_ids, [self.room])
        self.assertEqual(op.where.operands[1].operands[0].value.entity_ids, [self.door])
        self.assertEqual(op.exclude.entity_ids, [self.room])
        self.assertEqual(decoded.steps[1].operation.reference_entity_ids, [self.room])
        self.assertEqual(decoded.steps[1].operation.input_step_id, self.alias(self.door))
        inspection = PlanProposal(status="inspect", interpretation="Inspect literal source record", explicitly_requests_entire_model=False,
                                 steps=[], requests=[{"action": "inspect", "entity_ids": [self.alias(self.room)]}])
        self.assertEqual(context.decode_proposal(inspection).requests[0].entity_ids, [self.room])

    def test_executable_identity_roundtrip_and_material_names_stay_literal(self):
        context = self.context()
        alias = self.expose(context, self.door)["catalog"]["entities"][0]["id"]
        proposal = self.proposal({"kind": "compare", "field": {"kind": "entity_id", "key": "entity_id"},
                                 "operator": "eq", "value": {"kind": "references", "entity_ids": [alias]}})
        decoded = context.decode_proposal(proposal)
        plan = m.QueryPlan(id="p", request_id="q", scope=self.engine.scope(), steps=decoded.steps, outputs={"answer": decoded.output_step_id})
        validate_plan(plan, self.engine.bundle, self.engine.capabilities)
        self.assertEqual(self.engine.execute(plan).claims[0].value.entity_ids, [self.door])
        proposal.steps.append(m.PlanStep(id="material", operation=m.MaterialQuantityOperation(kind="material_quantity", input_step_id=alias,
                              material_names=[alias, self.door], output_unit_id="unit:m3")))
        proposal.output_step_id = "material"
        material = context.decode_proposal(proposal).steps[-1].operation
        self.assertEqual(material.material_names, [alias, self.door])
        self.assertEqual(material.input_step_id, alias)

    def test_exposure_is_operational_accumulates_per_context_and_never_resolves_hidden_or_guessed_aliases(self):
        context = self.context({self.door, self.other})
        self.expose(context, self.door)
        # A literal mention is not exposure of an operational reference.
        context.encode_payload({"question": self.alias(self.other), "catalog": {"properties": [{"key": self.other}]}})
        def selected(identifier):
            proposed = self.proposal({"kind": "compare", "field": {"kind": "entity_id", "key": "id"}, "operator": "eq",
                                     "value": {"kind": "references", "entity_ids": [identifier]}})
            return context.decode_proposal(proposed)
        self.assertEqual(selected(self.alias(self.door)).steps[0].operation.where.value.entity_ids, [self.door])
        for guessed in [self.alias(self.other), self.alias(self.hidden), "e#9999999", OUTSIDE_SCOPE]:
            decoded = selected(guessed)
            self.assertEqual(decoded.steps[0].operation.where.value.entity_ids, [guessed])
            plan = m.QueryPlan(id="p", request_id="q", scope=self.engine.scope(), steps=decoded.steps, outputs={"answer": decoded.output_step_id})
            with self.assertRaises(ValueError):
                validate_plan(plan, self.engine.bundle, self.engine.capabilities)
        self.expose(context, self.other)
        self.assertEqual(selected(self.alias(self.other)).steps[0].operation.where.value.entity_ids, [self.other])
        fresh = self.context({self.door, self.other})
        proposed = selected(self.alias(self.other))
        proposed.steps[0].operation.where.value.entity_ids = [self.alias(self.other)]
        self.assertEqual(fresh.decode_proposal(proposed).steps[0].operation.where.value.entity_ids, [self.alias(self.other)])

    def test_outside_scope_records_are_removed_and_cross_scope_references_redacted(self):
        context = self.context({self.door})
        raw = {"catalog": {"entities": [{"id": self.door}, {"id": self.hidden, "labels": ["secret label"]}],
                           "matching_elements": [{"entity_id": self.hidden, "guid": "secret GUID"}]},
               "discovery": {"search": {"action": "search", "records": [
                   {"entity_id": self.door, "relations": [{"entity_ids": [self.hidden, self.door]}]},
                   {"entity_id": self.hidden, "name": "secret name"}]}}}
        encoded = context.encode_payload(raw)
        serialized = json.dumps(encoded)
        self.assertNotIn(self.hidden, serialized)
        self.assertNotIn("secret", serialized)
        record = encoded["discovery"]["search"]["records"][0]
        self.assertEqual(record["relations"][0]["entity_ids"], [OUTSIDE_SCOPE, self.alias(self.door)])
        self.assertEqual(len(encoded["catalog"]["entities"]), 1)

    def test_native_metadata_hints_replace_only_proof_wrappers(self):
        context = self.context()
        fact = next(f for (owner, _), facts in self.engine.facts.items() if owner == self.door for f in facts)
        raw = {"catalog": {"source_metadata": [{"entity_id": self.door, "property_key": fact.property_key,
               "fact_id": fact.id, "anchor_ids": fact.provenance.anchor_ids, "value": {"kind": "text", "value": {"text": fact.id}}}]}}
        encoded = context.encode_payload(raw)["catalog"]["source_metadata"][0]
        self.assertTrue(encoded["source_hints"])
        self.assertNotIn("fact_id", encoded)
        self.assertNotIn("anchor_ids", encoded)
        self.assertEqual(encoded["value"]["value"]["text"], fact.id)
        self.assertTrue(any("step" in hint or "guid" in hint for hint in encoded["source_hints"]))

    def test_ambiguous_missing_locators_and_alias_namespace_collisions_stay_canonical(self):
        entities = {"a": None, "b": None, "c": None, "e#9": None, "d": None}
        engine = SimpleNamespace(entities=entities, facts={}, anchors={})
        elements = {"a": {"step_id": 1}, "b": {"step_id": 1}, "c": {"step_id": None},
                    "d": {"step_id": 9}, "e#9": {"step_id": 10}}
        context = PlanningContext(engine, elements, set(entities))
        encoded = self.expose(context, "a", "b", "c", "d")
        self.assertEqual([row["id"] for row in encoded["catalog"]["entities"]], ["a", "b", "c", "d"])
        with self.assertRaises(ValueError):
            PlanningContext(engine, elements, {"unknown"})


if __name__ == "__main__":
    unittest.main()

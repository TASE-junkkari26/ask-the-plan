"""Source discovery is bounded, scope-bound and independent of model providers."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ifcopenshell.guid

from contracts import models as m
from ifc_api.config import IfcSettings
from ifc_api.discovery import DiscoveryRequest, MAX_RESULT_CHARS, SourceDiscovery, scope_fingerprint
from ifc_api.providers import PlannerReply, PlannerUsage
from ifc_api.service import IfcService, PlanProposal
from ifc_engine.catalog import attribute_key, property_key
from image_api.errors import ApiError
from tests.test_ifc_engine import sample_model


class ScriptedPlanner:
    name = "fixture"
    provenance = {"provider": "fixture", "requested_model": "scripted-planner", "thinking_level": "disabled"}

    def __init__(self, replies, *, delay=0):
        self.replies, self.calls, self.delay = list(replies), [], delay

    async def generate(self, payload, *, system, schema):
        self.calls.append(json.loads(payload))
        if self.delay:
            await asyncio.sleep(self.delay)
        response = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        return PlannerReply(text=json.dumps(response), model="scripted-planner",
                            usage=PlannerUsage(prompt_tokens=20, completion_tokens=10, thought_tokens=0))


def inspect_request(**action):
    return {"status": "inspect", "interpretation": "Inspect literal source metadata.",
            "explicitly_requests_entire_model": False, "steps": [], "requests": [action]}


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "discovery.ifc"
        source, cls.doors, cls.rooms, *_ = sample_model(cls.path)
        cls.doors[0].Name = "M_Single-Flush:0762 x 2032mm"
        cls.doors[1].Name = "M_Double-Flush:1524 x 2032mm"
        cls.rooms[0].LongName = "Bathroom 1"
        cls.rooms[1].LongName = "Besprechungsraum I"
        pset = source.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Pset_DoorCommon",
            HasProperties=[source.create_entity("IfcPropertySingleValue", Name="IsExternal",
                          NominalValue=source.create_entity("IfcBoolean", False))])
        source.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                             RelatedObjects=[cls.doors[0]], RelatingPropertyDefinition=pset)
        null_set = source.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Pset_DoorCommon",
            HasProperties=[source.create_entity("IfcPropertySingleValue", Name="IsExternal", NominalValue=None)])
        source.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                             RelatedObjects=[cls.doors[1]], RelatingPropertyDefinition=null_set)
        source.write(str(cls.path))
        cls.sha = hashlib.sha256(cls.path.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.service = IfcService(None, settings=IfcSettings(fast_plans=False))
        description = self.service._load(self.path, self.sha, self.path.stat().st_size)
        self.model = self.service._model(description.model_id, self.sha)
        self.index = SourceDiscovery(self.model.engine, self.model.elements)
        self.members = set(self.model.elements)

    def tearDown(self):
        self.service.close()

    def request(self, *, scope="model", ids=None):
        return m.IfcQuestionRequest(model_id=self.model.model_id, source_sha256=self.sha,
            question="How many single-flush doors?", scope=scope, visible_step_ids=ids)

    def ready(self):
        plan = self.model.engine.plan("door")
        return {"status": "ready", "interpretation": "Count source door occurrences in captured scope.",
                "explicitly_requests_entire_model": False,
                "steps": [step.model_dump(mode="json") for step in plan.steps],
                "output_step_id": next(iter(plan.outputs.values()))}

    def test_partial_source_name_search_preserves_original_spelling_and_scope(self):
        wanted = self.model.by_step[self.doors[0].id()]
        records = self.index.execute(DiscoveryRequest(action="search", query="single flush doors",
            concept_ids=["concept:door"]), self.members)
        self.assertEqual(records["records"][0]["entity_id"], wanted)
        self.assertEqual(records["records"][0]["name"], self.doors[0].Name)
        hidden = self.index.execute(DiscoveryRequest(action="search", query="single flush",
            concept_ids=["concept:door"]), {self.model.by_step[self.doors[2].id()]})
        self.assertEqual(hidden["records"], [])
        with self.assertRaisesRegex(ValueError, "outside the captured scope"):
            self.index.execute(DiscoveryRequest(action="inspect", entity_ids=[wanted]), set())

    def test_fact_facets_preserve_false_missing_and_literal_long_name(self):
        door_ids = {self.model.by_step[door.id()] for door in self.doors}
        output = self.index.execute(DiscoveryRequest(action="facets",
            property_keys=[property_key("Pset_DoorCommon", "IsExternal")]), door_ids)
        facet = output["facets"][0]
        self.assertEqual(facet["eligible_entities"], 3)
        self.assertEqual(facet["missing_entities"], 1)
        self.assertEqual(facet["explicit_null_entities"], 1)
        self.assertEqual(facet["source_status_entity_counts"], {"present": 1, "explicit_null": 1, "not_in_source": 1})
        self.assertEqual(facet["values"][0]["value"], {"kind": "boolean", "value": False})
        self.assertEqual(facet["values"][0]["source_fact_count"], 1)
        room_id = self.model.by_step[self.rooms[1].id()]
        inspected = self.index.execute(DiscoveryRequest(action="inspect", entity_ids=[room_id],
            property_keys=[attribute_key("LongName")]), self.members)
        self.assertEqual(inspected["records"][0]["facts"][0]["value"]["value"]["text"], "Besprechungsraum I")
        self.assertTrue(inspected["records"][0]["facts"][0]["anchor_ids"])

    def test_search_is_explicitly_candidate_only_and_source_snapshot_is_unchanged(self):
        before = len(self.model.engine.facts)
        output = self.index.execute(DiscoveryRequest(action="search", query="doors", limit=1,
            concept_ids=["concept:door"]), self.members)
        self.assertEqual(output["matching_total"], 3)
        self.assertTrue(output["truncated"])
        self.assertEqual(output["inventory_completeness"], "candidate_search")
        self.assertLessEqual(len(json.dumps(output, ensure_ascii=False)), MAX_RESULT_CHARS)
        self.assertEqual(before, len(self.model.engine.facts))
        self.assertNotEqual(scope_fingerprint(self.sha, self.members), scope_fingerprint(self.sha, set()))

    def test_properties_discover_original_paths_without_catalog_dump(self):
        result = self.index.execute(DiscoveryRequest(action="properties", query="FireRating"), self.members)
        self.assertIn(property_key("Pset_DoorCommon", "FireRating"), [row["key"] for row in result["records"]])
        with self.assertRaises(ValueError):
            self.index.execute(DiscoveryRequest(action="inspect", entity_ids=["other-revision"],
                property_keys=["invented/path"]), self.members)

    async def test_long_question_retains_full_text_with_bounded_initial_search(self):
        question = ("What is the sound transmission class (STC) rating between treatment rooms? "
            "If this information is not directly available in the BIM model, what are the typical "
            "STC ratings for similar partition wall constructions?")
        planner = ScriptedPlanner([{"status": "missing_information", "interpretation": "Offline inspection fixture.",
            "explicitly_requests_entire_model": False, "steps": []}])
        self.service.planner = planner
        request = self.request().model_copy(update={"question": question})
        response = await self.service.question(request, "request:long-question")
        self.assertEqual(response.result.status, "missing_information")
        self.assertEqual(planner.calls[0]["question"], question)
        self.assertTrue(planner.calls[0]["discovery"]["search"]["query_truncated"])
        self.assertEqual(len(planner.calls), 1)

    def test_unsearchable_long_literal_is_not_a_zero_match_inventory(self):
        search = self.index.initial("A" * 201, self.members)["search"]
        self.assertIsNone(search["matching_total"])
        self.assertTrue(search["query_truncated"])
        self.assertEqual(search["records"], [])

    async def test_inspection_loop_executes_real_plan_and_aggregates_usage(self):
        planner = ScriptedPlanner([inspect_request(action="search", query="single flush"), self.ready()])
        self.service.planner = planner
        response = await self.service.question(self.request(), "request:discovery")
        self.assertEqual(response.result.status, "answered")
        self.assertEqual(response.result.claims[0].value.value, 3)
        self.assertEqual(response.planning.model_requests, 2)
        self.assertEqual(response.planning.inspection_count, 1)
        self.assertEqual(response.planning.prompt_tokens, 40)
        self.assertEqual(response.result.metrics.model_output_tokens, 20)
        self.assertEqual(len(planner.calls[1]["inspection_history"]), 1)
        self.assertIn("scope_fingerprint", planner.calls[1])
        self.assertNotIn(str(self.path), json.dumps(planner.calls))

    async def test_compact_inspection_and_plan_resolve_to_canonical_public_evidence(self):
        owner = self.model.by_step[self.doors[0].id()]
        expected = "e#" + str(self.doors[0].id())
        ready = self.ready()
        ready["steps"][0]["operation"]["where"] = {"kind": "compare",
            "field": {"kind": "entity_id", "key": "entity_id"}, "operator": "eq",
            "value": {"kind": "references", "entity_ids": [expected]}}
        planner = ScriptedPlanner([inspect_request(action="inspect", entity_ids=[expected],
            property_keys=[attribute_key("Name")]), ready])
        self.service.planner = planner
        response = await self.service.question(self.request(), "request:compact")
        self.assertEqual(response.result.status, "answered")
        self.assertEqual(response.result.claims[0].value.value, 1)
        observed = planner.calls[1]["inspection_history"][0]
        self.assertEqual(observed["request"]["entity_ids"], [expected])
        self.assertEqual(observed["result"]["records"][0]["entity_id"], expected)
        self.assertEqual(response.plan.steps[0].operation.where.value.entity_ids, [owner])
        self.assertEqual([element.entity_id for element in response.included_elements], [owner])
        self.assertTrue(response.anchors)
        self.assertTrue(all(anchor.id.startswith("anchor:") for anchor in response.anchors))
        self.assertNotIn('"entity_ids":["e#', response.model_dump_json())

    async def test_ignored_named_room_is_repaired_before_any_plan_executes(self):
        plan = self.model.engine.plan("space")
        broad = {"status": "ready", "interpretation": "Count only room 7.16.",
            "explicitly_requests_entire_model": False,
            "steps": [step.model_dump(mode="json") for step in plan.steps],
            "output_step_id": next(iter(plan.outputs.values()))}
        corrected = json.loads(json.dumps(broad))
        corrected["steps"][0]["operation"]["where"] = {"kind": "compare",
            "field": {"kind": "property", "key": attribute_key("Name")}, "operator": "eq",
            "value": {"kind": "text", "value": {"text": "7.16"}}}
        planner = ScriptedPlanner([broad, corrected])
        self.service.planner = planner
        request = self.request().model_copy(update={"question": "How many instances of room 7.16 exist?"})
        with patch.object(self.model.engine, "execute", wraps=self.model.engine.execute) as execute:
            response = await self.service.question(request, "request:room-repair")
        self.assertEqual(response.result.status, "answered")
        self.assertEqual(response.result.claims[0].value.value, 1)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(response.planning.model_requests, 2)
        self.assertIn("plan_repair", planner.calls[1])
        self.assertEqual(len(response.included_elements), 1)
        self.assertEqual(response.included_elements[0].step_id, self.rooms[0].id())

    async def test_inspection_budget_and_model_request_limit_return_honest_nonanswer(self):
        for settings in [IfcSettings(max_model_requests=1, fast_plans=False), IfcSettings(max_inspections=0, fast_plans=False)]:
            with self.subTest(settings=settings):
                planner = ScriptedPlanner([inspect_request(action="search", query="doors")])
                self.service.planner, self.service.settings = planner, settings
                response = await self.service.question(self.request(), "request:budget")
                self.assertEqual(response.result.status, "missing_information")
                self.assertFalse(response.result.claims)
                self.assertEqual(len(planner.calls), 1)

    async def test_unknown_or_out_of_scope_inspection_does_not_expose_other_objects(self):
        hidden = self.model.by_step[self.doors[1].id()]
        planner = ScriptedPlanner([inspect_request(action="inspect", entity_ids=[hidden]), self.ready()])
        self.service.planner = planner
        response = await self.service.question(self.request(scope="view", ids=[self.doors[0].id()]), "request:scope")
        self.assertEqual(response.result.claims[0].value.value, 1)
        observation = planner.calls[1]["inspection_history"][0]["result"]
        self.assertIn("error", observation)
        self.assertNotIn(self.doors[1].Name, json.dumps(observation))
        self.assertNotIn(self.doors[1].Name, json.dumps(planner.calls[0]))

    async def test_one_deadline_covers_multiple_provider_requests(self):
        self.service.planner = ScriptedPlanner([inspect_request(action="search", query="doors"), self.ready()], delay=.02)
        self.service.deadline_seconds = .025
        with self.assertRaises(ApiError) as error:
            await self.service.question(self.request(), "request:timeout")
        self.assertEqual(error.exception.code, "deadline_exceeded")

    def test_ready_proposals_cannot_smuggle_unexecuted_discovery_requests(self):
        with self.assertRaises(ValueError):
            PlanProposal.model_validate({**self.ready(), "requests": [{"action": "search", "query": "doors"}]})


if __name__ == "__main__":
    unittest.main()

"""Mocked IFC question planning preserves source topology and readable evidence.

These integration checks use generated IFC data and one mocked provider reply;
they do not measure live model interpretation or dataset-wide answer accuracy.
"""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from contracts import models as m
from contracts.validation import validate_plan, validate_result
from ifc_engine.catalog import POLICIES, attribute_key
from ifc_api.service import PlanProposal
import tests.test_ifc_api as api_fixtures
from tests.test_ifc_spatial_queries import spatial_source


def select_objects(concept, step_ids=()):
    operation = {"kind": "select", "concept_ids": ["concept:" + concept],
                 "count_policy": POLICIES["all_matches"].model_dump()}
    if step_ids:
        comparisons = [{"kind": "compare", "field": {"kind": "native_identifier", "key": "step_id"},
                        "operator": "eq", "value": {"kind": "text", "value": {"text": str(step)}}}
                       for step in step_ids]
        operation["where"] = comparisons[0] if len(comparisons) == 1 else {"kind": "any", "operands": comparisons}
    return {"id": "objects", "operation": operation}


def ready(steps, *, outputs=None):
    return {"status": "ready", "interpretation": "Read the requested source objects, relationships and metadata.",
            "explicitly_requests_entire_model": False, "steps": steps,
            "output_step_id": None if outputs else steps[-1]["id"], "outputs": outputs or {}}


class IfcSpatialApiTests(unittest.IsolatedAsyncioTestCase):
    # Reuse only the credential-free transport/upload harness, without inheriting
    # or rediscovering the unrelated window tests from its defining module.
    api = api_fixtures.IfcApiTests.api
    upload = api_fixtures.IfcApiTests.upload

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "spatial-api.ifc"
        source, cls.objects, cls.relationships = spatial_source(cls.path)
        source.header.file_name.originating_system = "Literal source authoring program 2026"
        cls.objects["project"].Description = "Literal university facilities model"
        source.write(str(cls.path))
        cls.content = cls.path.read_bytes()
        cls.sha = hashlib.sha256(cls.content).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.provider_requests = []
        self.reply = None

    async def ask(self, client, model, question):
        response = await client.post("/api/ifc/questions", json={
            "model_id": model["model_id"], "source_sha256": model["source_sha256"],
            "question": question, "scope": "model", "visible_step_ids": None})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.provider_requests), 1, "Narration must not make another inference request")
        return m.IfcQuestionResponse.model_validate(response.json())

    def topology_proposal(self, relation, keys, *, concept="space", **attributes):
        return ready([select_objects(concept, [self.objects[key].id() for key in keys]),
            {"id": "relationships", "operation": {"kind": "spatial_query", "input_step_id": "objects",
             "relation": relation, **attributes}}])

    def step_anchors(self, answer):
        return {int(anchor.selector.value) for anchor in answer.anchors if anchor.selector.kind == "step_id"}

    async def test_containment_answer_names_original_room_and_its_source_relationship(self):
        # The distribution board has a native containment link to the room; its
        # name alone contains no room or floor information.
        self.reply = self.topology_proposal("containers", ["equipment"], concept="electric_distribution_board",
                                            container_kind="space")
        self.reply["steps"][0]["operation"]["concept_ids"] = ["ifc:IfcElectricDistributionBoard"]
        async with self.api() as (client, app):
            model = await self.upload(client)
            answer = await self.ask(client, model, "Which room contains Panel-01?")
            self.assertEqual(answer.result.status, "answered")
            explanation = answer.result.explanation.text
            self.assertIn("Panel-01", explanation)
            self.assertIn("1B07 · Büro", explanation)
            self.assertIn("according to native IFC containment", explanation)
            self.assertEqual({element.step_id for element in answer.included_elements},
                             {self.objects[key].id() for key in ["equipment", "a"]})
            self.assertIn(self.relationships["equipment_location"].id(), self.step_anchors(answer))
            state = app.state.ifc_service._model(model["model_id"], self.sha)
            validate_plan(answer.plan, state.engine.bundle, state.engine.capabilities)
            validate_result(answer.result, state.engine.bundle, answer.plan)
            self.assertTrue(any(binding.value_path == "/rows/0/related" for binding in answer.result.claims[0].evidence))

    async def test_shared_wall_adjacency_remains_partial_and_narrative_qualifies_candidates(self):
        self.reply = self.topology_proposal("boundary_neighbors", ["a"])
        async with self.api() as (client, _):
            model = await self.upload(client)
            answer = await self.ask(client, model, "Which rooms are adjacent to room 1B07?")
            self.assertEqual(answer.result.status, "partial")
            self.assertTrue(any(issue.code == "incomplete_coverage" for issue in answer.result.issues))
            self.assertIn("candidate neighbor", answer.result.explanation.text)
            self.assertIn("121.A", answer.result.explanation.text)
            self.assertIn("not verified geometric neighbors", answer.result.issues[0].message.text)
            self.assertIn(self.relationships["wall_c"].id(), self.step_anchors(answer))

    async def test_outdoor_access_counts_rooms_once_and_keeps_included_excluded_and_door_inputs(self):
        self.reply = self.topology_proposal("outdoor_access", ["a", "b", "c"])
        self.reply["steps"].append({"id": "count", "operation": {
            "kind": "aggregate", "input_step_id": "relationships", "method": "count"}})
        self.reply["output_step_id"] = "count"
        async with self.api() as (client, _):
            model = await self.upload(client)
            answer = await self.ask(client, model, "How many rooms have access to outdoor space?")
            self.assertEqual(answer.result.status, "answered")
            self.assertEqual(answer.result.claims[0].value.value, 2)
            self.assertEqual(answer.result.claims[0].count_policy.grain, "occurrence")
            self.assertEqual({element.step_id for element in answer.included_elements},
                             {self.objects[key].id() for key in ["a", "b"]})
            self.assertIn(self.objects["c"].id(), {element.step_id for element in answer.excluded_elements})
            self.assertTrue({self.relationships[key].id() for key in
                ["exterior_a", "exterior_a_duplicate", "exterior_a_second", "exterior_b", "outside_fill"]}
                <= self.step_anchors(answer))
            self.assertIn("2 modeled occurrence(s)", answer.result.explanation.text)
            self.assertIn("not a verified fire exit", answer.result.explanation.text)

    async def test_file_schema_and_descriptive_metadata_come_from_original_header_and_project(self):
        fields = [{"kind": "entity_id", "key": "entity_id"}] + [
            {"kind": "property", "key": attribute_key(name)} for name in ["FILE_SCHEMA", "OriginatingSystem", "Description"]]
        self.reply = ready([select_objects("project"), {"id": "metadata", "operation": {
            "kind": "project", "input_step_id": "objects", "fields": fields}}])
        async with self.api() as (client, _):
            model = await self.upload(client)
            answer = await self.ask(client, model, "Describe the project and the software and IFC standard used in this file.")
            self.assertEqual(answer.result.status, "answered")
            for literal in ["IFC4", "Literal source authoring program 2026", "Literal university facilities model"]:
                self.assertIn(literal, answer.result.explanation.text)
            self.assertEqual({fact.property_key for fact in answer.facts},
                             {attribute_key(name) for name in ["FILE_SCHEMA", "OriginatingSystem", "Description"]})
            header_anchors = [anchor for anchor in answer.anchors if anchor.selector.kind == "file_metadata"]
            self.assertEqual({anchor.selector.value for anchor in header_anchors}, {"FILE_SCHEMA", "FILE_NAME"})
            self.assertEqual({element.step_id for element in answer.included_elements}, {self.objects["project"].id()})

    async def test_compound_question_returns_both_named_outputs_without_extra_provider_call(self):
        self.reply = ready([
            select_objects("project"),
            {"id": "metadata", "operation": {"kind": "project", "input_step_id": "objects", "fields": [
                {"kind": "property", "key": attribute_key("FILE_SCHEMA")},
                {"kind": "property", "key": attribute_key("OriginatingSystem")}] }},
            {"id": "storeys", "operation": {"kind": "select", "concept_ids": ["concept:storey"],
                "count_policy": POLICIES["all_matches"].model_dump()}},
            {"id": "count", "operation": {"kind": "aggregate", "input_step_id": "storeys", "method": "count"}}],
            outputs={"file_metadata": "metadata", "storey_count": "count"})
        async with self.api() as (client, _):
            model = await self.upload(client)
            answer = await self.ask(client, model, "Which software and IFC schema were used, and how many storeys are modeled?")
            self.assertEqual(answer.result.status, "answered")
            self.assertEqual(answer.plan.outputs, {"file_metadata": "metadata", "storey_count": "count"})
            self.assertEqual({claim.output_key for claim in answer.result.claims}, {"file_metadata", "storey_count"})
            counts = [claim for claim in answer.result.claims if claim.output_key == "storey_count"]
            self.assertEqual(counts[0].value.value, 2)
            self.assertIn("IFC4", answer.result.explanation.text)
            self.assertIn("storey_count: 2", answer.result.explanation.text)

    async def test_file_metadata_does_not_silently_escape_drawable_view_scope(self):
        self.reply = ready([select_objects("project"), {"id": "metadata", "operation": {
            "kind": "project", "input_step_id": "objects", "fields": [
                {"kind": "property", "key": attribute_key("FILE_SCHEMA")}]}}])
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await client.post("/api/ifc/questions", json={
                "model_id": model["model_id"], "source_sha256": model["source_sha256"],
                "question": "Which IFC standard is declared in this file?", "scope": "view",
                "visible_step_ids": [self.objects["a"].id()]})
            self.assertEqual(response.status_code, 200, response.text)
            answer = m.IfcQuestionResponse.model_validate(response.json())
            self.assertEqual(answer.result.status, "needs_clarification")
            self.assertFalse(answer.result.claims)
            self.assertIn("Choose Entire IFC model", answer.result.issues[0].message.text)

    async def test_planner_catalog_contains_native_topology_metadata_and_literal_room_labels(self):
        self.reply = self.topology_proposal("containers", ["equipment"], container_kind="storey")
        self.reply["steps"][0]["operation"]["concept_ids"] = ["ifc:IfcElectricDistributionBoard"]
        async with self.api() as (client, _):
            model = await self.upload(client)
            await self.ask(client, model, "Where is Panel-01 relative to Büro?")
            message = next(message for message in self.provider_requests[0]["messages"] if message["role"] == "user")
            catalog = json.loads(message["content"])["catalog"]
            self.assertEqual(set(catalog["spatial_queries"]), {"containers", "boundary_neighbors", "door_connections", "outdoor_access"})
            self.assertTrue({"bounded_by", "external_boundary", "has_opening", "filled_by"} <= set(catalog["relations"]))
            self.assertIn("concept:project", catalog["concepts"])
            self.assertTrue(any(entity["labels"] == ["1B07", "Büro"] for entity in catalog["entities"]))
            self.assertTrue(any("Spatial regression fixture" in entity["labels"] for entity in catalog["entities"]))
            self.assertTrue(any(fact["property_key"] == attribute_key("FILE_SCHEMA") and
                                fact["value"]["value"]["text"] == "IFC4" for fact in catalog["source_metadata"]))

    async def test_absent_source_description_returns_missing_information_without_narrative(self):
        # Site.Description is explicitly null in the fixture. The system must
        # not invent a site history or substitute the project description.
        self.reply = ready([select_objects("site"), {"id": "description", "operation": {
            "kind": "project", "input_step_id": "objects", "fields": [
                {"kind": "property", "key": attribute_key("Description")}]}}])
        async with self.api() as (client, _):
            model = await self.upload(client)
            answer = await self.ask(client, model, "What description is recorded for the site?")
            self.assertEqual(answer.result.status, "missing_information")
            self.assertFalse(answer.result.claims)
            self.assertIsNone(answer.result.explanation)
            self.assertFalse(answer.included_elements)

    def test_compound_plan_cannot_silently_combine_single_and_named_output_modes(self):
        value = ready([select_objects("project")], outputs={"metadata": "objects"})
        value["output_step_id"] = "objects"
        with self.assertRaisesRegex(ValueError, "use output_step_id or named outputs"):
            PlanProposal.model_validate(value)


if __name__ == "__main__":
    unittest.main()

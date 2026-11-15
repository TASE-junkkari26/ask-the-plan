"""Finite source pages preserve original items, cursors and captured scope."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ifcopenshell.guid

from contracts import models as m
from ifc_api.config import IfcSettings
from ifc_api.discovery import DiscoveryRequest, MAX_RESULT_CHARS, SourceDiscovery
from ifc_api.service import IfcService, PlanProposal
from ifc_engine.catalog import attribute_key, property_key
from image_api.errors import ApiError
from tests.test_ifc_discovery import ScriptedPlanner, inspect_request
from tests.test_ifc_engine import sample_model


class DiscoveryPaginationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "pages.ifc"
        source, _, _, _, ground, _ = sample_model(cls.path)
        cls.spaces = []
        for index in range(55):
            cls.spaces.append(source.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name=f"R{index:02d}",
                LongName=f"Toiminto_Å{index:02d}_" + "x" * 100, Description=f"Ryhmä_{index % 7}"))
        cls.large = source.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Oversized", LongName="ä" * 30000)
        source.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=ground, RelatedObjects=[*cls.spaces, cls.large])
        properties = [source.create_entity("IfcPropertySingleValue", Name=f"Property_{index:02d}",
                      NominalValue=source.create_entity("IfcLabel", f"Literal_{index:02d}")) for index in range(55)]
        pset = source.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Paging", HasProperties=properties)
        source.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[cls.spaces[0]], RelatingPropertyDefinition=pset)
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
        self.members = {self.model.by_step[space.id()] for space in self.spaces}
        self.large_id = self.model.by_step[self.large.id()]

    def tearDown(self):
        self.service.close()

    def pages(self, *, action, members=None, **kwargs):
        offset, outputs = 0, []
        for _ in range(100):
            page = self.index.execute(DiscoveryRequest(action=action, offset=offset, **kwargs),
                                      self.members if members is None else members)
            self.assertLessEqual(len(json.dumps(page, ensure_ascii=False)), MAX_RESULT_CHARS)
            outputs.append(page)
            self.assertFalse(page.get("unpageable"), page)
            if page["next_offset"] is None:
                return outputs
            self.assertEqual(page["next_offset"], offset + len(page["records"]))
            self.assertGreater(page["next_offset"], offset)
            offset = page["next_offset"]
        self.fail("Pagination did not terminate")

    def test_search_reconstructs_every_authorized_original_record(self):
        pages = self.pages(action="search", query="space", concept_ids=["concept:space"], limit=20,
                           property_keys=[attribute_key("Name")])
        records = [record for page in pages for record in page["records"]]
        self.assertEqual({record["entity_id"] for record in records}, self.members)
        self.assertEqual(len(records), len(self.members))
        self.assertTrue(all(page["matching_total"] == 55 for page in pages))
        self.assertEqual([record["entity_id"] for record in records], sorted(self.members))
        self.assertTrue(all(record["name"] == self.model.elements[record["entity_id"]].name for record in records))
        scoped = set(sorted(self.members)[:23])
        pages = self.pages(action="search", query="space", concept_ids=["concept:space"], limit=7, members=scoped)
        self.assertEqual({record["entity_id"] for page in pages for record in page["records"]}, scoped)

    def test_properties_reconstruct_complete_sorted_vocabulary(self):
        pages = self.pages(action="properties", query="Property_", limit=11)
        keys = [row["key"] for page in pages for row in page["records"]]
        self.assertEqual(keys, [property_key("Paging", f"Property_{index:02d}") for index in range(55)])
        self.assertTrue(all(page["matching_total"] == 55 for page in pages))
        owner = self.model.by_step[self.spaces[0].id()]
        empty = self.index.execute(DiscoveryRequest(action="properties", query="Property_"), self.members - {owner})
        self.assertEqual(empty["matching_total"], 0)
        self.assertIsNone(empty["next_offset"])

    def test_response_budget_trim_advances_by_actual_returned_records(self):
        with patch("ifc_api.discovery.MAX_RESULT_CHARS", 3500):
            pages = self.pages(action="search", query="space", concept_ids=["concept:space"], limit=20,
                               property_keys=[attribute_key("Name")])
        self.assertLess(len(pages[0]["records"]), 20)
        self.assertGreater(len(pages[0]["records"]), 0)
        ids = [row["entity_id"] for page in pages for row in page["records"]]
        self.assertEqual(ids, sorted(self.members))
        with patch("ifc_api.discovery.MAX_RESULT_CHARS", 1000):
            pages = self.pages(action="properties", query="Property_", limit=20)
        keys = [row["key"] for page in pages for row in page["records"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 55)

    def test_facets_have_independent_actual_cursors_and_reconstruct_literal_values(self):
        long_name, description = attribute_key("LongName"), attribute_key("Description")
        with patch("ifc_api.discovery.MAX_RESULT_CHARS", 4000):
            first = self.index.execute(DiscoveryRequest(action="facets", property_keys=[long_name, description], limit=20), self.members)
        self.assertLessEqual(len(json.dumps(first, ensure_ascii=False)), 4000)
        observed = {}
        for initial in first["facets"]:
            key, values, page = initial["property_key"], list(initial["values"]), initial
            self.assertEqual(first["next_offsets"][key], page["next_offset"])
            for _ in range(10):
                self.assertFalse(page["unpageable"], page)
                if page["next_offset"] is None:
                    break
                offset = page["next_offset"]
                page = self.index.execute(DiscoveryRequest(action="facets", property_keys=[key], limit=20, offset=offset), self.members)["facets"][0]
                self.assertEqual(page["offset"], offset)
                values.extend(page["values"])
            else:
                self.fail("Facet pages did not terminate")
            observed[key] = values
            self.assertEqual(len(values), page["matching_total"])
            self.assertEqual(len({json.dumps(value["value"], sort_keys=True) for value in values}), len(values))
            self.assertEqual(sum(value["source_fact_count"] for value in values), 55)
        self.assertEqual({value["value"]["value"]["text"] for value in observed[long_name]}, {space.LongName for space in self.spaces})
        self.assertEqual(len(observed[description]), 7)
        self.assertNotEqual(first["next_offsets"][long_name], first["next_offsets"][description])

    def test_oversized_items_and_distinct_value_bound_are_explicit_unpageable(self):
        for action in ["search", "facets"]:
            request = DiscoveryRequest(action=action, query="space", property_keys=[attribute_key("LongName")])
            output = self.index.execute(request, {self.large_id})
            page = output["facets"][0] if action == "facets" else output
            self.assertEqual(page["matching_total"], 1)
            self.assertEqual(page["returned_count"], 0)
            self.assertIsNone(page["next_offset"])
            self.assertTrue(page["unpageable"])
            self.assertTrue(page["truncated"])
            self.assertEqual(page["blocked_offset"], 0)
            self.assertLessEqual(len(json.dumps(output, ensure_ascii=False)), MAX_RESULT_CHARS)
        with patch("ifc_api.discovery.MAX_FACET_VALUES", 4):
            page = self.index.execute(DiscoveryRequest(action="facets", property_keys=[attribute_key("LongName")], limit=20), self.members)["facets"][0]
        self.assertFalse(page["value_inventory_complete"])
        self.assertIsNone(page["matching_total"])
        self.assertGreater(page["omitted_source_facts"], 0)
        self.assertTrue(page["unpageable"])
        self.assertEqual(page["unpageable_reason"], "value_inventory_limit")

    def test_offsets_are_bounded_strict_and_inspection_cannot_page(self):
        for offset in [-1, 1001, True, 1.0]:
            with self.assertRaises(ValueError):
                DiscoveryRequest(action="search", query="room", offset=offset)
        with self.assertRaises(ValueError):
            DiscoveryRequest(action="inspect", entity_ids=[next(iter(self.members))], offset=1)
        self.assertEqual(DiscoveryRequest(action="search", query="room", offset=1000).offset, 1000)
        schema = PlanProposal.model_json_schema()["$defs"]["DiscoveryRequest"]["properties"]["offset"]
        self.assertEqual((schema["minimum"], schema["maximum"]), (0, 1000))

    async def test_paginated_service_request_stays_revision_bound_and_costs_one_action(self):
        selected = self.model.engine.plan("space")
        ready = {"status": "ready", "interpretation": "Count source spaces after bounded metadata inspection.",
                 "explicitly_requests_entire_model": False, "steps": [step.model_dump(mode="json") for step in selected.steps],
                 "output_step_id": next(iter(selected.outputs.values()))}
        planner = ScriptedPlanner([inspect_request(action="properties", query="Property_", offset=20, limit=20), ready])
        self.service.planner = planner
        request = m.IfcQuestionRequest(model_id=self.model.model_id, source_sha256=self.sha,
                                      question="Review source property vocabulary, then count spaces.", scope="model")
        response = await self.service.question(request, "question:paged")
        self.assertEqual(response.planning.inspection_count, 1)
        observation = planner.calls[1]["inspection_history"][0]["result"]
        self.assertEqual(observation["offset"], 20)
        self.assertEqual(observation["next_offset"], 40)
        with self.assertRaises(ApiError) as error:
            await self.service.question(request.model_copy(update={"source_sha256": "0" * 64}), "question:other-revision")
        self.assertEqual(error.exception.code, "source_mismatch")
        self.assertEqual(len(planner.calls), 2)


if __name__ == "__main__":
    unittest.main()

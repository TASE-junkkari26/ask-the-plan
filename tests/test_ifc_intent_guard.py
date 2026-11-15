"""Ignored named rooms cannot become answers over an unrelated full inventory."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from contracts import models as m
from ifc_api.intent_guard import check_room_binding
from ifc_api.service import PlanProposal
from ifc_engine.catalog import attribute_key
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_engine import sample_model


class RoomIntentGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "fixture.ifc"
        self.source, _, self.rooms, *_ = sample_model(self.path)
        self.rooms[0].LongName = "Consultation"
        self.source.write(str(self.path))
        self.engine = IfcQueryEngine.open(self.path)
        self.room = self.engine.resolve_entity(self.rooms[0].GlobalId)
        self.other = self.engine.resolve_entity(self.rooms[1].GlobalId)

    def identity(self, identifier=None):
        return {"kind": "compare", "field": {"kind": "entity_id", "key": "entity_id"}, "operator": "eq",
                "value": {"kind": "references", "entity_ids": [identifier or self.room]}}

    def select(self, where=None, identifier="rooms"):
        return {"id": identifier, "operation": {"kind": "select", "concept_ids": ["concept:space"], "where": where,
                "count_policy": {"grain": "occurrence", "hierarchy": "all_matches", "rule_key": "ifc.occurrence.v1"}}}

    def proposal(self, steps=None, **extra):
        return PlanProposal(status="ready", interpretation="Resolve requested source room", explicitly_requests_entire_model=False,
                            steps=steps or [self.select()], **(extra or {"output_step_id": "rooms"}))

    def test_unfiltered_inventory_rejected_for_literal_english_finnish_and_quoted_combined_room(self):
        for question in ["Which rooms connect to room 7.16?", "Mitkä huoneet liittyvät huoneeseen '7.16'?",
                         'Which spaces are adjacent to space "Consultation (7.16)"?', "What is the area of room Consultation?"]:
            self.assertIsNotNone(check_room_binding(self.engine, question, self.proposal()), question)
            self.assertIsNone(check_room_binding(self.engine, question, self.proposal([self.select(self.identity())])), question)

    def test_unused_bound_step_and_unbound_named_output_do_not_pass(self):
        steps = [self.select(self.identity(), "right"), self.select(None, "wrong")]
        self.assertIsNotNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal(steps, output_step_id="wrong")))
        self.assertIsNotNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal(steps, outputs={"right": "right", "wrong": "wrong"})))
        self.assertIsNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal(steps, output_step_id="right")))

    def test_or_cannot_leak_other_rooms_and_negative_identity_does_not_bind(self):
        other = self.identity(self.other)
        for where in [{"kind": "any", "operands": [self.identity(), other]},
                      {"kind": "not", "operands": [self.identity()]},
                      {**self.identity(), "operator": "ne"}]:
            self.assertIsNotNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal([self.select(where)])))
        for where in [{"kind": "all", "operands": [self.identity(), other]},
                      {"kind": "any", "operands": [self.identity(), self.identity()]}]:
            self.assertIsNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal([self.select(where)])))

    def test_exact_native_name_guid_step_and_single_relation_target_bind(self):
        where_values = [
            {"kind": "compare", "field": {"kind": "property", "key": attribute_key("Name")}, "operator": "eq", "value": {"kind": "text", "value": {"text": "7.16"}}},
            {"kind": "compare", "field": {"kind": "native_identifier", "key": "ifc_guid"}, "operator": "eq", "value": {"kind": "text", "value": {"text": self.rooms[0].GlobalId}}},
            {"kind": "compare", "field": {"kind": "native_identifier", "key": "step_id"}, "operator": "eq", "value": {"kind": "text", "value": {"text": str(self.rooms[0].id())}}},
            {"kind": "related_to", "predicate": "adjacent_to", "direction": "outgoing", "entity_ids": [self.room]},
        ]
        for where in where_values:
            self.assertIsNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal([self.select(where)])))
        where_values[-1]["entity_ids"].append(self.other)
        self.assertIsNotNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal([self.select(where_values[-1])])))

    def test_source_identity_propagates_to_spatial_output_or_measurement_reference(self):
        steps = [self.select(self.identity()), {"id": "connections", "operation": {
            "kind": "spatial_query", "input_step_id": "rooms", "relation": "door_connections"}}]
        self.assertIsNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal(steps, output_step_id="connections")))
        steps = [self.select(), {"id": "distances", "operation": {"kind": "measure", "input_step_id": "rooms", "metric": "distance",
                 "reference_entity_ids": [self.room], "output_unit_id": "unit:m", "basis": "surface_centroids"}}]
        self.assertIsNone(check_room_binding(self.engine, "What are the distances to room 7.16?", self.proposal(steps, output_step_id="distances")))

    def test_unknown_ambiguous_or_non_singular_labels_do_not_activate_and_hidden_rooms_not_hydrated(self):
        for question in ["How many rooms are there?", "Which rooms connect to room Unknown?", "What are the rooms 7.16 and Office?",
                         "Which rooms connect to room 7.160?"]:
            self.assertIsNone(check_room_binding(self.engine, question, self.proposal()), question)
        with patch.object(self.engine, "ensure_fields", wraps=self.engine.ensure_fields) as ensure:
            self.assertIsNone(check_room_binding(self.engine, "Which rooms connect to room 7.16?", self.proposal(), {self.other}))
        self.assertTrue(all(set(call.args[0]) <= {self.other} for call in ensure.call_args_list))
        self.rooms[1].Name = "7.16"
        self.source.write(str(self.path))
        duplicate = IfcQueryEngine.open(self.path)
        self.assertIsNone(check_room_binding(duplicate, "Which rooms connect to room 7.16?", self.proposal()))

    def test_duplicate_native_guid_cannot_bind_multiple_authorized_rooms(self):
        self.rooms[1].GlobalId = self.rooms[0].GlobalId
        self.source.write(str(self.path))
        engine = IfcQueryEngine.open(self.path)
        identifier = engine.resolve_entity("7.16")
        where = {"kind": "compare", "field": {"kind": "native_identifier", "key": "ifc_guid"},
                 "operator": "eq", "value": {"kind": "text", "value": {"text": self.rooms[0].GlobalId}}}
        proposed = self.proposal([self.select(where)])
        self.assertIsNotNone(check_room_binding(engine, "Which rooms connect to room 7.16?", proposed))
        self.assertIsNone(check_room_binding(engine, "Which rooms connect to room 7.16?", proposed, {identifier}))
        where["field"]["key"] = "step_id"
        where["value"]["value"]["text"] = str(self.rooms[0].id())
        self.assertIsNone(check_room_binding(engine, "Which rooms connect to room 7.16?", self.proposal([self.select(where)])))


if __name__ == "__main__":
    unittest.main()

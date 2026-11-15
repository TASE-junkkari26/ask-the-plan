"""Native cutoff ties retain source objects, table cells and exact scope."""
from pathlib import Path
import math
import tempfile
import unittest

import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from ifc_engine.catalog import attribute_key
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_engine import sample_model


class IfcRankingTieTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "ranking.ifc"
        self.source, self.doors, _, _, self.ground, _ = sample_model(self.path)
        self.doors[0].OverallWidth = self.doors[1].OverallWidth = 1100.
        self.doors[2].OverallWidth = 900.

    def engine(self):
        self.source.write(str(self.path))
        return IfcQueryEngine.open(self.path)

    def add_ground_doors(self, number):
        doors = [self.source.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(),
            Name=f"Additional wide door {index}", OverallWidth=1100.) for index in range(number)]
        self.source.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(),
            RelatedElements=doors, RelatingStructure=self.ground)

    def rank(self, engine, *, include_ties=True, limit=1, exact=None, count=False):
        plan = engine.plan("door", operation="rank", property="OverallWidth", storey="Ground", limit=limit)
        plan.steps[1].operation.include_ties = include_ties
        if exact is not None:
            plan.scope.exact_entity_ids = [engine.resolve_entity(name) for name in exact]
        if count:
            plan.steps[2] = m.PlanStep(id="answer", operation=m.AggregateOperation(kind="aggregate",
                input_step_id="ranked", method="count"))
        return plan

    def execute(self, engine, plan, status="answered"):
        validate_plan(plan, engine.bundle, engine.capabilities)
        result = engine.execute(plan)
        self.assertEqual(result.status, status, result.model_dump_json())
        validate_bundle(engine.bundle)
        validate_result(result, engine.bundle, plan)
        return result

    def test_duplicate_native_widths_return_both_source_doors_and_count_them(self):
        engine = self.engine()
        plan = self.rank(engine, count=True)
        result = self.execute(engine, plan)
        expected = {engine.resolve_entity(name) for name in ("D1", "D2")}
        self.assertEqual(result.claims[0].value.value, 2)
        rank = next(node for node in result.calculations if node.plan_step_id == "ranked")
        self.assertEqual(set(rank.output.entity_ids), expected)
        self.assertEqual({fact.subject_id for fact in engine.bundle.facts if fact.id in rank.fact_ids}, expected)
        self.assertIn("1 additional tied source row(s) are included", result.explanation.text)

    def test_default_limit_and_existing_note_remain_unchanged(self):
        engine = self.engine()
        default = self.execute(engine, self.rank(engine, include_ties=False))
        self.assertEqual(len(default.claims[0].value.rows), 1)
        self.assertIn("1 additional source row(s) tie", default.explanation.text)
        all_ties = self.execute(engine, self.rank(engine))
        self.assertEqual(len(all_ties.claims[0].value.rows), 2)
        self.assertEqual(default.claims[0].value.rows[0], all_ties.claims[0].value.rows[0])
        repeated = self.execute(engine, self.rank(engine))
        self.assertEqual(repeated.claims[0].value, all_ties.claims[0].value)

    def test_hidden_equal_width_door_does_not_expand_the_captured_scope(self):
        engine = self.engine()
        result = self.execute(engine, self.rank(engine, exact=["D1"]))
        only = engine.resolve_entity("D1")
        self.assertEqual(len(result.claims[0].value.rows), 1)
        self.assertTrue(all(set(item.entity_ids) <= {only} for item in result.entity_sets))
        self.assertTrue(all(engine.facts[(only, attribute_key("OverallWidth"))][0].id in node.fact_ids
            for node in result.calculations if node.operation == "rank"))

    def test_table_cutoff_ties_keep_cells_members_and_excluded_source_objects(self):
        engine = self.engine()
        plan = engine.plan("door")
        width = attribute_key("OverallWidth")
        plan.steps = [plan.steps[0], m.PlanStep(id="rows", operation=m.ProjectOperation(kind="project",
            input_step_id="objects", fields=[m.FieldRef(kind="entity_id", key="entity_id"),
                m.FieldRef(kind="property", key=width)])), m.PlanStep(id="ranked", operation=m.RankOperation(
                    kind="rank", input_step_id="rows", field=m.FieldRef(kind="result_column", key=width),
                    direction="descending", limit=1, include_ties=True))]
        plan.outputs = {"answer": "ranked"}
        result = self.execute(engine, plan)
        self.assertEqual(len(result.claims[0].value.rows), 2)
        self.assertEqual(next(item for item in result.entity_sets if item.id == "set:ranked").count, 2)
        self.assertEqual(next(item for item in result.entity_sets if item.id == "set:ranked:excluded").entity_ids,
                         [engine.resolve_entity("D3")])
        self.assertTrue(any(binding.value_path == "/rows/1/" + width.replace("~", "~0").replace("/", "~1")
                            and binding.fact_ids for binding in result.claims[0].evidence))

    def test_ascending_cutoff_includes_ties_after_earlier_distinct_values(self):
        engine = self.engine()
        plan = engine.plan("door", operation="rank", property="OverallWidth", limit=2, direction="ascending")
        plan.steps[1].operation.include_ties = True
        result = self.execute(engine, plan)
        rows = result.claims[0].value.rows
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["entity_id"].entity_ids, [engine.resolve_entity("D3")])
        self.assertEqual({row["entity_id"].entity_ids[0] for row in rows[1:]},
                         {engine.resolve_entity("D1"), engine.resolve_entity("D2")})

    def test_equal_native_room_areas_tie_after_explicit_unit_conversion(self):
        for quantity in self.source.by_type("IfcQuantityArea"):
            if quantity.AreaValue == 21.:
                quantity.AreaValue = 19.
        engine = self.engine()
        plan = engine.plan("space", operation="rank", property="Qto_SpaceBaseQuantities.NetFloorArea", limit=1)
        plan.steps[1].operation.include_ties = True
        result = self.execute(engine, plan)
        rows = result.claims[0].value.rows
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["entity_id"].entity_ids[0] for row in rows},
                         {engine.resolve_entity("7.16"), engine.resolve_entity("Office")})
        # Two source quantity records for 7.16 still represent one canonical room.
        self.assertEqual(next(item for item in result.entity_sets if item.id == "set:ranked").count, 2)

    def test_close_exact_native_widths_do_not_become_estimated_roundoff_ties(self):
        self.doors[1].OverallWidth = 1100.000000000001
        engine = self.engine()
        result = self.execute(engine, self.rank(engine))
        self.assertEqual(len(result.claims[0].value.rows), 1)
        self.assertEqual(result.claims[0].value.rows[0]["entity_id"].entity_ids, [engine.resolve_entity("D2")])
        self.assertNotIn("computation round-off", result.explanation.text if result.explanation else "")

    def test_estimated_derived_cutoff_tolerance_stops_at_sixty_four_ulps(self):
        engine = self.engine()
        def area(value):
            return m.QuantityValue(kind="quantity", magnitude=str(value), unit_id="unit:m2", quantity_kind="area",
                basis="footprint", quality="estimated", unit_resolution="derived")
        inside = 16. + 64 * math.ulp(16.)
        beyond = 16. + 65 * math.ulp(16.)
        self.assertTrue(engine._ranking_tie(area(inside), area(16.))[0])
        self.assertFalse(engine._ranking_tie(area(beyond), area(16.))[0])
        self.assertEqual(engine._ranking_tie(area(inside), area(16.))[1],
                         engine._ranking_tie(area(beyond), area(16.))[1])

    def test_exactly_one_hundred_tied_outputs_are_supported(self):
        self.add_ground_doors(98)
        engine = self.engine()
        result = self.execute(engine, self.rank(engine, count=True))
        self.assertEqual(result.claims[0].value.value, 100)
        rank = next(node for node in result.calculations if node.plan_step_id == "ranked")
        self.assertEqual(len(rank.output.entity_ids), 100)

    def test_more_than_one_hundred_cutoff_ties_asks_without_a_truncated_claim(self):
        self.add_ground_doors(99)
        engine = self.engine()
        result = self.execute(engine, self.rank(engine), status="needs_clarification")
        self.assertFalse(result.claims)
        self.assertIn("101 rows", result.issues[0].message.text)
        self.assertTrue(result.issues[0].fact_ids)
        self.assertTrue(result.issues[0].anchor_ids)
        default = self.execute(engine, self.rank(engine, include_ties=False))
        self.assertEqual(len(default.claims[0].value.rows), 1)
        self.assertIn("100 additional source row(s) tie", default.explanation.text)

    def test_requested_limit_above_bound_is_allowed_when_actual_output_is_small(self):
        engine = self.engine()
        result = self.execute(engine, self.rank(engine, limit=200))
        self.assertEqual(len(result.claims[0].value.rows), 2)


if __name__ == "__main__":
    unittest.main()

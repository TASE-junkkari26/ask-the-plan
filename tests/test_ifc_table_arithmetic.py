"""Source-bound arithmetic, units, scope and table-cell calculation evidence."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from ifc_engine.catalog import POLICIES, attribute_key
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_engine import sample_model


class IfcArithmeticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "arithmetic.ifc"
        sample_model(cls.path)
        cls.loaded = IfcQueryEngine.open(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.engine = IfcQueryEngine(self.loaded.bundle.model_copy(deep=True), schema=self.loaded.schema)

    def select(self, name, concept, labels=None):
        where = None
        if labels is not None:
            where = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"), operator="in",
                value=m.ListValue(kind="list", items=[m.ReferencesValue(kind="references", entity_ids=[self.engine.resolve_entity(label)]) for label in labels]))
        return m.PlanStep(id=name, operation=m.SelectOperation(kind="select", concept_ids=["concept:" + concept],
            count_policy=POLICIES["all_matches"], where=where))

    def aggregate(self, name, source, method="count", property=None):
        return m.PlanStep(id=name, operation=m.AggregateOperation(kind="aggregate", input_step_id=source, method=method,
            field=m.FieldRef(kind="property", key=self.engine.resolve_property(property)) if property else None))

    def execute(self, steps, output=None, scope=None, status="answered"):
        plan = m.QueryPlan(id="plan:arithmetic", request_id="request:arithmetic", scope=scope or self.engine.scope(),
                           steps=steps, outputs={"answer": output or steps[-1].id})
        validate_plan(plan, self.engine.bundle, self.engine.capabilities)
        result = self.engine.execute(plan)
        self.assertEqual(result.status, status, result.model_dump_json())
        validate_bundle(self.engine.bundle)
        validate_result(result, self.engine.bundle, plan)
        return result

    def arithmetic(self, operator, unit=None):
        return m.PlanStep(id="derived", operation=m.ArithmeticOperation(kind="arithmetic", input_step_ids=["left", "right"],
                                                                       operator=operator, output_unit_id=unit))

    def test_ratio_percent_preserves_both_computed_source_counts_and_scope(self):
        result = self.execute([self.select("doors", "door"), self.aggregate("left", "doors"),
            self.select("rooms", "space"), self.aggregate("right", "rooms"), self.arithmetic("divide", "unit:%")])
        value = result.claims[0].value
        self.assertEqual((Decimal(value.magnitude), value.unit_id, value.quantity_kind), (Decimal(150), "unit:%", "ratio"))
        node = next(node for node in result.calculations if node.plan_step_id == "derived")
        self.assertEqual(node.operation, "divide")
        self.assertEqual(node.input_node_ids[:2], ["calculation:left", "calculation:right"])
        self.assertEqual(node.rule_key, "ifc.scalar_arithmetic.v1:divide")
        self.assertIsNone(node.included_set_id)
        self.assertEqual(result.claims[0].evidence[0].entity_set_ids, [])

    def test_floor_elevation_difference_converts_millimetres_to_metres(self):
        result = self.execute([self.select("upper", "storey", ["Upper"]), self.aggregate("left", "upper", "sum", "Elevation"),
            self.select("ground", "storey", ["Ground"]), self.aggregate("right", "ground", "sum", "Elevation"), self.arithmetic("subtract", "unit:m")])
        self.assertEqual(Decimal(result.claims[0].value.magnitude), Decimal(3))
        self.assertTrue(result.claims[0].evidence[0].fact_ids)

    def test_length_product_derives_area_with_native_input_evidence(self):
        result = self.execute([self.select("a", "door", ["D1"]), self.aggregate("left", "a", "sum", "OverallWidth"),
            self.select("b", "door", ["D2"]), self.aggregate("right", "b", "sum", "OverallWidth"), self.arithmetic("multiply", "unit:m2")])
        self.assertEqual(Decimal(result.claims[0].value.magnitude), Decimal("0.99"))
        self.assertEqual(result.claims[0].value.quantity_kind, "area")
        self.assertEqual(len(result.claims[0].evidence[0].fact_ids), 2)

    def test_zero_denominator_is_missing_information_and_zero_numerator_is_valid(self):
        base = [self.select("a", "door"), self.aggregate("left", "a"), self.select("b", "window"), self.aggregate("right", "b")]
        result = self.execute([*base, self.arithmetic("divide")], status="missing_information")
        self.assertFalse(result.claims)
        reverse = m.PlanStep(id="derived", operation=m.ArithmeticOperation(kind="arithmetic", input_step_ids=["right", "left"], operator="divide"))
        result = self.execute([*base, reverse])
        self.assertEqual(Decimal(result.claims[0].value.magnitude), 0)

    def test_arithmetic_does_not_add_different_dimensions(self):
        self.execute([self.select("a", "door", ["D1"]), self.aggregate("left", "a", "sum", "OverallWidth"),
            self.select("b", "space"), self.aggregate("right", "b", "sum", "Qto_SpaceBaseQuantities.NetFloorArea"),
            self.arithmetic("add")], status="conflicting_evidence")

    def test_same_dimension_different_net_gross_bases_are_not_added(self):
        key = self.engine.resolve_property("Qto_SpaceBaseQuantities.NetFloorArea")
        for fact in self.engine.facts[self.engine.resolve_entity("Office"), key]:
            fact.value.basis = "gross"
        base = [self.select("a", "space", ["7.16"]), self.aggregate("left", "a", "sum", key),
                self.select("b", "space", ["Office"]), self.aggregate("right", "b", "sum", key)]
        self.execute([*base, self.arithmetic("add")], status="conflicting_evidence")
        ratio = self.execute([*base, self.arithmetic("divide", "unit:1")], status="partial")
        self.assertEqual(ratio.claims[0].value.quantity_kind, "ratio")

    def test_estimated_source_operands_keep_estimated_arithmetic_and_conversion_quality(self):
        key = self.engine.resolve_property("OverallWidth")
        for fact in self.engine.facts[self.engine.resolve_entity("D1"), key]:
            fact.value.quality = "estimated"
        result = self.execute([self.select("a", "door", ["D1"]), self.aggregate("left", "a", "sum", key),
            self.select("b", "door", ["D2"]), self.aggregate("right", "b", "sum", key), self.arithmetic("divide", "unit:1")], status="partial")
        self.assertEqual(result.claims[0].quality, "estimated")
        self.assertEqual(result.claims[0].value.quality, "estimated")
        self.assertEqual(next(node for node in result.calculations if node.plan_step_id == "derived").quality, "estimated")

    def test_count_subtraction_can_retain_a_signed_calculated_number(self):
        result = self.execute([self.select("a", "window"), self.aggregate("left", "a"),
            self.select("b", "door"), self.aggregate("right", "b"), self.arithmetic("subtract")])
        self.assertEqual((result.claims[0].value.quantity_kind, Decimal(result.claims[0].value.magnitude)), ("number", -3))

    def test_view_scope_is_enforced_for_both_operands(self):
        scope = self.engine.scope()
        scope.exact_entity_ids = [self.engine.resolve_entity("D1"), self.engine.resolve_entity("7.16")]
        result = self.execute([self.select("a", "door"), self.aggregate("left", "a"),
            self.select("b", "space"), self.aggregate("right", "b"), self.arithmetic("divide")], scope=scope)
        self.assertEqual(Decimal(result.claims[0].value.magnitude), 1)
        self.assertTrue(all(set(s.entity_ids) <= set(scope.exact_entity_ids) for s in result.entity_sets))

    def projected(self, concept="door", labels=("D1", "D2"), property="OverallWidth"):
        key = self.engine.resolve_property(property)
        return [self.select("objects", concept, labels), m.PlanStep(id="rows", operation=m.ProjectOperation(kind="project",
            input_step_id="objects", fields=[m.FieldRef(kind="entity_id", key="object"), m.FieldRef(kind="label", key="name"),
                                            m.FieldRef(kind="property", key=key)]))], key

    def test_row_arithmetic_computes_typed_values_with_cell_operand_nodes(self):
        steps, key = self.projected()
        steps.append(m.PlanStep(id="calculated", operation=m.TableCalculateOperation(kind="table_calculate", input_step_id="rows",
            operator="multiply", fields=[m.FieldRef(kind="result_column", key=key)] * 2, value_key="area", output_unit_id="unit:m2")))
        result = self.execute(steps)
        self.assertEqual({Decimal(row["area"].magnitude) for row in result.claims[0].value.rows}, {Decimal("0.81"), Decimal("1.21")})
        products = [node for node in result.calculations if node.operation == "multiply"]
        self.assertEqual(len(products), 2)
        self.assertTrue(all(len(node.input_node_ids) == 2 and node.fact_ids for node in products))

    def test_percent_of_total_has_denominator_evidence_for_each_cell(self):
        steps, key = self.projected()
        steps.append(m.PlanStep(id="shares", operation=m.TableCalculateOperation(kind="table_calculate", input_step_id="rows",
            operator="percent_of_total", fields=[m.FieldRef(kind="result_column", key=key)], value_key="percentage")))
        result = self.execute(steps)
        self.assertEqual({Decimal(row["percentage"].magnitude) for row in result.claims[0].value.rows}, {Decimal(45), Decimal(55)})
        ratios = [node for node in result.calculations if node.operation == "divide"]
        self.assertEqual(len(ratios), 2)
        self.assertTrue(all(len(node.fact_ids) == 2 for node in ratios))
        self.assertTrue(any(node.operation == "add" for node in result.calculations))

    def test_consecutive_levels_retain_both_names_and_original_elevation_facts(self):
        steps, key = self.projected("storey", ("Upper", "Ground"), "Elevation")
        steps.append(m.PlanStep(id="heights", operation=m.TableCalculateOperation(kind="table_calculate", input_step_id="rows",
            operator="consecutive_difference", fields=[m.FieldRef(kind="result_column", key=key)],
            order_by=m.FieldRef(kind="result_column", key=key), value_key="floor_to_floor", output_unit_id="unit:m")))
        result = self.execute(steps)
        rows = result.claims[0].value.rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"].value.text, "Ground")
        self.assertEqual(rows[0]["following"].fields["name"].value.text, "Upper")
        self.assertEqual(Decimal(rows[0]["floor_to_floor"].magnitude), 3)
        difference = next(node for node in result.calculations if node.operation == "subtract")
        self.assertEqual(len(difference.fact_ids), 2)

    def test_duplicate_level_elevations_request_clarification_instead_of_inventing_order(self):
        key = self.engine.resolve_property("Elevation")
        for fact in self.engine.facts[self.engine.resolve_entity("Upper"), key]:
            fact.value.magnitude = "0"
            fact.value.normalized.magnitude = "0"
        steps, key = self.projected("storey", ("Upper", "Ground"), "Elevation")
        steps.append(m.PlanStep(id="heights", operation=m.TableCalculateOperation(kind="table_calculate", input_step_id="rows",
            operator="consecutive_difference", fields=[m.FieldRef(kind="result_column", key=key)], order_by=m.FieldRef(kind="result_column", key=key))))
        self.execute(steps, status="needs_clarification")

    def test_percentages_reject_an_all_zero_distribution(self):
        key = self.engine.resolve_property("OverallWidth")
        for label in ("D1", "D2"):
            for fact in self.engine.facts[self.engine.resolve_entity(label), key]:
                fact.value.magnitude = "0"
                fact.value.normalized.magnitude = "0"
        steps, key = self.projected()
        steps.append(m.PlanStep(id="shares", operation=m.TableCalculateOperation(kind="table_calculate", input_step_id="rows",
            operator="percent_of_total", fields=[m.FieldRef(kind="result_column", key=key)], value_key="percentage")))
        self.execute(steps, status="missing_information")

    def test_native_composite_properties_project_without_becoming_sortable_scalars(self):
        value = m.ListValue(kind="list", items=[m.RecordValue(kind="record", fields={"material": m.TextValue(kind="text", value=m.LocalizedText(text="Insulation"))})])
        self.assertEqual(self.engine._value_key(value), self.engine._value_key(value.model_copy(deep=True)))
        with self.assertRaisesRegex(ValueError, "no scalar comparison"):
            self.engine._scalar(value)

    def test_ranked_cutoff_ties_preserve_the_limit_and_explain_other_matching_objects(self):
        path = Path(self.directory.name) / "tied-widths.ifc"
        source, doors, *_ = sample_model(path)
        doors[1].OverallWidth = doors[0].OverallWidth
        source.write(str(path))
        engine = IfcQueryEngine.open(path)
        result = engine.query("door", operation="rank", property="OverallWidth", storey="Ground", limit=1)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(len(result.claims[0].value.rows), 1)
        self.assertIn("1 additional source row(s) tie", result.explanation.text)
        key = attribute_key("OverallWidth")
        column = next(column for column in result.claims[0].value.columns if column.key == key)
        self.assertEqual(column.label.text, "OverallWidth")
        repeated = engine.query("door", operation="rank", property="OverallWidth", storey="Ground", limit=1)
        self.assertEqual(result.claims[0].value.rows, repeated.claims[0].value.rows)

    def test_missing_group_labels_are_explicit_exact_bins_with_partial_status(self):
        key = self.engine.resolve_property("Pset_DoorCommon.FireRating")
        steps = [self.select("doors", "door"), m.PlanStep(id="types", operation=m.AggregateOperation(kind="aggregate",
            input_step_id="doors", method="count", group_by=[m.FieldRef(kind="property", key=key)], missing_groups="unclassified"))]
        result = self.execute(steps, status="partial")
        rows = result.claims[0].value.rows
        self.assertEqual(sum(row["value"].value for row in rows), 3)
        missing = [row for row in rows if row[key].kind == "unavailable"]
        self.assertEqual((len(missing), missing[0][key].reason, missing[0]["value"].value), (1, "not_in_source", 1))
        self.assertEqual(result.claims[0].quality, "exact")
        self.assertEqual(result.issues[0].entity_ids, [self.engine.resolve_entity("D3")])
        index = next(index for index, row in enumerate(rows) if row[key].kind == "unavailable")
        pointer = f"/rows/{index}/" + key.replace("~", "~0").replace("/", "~1")
        binding = next(binding for binding in result.claims[0].evidence if binding.value_path == pointer)
        sets = {item.id: item for item in result.entity_sets}
        self.assertEqual(sets[binding.entity_set_ids[0]].entity_ids, [self.engine.resolve_entity("D3")])
        self.assertTrue(binding.anchor_ids)
        successful_facts = {fact.id for fact in self.engine.bundle.facts if fact.status == "present"}
        self.assertTrue(all(set(node.fact_ids) <= successful_facts for node in result.calculations))

    def test_missing_group_default_fails_instead_of_hiding_unclassified_objects(self):
        key = self.engine.resolve_property("Pset_DoorCommon.FireRating")
        self.execute([self.select("doors", "door"), m.PlanStep(id="types", operation=m.AggregateOperation(kind="aggregate",
            input_step_id="doors", method="count", group_by=[m.FieldRef(kind="property", key=key)]))], status="missing_information")


if __name__ == "__main__":
    unittest.main()

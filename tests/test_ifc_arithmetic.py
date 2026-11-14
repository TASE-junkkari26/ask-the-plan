"""Executed scalar quantities retain source inputs, dimensions and uncertainty."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from contracts import models as m
from contracts.validation import validate_plan, validate_result
from ifc_engine.catalog import POLICIES
from ifc_engine.engine import IfcQueryEngine
from ifc_engine.scalar_math import ScalarArithmeticError, scalar_arithmetic
from ifc_engine.units import standard_units
from tests.test_ifc_engine import sample_model


def quantity(number, unit="m", kind="length", basis="modeled", quality="exact"):
    return m.QuantityValue(kind="quantity", magnitude=number, unit_id="unit:" + unit,
        quantity_kind=kind, basis=basis, unit_resolution="explicit", quality=quality)


class ScalarMathTests(unittest.TestCase):
    def setUp(self):
        self.units = standard_units()

    def test_decimal_addition_and_unit_conversion_are_exact(self):
        value, quality = scalar_arithmetic([quantity("0.1"), quantity("200", "mm")], "add", self.units, "unit:m")
        self.assertEqual(Decimal(value.magnitude), Decimal("0.3"))
        self.assertEqual(quality, "exact")

    def test_product_dimension_and_percentage(self):
        area, _ = scalar_arithmetic([quantity("2"), quantity("3000", "mm")], "multiply", self.units)
        self.assertEqual(area.quantity_kind, "area")
        self.assertEqual(Decimal(area.magnitude), Decimal(6))
        self.units["unit:%"] = m.Unit(id="unit:%", symbol="%", kind="physical",
            dimension=(0, 0, 0, 0, 0, 0, 0), si_multiplier="0.01")
        percent, _ = scalar_arithmetic([m.CountValue(kind="count", value=1), m.CountValue(kind="count", value=4)],
                                      "divide", self.units, "unit:%")
        self.assertEqual(Decimal(percent.magnitude), Decimal(25))
        self.assertEqual(percent.quantity_kind, "ratio")

    def test_repeating_decimal_is_estimated(self):
        value, quality = scalar_arithmetic([m.CountValue(kind='count', value=1),
            m.CountValue(kind='count', value=3)], 'divide', self.units)
        self.assertEqual(quality, 'estimated')
        self.assertEqual(value.quality, 'estimated')

    def test_incompatible_dimensions_or_quantity_bases_fail(self):
        for values in ([quantity("2"), quantity("3", "m2", "area")],
                       [quantity("2", basis="net"), quantity("3", basis="gross")]):
            with self.assertRaises(ScalarArithmeticError):
                scalar_arithmetic(values, "add", self.units)

    def test_zero_denominator_unknown_unit_and_unsourced_currency_conversion_fail(self):
        with self.assertRaisesRegex(ScalarArithmeticError, "zero"):
            scalar_arithmetic([m.CountValue(kind="count", value=1), m.CountValue(kind="count", value=0)], "divide", self.units)
        with self.assertRaisesRegex(ScalarArithmeticError, "unresolved"):
            scalar_arithmetic([quantity("2", "unknown"), quantity("3")], "multiply", self.units)
        for symbol in ("EUR", "USD"):
            self.units["unit:" + symbol] = m.Unit(id="unit:" + symbol, symbol=symbol, kind="physical",
                dimension=(0, 0, 0, 0, 0, 0, 0), si_multiplier="1")
        with self.assertRaisesRegex(ScalarArithmeticError, "exchange rate"):
            scalar_arithmetic([quantity("2", "EUR", "currency"), quantity("3", "USD", "currency")], "add", self.units)

    def test_bounds_and_estimates_propagate_conservatively(self):
        value, quality = scalar_arithmetic([quantity("2", quality="lower_bound"), quantity("3", quality="upper_bound")], "subtract", self.units)
        self.assertEqual(quality, "lower_bound")
        self.assertEqual(value.quality, "lower_bound")
        _, quality = scalar_arithmetic([quantity("2", quality="lower_bound"), quantity("3", quality="upper_bound")], "multiply", self.units)
        self.assertEqual(quality, "estimated")
        _, quality = scalar_arithmetic([quantity("2", quality="estimated"), quantity("3")], "add", self.units)
        self.assertEqual(quality, "estimated")


class IfcArithmeticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        path = Path(cls.directory.name) / "arithmetic.ifc"
        sample_model(path)
        cls.loaded = IfcQueryEngine.open(path)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.engine = IfcQueryEngine(self.loaded.bundle.model_copy(deep=True))

    def average_area_plan(self):
        plan = self.engine.plan("space", operation="sum", property="Qto_SpaceBaseQuantities.NetFloorArea")
        plan.steps.extend([
            m.PlanStep(id="rooms", operation=m.AggregateOperation(kind="aggregate", input_step_id="objects", method="count")),
            m.PlanStep(id="average", operation=m.ArithmeticOperation(kind="arithmetic", input_step_ids=["answer", "rooms"], operator="divide"))])
        plan.outputs = {"average_area": "average"}
        plan.required_capabilities = ["arithmetic.divide"]
        return plan

    def test_average_area_executes_with_all_source_inputs_and_matching_coverage(self):
        plan = self.average_area_plan()
        validate_plan(plan, self.engine.bundle, self.engine.capabilities)
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered")
        self.assertEqual(Decimal(result.claims[0].value.magnitude), Decimal(20))
        self.assertEqual(result.claims[0].value.unit_id, "unit:m2")
        node = result.calculations[-1]
        self.assertEqual(node.operation, "divide")
        self.assertEqual(node.input_node_ids, ["calculation:answer", "calculation:rooms"])
        self.assertTrue(node.fact_ids)
        self.assertTrue(node.anchor_ids)
        validate_result(result, self.engine.bundle, plan)

    def test_estimated_source_quantities_propagate_to_partial_arithmetic(self):
        for fact in self.engine.bundle.facts:
            if isinstance(fact.value, m.QuantityValue) and fact.value.quantity_kind == "area":
                fact.value.quality = "estimated"
        plan = self.average_area_plan()
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.claims[0].quality, "estimated")
        self.assertEqual(result.claims[0].value.quality, "estimated")
        validate_result(result, self.engine.bundle, plan)

    def test_incompatible_addition_is_a_typed_failure(self):
        plan = self.average_area_plan()
        plan.steps[-1].operation.operator = "add"
        plan.required_capabilities = []
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "conflicting_evidence")
        self.assertFalse(result.claims)

    def test_division_by_source_zero_is_missing_information_not_zero(self):
        plan = self.engine.plan("door")
        plan.steps.extend([
            m.PlanStep(id="windows", operation=m.SelectOperation(kind="select", concept_ids=["concept:window"], count_policy=POLICIES["all_matches"])),
            m.PlanStep(id="zero", operation=m.AggregateOperation(kind="aggregate", input_step_id="windows", method="count")),
            m.PlanStep(id="ratio", operation=m.ArithmeticOperation(kind="arithmetic", input_step_ids=["answer", "zero"], operator="divide"))])
        plan.outputs = {"ratio": "ratio"}
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "missing_information")
        self.assertFalse(result.claims)
        self.assertIn("zero", result.issues[0].message.text)

    def test_measurement_stays_unimplemented(self):
        plan = self.engine.plan("space")
        plan.steps[-1].operation = m.MeasureOperation(kind="measure", input_step_id="objects", metric="area", output_unit_id="unit:m2", basis="net")
        self.assertEqual(self.engine.execute(plan).status, "unsupported_operation")

    def test_count_arithmetic_exposes_inputs_without_inventing_result_members(self):
        plan = self.engine.plan('door')
        plan.steps.extend([
            m.PlanStep(id='one', operation=m.SelectOperation(kind='select', concept_ids=['concept:door'],
                count_policy=POLICIES['all_matches'], where=m.ComparePredicate(kind='compare',
                    field=m.FieldRef(kind='label', key='label'), operator='eq',
                    value=m.TextValue(kind='text', value=m.LocalizedText(text='D3'))))),
            m.PlanStep(id='one_count', operation=m.AggregateOperation(kind='aggregate', input_step_id='one', method='count')),
            m.PlanStep(id='difference', operation=m.ArithmeticOperation(kind='arithmetic',
                input_step_ids=['answer', 'one_count'], operator='subtract'))])
        plan.outputs = {'difference': 'difference'}
        result = self.engine.execute(plan)
        self.assertEqual(result.status, 'answered')
        self.assertEqual(result.claims[0].value.value, 2)
        self.assertFalse(result.claims[0].evidence[0].entity_set_ids)
        self.assertIsNone(result.calculations[-1].included_set_id)
        self.assertEqual(result.calculations[-1].input_node_ids, ['calculation:answer', 'calculation:one_count'])
        validate_result(result, self.engine.bundle, plan)


if __name__ == "__main__":
    unittest.main()

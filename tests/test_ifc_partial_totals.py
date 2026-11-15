"""Explicit subtotals retain missing native quantities as nonnegative unknowns."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_geometry import geometry_source


class PartialNativeQuantityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "partial-quantities.ifc"
        self.model, self.objects = geometry_source(self.path)
        self.wall = self.objects["wall"]
        self.unknown = self.root("IfcWall", Name="Unresolved source wall")

    def root(self, kind, **fields):
        return self.model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **fields)

    def recorded(self, number=5.):
        material = self.model.create_entity("IfcMaterial", Name="Concrete")
        self.root("IfcRelAssociatesMaterial", RelatedObjects=[self.wall], RelatingMaterial=material)
        unit = self.model.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE")
        volume = self.model.create_entity("IfcQuantityVolume", Name="NetVolume", VolumeValue=number, Unit=unit)
        definition = self.root("IfcElementQuantity", Name="Qto_WallBaseQuantities", Quantities=[volume])
        self.root("IfcRelDefinesByProperties", RelatedObjects=[self.wall], RelatingPropertyDefinition=definition)

    def layered(self):
        layers = [self.model.create_entity("IfcMaterialLayer", Material=self.model.create_entity("IfcMaterial", Name=name),
            LayerThickness=number) for name, number in [("Concrete", .15), ("Insulation", .05)]]
        definition = self.model.create_entity("IfcMaterialLayerSet", MaterialLayers=layers)
        usage = self.model.create_entity("IfcMaterialLayerSetUsage", ForLayerSet=definition, LayerSetDirection="AXIS2",
            DirectionSense="POSITIVE", OffsetFromReferenceLine=0.)
        self.root("IfcRelAssociatesMaterial", RelatedObjects=[self.wall], RelatingMaterial=usage)

    def engine(self):
        self.model.write(str(self.path))
        return IfcQueryEngine.open(self.path)

    def plan(self, engine, *, source="material", names=("Concrete",), partial=True, exact=None, output_unit=None):
        plan = engine.plan("wall")
        if exact is not None:
            plan.scope.exact_entity_ids = [engine.resolve_entity(name) for name in exact]
        producer = (m.MaterialQuantityOperation(kind="material_quantity", input_step_id="objects", material_names=list(names))
                    if source == "material" else m.MeasureOperation(kind="measure", input_step_id="objects",
                        metric="area" if source == "area" else "volume", basis="net_opaque_face" if source == "area" else "solid",
                        output_unit_id="unit:m2" if source == "area" else "unit:m3"))
        plan.steps = [plan.steps[0], m.PlanStep(id="quantities", operation=producer),
            m.PlanStep(id="total", operation=m.AggregateOperation(kind="aggregate", input_step_id="quantities", method="sum",
                field=m.FieldRef(kind="result_column", key="volume" if source == "material" else "value"),
                missing_values="partial" if partial else "fail", output_unit_id=output_unit))]
        plan.outputs = {"answer": "total"}
        return plan

    def execute(self, engine, plan, status="partial"):
        validate_plan(plan, engine.bundle, engine.capabilities)
        result = engine.execute(plan)
        self.assertEqual(result.status, status, result.model_dump_json())
        validate_bundle(engine.bundle)
        validate_result(result, engine.bundle, plan)
        return result

    def test_recorded_material_subtotal_retains_unknown_subject_and_all_cell_inputs(self):
        self.recorded()
        engine = self.engine()
        result = self.execute(engine, self.plan(engine, output_unit="unit:ft3"))
        claim = result.claims[0]
        self.assertEqual(claim.quality, "lower_bound")
        self.assertEqual(claim.value.quality, "lower_bound")
        self.assertAlmostEqual(float(claim.value.magnitude), 5 / .028316846592)
        unknown = engine.resolve_entity(self.unknown.GlobalId)
        coverage = next(item for item in engine.bundle.coverage if item.id in claim.coverage_ids)
        self.assertEqual(coverage.unresolved_entity_ids, [unknown])
        total = next(node for node in result.calculations if node.plan_step_id == "total")
        self.assertEqual(total.rule_key, "ifc.partial-nonnegative-sum.v1")
        self.assertEqual(len(total.input_node_ids), 3)
        lookups = [node for node in result.calculations if ":source-cell:" in node.id and node.operation == "lookup"]
        self.assertEqual({node.output.kind for node in lookups}, {"quantity", "unavailable"})
        self.assertTrue(all(node.material_evidence and node.anchor_ids for node in lookups))

    def test_default_failure_is_preserved_and_complete_partial_mode_is_an_ordinary_total(self):
        self.recorded()
        engine = self.engine()
        self.execute(engine, self.plan(engine, partial=False), "incomplete_coverage")
        result = self.execute(engine, self.plan(engine, exact=[self.wall.GlobalId]), "answered")
        self.assertEqual(result.claims[0].quality, "exact")
        self.assertEqual(Decimal(result.claims[0].value.magnitude), 5)

    def test_known_no_match_zero_with_unknown_is_a_partial_bound_not_physical_zero(self):
        self.recorded()
        engine = self.engine()
        result = self.execute(engine, self.plan(engine, names=["Insulation"]))
        self.assertEqual(Decimal(result.claims[0].value.magnitude), 0)
        self.assertEqual(result.claims[0].quality, "lower_bound")
        self.assertIn("zero subtotal does not establish physical absence", result.explanation.text)

    def test_all_unavailable_materials_yield_missing_information_without_a_number(self):
        engine = self.engine()
        result = self.execute(engine, self.plan(engine), "missing_information")
        self.assertFalse(result.claims)

    def test_area_subtotal_keeps_its_one_face_basis_and_unknown_geometry(self):
        self.layered()
        engine = self.engine()
        result = self.execute(engine, self.plan(engine, source="area"))
        self.assertAlmostEqual(float(result.claims[0].value.magnitude), 15.)
        self.assertEqual(result.claims[0].value.basis, "net_opaque_face")
        self.assertEqual(result.claims[0].quality, "lower_bound")
        self.execute(engine, self.plan(engine, source="area", partial=False), "incomplete_coverage")

    def test_measured_volume_does_not_gain_an_arbitrary_partial_sum_assumption(self):
        engine = self.engine()
        result = self.execute(engine, self.plan(engine, source="volume"), "unsupported_operation")
        self.assertFalse(result.claims)

    def test_missing_property_mean_and_unproven_result_columns_are_not_enabled(self):
        self.recorded()
        engine = self.engine()
        plan = self.plan(engine)
        plan.steps[-1].operation.method = "mean"
        self.assertEqual(engine.execute(plan).status, "unsupported_operation")
        from ifc_engine.partial_totals import execute_partial_sum
        def strip_lineage(engine, state, operation, step_id, members):
            state.cells[0]["volume"].source_record = None
            return execute_partial_sum(engine, state, operation, step_id, members)
        with patch("ifc_engine.partial_totals.execute_partial_sum", side_effect=strip_lineage):
            self.execute(engine, self.plan(engine), "unsupported_operation")

    def test_negative_or_incompatible_source_cells_are_rejected(self):
        self.recorded()
        engine = self.engine()
        from ifc_engine.partial_totals import execute_partial_sum
        for change in ("negative", "basis"):
            def alter(engine, state, operation, step_id, members):
                value = next(row["volume"] for row in state.value.rows if row["volume"].kind == "quantity")
                if change == "negative":
                    value.magnitude = "-5"
                else:
                    value.basis = "gross"
                return execute_partial_sum(engine, state, operation, step_id, members)
            with patch("ifc_engine.partial_totals.execute_partial_sum", side_effect=alter):
                self.execute(engine, self.plan(engine), "conflicting_evidence")

    def test_known_and_unknown_material_cells_on_one_host_keep_that_host_unresolved(self):
        self.layered()
        engine = self.engine()
        from ifc_engine.material_quantities import execute_material_quantity
        def interrupted(engine, state, operation, members):
            execute_material_quantity(engine, state, operation, members)
            index = next(i for i, row in enumerate(state.value.rows) if row["material"].kind == "text"
                         and row["material"].value.text == "Insulation")
            subject = state.material_records[index]["subject_id"]
            state.value.rows[index]["volume"] = m.UnavailableValue(kind="unavailable", reason="unknown", explanation="Cell calculation was not completed.")
            state.value.rows[index]["method"] = m.TextValue(kind="text", value=m.LocalizedText(text="unavailable"))
            state.cells[index]["volume"].evidence_kind = "unavailable"
            state.material_records[index].update(volume_m3=None, status="unavailable", method="unavailable")
            state.unresolved.add(subject)
            state.coverage_complete = False
        with patch("ifc_engine.material_quantities.execute_material_quantity", side_effect=interrupted):
            result = self.execute(engine, self.plan(engine, names=(), exact=[self.wall.GlobalId]))
        self.assertAlmostEqual(float(result.claims[0].value.magnitude), 2.25)
        coverage = next(item for item in engine.bundle.coverage if item.id in result.claims[0].coverage_ids)
        self.assertEqual(coverage.unresolved_entity_ids, [engine.resolve_entity(self.wall.GlobalId)])

    def test_bounds_cannot_enter_scalar_arithmetic(self):
        self.recorded()
        engine = self.engine()
        plan = self.plan(engine)
        plan.steps.append(m.PlanStep(id="ratio", operation=m.ArithmeticOperation(kind="arithmetic",
            input_step_ids=["total", "total"], operator="divide")))
        plan.outputs = {"answer": "ratio"}
        self.execute(engine, plan, "incomplete_coverage")


if __name__ == "__main__":
    unittest.main()

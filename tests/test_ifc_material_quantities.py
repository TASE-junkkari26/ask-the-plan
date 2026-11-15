"""Material amounts require actual source assignment and verified volume bases."""
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


class MaterialQuantityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "material-volumes.ifc"
        self.source, self.objects = geometry_source(self.path)
        self.wall = self.objects["wall"]

    def root(self, kind, **options):
        return self.source.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **options)

    def homogeneous(self, name="Concrete"):
        material = self.source.create_entity("IfcMaterial", Name=name)
        self.root("IfcRelAssociatesMaterial", RelatedObjects=[self.wall], RelatingMaterial=material)
        return material

    def layers(self, *, names=("Concrete", "Insulation"), thicknesses=(.1, .1), usage=True):
        layers = [self.source.create_entity("IfcMaterialLayer", Material=self.source.create_entity("IfcMaterial", Name=name),
            LayerThickness=thickness) for name, thickness in zip(names, thicknesses)]
        definition = self.source.create_entity("IfcMaterialLayerSet", MaterialLayers=layers, LayerSetName="Native layers")
        assignment = self.source.create_entity("IfcMaterialLayerSetUsage", ForLayerSet=definition, LayerSetDirection="AXIS2",
            DirectionSense="POSITIVE", OffsetFromReferenceLine=0.) if usage else definition
        self.root("IfcRelAssociatesMaterial", RelatedObjects=[self.wall], RelatingMaterial=assignment)
        return layers, assignment

    def volume(self, value, *, name="NetVolume", owner=None):
        unit = self.source.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE")
        record = self.source.create_entity("IfcQuantityVolume", Name=name, VolumeValue=value, Unit=unit)
        definition = self.root("IfcElementQuantity", Name="BaseQuantities", Quantities=[record])
        self.root("IfcRelDefinesByProperties", RelatedObjects=[owner or self.wall], RelatingPropertyDefinition=definition)
        return record

    def engine(self, deferred=False):
        self.source.write(str(self.path))
        engine = IfcQueryEngine.open(self.path, defer_properties=deferred)
        if engine.hydrator:
            self.addCleanup(engine.hydrator.close)
        return engine

    def plan(self, engine, *, names=(), method="auto", scope=None, total=False):
        plan = engine.plan("wall")
        plan.scope = scope or engine.scope()
        plan.steps = [plan.steps[0], m.PlanStep(id="materials", operation=m.MaterialQuantityOperation(kind="material_quantity",
            input_step_id="objects", material_names=list(names), method=method))]
        plan.outputs = {"answer": "materials"}
        if total:
            plan.steps.append(m.PlanStep(id="total", operation=m.AggregateOperation(kind="aggregate", input_step_id="materials",
                method="sum", field=m.FieldRef(kind="result_column", key="volume"), output_unit_id="unit:m3")))
            plan.outputs = {"answer": "total"}
        return plan

    def execute(self, engine, **options):
        plan = self.plan(engine, **options)
        validate_plan(plan, engine.bundle, engine.capabilities)
        result = engine.execute(plan)
        validate_bundle(engine.bundle)
        validate_result(result, engine.bundle, plan)
        return result

    def test_recorded_homogeneous_net_volume_needs_no_geometry_and_retains_original_quantity(self):
        material = self.homogeneous()
        self.volume(7.5)
        for deferred in (False, True):
            engine = self.engine(deferred)
            with patch.object(engine.geometry, "measure_many", side_effect=AssertionError("Unnecessary geometry")):
                result = self.execute(engine, names=["Concrete"])
            self.assertEqual(result.status, "answered", result.model_dump_json())
            row = result.claims[0].value.rows[0]
            self.assertEqual(Decimal(row["volume"].magnitude), Decimal("7.5"))
            proof = next(node for node in result.calculations if node.material_evidence).material_evidence[0]
            self.assertEqual(proof.method, "recorded_net_homogeneous")
            self.assertEqual(proof.material_step_ids, [material.id()])
            self.assertEqual(proof.recorded_quantity.basis, "net")
            self.assertTrue(result.claims[0].evidence[0].fact_ids)

    def test_explicit_geometry_keeps_a_disagreeing_recorded_quantity_separate(self):
        self.homogeneous()
        self.volume(7.5)
        engine = self.engine()
        result = self.execute(engine, names=["Concrete"], method="geometry")
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertAlmostEqual(float(result.claims[0].value.rows[0]["volume"].magnitude), 3.)
        self.assertEqual(result.claims[0].quality, "estimated")
        proof = next(node for node in result.calculations if node.material_evidence).material_evidence[0]
        self.assertEqual(Decimal(proof.recorded_quantity.magnitude), Decimal("7.5"))
        self.assertEqual(proof.method, "closed_mesh_homogeneous")

    def test_gross_volume_is_never_used_as_homogeneous_net_volume(self):
        self.homogeneous()
        self.volume(9., name="GrossVolume")
        engine = self.engine()
        result = self.execute(engine, names=["Concrete"], method="recorded_net")
        self.assertEqual(result.status, "partial", result.model_dump_json())
        self.assertEqual(result.claims[0].value.rows[0]["volume"].kind, "unavailable")

    def test_null_alternative_does_not_silently_become_consensus_recorded_net_volume(self):
        self.homogeneous()
        self.volume(7.5)
        missing = self.source.create_entity("IfcPropertySingleValue", Name="NetVolume", NominalValue=None)
        definition = self.root("IfcPropertySet", Name="BaseQuantities", HasProperties=[missing])
        self.root("IfcRelDefinesByProperties", RelatedObjects=[self.wall], RelatingPropertyDefinition=definition)
        for deferred in (False, True):
            engine = self.engine(deferred)
            result = self.execute(engine, names=["Concrete"], method="recorded_net")
            self.assertEqual(result.status, "partial", result.model_dump_json())
            self.assertEqual(result.claims[0].value.rows[0]["volume"].kind, "unavailable")

    def test_multiple_absent_literal_names_have_distinct_qualified_zeros(self):
        self.homogeneous()
        engine = self.engine()
        result = self.execute(engine, names=["Glass", "Steel"])
        self.assertEqual(result.status, "answered", result.model_dump_json())
        rows = result.claims[0].value.rows
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["material"].value.text for row in rows}, {"Glass", "Steel"})
        self.assertTrue(all(Decimal(row["volume"].magnitude) == 0 for row in rows))
        evidence = next(node for node in result.calculations if node.material_evidence).material_evidence[0]
        self.assertEqual(evidence.metadata["requested_material_names"], ["Glass", "Steel"])

    def test_uniform_native_layers_are_allocated_only_after_real_geometric_verification(self):
        layers, _ = self.layers(thicknesses=(.15, .05))
        engine = self.engine(True)
        result = self.execute(engine, names=["Insulation"], total=True)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertAlmostEqual(float(result.claims[0].value.magnitude), .75)
        self.assertEqual(result.claims[0].quality, "estimated")
        proof = next(node for node in result.calculations if node.material_evidence).material_evidence[0]
        self.assertEqual(proof.method, "verified_uniform_layers")
        self.assertAlmostEqual(proof.host_volume_m3, 3.)
        self.assertAlmostEqual(proof.selected_thickness_m, .05)
        self.assertAlmostEqual(proof.total_thickness_m, .2)
        self.assertIn(layers[1].Material.id(), proof.material_step_ids)
        self.assertEqual(len(proof.specified_layers), 2)

    def test_face_only_body_prism_proof_cannot_be_reused_for_material_allocation(self):
        from ifc_engine.layer_geometry import verify_layered_batch
        self.layers(thicknesses=(.15, .05))
        engine = self.engine()
        identifier = engine.resolve_entity(self.wall.GlobalId)
        record = verify_layered_batch(self.source, {identifier: self.wall.id()}, .001)["records"][0]
        self.assertEqual(record["status"], "verified")
        record["method"] = "uniform_layer_axis_body_prism.v1"
        with patch.object(engine.geometry, "verify_layered_volumes", return_value={"records": [record]}):
            result = self.execute(engine, names=["Insulation"])
        self.assertEqual(result.status, "partial", result.model_dump_json())
        self.assertEqual(result.claims[0].value.rows[0]["volume"].kind, "unavailable")
        self.assertTrue(all(item.volume_m3 is None for node in result.calculations for item in node.material_evidence))

    def test_thickness_mismatch_is_unknown_rather_than_a_blind_volume_fraction(self):
        self.layers(thicknesses=(.2, .1))
        engine = self.engine()
        result = self.execute(engine, names=["Insulation"])
        self.assertEqual(result.status, "partial", result.model_dump_json())
        self.assertEqual(result.claims[0].value.rows[0]["volume"].kind, "unavailable")
        proof = next(node for node in result.calculations if node.material_evidence).material_evidence[0]
        self.assertIsNone(proof.volume_m3)
        self.assertIn("unverified_geometry", proof.metadata)

    def test_unoriented_layer_set_does_not_guess_a_bounding_box_axis(self):
        self.layers(usage=False)
        engine = self.engine()
        result = self.execute(engine, names=["Insulation"])
        self.assertEqual(result.status, "partial", result.model_dump_json())
        self.assertEqual(result.claims[0].value.rows[0]["volume"].kind, "unavailable")

    def test_missing_material_names_remain_unknown_rather_than_no_match_zero(self):
        self.layers(names=("Concrete", None))
        engine = self.engine()
        result = self.execute(engine, names=["Insulation"])
        self.assertEqual(result.status, "partial", result.model_dump_json())
        self.assertEqual(result.claims[0].value.rows[0]["volume"].kind, "unavailable")

    def test_no_literal_match_in_a_complete_assignment_is_a_qualified_recorded_zero(self):
        self.homogeneous()
        engine = self.engine()
        with patch.object(engine.geometry, "measure_many", side_effect=AssertionError("No geometry needed for a recorded absent material")):
            result = self.execute(engine, names=["Glass"], total=True)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(Decimal(result.claims[0].value.magnitude), 0)
        proof = next(node for node in result.calculations if node.material_evidence).material_evidence[0]
        self.assertEqual(proof.status, "recorded_not_used")
        self.assertEqual(proof.material_name, "Glass")

    def test_partial_known_hosts_never_feed_a_complete_total(self):
        self.layers(thicknesses=(.15, .05))
        self.root("IfcWall", Name="Unclassified material wall")
        engine = self.engine()
        result = self.execute(engine, names=["Insulation"])
        self.assertEqual(result.status, "partial", result.model_dump_json())
        self.assertEqual({row["volume"].kind for row in result.claims[0].value.rows}, {"quantity", "unavailable"})
        total = self.execute(engine, names=["Insulation"], total=True)
        self.assertEqual(total.status, "incomplete_coverage", total.model_dump_json())
        self.assertFalse(total.claims)

    def test_material_resources_are_metadata_not_hidden_countable_scope_operands(self):
        self.layers(thicknesses=(.15, .05))
        engine = self.engine()
        scope = engine.scope()
        scope.exact_entity_ids = [engine.resolve_entity(self.wall.GlobalId)]
        result = self.execute(engine, names=["Insulation"], scope=scope, total=True)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertAlmostEqual(float(result.claims[0].value.magnitude), .75)
        self.assertTrue(all(set(item.entity_ids) <= set(scope.exact_entity_ids) for item in result.entity_sets))

    def test_duplicate_material_names_keep_independent_native_resource_ids(self):
        layers, _ = self.layers(names=("Insulation", "Insulation"))
        engine = self.engine()
        result = self.execute(engine, names=["Insulation"], total=True)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertAlmostEqual(float(result.claims[0].value.magnitude), 3.)
        proof = next(node for node in result.calculations if node.material_evidence).material_evidence[0]
        self.assertEqual(set(proof.material_step_ids), {layer.Material.id() for layer in layers})

    def test_geometric_work_budget_does_not_turn_an_uninspected_host_into_absence(self):
        self.layers()
        engine = self.engine()
        with patch("ifc_engine.material_quantities.MAX_GEOMETRY_HOSTS", 0):
            result = self.execute(engine, names=["Insulation"])
        self.assertEqual(result.status, "partial", result.model_dump_json())
        row = result.claims[0].value.rows[0]
        self.assertEqual(row["volume"].kind, "unavailable")
        proof = next(node for node in result.calculations if node.material_evidence).material_evidence[0]
        self.assertTrue(proof.metadata["uninspected_work_budget"])


if __name__ == "__main__":
    unittest.main()

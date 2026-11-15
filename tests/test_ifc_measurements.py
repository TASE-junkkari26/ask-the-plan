"""Native measurements retain source geometry, scope, units and bounded work."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ifcopenshell.guid
import numpy as np

from contracts import models as m
from contracts.validation import validate_plan, validate_result
from ifc_engine.catalog import POLICIES, attribute_key
from ifc_engine.engine import IfcQueryEngine
from ifc_engine.geometry import GeometryProvider, _measure_batch, _solid_volume
from ifc_engine.ingest import file_sha256
from tests.test_ifc_geometry import geometry_source


class IfcMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "measurements.ifc"
        self.model, self.objects = geometry_source(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def batch(self, metric, basis, subjects=None, references=None, **extra):
        return _measure_batch(self.model, {"metric": metric, "basis": basis,
            "subjects": subjects or {"room": [self.objects["room"].id()]},
            "references": references or {}, **extra}, .001)

    def value(self, batch):
        self.assertEqual(batch["status"], "match", batch)
        self.assertEqual(len(batch["records"]), 1)
        return batch["records"][0]["value"]

    def engine(self):
        self.model.write(str(self.path))
        return IfcQueryEngine.open(self.path)

    def plan(self, engine, metric, basis, names=("Convex room",), references=(), unit=None, exact=None):
        ids = [engine.resolve_entity(name) for name in names]
        scope = engine.scope()
        if exact is not None:
            scope.exact_entity_ids = [engine.resolve_entity(name) for name in exact]
        kind = "area" if metric in {"area", "union_area", "enclosed_area"} else "volume" if metric == "volume" else "length"
        return m.QueryPlan(id="plan:measurements", request_id="request:measurements", scope=scope, steps=[
            m.PlanStep(id="objects", operation=m.SelectOperation(kind="select", concept_ids=[],
                count_policy=POLICIES["all_matches"], where=m.BooleanPredicate(kind="any", operands=[
                    m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="entity_id"),
                        operator="eq", value=m.ReferencesValue(kind="references", entity_ids=[identifier])) for identifier in ids]))),
            m.PlanStep(id="measure", operation=m.MeasureOperation(kind="measure", input_step_id="objects",
                metric=metric, output_unit_id=unit or {"length": "unit:m", "area": "unit:m2", "volume": "unit:m3"}[kind],
                basis=basis, reference_entity_ids=[engine.resolve_entity(name) for name in references]))], outputs={"answer": "measure"})

    def execute(self, engine, plan, status="answered"):
        validate_plan(plan, engine.bundle, engine.capabilities)
        result = engine.execute(plan)
        self.assertEqual(result.status, status, result.model_dump_json(indent=2))
        validate_result(result, engine.bundle, plan)
        return result

    def test_mesh_dimensions_surface_and_solid_volume_are_different_quantities(self):
        self.assertAlmostEqual(self.value(self.batch("height", "world_z_extent")), 3.)
        self.assertAlmostEqual(self.value(self.batch("base_elevation", "world_min_z")), 0.)
        self.assertAlmostEqual(self.value(self.batch("area", "surface")), 110.)
        self.assertAlmostEqual(self.value(self.batch("area", "footprint")), 25.)
        self.assertAlmostEqual(self.value(self.batch("perimeter", "footprint")), 20.)
        self.assertAlmostEqual(self.value(self.batch("volume", "solid")), 75.)

    def test_millimetre_rotated_native_geometry_is_measured_in_physical_metres(self):
        self.model, self.objects = geometry_source(self.path, millimetres=True, rotate=True)
        self.assertAlmostEqual(self.value(self.batch("height", "world_z_extent")), 3.)
        self.assertAlmostEqual(self.value(self.batch("volume", "solid")), 75.)

    def test_distance_uses_projected_shapes_and_retains_nearest_points(self):
        equipment = self.objects["equipment"]
        equipment.ObjectPlacement.RelativePlacement.Location.Coordinates = (8., 1., 1.)
        result = self.batch("horizontal_distance", "minimum_projected_separation",
            references={"equipment": [equipment.id()]})
        self.assertAlmostEqual(self.value(result), 3.)
        self.assertEqual(result["records"][0]["metadata"]["nearest_points_xy_m"], [[5., 1.], [8., 1.]])
        self.assertEqual(result["records"][0]["reference_entity_ids"], ["equipment"])

    def test_union_footprints_remove_overlap_instead_of_summing_boxes(self):
        steps = [self.objects["room"].id(), self.objects["equipment"].id()]
        result = self.batch("union_area", "footprint", subjects={"union": steps}, explicit_root_steps=steps)
        self.assertAlmostEqual(self.value(result), 25.)

    def layered_wall(self):
        material=self.model.createIfcMaterial("Opaque")
        layer=self.model.createIfcMaterialLayer(material,.2,None)
        layer_set=self.model.createIfcMaterialLayerSet([layer],"Uniform wall")
        usage=self.model.createIfcMaterialLayerSetUsage(layer_set,"AXIS2","POSITIVE",0.,None)
        self.model.create_entity("IfcRelAssociatesMaterial",GlobalId=ifcopenshell.guid.new(),RelatedObjects=[self.objects["wall"]],RelatingMaterial=usage)
        return usage

    def test_standing_height_has_complete_vertical_patch_proof_and_distinct_basis(self):
        raw=self.batch("height","validated_vertical_spans",subjects={"wall":[self.objects["wall"].id()]})["records"][0]
        self.assertEqual(raw["status"],"verified",raw)
        self.assertAlmostEqual(raw["value"],3.)
        self.assertEqual(raw["method"],"validated_vertical_wall_spans.v1")
        self.assertEqual(raw["metadata"]["ground_contact"],"not_established")
        self.assertGreater(raw["metadata"]["verified_side_patch_count"],0)
        engine=self.engine();result=self.execute(engine,self.plan(engine,"height","validated_vertical_spans",names=("Shared long wall",)))
        self.assertEqual(result.claims[0].value.rows[0]["value"].basis,"validated_vertical_spans")
        self.assertEqual(result.claims[0].quality,"estimated")

    def test_one_opaque_face_has_distinct_area_and_native_layer_dependency_anchors(self):
        usage=self.layered_wall()
        raw=self.batch("area","net_opaque_face",subjects={"wall":[self.objects["wall"].id()]})["records"][0]
        self.assertEqual(raw["status"],"verified",raw)
        self.assertAlmostEqual(raw["value"],15.)
        self.assertIn(usage.id(),raw["metadata"]["native_input_step_ids"])
        self.assertNotEqual(raw["value"],self.value(self.batch("area","surface",subjects={"wall":[self.objects["wall"].id()]})))
        engine=self.engine();result=self.execute(engine,self.plan(engine,"area","net_opaque_face",names=("Shared long wall",)))
        record=next(n for n in result.calculations if n.plan_step_id=="measure").measurement_evidence[0]
        self.assertEqual(record.method,"uniform_prism_one_face_area.v1")
        anchored={engine.anchors[a].selector.value for a in result.claims[0].evidence[0].anchor_ids}
        self.assertIn(str(usage.id()),anchored)
        self.assertIn(str(self.model.by_type("IfcSIUnit")[0].id()),anchored)

    def test_body_face_measurement_cannot_relax_material_volume_allocation(self):
        usage=self.layered_wall();usage.ForLayerSet.MaterialLayers[0].LayerThickness=.2
        other=self.model.createIfcMaterial("Other")
        second=self.model.createIfcMaterialLayer(other,.1,None)
        usage.ForLayerSet.MaterialLayers=[*usage.ForLayerSet.MaterialLayers,second]
        engine=self.engine()
        face_plan=self.plan(engine,"area","net_opaque_face",names=("Shared long wall",))
        face=self.execute(engine,face_plan)
        self.assertEqual(Decimal(face.claims[0].value.rows[0]["value"].magnitude),Decimal(15))
        proof=next(n for n in face.calculations if n.plan_step_id=="measure").measurement_evidence[0]
        self.assertFalse(proof.metadata["declared_thickness_matches_body"])
        self.assertFalse(proof.metadata["material_allocation_eligible"])
        material_plan=face_plan.model_copy(deep=True)
        material_plan.steps=[material_plan.steps[0],m.PlanStep(id="material",operation=m.MaterialQuantityOperation(
            kind="material_quantity",input_step_id="objects",material_names=["Opaque"],method="geometry"))]
        material_plan.outputs={"answer":"material"}
        allocated=self.execute(engine,material_plan,"partial")
        self.assertIsInstance(allocated.claims[0].value.rows[0]["volume"],m.UnavailableValue)
        self.assertTrue(all(r.volume_m3 is None for n in allocated.calculations for r in n.material_evidence))

    def test_one_opaque_face_rejects_missing_usage_and_horizontal_slab_caps(self):
        raw=self.batch("area","net_opaque_face",subjects={"wall":[self.objects["wall"].id()]})["records"][0]
        self.assertEqual(raw["status"],"unavailable")
        usage=self.layered_wall();usage.LayerSetDirection="AXIS3"
        wall=self.objects["wall"];solid=wall.Representation.Representations[0].Items[0]
        solid.Depth=.2
        solid.SweptArea.OuterCurve.Points=[self.objects["point"](p) for p in [(0.,0.),(5.,0.),(5.,3.),(0.,3.),(0.,0.)]]
        raw=self.batch("area","net_opaque_face",subjects={"wall":[wall.id()]})["records"][0]
        self.assertEqual(raw["status"],"unavailable",raw)
        self.assertEqual(raw["metadata"]["reason_code"],"layer_normal_is_not_horizontal")

    def test_open_or_inconsistently_oriented_mesh_cannot_be_solid_volume(self):
        vertices = np.asarray([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
        open_faces = np.asarray([[0, 2, 1], [0, 1, 3], [1, 2, 3]])
        with self.assertRaises(ValueError):
            _solid_volume(vertices, open_faces)
        faces = np.asarray([[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]])
        self.assertAlmostEqual(_solid_volume(vertices, faces), 1 / 6)
        faces[0] = faces[0][::-1]
        with self.assertRaises(ValueError):
            _solid_volume(vertices, faces)

    def test_curve_length_requires_native_axis_instead_of_mesh_extents(self):
        result = self.batch("length", "axis")
        self.assertEqual(result["records"][0]["status"], "unavailable")
        room = self.objects["room"]
        context = self.model.by_type("IfcGeometricRepresentationContext")[0]
        curve = self.model.createIfcPolyline([self.model.createIfcCartesianPoint((0., 0., 0.)),
            self.model.createIfcCartesianPoint((3., 0., 0.)), self.model.createIfcCartesianPoint((3., 4., 0.))])
        representation = self.model.createIfcShapeRepresentation(context, "Axis", "Curve3D", [curve])
        room.Representation.Representations = [*room.Representation.Representations, representation]
        self.assertAlmostEqual(self.value(self.batch("length", "axis")), 7.)

    def test_bounding_box_or_route_bases_are_not_silently_accepted(self):
        for metric, basis in [("volume", "bounding_box"), ("distance", "escape_route"), ("area", "net"), ("area", "gross_one_face")]:
            result = self.batch(metric, basis)
            self.assertEqual(result["status"], "unknown")
            self.assertFalse(result["records"])

    def test_real_worker_binds_geometry_hash_and_measurement_method(self):
        provider = GeometryProvider(self.path, file_sha256(self.path))
        result = provider.measure_many("height", {"room": [self.objects["room"].id()]}, basis="world_z_extent")
        self.assertAlmostEqual(self.value(result), 3.)
        self.assertEqual(result["source_sha256"], file_sha256(self.path))
        self.assertEqual(result["records"][0]["frame"], "ifc_world")
        self.assertTrue(result["records"][0]["representation_step_ids"])
        self.path.write_bytes(self.path.read_bytes() + b"\n")
        changed = provider.measure_many("height", {"room": [self.objects["room"].id()]}, basis="world_z_extent")
        self.assertEqual(changed["status"], "unknown")
        self.assertFalse(changed["records"])

    def test_measurement_table_preserves_estimates_units_and_native_inputs(self):
        engine = self.engine()
        result = self.execute(engine, self.plan(engine, "height", "world_z_extent", unit="unit:mm"))
        claim = result.claims[0]
        self.assertEqual(claim.quality, "estimated")
        value = claim.value.rows[0]["value"]
        self.assertEqual(Decimal(value.magnitude), Decimal(3000))
        self.assertEqual(value.unit_id, "unit:mm")
        self.assertEqual(value.quality, "estimated")
        evidence = next(node for node in result.calculations if node.plan_step_id == "measure").measurement_evidence[0]
        self.assertEqual(evidence.source_step_ids, [self.objects["room"].id()])
        self.assertEqual(evidence.unit, "m")
        self.assertEqual(evidence.value, 3.)
        self.assertEqual(evidence.metadata["source_sha256"], file_sha256(self.path))

    def test_reference_object_outside_exact_scope_is_rejected(self):
        engine = self.engine()
        plan = self.plan(engine, "horizontal_distance", "minimum_projected_separation",
            references=("Panel-01",), exact=("Convex room",))
        result = engine.execute(plan)
        self.assertEqual(result.status, "incomplete_coverage", result.model_dump_json())

    def test_estimated_geometry_can_feed_a_sum_without_becoming_exact(self):
        engine = self.engine()
        plan = self.plan(engine, "volume", "solid", names=("Convex room", "Panel-01"))
        plan.steps.append(m.PlanStep(id="total", operation=m.AggregateOperation(kind="aggregate", input_step_id="measure", method="sum", field=m.FieldRef(kind="result_column", key="value"), output_unit_id="unit:m3")))
        plan.outputs = {"answer": "total"}
        result = self.execute(engine, plan)
        self.assertEqual(Decimal(result.claims[0].value.magnitude), Decimal(76))
        self.assertEqual(result.claims[0].quality, "estimated")
        self.assertEqual(result.claims[0].value.quality, "estimated")

    def test_union_area_is_a_single_scalar_with_all_inputs(self):
        engine = self.engine()
        plan = self.plan(engine, "union_area", "footprint", names=("Convex room", "Panel-01"))
        result = self.execute(engine, plan)
        self.assertEqual(Decimal(result.claims[0].value.magnitude), Decimal(25))
        evidence = next(node for node in result.calculations if node.plan_step_id == "measure").measurement_evidence[0]
        self.assertEqual(len(evidence.metadata["combined_entity_ids"]), 2)

    def test_native_terrain_elevations_are_source_attributes_not_mesh_minima(self):
        self.model.create_entity("IfcBuilding", GlobalId=ifcopenshell.guid.new(), Name="Hill church",
            ElevationOfTerrain=190., ElevationOfRefHeight=191.)
        engine = self.engine()
        entity = engine.resolve_entity("Hill church")
        for name, number in [("ElevationOfTerrain", 190), ("ElevationOfRefHeight", 191)]:
            fact = engine.facts[entity, attribute_key(name)][0]
            self.assertEqual(fact.value.quantity_kind, "length")
            self.assertEqual(Decimal(fact.value.magnitude), Decimal(number))
            self.assertTrue(fact.provenance.anchor_ids)

    def test_partial_geometry_keeps_known_estimates_and_blocks_complete_sum(self):
        self.model.create_entity("IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(), Name="No shape")
        engine = self.engine()
        plan = self.plan(engine, "volume", "solid", names=("Convex room", "No shape"))
        result = self.execute(engine, plan, "partial")
        values = [row["value"] for row in result.claims[0].value.rows]
        self.assertEqual(sum(isinstance(value, m.QuantityValue) for value in values), 1)
        self.assertEqual(sum(isinstance(value, m.UnavailableValue) for value in values), 1)
        plan.steps.append(m.PlanStep(id="total", operation=m.AggregateOperation(kind="aggregate", input_step_id="measure", method="sum", field=m.FieldRef(kind="result_column", key="value"), output_unit_id="unit:m3")))
        plan.outputs = {"answer": "total"}
        self.execute(engine, plan, "incomplete_coverage")

    def test_native_parent_with_hidden_geometry_does_not_expand_the_view(self):
        parent = self.model.create_entity("IfcBuilding", GlobalId=ifcopenshell.guid.new(), Name="Model parent")
        self.model.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(),
            RelatingStructure=parent, RelatedElements=[self.objects["equipment"]])
        engine = self.engine()
        self.execute(engine, self.plan(engine, "height", "world_z_extent", names=("Model parent",)))
        self.execute(engine, self.plan(engine, "height", "world_z_extent", names=("Model parent",), exact=("Model parent",)), "incomplete_coverage")

    def test_represented_occurrence_can_measure_its_own_shape_without_hidden_parts(self):
        equipment = self.objects["equipment"]
        child = self.model.create_entity("IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(), Name="Hidden part")
        self.model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=equipment, RelatedObjects=[child])
        engine = self.engine()
        result = self.execute(engine, self.plan(engine, "height", "world_z_extent", names=("Panel-01",), exact=("Panel-01",)))
        self.assertEqual(Decimal(result.claims[0].value.rows[0]["value"].magnitude), Decimal(1))

    def test_record_cache_reuses_subsets_and_rebinds_labels_without_mutable_aliases(self):
        provider = GeometryProvider(self.path, file_sha256(self.path))
        room, equipment = self.objects["room"].id(), self.objects["equipment"].id()
        with patch.object(provider, "_request", wraps=provider._request) as request:
            first = provider.measure_many("area", {"room": [room], "equipment": [equipment]}, basis="footprint", explicit_root_steps=[room, equipment])
            self.assertEqual(first["status"], "match")
            second = provider.measure_many("area", {"another label": [room]}, basis="footprint", explicit_root_steps=[room])
            self.assertAlmostEqual(self.value(second), 25.)
            self.assertEqual(second["records"][0]["subject_id"], "another label")
            self.assertEqual(request.call_count, 1)
            second["records"][0]["metadata"]["minimum_m"][0] = 999.
            third = provider.measure_many("area", {"room": [room]}, basis="footprint", explicit_root_steps=[room])
            self.assertEqual(third["records"][0]["metadata"]["minimum_m"][0], 0.)

    def test_successful_record_survives_an_unrelated_invalid_shape_in_same_batch(self):
        provider = GeometryProvider(self.path, file_sha256(self.path))
        good, bad = self.objects["room"].id(), self.objects["a"].id()
        with patch.object(provider, "_request", wraps=provider._request) as request:
            first = provider.measure_many("area", {"good": [good], "bad": [bad]}, basis="footprint", explicit_root_steps=[good, bad])
            self.assertEqual(first["status"], "unknown")
            self.assertEqual({record["status"] for record in first["records"]}, {"verified", "unavailable"})
            second = provider.measure_many("area", {"good": [good]}, basis="footprint", explicit_root_steps=[good])
            self.assertAlmostEqual(self.value(second), 25.)
            self.assertEqual(request.call_count, 1)
            provider.measure_many("area", {"bad": [bad]}, basis="footprint", explicit_root_steps=[bad])
            self.assertEqual(request.call_count, 2)  # Unknown is not a persistent failed-value cache.

    def test_record_cache_separates_groups_basis_tolerance_and_scope_prerequisites(self):
        provider = GeometryProvider(self.path, file_sha256(self.path))
        room, equipment = self.objects["room"].id(), self.objects["equipment"].id()
        with patch.object(provider, "_request", wraps=provider._request) as request:
            cases = [([room, equipment], [room], (), .001, "footprint"),
                     ([room], [room], (), .001, "footprint"),
                     ([room, equipment], [room, equipment], (), .001, "footprint"),
                     ([room, equipment], [room], ("source",), .001, "footprint"),
                     ([room, equipment], [room], (), .002, "footprint"),
                     ([room, equipment], [room], (), .001, "surface")]
            for steps, roots, incomplete, tolerance, basis in cases:
                result = provider.measure_many("area", {"source": steps}, basis=basis, explicit_root_steps=roots,
                    incomplete_groups=incomplete, tolerance_m=tolerance)
                self.assertAlmostEqual(self.value(result), 110. if basis == "surface" else 25.)
            self.assertEqual(request.call_count, len(cases))
            self.path.write_bytes(self.path.read_bytes() + b"\n")
            changed = provider.measure_many("area", {"source": [room]}, basis="footprint", explicit_root_steps=[room])
            self.assertEqual(changed["status"], "unknown")
            self.assertFalse(changed["records"])
            self.assertEqual(request.call_count, len(cases))

    def test_record_cache_has_entry_and_byte_limits(self):
        provider = GeometryProvider(self.path, file_sha256(self.path))
        provider._measurement_cache_max_records = 2
        room = self.objects["room"].id()
        with patch.object(provider, "_request", wraps=provider._request) as request:
            for tolerance in [.001, .002, .003]:
                provider.measure_many("height", {"source": [room]}, basis="world_z_extent", tolerance_m=tolerance)
            self.assertEqual(len(provider._measurement_cache), 2)
            provider.measure_many("height", {"source": [room]}, basis="world_z_extent", tolerance_m=.001)
            self.assertEqual(request.call_count, 4)
            provider.close()
            self.assertFalse(provider._measurement_cache)
            self.assertEqual(provider._measurement_cache_bytes, 0)
        small = GeometryProvider(self.path, file_sha256(self.path))
        small._measurement_cache_max_bytes = 1
        self.assertAlmostEqual(self.value(small.measure_many("height", {"source": [room]}, basis="world_z_extent")), 3.)
        self.assertFalse(small._measurement_cache)
        self.assertEqual(small._measurement_cache_bytes, 0)

    def test_authorized_space_prefetch_answers_only_requested_rooms_and_warms_others(self):
        self.model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Second room",
            Representation=self.objects["equipment"].Representation, ObjectPlacement=self.objects["equipment"].ObjectPlacement)
        engine = self.engine()
        def direct_batch(_method, _steps, tolerance, _timeout=None, *, options):
            return _measure_batch(self.model, options, tolerance)
        # Native calculations are real; avoid making cache correctness depend
        # on subprocess-start timing on a loaded shared test machine.
        with patch.object(engine.geometry, "_request", side_effect=direct_batch) as request:
            first = self.execute(engine, self.plan(engine, "area", "footprint"))
            self.assertEqual(len(first.claims[0].value.rows), 1)
            self.assertEqual(first.claims[0].value.rows[0]["subject"].entity_ids, [engine.resolve_entity("Convex room")])
            second = self.execute(engine, self.plan(engine, "area", "footprint", names=("Second room",)))
            self.assertEqual(Decimal(second.claims[0].value.rows[0]["value"].magnitude), Decimal(1))
            self.assertEqual(request.call_count, 1)

    def test_view_prefetch_does_not_measure_hidden_rooms_or_require_hidden_furniture(self):
        room = self.objects["room"]
        self.model.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(),
            RelatingStructure=room, RelatedElements=[self.objects["equipment"]])
        engine = self.engine()
        plan = self.plan(engine, "area", "footprint", exact=("Convex room",))
        with patch.object(engine.geometry, "_request", wraps=engine.geometry._request) as request:
            result = self.execute(engine, plan)
            self.assertEqual(Decimal(result.claims[0].value.rows[0]["value"].magnitude), Decimal(25))
            self.assertEqual(list(request.call_args.kwargs["options"]["subjects"]), [engine.resolve_entity("Convex room")])

    def test_missing_room_body_cannot_be_replaced_by_its_contents_footprint(self):
        room = self.objects["a"]
        self.model.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(),
            RelatingStructure=room, RelatedElements=[self.objects["equipment"]])
        engine = self.engine()
        self.execute(engine, self.plan(engine, "area", "footprint", names=("1B07",)), "missing_information")

    def test_incomplete_vertical_room_shell_does_not_become_zero_floor_area(self):
        room = self.objects["a"]
        coordinates = self.model.create_entity("IfcCartesianPointList3D", CoordList=[(0., 0., 0.), (1., 0., 0.), (0., 0., 3.)])
        item = self.model.create_entity("IfcTriangulatedFaceSet", Coordinates=coordinates, CoordIndex=[(1, 2, 3)], Closed=False)
        context = self.model.by_type("IfcGeometricRepresentationContext")[0]
        representation = self.model.createIfcShapeRepresentation(context, "Body", "Tessellation", [item])
        room.Representation = self.model.createIfcProductDefinitionShape(None, None, [representation])
        engine = self.engine()
        self.execute(engine, self.plan(engine, "area", "footprint", names=("1B07",)), "missing_information")


if __name__ == "__main__":
    unittest.main()

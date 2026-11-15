"""Native layer allocation needs a proven uniform solid and explicit usage."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ifcopenshell.guid

from ifc_engine.geometry import GeometryProvider
from ifc_engine.ingest import file_sha256
from ifc_engine.layer_geometry import verify_layered_batch, verify_layer_axis_body_batch
from tests.test_ifc_geometry import geometry_source


class LayerGeometryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "layers.ifc"
        self.model, self.objects = geometry_source(self.path)
        self.wall = self.objects["wall"]
        self.usage, self.association = self.add_usage()

    def tearDown(self):
        self.directory.cleanup()

    def root(self, kind, **fields):
        return self.model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **fields)

    def add_usage(self, *, thicknesses=(.1, .1), offset=0., sense="POSITIVE", owner=None):
        layers = []
        for name, thickness in zip(["Concrete", "Insulation"], thicknesses):
            material = self.model.create_entity("IfcMaterial", Name=name)
            layers.append(self.model.create_entity("IfcMaterialLayer", Material=material, LayerThickness=thickness))
        layer_set = self.model.create_entity("IfcMaterialLayerSet", MaterialLayers=layers, LayerSetName="Explicit layers")
        usage = self.model.create_entity("IfcMaterialLayerSetUsage", ForLayerSet=layer_set, LayerSetDirection="AXIS2",
            DirectionSense=sense, OffsetFromReferenceLine=offset)
        association = self.root("IfcRelAssociatesMaterial", RelatedObjects=[owner or self.wall], RelatingMaterial=usage)
        return usage, association

    def verify(self):
        return verify_layered_batch(self.model, {"wall": self.wall.id()}, .001)["records"][0]

    def test_closed_uniform_wall_has_real_volume_and_native_layer_proof(self):
        result = self.verify()
        self.assertEqual(result["status"], "verified", result)
        self.assertAlmostEqual(result["volume_m3"], 3.)
        self.assertAlmostEqual(result["axis_thickness_m"], .2)
        self.assertAlmostEqual(result["specified_total_thickness_m"], .2)
        self.assertAlmostEqual(result["metadata"]["cap_area_m2"], 15.)
        self.assertLess(result["metadata"]["cap_symdiff_m2"], 1e-10)
        self.assertEqual([layer["name"] for layer in result["layers"]], ["Concrete", "Insulation"])
        self.assertTrue({self.wall.id(), self.usage.id(), self.association.id()} <= set(result["source_step_ids"]))
        self.assertEqual(result["metadata"]["axis"], "AXIS2")

    def test_thickness_and_offset_mismatches_are_not_allocated(self):
        self.usage.ForLayerSet.MaterialLayers[0].LayerThickness = .2
        result = self.verify()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["metadata"]["reason_code"], "layer_thickness_geometry_mismatch")
        self.usage.ForLayerSet.MaterialLayers[0].LayerThickness = .1
        self.usage.OffsetFromReferenceLine = -.1
        result = self.verify()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["metadata"]["reason_code"], "layer_offset_geometry_mismatch")

    def test_face_body_proof_keeps_actual_geometry_separate_from_authored_thickness(self):
        self.usage.ForLayerSet.MaterialLayers[0].LayerThickness=.2
        strict=self.verify()
        body=verify_layer_axis_body_batch(self.model,{"wall":self.wall.id()},.001)["records"][0]
        self.assertEqual(strict["status"],"unavailable")
        self.assertEqual(strict["metadata"]["reason_code"],"layer_thickness_geometry_mismatch")
        self.assertEqual(body["status"],"verified",body)
        self.assertEqual(body["method"],"uniform_layer_axis_body_prism.v1")
        self.assertAlmostEqual(body["axis_thickness_m"],.2)
        self.assertAlmostEqual(body["specified_total_thickness_m"],.3)
        self.assertAlmostEqual(body["metadata"]["cap_area_m2"],15.)
        self.assertFalse(body["metadata"]["declared_thickness_matches_body"])
        self.assertFalse(body["metadata"]["material_allocation_eligible"])

    def test_body_face_proof_reports_offset_disagreement_and_still_rejects_taper(self):
        self.usage.OffsetFromReferenceLine=-.1
        body=verify_layer_axis_body_batch(self.model,{"wall":self.wall.id()},.001)["records"][0]
        self.assertEqual(body["status"],"verified",body)
        self.assertTrue(body["metadata"]["declared_thickness_matches_body"])
        self.assertFalse(body["metadata"]["declared_interval_matches_body"])
        self.assertEqual(self.verify()["status"],"unavailable")
        curve=self.wall.Representation.Representations[0].Items[0].SweptArea.OuterCurve
        curve.Points=[self.objects["point"](p) for p in [(0.,0.),(5.,0.),(5.,.1),(0.,.2),(0.,0.)]]
        body=verify_layer_axis_body_batch(self.model,{"wall":self.wall.id()},.001)["records"][0]
        self.assertEqual(body["status"],"unavailable")
        self.assertEqual(body["metadata"]["reason_code"],"nonuniform_axis_geometry")

    def test_negative_direction_preserves_native_layer_sense(self):
        self.usage.DirectionSense = "NEGATIVE"
        self.usage.OffsetFromReferenceLine = .2
        result = self.verify()
        self.assertEqual(result["status"], "verified", result)
        self.assertEqual(result["metadata"]["direction_sense"], "NEGATIVE")
        self.assertAlmostEqual(result["volume_m3"], 3.)

    def test_rotated_millimetre_source_is_checked_in_world_metres(self):
        self.model, self.objects = geometry_source(self.path, millimetres=True)
        self.wall = self.objects["wall"]
        self.wall.ObjectPlacement.RelativePlacement.RefDirection = self.model.createIfcDirection((0., 1., 0.))
        self.wall.ObjectPlacement.RelativePlacement.Location = self.objects["point"]((20., 30., 4.))
        self.usage, self.association = self.add_usage(thicknesses=(100., 100.))
        result = self.verify()
        self.assertEqual(result["status"], "verified", result)
        self.assertAlmostEqual(result["volume_m3"], 3.)
        self.assertEqual(result["metadata"]["axis_world"], [-1., 0., 0.])
        self.assertEqual(result["metadata"]["origin_m"], [20., 30., 4.])
        self.assertAlmostEqual(result["metadata"]["length_scale_to_m"], .001)

    def test_tapered_host_is_unavailable_even_when_maximum_width_matches(self):
        curve = self.wall.Representation.Representations[0].Items[0].SweptArea.OuterCurve
        curve.Points = [self.objects["point"](point) for point in [(0., 0.), (5., 0.), (5., .1), (0., .2), (0., 0.)]]
        result = self.verify()
        self.assertEqual(result["status"], "unavailable", result)
        self.assertEqual(result["metadata"]["reason_code"], "nonuniform_axis_geometry")

    def test_open_host_and_missing_layer_usage_remain_unknown(self):
        self.wall.Representation = None
        self.assertEqual(self.verify()["status"], "unavailable")
        self.wall = self.objects["room"]
        result = self.verify()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["metadata"]["reason_code"], "layer_usage_missing")

    def test_perforated_uniform_prism_preserves_hole_and_net_volume(self):
        def curve(points):
            return self.model.createIfcPolyline([self.objects["point"](point) for point in points])
        outer = curve([(0., 0.), (0., -3.), (5., -3.), (5., 0.), (0., 0.)])
        inner = curve([(1., -1.), (2., -1.), (2., -2.), (1., -2.), (1., -1.)])
        profile = self.model.create_entity("IfcArbitraryProfileDefWithVoids", ProfileType="AREA", OuterCurve=outer, InnerCurves=[inner])
        axis = self.model.createIfcAxis2Placement3D(self.objects["point"]((0., 0., 0.)),
            self.model.createIfcDirection((0., 1., 0.)), self.model.createIfcDirection((1., 0., 0.)))
        solid = self.model.createIfcExtrudedAreaSolid(profile, axis, self.model.createIfcDirection((0., 0., 1.)), .2)
        self.wall.Representation.Representations[0].Items = [solid]
        result = self.verify()
        self.assertEqual(result["status"], "verified", result)
        self.assertAlmostEqual(result["volume_m3"], 2.8)
        self.assertAlmostEqual(result["metadata"]["cap_area_m2"], 14.)
        self.assertEqual(result["metadata"]["cap_hole_count"], 1)
        self.usage.ForLayerSet.MaterialLayers[0].LayerThickness=.2
        body=verify_layer_axis_body_batch(self.model,{"wall":self.wall.id()},.001)["records"][0]
        self.assertEqual(body["status"],"verified",body)
        self.assertAlmostEqual(body["metadata"]["cap_area_m2"],14.)
        self.assertEqual(body["metadata"]["cap_hole_count"],1)
        self.assertEqual(self.verify()["status"],"unavailable")

    def test_ambiguous_native_assignments_do_not_choose_one_usage(self):
        self.add_usage()
        result = self.verify()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["metadata"]["reason_code"], "material_assignment_ambiguous")

    def test_worker_source_hash_cache_and_retirement(self):
        self.model.write(str(self.path))
        provider = GeometryProvider(self.path, file_sha256(self.path))
        with patch.object(provider, "_request", wraps=provider._request) as request:
            result = provider.verify_layered_volumes({"wall": self.wall.id()})
            self.assertEqual(result["status"], "match", result)
            self.assertAlmostEqual(result["records"][0]["volume_m3"], 3.)
            again = provider.verify_layered_volumes({"renamed": self.wall.id()})
            self.assertEqual(again["records"][0]["subject_id"], "renamed")
            self.assertEqual(request.call_count, 1)
            self.path.write_bytes(self.path.read_bytes() + b"\n")
            changed = provider.verify_layered_volumes({"wall": self.wall.id()})
            self.assertEqual(changed["status"], "unknown")
            self.assertFalse(changed["records"])
            self.assertEqual(request.call_count, 1)
        provider.close()
        self.assertFalse(provider._measurement_cache)


if __name__ == "__main__":
    unittest.main()

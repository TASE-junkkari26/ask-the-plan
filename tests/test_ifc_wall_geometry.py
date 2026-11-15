"""Wall heights follow local side patches; one face is not total mesh area."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ifcopenshell.guid
import numpy as np

from ifc_engine.layer_geometry import verify_layered_batch, verify_layer_axis_body_batch
from ifc_engine.wall_geometry import net_opaque_face_area, validated_vertical_spans
from tests.test_ifc_geometry import geometry_source


def terrain_wall(*, heights=(3., 3., 3., 3.), bottom=False):
    base = np.asarray([(0., 0., 2.), (10., 0., 26.), (10., .5, 26.), (0., .5, 2.)])
    vertices = np.vstack([base, base + np.asarray([[0., 0., height] for height in heights])])
    faces = []
    for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
        faces.extend([(a, b, b + 4), (a, b + 4, a + 4)])
    faces.extend([(4, 5, 6), (4, 6, 7)])
    if bottom:
        faces.extend([(0, 2, 1), (0, 3, 2)])
    return vertices, np.asarray(faces)


class VerticalWallSpanTests(unittest.TestCase):
    def test_terrain_following_open_bottom_wall_has_three_metre_local_height(self):
        vertices, faces = terrain_wall()
        result = validated_vertical_spans(vertices, faces)
        self.assertEqual(result["status"], "verified", result)
        self.assertAlmostEqual(result["value"], 3.)
        proof = result["metadata"]
        self.assertEqual(proof["global_elevation_interval_m"], [2., 29.])
        self.assertEqual(proof["observed_paired_span_interval_m"], [3., 3.])
        self.assertEqual(proof["verified_side_patch_count"], 4)
        self.assertEqual(proof["ground_contact"], "not_established")
        source_faces = [index for record in proof["vertical_side_patch_proof"] for index in record["source_triangle_ids"]]
        self.assertEqual(sorted(source_faces), list(range(8)))
        self.assertEqual(proof["top_triangle_ids"], [8, 9])

    def test_rotation_and_translation_preserve_the_world_vertical_section_height(self):
        vertices, faces = terrain_wall(bottom=True)
        angle = .63
        rotation = np.asarray([[np.cos(angle), -np.sin(angle), 0.], [np.sin(angle), np.cos(angle), 0.], [0., 0., 1.]])
        result = validated_vertical_spans(vertices @ rotation.T + np.asarray([100., -200., 51.]), faces)
        self.assertEqual(result["status"], "verified", result)
        self.assertAlmostEqual(result["value"], 3.)
        self.assertEqual(result["metadata"]["bottom_triangle_ids"], [10, 11])

    def test_incomplete_side_patch_is_unknown_even_when_all_vertex_pairs_say_three(self):
        vertices, faces = terrain_wall()
        result = validated_vertical_spans(vertices, faces[1:])
        self.assertEqual(result["status"], "unavailable", result)
        self.assertIsNone(result["value"])
        self.assertEqual(result["metadata"]["observed_paired_span_interval_m"], [3., 3.])
        self.assertEqual(result["metadata"]["unsupported_side_patch_count"], 1)

    def test_variable_two_and_three_metre_sections_do_not_become_a_majority_height(self):
        result = validated_vertical_spans(*terrain_wall(heights=(2., 3., 3., 2.)))
        self.assertEqual(result["status"], "unavailable", result)
        self.assertIsNone(result["value"])
        self.assertEqual(result["metadata"]["observed_paired_span_interval_m"], [2., 3.])
        self.assertEqual(result["metadata"]["reason_code"], "nonuniform_local_vertical_spans")

    def test_unpaired_roof_or_surface_vertex_prevents_a_uniform_wall_height(self):
        vertices, faces = terrain_wall()
        vertices = np.vstack([vertices, [5., .25, 40.]])
        faces = np.vstack([faces[:8], [4, 5, 8], [5, 6, 8], [6, 7, 8], [7, 4, 8]])
        result = validated_vertical_spans(vertices, faces)
        self.assertEqual(result["status"], "unavailable", result)
        self.assertIsNone(result["value"])
        self.assertEqual(result["metadata"]["unpaired_column_count"], 1)

    def test_bounded_patch_budget_is_not_a_missing_height_or_zero(self):
        with patch("ifc_engine.wall_geometry.MAX_PATCHES", 0):
            result = validated_vertical_spans(*terrain_wall())
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["metadata"]["reason_code"], "geometry_work_budget")
        self.assertIsNone(result["value"])


class OpaqueWallFaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.model, self.objects = geometry_source(Path(self.directory.name) / "face.ifc")
        self.wall = self.objects["wall"]
        material = self.model.create_entity("IfcMaterial", Name="Recorded wall material")
        layer = self.model.create_entity("IfcMaterialLayer", Material=material, LayerThickness=.2)
        definition = self.model.create_entity("IfcMaterialLayerSet", MaterialLayers=[layer])
        self.usage = self.model.create_entity("IfcMaterialLayerSetUsage", ForLayerSet=definition,
            LayerSetDirection="AXIS2", DirectionSense="POSITIVE", OffsetFromReferenceLine=0.)
        self.model.create_entity("IfcRelAssociatesMaterial", GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[self.wall], RelatingMaterial=self.usage)

    def proof(self):
        return verify_layered_batch(self.model, {"wall": self.wall.id()}, .001)["records"][0]

    def test_one_verified_wall_face_is_not_the_area_of_all_faces(self):
        result = net_opaque_face_area(self.proof())
        self.assertEqual(result["status"], "verified", result)
        self.assertAlmostEqual(result["value"], 15.)
        self.assertEqual(result["metadata"]["face_count"], 1)
        self.assertEqual(result["metadata"]["face_basis"], "net_opaque_face")

    def test_opening_hole_stays_subtracted_from_the_opaque_face(self):
        point = self.objects["point"]
        def curve(points):
            return self.model.createIfcPolyline([point(value) for value in points])
        outer = curve([(0., 0.), (0., -3.), (5., -3.), (5., 0.), (0., 0.)])
        inner = curve([(1., -1.), (2., -1.), (2., -2.), (1., -2.), (1., -1.)])
        profile = self.model.create_entity("IfcArbitraryProfileDefWithVoids", ProfileType="AREA", OuterCurve=outer, InnerCurves=[inner])
        axis = self.model.createIfcAxis2Placement3D(point((0., 0., 0.)), self.model.createIfcDirection((0., 1., 0.)),
            self.model.createIfcDirection((1., 0., 0.)))
        self.wall.Representation.Representations[0].Items = [self.model.createIfcExtrudedAreaSolid(profile, axis,
            self.model.createIfcDirection((0., 0., 1.)), .2)]
        result = net_opaque_face_area(self.proof())
        self.assertEqual(result["status"], "verified", result)
        self.assertAlmostEqual(result["value"], 14.)
        self.assertEqual(result["metadata"]["cap_hole_count"], 1)

    def test_floor_like_layer_axis_cannot_be_presented_as_a_vertical_facade_face(self):
        record = self.proof()
        record["metadata"]["axis_world"] = [0., 0., 1.]
        result = net_opaque_face_area(record)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["value"])

    def test_actual_body_face_survives_declared_layer_thickness_mismatch(self):
        self.usage.ForLayerSet.MaterialLayers[0].LayerThickness=.3
        body=verify_layer_axis_body_batch(self.model,{"wall":self.wall.id()},.001)["records"][0]
        result=net_opaque_face_area(body)
        self.assertEqual(result["status"],"verified",result)
        self.assertAlmostEqual(result["value"],15.)
        self.assertFalse(result["metadata"]["declared_thickness_matches_body"])
        self.assertFalse(result["metadata"]["material_allocation_eligible"])

    def test_layer_mismatch_does_not_fall_back_to_half_the_total_surface_area(self):
        self.usage.ForLayerSet.MaterialLayers[0].LayerThickness = .3
        result = net_opaque_face_area(self.proof())
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["value"])


if __name__ == "__main__":
    unittest.main()

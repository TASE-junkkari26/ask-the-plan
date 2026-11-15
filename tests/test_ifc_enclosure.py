"""Enclosed areas use real joint closures and exclude closure-only courtyards."""
from decimal import Decimal
import unittest
from unittest.mock import patch

import ifcopenshell.guid
from shapely.geometry import box
from shapely.ops import unary_union

from ifc_engine.enclosure import enclosed_regions
from tests import test_ifc_measurements as measurement_helpers


class EnclosedRegionTests(unittest.TestCase):
    def setUp(self):
        self.wall = unary_union([box(0, 0, 10, 1), box(0, 0, 1, 10), box(9, 0, 10, 10)])

    def test_explicit_joint_closures_create_a_bounded_source_region(self):
        result = enclosed_regions(self.wall, {"left": box(0, 9, 5, 10), "right": box(5, 9, 10, 10)}, .001)
        self.assertEqual(result["status"], "verified")
        self.assertAlmostEqual(result["value"], 64.)
        self.assertGreater(result["metadata"]["regions"][0]["subject_boundary_length_m"], 20)
        self.assertEqual(set(result["metadata"]["regions"][0]["contributing_references"]), {"left", "right"})
        self.assertTrue(result["metadata"]["region_geometry_xy_m"])
        self.assertEqual(enclosed_regions(self.wall, {"left": box(0, 9, 5, 10)}, .001)["status"], "unavailable")

    def test_open_ring_never_becomes_zero_or_an_artificial_hull(self):
        result = enclosed_regions(self.wall, {}, .001)
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("value", result)
        # Even a small real opening remains open: tolerance does not close it.
        result = enclosed_regions(self.wall, {"left": box(0, 9, 4.9999, 10), "right": box(5.0001, 9, 10, 10)}, .001)
        self.assertEqual(result["status"], "unavailable")

    def test_courtyard_of_closure_object_is_excluded_without_subject_wall(self):
        courtyard = box(20, 20, 24, 24).difference(box(21, 21, 23, 23))
        result = enclosed_regions(self.wall, {"courtyard": courtyard}, .001)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["rejected_regions"][0]["reason"], "closure_only_courtyard")
        result = enclosed_regions(self.wall, {"gate": box(0, 9, 10, 10), "courtyard": courtyard}, .001)
        self.assertAlmostEqual(result["value"], 64.)
        self.assertTrue(any(region["reason"] == "closure_only_courtyard" for region in result["metadata"]["rejected_regions"]))

    def test_nested_associated_regions_are_not_double_counted(self):
        outer = box(0, 0, 20, 20).difference(box(2, 2, 18, 18))
        inner = box(8, 8, 12, 12).difference(box(9, 9, 11, 11))
        result = enclosed_regions(unary_union([outer, inner]), {}, .001)
        self.assertEqual(result["status"], "verified")
        self.assertAlmostEqual(result["value"], 256.)

    def test_coordinate_budget_is_explicit(self):
        with patch("ifc_engine.enclosure.MAX_ENCLOSURE_COORDINATES", 4):
            result = enclosed_regions(self.wall, {"gate": box(0, 9, 10, 10)}, .001)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason_code"], "enclosure_geometry_work_budget")


class IfcEnclosureTests(unittest.TestCase):
    """Reuse fixture utilities without duplicating the measurement test suite."""
    setUp = measurement_helpers.IfcMeasurementTests.setUp
    tearDown = measurement_helpers.IfcMeasurementTests.tearDown
    engine = measurement_helpers.IfcMeasurementTests.engine
    plan = measurement_helpers.IfcMeasurementTests.plan
    execute = measurement_helpers.IfcMeasurementTests.execute

    def object(self, name, rectangles):
        solids = []
        context = self.model.by_type("IfcGeometricRepresentationContext")[0]
        for x0, y0, x1, y1 in rectangles:
            points = [self.objects["point"](p) for p in [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]
            profile = self.model.createIfcArbitraryClosedProfileDef("AREA", None, self.model.createIfcPolyline(points))
            axis = self.model.createIfcAxis2Placement3D(self.objects["point"]((0., 0., 0.)), None, None)
            solids.append(self.model.createIfcExtrudedAreaSolid(profile, axis, self.model.createIfcDirection((0., 0., 1.)), 3.))
        representation = self.model.createIfcShapeRepresentation(context, "Body", "SweptSolid", solids)
        return self.model.create_entity("IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(), Name=name,
            Representation=self.model.createIfcProductDefinitionShape(None, None, [representation]))

    def model_objects(self):
        self.object("Boundary", [(0., 0., 10., 1.), (0., 0., 1., 10.), (9., 0., 10., 10.)])
        self.object("Gate-left", [(0., 9., 5., 10.)])
        self.object("Gate-right", [(5., 9., 10., 10.)])

    def test_native_closures_are_combined_and_provenance_survives_cache(self):
        self.model_objects()
        engine = self.engine()
        plan = self.plan(engine, "enclosed_area", "bounded_regions", names=("Boundary",), references=("Gate-left", "Gate-right"))
        with patch.object(engine.geometry, "_request", wraps=engine.geometry._request) as request:
            result = self.execute(engine, plan)
            row = result.claims[0].value.rows[0]
            self.assertEqual(Decimal(row["value"].magnitude), Decimal(64))
            self.assertEqual(row["value"].quality, "estimated")
            self.assertEqual(len(row["reference"].entity_ids), 2)
            evidence = next(node for node in result.calculations if node.plan_step_id == "measure").measurement_evidence[0]
            self.assertEqual(len(evidence.reference_entity_ids), 2)
            self.assertEqual(evidence.unit, "m2")
            self.assertTrue(evidence.metadata["region_geometry_xy_m"])
            self.execute(engine, plan)
            self.assertEqual(request.call_count, 1)

    def test_missing_closure_is_unknown_and_hidden_closure_cannot_use_warm_cache(self):
        self.model_objects()
        engine = self.engine()
        partial = self.plan(engine, "enclosed_area", "bounded_regions", names=("Boundary",), references=("Gate-left",))
        self.execute(engine, partial, "missing_information")
        complete = self.plan(engine, "enclosed_area", "bounded_regions", names=("Boundary",), references=("Gate-left", "Gate-right"))
        self.execute(engine, complete)
        narrow = self.plan(engine, "enclosed_area", "bounded_regions", names=("Boundary",), references=("Gate-left", "Gate-right"), exact=("Boundary", "Gate-left"))
        result = engine.execute(narrow)
        self.assertEqual(result.status, "incomplete_coverage")


if __name__ == "__main__":
    unittest.main()

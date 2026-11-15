"""Route plans preserve a physical starting convention and a real target DAG."""
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from contracts import models as m
from contracts.validation import validate_plan, validate_result
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_geometry import geometry_source


class RouteContractTests(unittest.TestCase):
    def test_explicit_start_cannot_be_missing_nonfinite_or_silently_ignored(self):
        base = dict(kind="route_query", input_step_id="origins")
        for options in [dict(start_basis="explicit_point"), dict(start_point_m=(1., 2., 3.)),
                        dict(start_basis="explicit_point", start_point_m=(float("nan"), 0., 0.))]:
            with self.subTest(options=options), self.assertRaises(ValidationError):
                m.RouteQueryOperation(**base, **options)
        operation = m.RouteQueryOperation(**base, start_basis="explicit_point", start_point_m=(1., 2., 3.))
        self.assertEqual(operation.start_point_m, (1., 2., 3.))

    def test_farthest_search_cannot_be_confused_with_one_representative_point(self):
        for options in [dict(mode="farthest"), dict(start_basis="farthest_sampled")]:
            with self.subTest(options=options), self.assertRaises(ValidationError):
                m.RouteQueryOperation(kind="route_query", input_step_id="origins", **options)
        self.assertEqual(m.RouteQueryOperation(kind="route_query", input_step_id="origins",
            mode="farthest", start_basis="farthest_sampled").mode, "farthest")

    def test_verified_path_needs_finite_physical_points_and_unavailable_is_not_a_path(self):
        base = dict(subject_id="room:origin", method="native_walking_route.v1", frame="ifc_world", tolerance_m=.001)
        for status, points in [("verified", []), ("verified", [(0., 0., 0.), (1., float("inf"), 0.)]),
                               ("unavailable", [(0., 0., 0.), (1., 0., 0.)])]:
            with self.subTest(status=status, points=points), self.assertRaises(ValidationError):
                m.RouteEvaluation(**base, status=status, path_points_m=points)
        self.assertEqual(m.RouteEvaluation(**base, status="partial",
            path_points_m=[(0., 0., 0.), (1., 0., 0.)]).quality, "estimated")

    def test_target_selection_is_an_earlier_dag_dependency_and_distance_is_numeric(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "routes.ifc"
            geometry_source(path)
            engine = IfcQueryEngine.open(path)
            plan = engine.plan("space")
            plan.steps = [plan.steps[0], m.PlanStep(id="route", operation=m.RouteQueryOperation(
                kind="route_query", input_step_id="objects", target_step_id="later_target"))]
            plan.outputs = {"answer": "route"}
            with self.assertRaises(ValidationError):
                m.QueryPlan.model_validate(plan.model_dump())
            plan.steps[1].operation.target_step_id = None
            plan.steps.append(m.PlanStep(id="longest", operation=m.RankOperation(kind="rank", input_step_id="route",
                field=m.FieldRef(kind="result_column", key="distance"), direction="descending", limit=1)))
            plan.outputs = {"answer": "longest"}
            plan = m.QueryPlan.model_validate(plan.model_dump())
            validate_plan(plan, engine.bundle, engine.capabilities)

    def test_exported_route_may_not_consume_a_hidden_room(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "routes.ifc"
            geometry_source(path)
            engine = IfcQueryEngine.open(path)
            plan = engine.plan("space")
            room = engine.resolve_entity("Convex room")
            other = engine.resolve_entity("Panel-01")
            plan.scope.exact_entity_ids = [room]
            result = engine.execute(plan)
            self.assertEqual(result.status, "answered")
            node = result.calculations[-1]
            node.quality = "estimated"
            node.route_evidence = [m.RouteEvaluation(subject_id=room, method="native_walking_route.v1",
                frame="ifc_world", tolerance_m=.001, status="partial", room_ids=[other])]
            with self.assertRaisesRegex(ValueError, "outside the captured scope"):
                validate_result(result, engine.bundle, plan)


if __name__ == "__main__":
    unittest.main()

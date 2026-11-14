"""Exterior lower bounds and spatial uncertainty keep their distinct semantics."""
from pathlib import Path
import tempfile
import unittest

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from ifc_engine.catalog import POLICIES
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_exterior_queries import exterior_source
from tests.test_ifc_spatial_queries import spatial_source


class IfcMergeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def engine(self, fixture):
        path = Path(self.directory.name) / (fixture.__name__ + ".ifc")
        fixture(path)
        return IfcQueryEngine.open(path)

    @staticmethod
    def selection(engine, concept, names):
        return m.PlanStep(id="selected", operation=m.SelectOperation(
            kind="select", concept_ids=[concept], count_policy=POLICIES["all_matches"],
            where=m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"),
                operator="in", value=m.ListValue(kind="list", items=[
                    m.ReferencesValue(kind="references", entity_ids=[engine.resolve_entity(name)])
                    for name in names]))))

    def execute(self, engine, steps):
        plan = m.QueryPlan(id="plan:merge", request_id="request:merge", scope=engine.scope(),
            steps=steps, outputs={"answer": steps[-1].id})
        validate_plan(plan, engine.bundle, engine.capabilities)
        result = engine.execute(plan)
        validate_bundle(engine.bundle)
        validate_result(result, engine.bundle, plan)
        return result

    def exterior_steps(self, engine, method="auto"):
        return [self.selection(engine, "concept:door", ["direct", "unknown"]),
            m.PlanStep(id="exterior", operation=m.SpatialQueryOperation(kind="spatial_query",
                input_step_id="selected", relation="exterior_doors", method=method)),
            m.PlanStep(id="count", operation=m.AggregateOperation(kind="aggregate",
                input_step_id="exterior", method="count"))]

    def test_exterior_lower_bound_keeps_quality_unresolved_coverage_and_operation_proof(self):
        engine = self.engine(exterior_source)
        result = self.execute(engine, self.exterior_steps(engine))
        self.assertEqual(result.status, "partial")
        claim = result.claims[0]
        self.assertEqual(claim.value.value, 1)
        self.assertEqual(claim.quality, "lower_bound")
        calculations = {node.plan_step_id: node for node in result.calculations}
        self.assertEqual(calculations["exterior"].quality, "lower_bound")
        self.assertEqual(calculations["count"].quality, "lower_bound")
        coverage = next(item for item in engine.bundle.coverage if item.id in claim.coverage_ids)
        self.assertEqual(coverage.completeness, "partial")
        self.assertEqual(coverage.unresolved_entity_ids, [engine.resolve_entity("unknown")])
        self.assertEqual([key.split(":", 1)[0] for key in coverage.operation_keys],
            ["select", "spatial_query", "aggregate"])
        self.assertTrue(coverage.provenance.anchor_ids)

    def test_unresolved_or_candidate_topology_cannot_become_an_exact_related_count(self):
        engine = self.engine(spatial_source)
        for names, relation in [(["1B07", "7.16"], "door_connections"),
                                (["1B07"], "boundary_neighbors")]:
            with self.subTest(relation=relation):
                result = self.execute(engine, [self.selection(engine, "concept:space", names),
                    m.PlanStep(id="topology", operation=m.SpatialQueryOperation(kind="spatial_query",
                        input_step_id="selected", relation=relation, method="native")),
                    m.PlanStep(id="related", operation=m.RelatedEntitiesOperation(kind="related_entities",
                        input_step_id="topology")),
                    m.PlanStep(id="count", operation=m.AggregateOperation(kind="aggregate",
                        input_step_id="related", method="count"))])
                self.assertEqual(result.status, "incomplete_coverage")
                self.assertFalse(result.claims)

    def test_geometry_method_cannot_silently_use_exterior_classifications(self):
        engine = self.engine(exterior_source)
        result = self.execute(engine, self.exterior_steps(engine, method="geometry"))
        self.assertEqual(result.status, "unsupported_operation")
        self.assertFalse(result.claims)


if __name__ == "__main__":
    unittest.main()

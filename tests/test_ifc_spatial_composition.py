"""Spatial compositions count source objects and retain uncertainty and evidence."""
from pathlib import Path
import tempfile
import unittest

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from ifc_engine.catalog import POLICIES
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_spatial_queries import spatial_source


class SpatialCompositionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        path = Path(self.directory.name) / "composition.ifc"
        spatial_source(path)
        self.engine = IfcQueryEngine.open(path)

    def plan(self, names, relation, *, count=True):
        ids = [self.engine.resolve_entity(name) for name in names]
        steps = [m.PlanStep(id="rooms", operation=m.SelectOperation(
            kind="select", concept_ids=["concept:space"], count_policy=POLICIES["all_matches"],
            where=m.BooleanPredicate(kind="any", operands=[m.ComparePredicate(
                kind="compare", field=m.FieldRef(kind="entity_id", key="id"), operator="eq",
                value=m.ReferencesValue(kind="references", entity_ids=[item])) for item in ids]))),
            m.PlanStep(id="connections", operation=m.SpatialQueryOperation(
                kind="spatial_query", input_step_id="rooms", relation=relation, method="native")),
            m.PlanStep(id="related", operation=m.RelatedEntitiesOperation(
                kind="related_entities", input_step_id="connections"))]
        if count:
            steps.append(m.PlanStep(id="total", operation=m.AggregateOperation(
                kind="aggregate", input_step_id="related", method="count")))
        return m.QueryPlan(id="plan:composition", request_id="request:composition",
                           scope=self.engine.scope(), steps=steps, outputs={"answer": steps[-1].id})

    def execute(self, plan):
        validate_plan(plan, self.engine.bundle, self.engine.capabilities)
        result = self.engine.execute(plan)
        validate_bundle(self.engine.bundle)
        validate_result(result, self.engine.bundle, plan)
        return result

    def test_connected_room_count_excludes_origin_door_and_duplicate_boundaries(self):
        result = self.execute(self.plan(["1B07"], "door_connections"))
        self.assertEqual(result.status, "answered")
        self.assertEqual(result.claims[0].value.value, 1)
        counted = next(item for item in result.entity_sets if item.id == "set:total")
        self.assertEqual(counted.entity_ids, [self.engine.resolve_entity("1B08")])
        calculation = next(item for item in result.calculations if item.id == "calculation:total")
        self.assertTrue(calculation.spatial_evidence)
        self.assertTrue(calculation.anchor_ids)

    def test_related_rooms_can_feed_property_projection(self):
        plan = self.plan(["1B07"], "door_connections", count=False)
        plan.steps.append(m.PlanStep(id="labels", operation=m.ProjectOperation(
            kind="project", input_step_id="related", fields=[m.FieldRef(kind="label", key="label")])))
        plan.outputs = {"answer": "labels"}
        result = self.execute(plan)
        self.assertEqual(result.status, "answered")
        self.assertEqual(result.claims[0].value.rows[0]["label"].value.text, "1B08")

    def test_candidate_neighbors_cannot_be_promoted_to_an_exact_count(self):
        result = self.execute(self.plan(["1B07"], "boundary_neighbors"))
        self.assertEqual(result.status, "incomplete_coverage")
        self.assertFalse(result.claims)

    def test_unknown_room_does_not_become_zero_in_aggregate(self):
        result = self.execute(self.plan(["1B07", "7.16"], "door_connections"))
        self.assertEqual(result.status, "incomplete_coverage")
        self.assertFalse(result.claims)

    def test_partial_related_report_retains_verified_members_and_unknown_inputs(self):
        result = self.execute(self.plan(["1B07", "7.16"], "door_connections", count=False))
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.claims[0].value.entity_ids, [self.engine.resolve_entity("1B08")])
        coverage = next(item for item in self.engine.bundle.coverage if item.id in result.claims[0].coverage_ids)
        self.assertEqual(coverage.completeness, "partial")
        self.assertEqual(coverage.unresolved_entity_ids, [self.engine.resolve_entity("7.16")])

    def test_different_spatial_relations_have_distinct_coverage(self):
        first = self.execute(self.plan(["1B07"], "door_connections", count=False))
        second = self.execute(self.plan(["1B07"], "boundary_neighbors", count=False))
        self.assertNotEqual(first.claims[0].coverage_ids, second.claims[0].coverage_ids)
        self.assertEqual(second.claims[0].quality, "estimated")

    def test_related_entities_rejects_non_reference_column_before_execution(self):
        plan = self.plan(["1B07"], "door_connections", count=False)
        plan.steps[-1].operation.column = "basis"
        with self.assertRaisesRegex(ValueError, "references column"):
            validate_plan(plan, self.engine.bundle, self.engine.capabilities)

    def test_projected_candidate_labels_keep_candidate_cell_evidence(self):
        plan = self.plan(["1B07"], "boundary_neighbors", count=False)
        plan.steps.append(m.PlanStep(id="labels", operation=m.ProjectOperation(
            kind="project", input_step_id="related", fields=[m.FieldRef(kind="label", key="label")])))
        plan.outputs = {"answer": "labels"}
        result = self.execute(plan)
        self.assertEqual(result.status, "partial")
        claim = result.claims[0]
        index = next(index for index, row in enumerate(claim.value.rows) if row["label"].value.text == "121.A")
        cell = next(binding for binding in claim.evidence if binding.value_path == f"/rows/{index}/label")
        self.assertEqual(cell.evidence_kind, "candidate")

    def test_reference_projection_cannot_escape_exact_scope(self):
        bundle = self.engine.bundle.model_copy(deep=True)
        origin, hidden = (self.engine.resolve_entity(name) for name in ("1B07", "1B08"))
        key = "test:references"
        bundle.properties.append(m.PropertyDefinition(key=key, labels=[], value_kind="references", definition="Test source reference"))
        bundle.facts.append(m.Fact(id="fact:reference", subject_id=origin, property_key=key, status="present",
            value=m.ReferencesValue(kind="references", entity_ids=[hidden]), provenance=self.engine.entities[origin].provenance))
        self.engine = IfcQueryEngine(bundle)
        plan = self.plan(["1B07"], "door_connections", count=False)
        plan.scope.exact_entity_ids = [origin]
        plan.steps = [plan.steps[0], m.PlanStep(id="references", operation=m.ProjectOperation(
            kind="project", input_step_id="rooms", fields=[m.FieldRef(kind="property", key=key)])),
            m.PlanStep(id="related", operation=m.RelatedEntitiesOperation(kind="related_entities",
                input_step_id="references", column=key))]
        result = self.execute(plan)
        self.assertEqual(result.status, "incomplete_coverage")
        self.assertFalse(result.claims)

    def test_boundary_step_locator_cannot_disagree_with_its_source_anchor(self):
        bundle = self.engine.bundle.model_copy(deep=True)
        bundle.space_boundaries[0].native_step_id = 999999
        with self.assertRaisesRegex(ValueError, "STEP locator"):
            validate_bundle(bundle)


if __name__ == "__main__":
    unittest.main()

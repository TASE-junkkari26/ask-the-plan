"""Deferred engine fields consult native data before absence or zero claims."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from ifc_engine.catalog import CLASS_KEY, attribute_key
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_engine import sample_model
from tests.test_ifc_exterior_queries import exterior_source


@dataclass
class Batch:
    facts: list
    anchors: list
    units: list
    checked_pairs: set


class SourceFacts:
    """Replay an independently extracted native fixture, without inference."""

    def __init__(self, source_bundle, failure=None):
        self.bundle = source_bundle
        self.checked = set()
        self.emitted = set()
        self.failure = failure
        self.calls = []

    def ensure_fields(self, entities, keys):
        self.calls.append((set(entities), set(keys)))
        if self.failure:
            class Failure(ValueError):
                code = self.failure
            raise Failure("Private native implementation detail")
        pairs = {(entity, key) for entity in entities for key in keys} - self.checked
        facts = [fact for fact in self.bundle.facts if (fact.subject_id, fact.property_key) in pairs]
        self.checked.update(pairs)
        self.emitted.update(fact.id for fact in facts)
        return Batch(facts, self.bundle.anchors, self.bundle.units, pairs)

    def reset(self):
        emitted = self.emitted
        self.emitted, self.checked = set(), set()
        return emitted


class IfcEngineHydrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "native.ifc"
        sample_model(cls.path)
        cls.source = IfcQueryEngine.open(cls.path).bundle

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        bundle = self.source.model_copy(deep=True)
        bundle.facts = [fact for fact in bundle.facts if fact.property_key == CLASS_KEY]
        self.engine = IfcQueryEngine(bundle)
        self.engine.hydrator = SourceFacts(self.source.model_copy(deep=True))

    def test_deferred_quantity_is_loaded_before_a_sum_and_exported_as_source_proof(self):
        plan = self.engine.plan("door", operation="sum", property="OverallWidth", storey="Ground", unit="m")
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(Decimal(result.claims[0].value.magnitude), 2)
        self.assertTrue(result.claims[0].evidence[0].fact_ids)
        validate_bundle(self.engine.bundle)
        validate_result(result, self.engine.bundle, plan)
        self.assertTrue(any(len(entities) == 2 and keys == {attribute_key("OverallWidth")}
                            for entities, keys in self.engine.hydrator.calls))

    def test_source_null_is_consulted_before_a_field_present_filter(self):
        plan = self.engine.plan("door")
        plan.steps[0].operation.where = m.PresentPredicate(kind="field_present", field=m.FieldRef(kind="property", key=attribute_key("OverallWidth")))
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(result.claims[0].value.value, 2)
        door = self.engine.resolve_entity("D3")
        self.assertIn((door, attribute_key("OverallWidth")), self.engine.hydrator.checked)
        self.assertEqual(self.engine.facts[door, attribute_key("OverallWidth")][0].status, "explicit_null")

    def test_reset_drops_only_request_facts_and_a_new_question_reloads_them(self):
        core = {fact.id for fact in self.engine.bundle.facts}
        first = self.engine.query("door", operation="sum", property="OverallWidth", storey="Ground", unit="m")
        exported = self.engine.bundle.model_copy(deep=True)
        self.engine.clear_hydration()
        self.assertEqual({fact.id for fact in self.engine.bundle.facts}, core)
        self.assertFalse(self.engine.hydrator.checked)
        validate_result(first, exported)
        second = self.engine.query("door", operation="sum", property="OverallWidth", storey="Ground", unit="m")
        self.assertEqual(second.status, "answered", second.model_dump_json())
        self.assertEqual(Decimal(second.claims[0].value.magnitude), 2)
        self.assertEqual(set(first.claims[0].evidence[0].fact_ids), set(second.claims[0].evidence[0].fact_ids))

    def test_real_native_reset_releases_request_anchors_and_preserves_exported_proof(self):
        engine = IfcQueryEngine.open(self.path, defer_properties=True)
        self.addCleanup(engine.hydrator.close)
        core_anchors = set(engine.anchors)
        first = engine.query("door", operation="sum", property="OverallWidth", storey="Ground", unit="m")
        self.assertEqual(first.status, "answered", first.model_dump_json())
        self.assertGreater(len(engine.anchors), len(core_anchors))
        proof = engine.bundle.model_copy(deep=True)
        engine.clear_hydration()
        self.assertEqual(set(engine.anchors), core_anchors)
        self.assertEqual({anchor.id for anchor in engine.bundle.anchors}, core_anchors)
        validate_bundle(engine.bundle)
        validate_result(first, proof)
        second = engine.query("door", operation="sum", property="OverallWidth", storey="Ground", unit="m")
        self.assertEqual(second.status, "answered", second.model_dump_json())
        self.assertEqual(set(first.claims[0].evidence[0].anchor_ids), set(second.claims[0].evidence[0].anchor_ids))

    def test_dense_source_auto_defers_and_does_not_reuse_a_forced_eager_cache(self):
        with tempfile.TemporaryDirectory() as cache:
            eager = IfcQueryEngine.open(self.path, cache_dir=cache, defer_properties=False)
            self.assertIsNone(eager.hydrator)
            self.assertEqual(len(list(Path(cache).glob("*.json"))), 1)
            with patch("ifc_engine.ingest.DEFER_PRODUCT_COUNT", 5):
                lazy = IfcQueryEngine.open(self.path, cache_dir=cache)
            self.addCleanup(lazy.hydrator.close)
            self.assertIsNotNone(lazy.hydrator)
            self.assertFalse(lazy.cache_hit)
            self.assertEqual(len(list(Path(cache).glob("*.json"))), 1)
            self.assertEqual(lazy.query("door").claims[0].value.value, 3)
            cached = IfcQueryEngine.open(self.path, cache_dir=cache, defer_properties=False)
            self.assertTrue(cached.cache_hit)

    def test_hydration_budget_failure_never_becomes_a_missing_field_or_zero(self):
        self.engine.hydrator.failure = "unsupported_operation"
        plan = self.engine.plan("door")
        plan.steps[0].operation.where = m.PresentPredicate(kind="field_present", field=m.FieldRef(kind="property", key=attribute_key("OverallWidth")))
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "unsupported_operation", result.model_dump_json())
        self.assertFalse(result.claims)
        self.assertNotIn("Private", result.model_dump_json())

    def test_a_native_class_count_needs_no_property_hydration(self):
        result = self.engine.query("door")
        self.assertEqual(result.status, "answered")
        self.assertEqual(result.claims[0].value.value, 3)
        self.assertFalse(self.engine.hydrator.calls)

    def test_identity_filters_reject_mistyped_or_nonsingleton_ids_before_source_reads(self):
        identifiers = [self.engine.resolve_entity(name) for name in ("D1", "D2")]
        ref = m.FieldRef(kind="entity_id", key="entity_id")
        invalid = [
            ("eq", m.TextValue(kind="text", value=m.LocalizedText(text="e#123"))),
            ("ne", m.ReferencesValue(kind="references", entity_ids=identifiers)),
            ("in", m.ReferencesValue(kind="references", entity_ids=identifiers)),
            ("in", m.ListValue(kind="list", items=[m.ReferencesValue(kind="references", entity_ids=identifiers)])),
            ("contains", m.ReferencesValue(kind="references", entity_ids=identifiers[:1])),
        ]
        for operator, value in invalid:
            with self.subTest(operator=operator, value=value.kind):
                plan = self.engine.plan("door")
                plan.steps[0].operation.where = m.ComparePredicate(kind="compare", field=ref, operator=operator, value=value)
                with self.assertRaises(ValueError):
                    validate_plan(plan, self.engine.bundle, self.engine.capabilities)
                result = self.engine.execute(plan)
                self.assertEqual(result.status, "execution_error", result.model_dump_json())
                self.assertFalse(result.claims)
        self.assertFalse(self.engine.hydrator.calls)

    def test_identity_in_list_remains_an_exact_guard_without_property_hydration(self):
        identifiers = [self.engine.resolve_entity(name) for name in ("D1", "D2")]
        plan = self.engine.plan("door")
        plan.steps[0].operation.where = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="entity_id"),
            operator="in", value=m.ListValue(kind="list", items=[m.ReferencesValue(kind="references", entity_ids=[identifier])
                for identifier in identifiers]))
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(result.claims[0].value.value, 2)
        self.assertFalse(self.engine.hydrator.calls)

    def test_native_identifier_filter_requires_a_supported_key_and_text_value(self):
        identifier = self.engine.resolve_entity("D1")
        for key, value in [("step_id", m.ReferencesValue(kind="references", entity_ids=[identifier])),
                           ("unsupported_locator", m.TextValue(kind="text", value=m.LocalizedText(text="123")))]:
            plan = self.engine.plan("door")
            plan.steps[0].operation.where = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="native_identifier", key=key),
                operator="eq", value=value)
            with self.assertRaises(ValueError):
                validate_plan(plan, self.engine.bundle, self.engine.capabilities)
            result = self.engine.execute(plan)
            self.assertEqual(result.status, "execution_error", result.model_dump_json())
            self.assertFalse(result.claims)
        self.assertFalse(self.engine.hydrator.calls)

    def test_identity_guard_limits_property_hydration_to_the_named_occurrence(self):
        identifier = self.engine.resolve_entity("D1")
        plan = self.engine.plan("door")
        plan.steps[0].operation.where = m.BooleanPredicate(kind="all", operands=[
            m.PresentPredicate(kind="field_present", field=m.FieldRef(kind="property", key=attribute_key("OverallWidth"))),
            m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"), operator="eq",
                value=m.ReferencesValue(kind="references", entity_ids=[identifier])),
        ])
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(result.claims[0].value.value, 1)
        self.assertTrue(self.engine.hydrator.calls)
        self.assertTrue(all(entities == {identifier} for entities, _ in self.engine.hydrator.calls))

    def test_decisive_identity_or_guard_needs_no_irrelevant_property_read(self):
        identifier = self.engine.resolve_entity("D1")
        plan = self.engine.plan("door", entity="D1")
        plan.steps[0].operation.where = m.BooleanPredicate(kind="any", operands=[
            m.PresentPredicate(kind="field_present", field=m.FieldRef(kind="property", key=attribute_key("OverallWidth"))),
            m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"), operator="eq",
                value=m.ReferencesValue(kind="references", entity_ids=[identifier])),
        ])
        self.engine.hydrator.failure = "unsupported_operation"
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(result.claims[0].value.value, 1)
        self.assertFalse(self.engine.hydrator.calls)

    def test_irrelevant_ambiguous_property_does_not_break_a_decisive_boolean(self):
        key = attribute_key("OverallWidth")
        # The native width on D1 is unknown; every door still has a recorded
        # false second comparison, so the conjunction is source-provably false.
        for fact in self.engine.hydrator.bundle.facts:
            if fact.subject_id == self.engine.resolve_entity("D1") and fact.property_key == key:
                fact.status, fact.value = "ambiguous", None
        plan = self.engine.plan("door")
        plan.steps[0].operation.where = m.BooleanPredicate(kind="all", operands=[
            m.PresentPredicate(kind="field_present", field=m.FieldRef(kind="property", key=key)),
            m.ComparePredicate(kind="compare", field=m.FieldRef(kind="property", key=attribute_key("Name")), operator="eq",
                value=m.TextValue(kind="text", value=m.LocalizedText(text="Not a source door"))),
        ])
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(result.claims[0].value.value, 0)

    def test_ambiguous_property_stays_an_error_without_a_decisive_boolean(self):
        key = attribute_key("OverallWidth")
        for fact in self.engine.hydrator.bundle.facts:
            if fact.subject_id == self.engine.resolve_entity("D1") and fact.property_key == key:
                fact.status, fact.value = "ambiguous", None
        plan = self.engine.plan("door", entity="D1")
        plan.steps[0].operation.where = m.BooleanPredicate(kind="all", operands=[
            m.PresentPredicate(kind="field_present", field=m.FieldRef(kind="property", key=key)),
            m.ComparePredicate(kind="compare", field=m.FieldRef(kind="property", key=attribute_key("Name")), operator="eq",
                value=m.TextValue(kind="text", value=m.LocalizedText(text="D1"))),
        ])
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "incomplete_coverage", result.model_dump_json())
        self.assertFalse(result.claims)

    def test_outside_scope_relationship_target_is_unknown_instead_of_an_exact_zero(self):
        identifier = self.engine.resolve_entity("D1")
        native_type = self.engine.resolve_entity("Door type")
        plan = self.engine.plan("door")
        plan.scope.exact_entity_ids = [identifier]
        plan.steps[0].operation.where = m.RelationPredicate(kind="related_to", predicate="typed_by", direction="outgoing", entity_ids=[native_type])
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "incomplete_coverage", result.model_dump_json())
        self.assertFalse(result.claims)
        self.assertEqual(result.issues[0].entity_ids, [identifier])
        plan.scope.exact_entity_ids = None
        result = self.engine.execute(plan)
        self.assertEqual((result.status, result.claims[0].value.value), ("answered", 2))

    def test_decisive_identity_guard_can_make_an_outside_relation_target_irrelevant(self):
        plan = self.engine.plan("door")
        plan.scope.exact_entity_ids = [self.engine.resolve_entity("D1")]
        plan.steps[0].operation.where = m.BooleanPredicate(kind="all", operands=[
            m.RelationPredicate(kind="related_to", predicate="typed_by", direction="outgoing", entity_ids=[self.engine.resolve_entity("Door type")]),
            m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"), operator="eq",
                value=m.ReferencesValue(kind="references", entity_ids=[self.engine.resolve_entity("D2")])),
        ])
        result = self.engine.execute(plan)
        self.assertEqual((result.status, result.claims[0].value.value), ("answered", 0))

    def test_hidden_type_traversal_is_incomplete_instead_of_empty_materials(self):
        plan = self.engine.plan("door", entity="D1")
        plan.scope.exact_entity_ids = [self.engine.resolve_entity("D1")]
        plan.steps = [plan.steps[0], m.PlanStep(id="type", operation=m.TraverseOperation(kind="traverse", input_step_id="objects",
            predicate="typed_by", direction="outgoing")), m.PlanStep(id="materials", operation=m.TraverseOperation(kind="traverse",
            input_step_id="type", predicate="has_material", direction="outgoing"))]
        plan.outputs = {"answer": "materials"}
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "incomplete_coverage", result.model_dump_json())
        self.assertFalse(result.claims)
        plan.scope = self.engine.scope()
        plan.steps[0].operation.where = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"), operator="eq",
            value=m.ReferencesValue(kind="references", entity_ids=[self.engine.resolve_entity("D1")]))
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual([self.engine.entities[identifier].labels[0].text for identifier in result.claims[0].value.entity_ids], ["Timber"])

    def test_recursive_traversal_does_not_hide_an_outside_intermediate(self):
        plan = self.engine.plan("stair", entity="Stair assembly")
        plan.scope.exact_entity_ids = [self.engine.resolve_entity("Stair assembly"), self.engine.resolve_entity("RISER")]
        plan.steps = [plan.steps[0], m.PlanStep(id="parts", operation=m.TraverseOperation(kind="traverse", input_step_id="objects",
            predicate="aggregates", direction="outgoing", recursive=True))]
        plan.outputs = {"answer": "parts"}
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "incomplete_coverage", result.model_dump_json())
        self.assertFalse(result.claims)

    def test_exterior_classification_consults_deferred_flags_and_type_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exterior.ifc"
            _, objects, _ = exterior_source(path, boundaries=False)
            engine = IfcQueryEngine.open(path, defer_properties=True)
            self.addCleanup(engine.hydrator.close)
            ids = [engine.resolve_entity(objects[key].GlobalId) for key in ("direct", "interior", "inherited", "override")]
            plan = engine.plan("door")
            plan.steps[0].operation.where = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"),
                operator="in", value=m.ListValue(kind="list", items=[m.ReferencesValue(kind="references", entity_ids=[identifier]) for identifier in ids]))
            plan.steps = [plan.steps[0], m.PlanStep(id="outside", operation=m.SpatialQueryOperation(kind="spatial_query",
                input_step_id="objects", relation="exterior_doors", exterior_basis="classification")),
                m.PlanStep(id="count", operation=m.AggregateOperation(kind="aggregate", input_step_id="outside", method="count"))]
            plan.outputs = {"answer": "count"}
            for _ in range(2):
                result = engine.execute(plan)
                self.assertEqual((result.status, result.claims[0].value.value), ("answered", 2), result.model_dump_json())
                self.assertTrue(result.claims[0].evidence[0].fact_ids)
                validate_result(result, engine.bundle, plan)
                engine.clear_hydration()


if __name__ == "__main__":
    unittest.main()

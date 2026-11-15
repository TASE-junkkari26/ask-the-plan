"""Contradictory native typing preserves counts, uncertainty and source proof."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_bundle, validate_result
from ifc_engine.catalog import POLICIES
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_engine import sample_model


class MultipleTypeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "multiple-types.ifc"
        self.source, self.doors, self.rooms, _, self.ground, _ = sample_model(self.path)

    def root(self, kind, **options):
        return self.source.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **options)

    def pset(self, name, value):
        prop = self.source.create_entity("IfcPropertySingleValue", Name=name,
                                         NominalValue=self.source.create_entity("IfcLabel", value))
        return self.root("IfcPropertySet", Name="Specifications", HasProperties=[prop])

    def type(self, obj, name, *, kind="IfcSpaceType", properties=()):
        native_type = self.root(kind, Name=name, PredefinedType="NOTDEFINED", HasPropertySets=list(properties))
        relation = self.root("IfcRelDefinesByType", RelatedObjects=[obj], RelatingType=native_type)
        return native_type, relation

    def engine(self, deferred):
        self.source.write(str(self.path))
        engine = IfcQueryEngine.open(self.path, defer_properties=deferred)
        if engine.hydrator:
            self.addCleanup(engine.hydrator.close)
        validate_bundle(engine.bundle)
        return engine

    def test_multiple_space_types_do_not_reject_the_model_or_duplicate_spaces(self):
        for name in ("A", "B", "C"):
            self.type(self.rooms[0], name)
        for deferred in (False, True):
            engine = self.engine(deferred)
            result = engine.query("space")
            self.assertEqual(result.status, "answered", result.model_dump_json())
            self.assertEqual(result.claims[0].value.value, 2)
            result = engine.query("space", entity="7.16", operation="lookup", property="SourceContext.TypeName")
            self.assertEqual(result.status, "incomplete_coverage", result.model_dump_json())

    def test_conflicting_inheritance_exports_all_type_relationship_proof(self):
        pairs = [self.type(self.rooms[0], value, properties=[self.pset("Rating", value)]) for value in ("A", "B")]
        for deferred in (False, True):
            engine = self.engine(deferred)
            result = engine.query("space", entity="7.16", operation="lookup", property="Specifications.Rating")
            self.assertEqual(result.status, "conflicting_evidence", result.model_dump_json())
            facts = {fact.id: fact for fact in engine.bundle.facts}
            anchors = {anchor for fact_id in result.issues[0].fact_ids for anchor in facts[fact_id].provenance.anchor_ids}
            steps = {engine.anchors[anchor].selector.value for anchor in anchors}
            self.assertTrue({str(relation.id()) for _, relation in pairs} <= steps)
            validate_result(result, engine.bundle)

    def test_missing_property_on_one_type_is_unresolved_instead_of_picking_the_other(self):
        self.type(self.rooms[0], "A", properties=[self.pset("Rating", "A")])
        self.type(self.rooms[0], "B")
        for deferred in (False, True):
            engine = self.engine(deferred)
            result = engine.query("space", entity="7.16", operation="lookup", property="Specifications.Rating")
            self.assertEqual(result.status, "incomplete_coverage", result.model_dump_json())

    def test_occurrence_override_replaces_all_conflicting_inherited_values(self):
        for value in ("A", "B"):
            self.type(self.rooms[0], value, properties=[self.pset("Rating", value)])
        self.root("IfcRelDefinesByProperties", RelatedObjects=[self.rooms[0]], RelatingPropertyDefinition=self.pset("Rating", "Own"))
        for deferred in (False, True):
            engine = self.engine(deferred)
            result = engine.query("space", entity="7.16", operation="lookup", property="Specifications.Rating")
            self.assertEqual(result.status, "answered", result.model_dump_json())
            self.assertEqual(next(iter(result.claims[0].value.rows[0].values())).kind, "references")
            self.assertTrue(any(value.kind == "text" and value.value.text == "Own"
                                for value in result.claims[0].value.rows[0].values()))

    def test_identical_inherited_values_remain_usable_despite_type_identity_ambiguity(self):
        for name in ("A", "B"):
            self.type(self.rooms[0], name, properties=[self.pset("Rating", "Shared")])
        for deferred in (False, True):
            engine = self.engine(deferred)
            result = engine.query("space", entity="7.16", operation="lookup", property="Specifications.Rating")
            self.assertEqual(result.status, "answered", result.model_dump_json())
            self.assertTrue(any(value.kind == "text" and value.value.text == "Shared"
                                for value in result.claims[0].value.rows[0].values()))

    def ambiguous_fixture(self):
        fixture = self.root("IfcFlowTerminal", Name="Ambiguous fixture")
        self.type(fixture, "Sanitary candidate", kind="IfcSanitaryTerminalType")
        self.type(fixture, "Lighting candidate", kind="IfcLightFixtureType")
        return fixture

    def test_ambiguous_generic_fixture_never_becomes_a_zero_semantic_count(self):
        self.ambiguous_fixture()
        for deferred in (False, True):
            engine = self.engine(deferred)
            for concept in ("sanitary_terminal", "light_fixture"):
                result = engine.query(concept)
                self.assertEqual(result.status, "conflicting_evidence", result.model_dump_json())
                self.assertFalse(result.claims)
            native = engine.query("IfcFlowTerminal")
            self.assertEqual((native.status, native.claims[0].value.value), ("answered", 1))

    def test_ambiguous_type_can_be_irrelevant_to_a_captured_view_or_identity_filter(self):
        self.ambiguous_fixture()
        known = self.root("IfcSanitaryTerminal", Name="Known fixture", PredefinedType="NOTDEFINED")
        engine = self.engine(True)
        plan = engine.plan("sanitary_terminal")
        identifier = engine.resolve_entity("Known fixture")
        plan.scope.exact_entity_ids = [identifier]
        result = engine.execute(plan)
        self.assertEqual((result.status, result.claims[0].value.value), ("answered", 1))
        plan.scope.exact_entity_ids = None
        plan.steps[0].operation.where = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"),
            operator="eq", value=m.ReferencesValue(kind="references", entity_ids=[identifier]))
        result = engine.execute(plan)
        self.assertEqual((result.status, result.claims[0].value.value), ("answered", 1))

    def test_union_of_all_candidate_semantic_categories_counts_the_occurrence_once(self):
        self.ambiguous_fixture()
        engine = self.engine(False)
        plan = engine.plan("sanitary_terminal")
        plan.steps[0].operation.concept_ids = ["concept:sanitary_terminal", "concept:light_fixture"]
        result = engine.execute(plan)
        self.assertEqual((result.status, result.claims[0].value.value), ("answered", 1))

    def test_distinct_types_agreeing_on_semantic_category_keep_a_complete_count(self):
        fixture = self.root("IfcFlowTerminal", Name="Typed fixture")
        self.type(fixture, "Sanitary A", kind="IfcSanitaryTerminalType")
        self.type(fixture, "Sanitary B", kind="IfcSanitaryTerminalType")
        for deferred in (False, True):
            engine = self.engine(deferred)
            result = engine.query("sanitary_terminal")
            self.assertEqual((result.status, result.claims[0].value.value), ("answered", 1))

    def test_inherited_material_ambiguity_and_own_override_remain_distinct(self):
        for name in ("Timber", "Concrete"):
            native_type, _ = self.type(self.rooms[0], name)
            material = self.source.create_entity("IfcMaterial", Name=name)
            self.root("IfcRelAssociatesMaterial", RelatedObjects=[native_type], RelatingMaterial=material)
        for own in (False, True):
            if own:
                material = self.source.create_entity("IfcMaterial", Name="Brick")
                self.root("IfcRelAssociatesMaterial", RelatedObjects=[self.rooms[0]], RelatingMaterial=material)
            for deferred in (False, True):
                engine = self.engine(deferred)
                plan = engine.plan("space", entity="7.16", operation="lookup", property="Name")
                plan.scope = engine.scope()
                plan.steps[0].operation.where = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="id"),
                    operator="eq", value=m.ReferencesValue(kind="references", entity_ids=[engine.resolve_entity("7.16")]))
                plan.steps[-1].operation = m.TraverseOperation(kind="traverse", input_step_id="objects", predicate="has_material", direction="outgoing")
                result = engine.execute(plan)
                self.assertEqual(result.status, "answered" if own else "conflicting_evidence", result.model_dump_json())
                if own:
                    self.assertEqual([engine.entities[identifier].labels[0].text for identifier in result.claims[0].value.entity_ids], ["Brick"])


if __name__ == "__main__":
    unittest.main()

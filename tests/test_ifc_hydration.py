"""Deferred native properties are inspected before absence, with bounded proof."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

import ifcopenshell.guid

from contracts import models as m
from ifc_engine.catalog import attribute_key, property_key
from ifc_engine.hydration import HydrationError
from ifc_engine.ingest import load_ifc
from tests.test_ifc_engine import sample_model


class NativeHydrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "source.ifc"
        self.model, self.doors, self.rooms, _, self.ground, _ = sample_model(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def root(self, kind, **fields):
        return self.model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **fields)

    def load(self):
        self.model.write(str(self.path))
        return load_ifc(self.path, defer_properties=True)

    def identifier(self, loaded, name):
        return next(entity.id for entity in loaded.bundle.entities if any(label.text == name for label in entity.labels))

    def test_type_inheritance_occurrence_override_and_eager_fact_identity(self):
        loaded = self.load()
        eager = load_ifc(self.path, defer_properties=False)
        key = property_key("Pset_DoorCommon", "FireRating")
        ids = [self.identifier(loaded, name) for name in ["D1", "D2"]]
        self.assertFalse(any(f.property_key == key for f in loaded.bundle.facts))
        batch = loaded.hydrator.ensure_fields(ids, [key])
        self.assertEqual({fact.subject_id: fact.value.value.text for fact in batch.facts}, {ids[0]: "60 min", ids[1]: "90 min"})
        expected = {fact.id for fact in eager.bundle.facts if fact.property_key == key and fact.subject_id in ids}
        self.assertEqual({fact.id for fact in batch.facts}, expected)
        self.assertTrue(all(fact.provenance.anchor_ids for fact in batch.facts))
        self.assertFalse(loaded.hydrator.ensure_fields(ids, [key]).facts)

    def test_explicit_null_overrides_type_and_source_absence_is_checked_separately(self):
        native_type = self.model.by_type("IfcDoorType")[0]
        name = "AccessRequirement"
        definition = self.root("IfcPropertySet", Name="Pset_Access", HasProperties=[self.model.createIfcPropertySingleValue(
            name, None, self.model.createIfcLabel("staff"), None)])
        native_type.HasPropertySets = [*native_type.HasPropertySets, definition]
        own = self.root("IfcPropertySet", Name="Pset_Access", HasProperties=[self.model.createIfcPropertySingleValue(name, None, None, None)])
        self.root("IfcRelDefinesByProperties", RelatedObjects=[self.doors[0]], RelatingPropertyDefinition=own)
        loaded = self.load()
        key = property_key("Pset_Access", name)
        ids = [self.identifier(loaded, label) for label in ["D1", "D2", "D3"]]
        batch = loaded.hydrator.ensure_fields(ids, [key])
        facts = {fact.subject_id: fact for fact in batch.facts}
        self.assertEqual(facts[ids[0]].status, "explicit_null")
        self.assertIsNone(facts[ids[0]].value)
        self.assertEqual(facts[ids[1]].value.value.text, "staff")
        self.assertNotIn(ids[2], facts)
        self.assertIn((ids[2], key), batch.checked_pairs)

    def test_quantities_keep_explicit_units_normalization_and_all_unit_anchors(self):
        loaded = self.load()
        key = property_key("Qto_SpaceBaseQuantities", "NetFloorArea")
        room = self.identifier(loaded, "7.16")
        batch = loaded.hydrator.ensure_fields([room], [key])
        self.assertEqual(len(batch.facts), 2)  # Distinct native duplicate records remain source evidence.
        for fact in batch.facts:
            self.assertEqual(fact.value.unit_resolution, "explicit")
            self.assertEqual(Decimal(fact.value.normalized.magnitude), Decimal(19))
            self.assertTrue(set(fact.value.unit_anchor_ids) <= {anchor.id for anchor in batch.anchors})

    def test_scalar_fields_include_literal_name_and_explicit_null(self):
        loaded = self.load()
        door = self.identifier(loaded, "D3")
        batch = loaded.hydrator.ensure_fields([door], [attribute_key("Name"), attribute_key("OverallWidth")])
        facts = {fact.property_key: fact for fact in batch.facts}
        self.assertEqual(facts[attribute_key("Name")].value.value.text, "D3")
        self.assertEqual(facts[attribute_key("OverallWidth")].status, "explicit_null")

    def test_derived_context_and_material_use_cached_native_indexes(self):
        loaded = self.load()
        door = self.identifier(loaded, "D1")
        context = property_key("SourceContext", "StoreyName")
        material = property_key("SourceMaterial", "Names")
        batch = loaded.hydrator.ensure_fields([door], [context])
        self.assertEqual(len(batch.facts), 1)
        self.assertEqual(batch.facts[0].value.value.text, "Ground")
        indexes = loaded.hydrator._enrichment_indexes
        batch = loaded.hydrator.ensure_fields([door], [material])
        self.assertEqual(len(batch.facts), 1)
        self.assertEqual(batch.facts[0].value.value.text, "Timber")
        self.assertIs(loaded.hydrator._enrichment_indexes, indexes)
        self.assertGreater(len(batch.facts[0].provenance.anchor_ids), 1)

    def test_budget_failure_does_not_commit_checked_pairs_or_lose_evidence(self):
        loaded = self.load()
        hydrator = loaded.hydrator
        key = property_key("Pset_DoorCommon", "FireRating")
        ids = [self.identifier(loaded, name) for name in ["D1", "D2"]]
        hydrator.max_facts = 1
        with self.assertRaises(HydrationError) as error:
            hydrator.ensure_fields(ids, [key])
        self.assertEqual(error.exception.code, "unsupported_operation")
        self.assertFalse(any(hydrator.is_checked(identifier, key) for identifier in ids))
        self.assertFalse(hydrator._emitted)
        hydrator.max_facts = 2
        batch = hydrator.ensure_fields(ids, [key])
        self.assertEqual(len(batch.facts), 2)
        self.assertTrue(all(set(fact.provenance.anchor_ids) <= {anchor.id for anchor in batch.anchors} for fact in batch.facts))

    def test_pair_budget_is_checked_before_a_batch_can_become_false_absence(self):
        loaded = self.load()
        ids = [self.identifier(loaded, name) for name in ["D1", "D2"]]
        key = property_key("AbsentSet", "AbsentProperty")
        loaded.hydrator.max_pairs = 1
        with self.assertRaises(HydrationError):
            loaded.hydrator.ensure_fields(ids, [key])
        self.assertFalse(loaded.hydrator.is_checked(ids[0], key))
        batch = loaded.hydrator.ensure_fields(ids[:1], [key])
        self.assertFalse(batch.facts)
        self.assertEqual(batch.checked_pairs, {(ids[0], key)})

    def test_reset_removes_only_new_facts_and_rehydration_returns_anchor_proof_again(self):
        loaded = self.load()
        door = self.identifier(loaded, "D1")
        key = property_key("Pset_DoorCommon", "FireRating")
        base_anchor_ids = set(loaded.hydrator.extractor.anchors)
        first = loaded.hydrator.ensure_fields([door], [key])
        self.assertGreater(len(loaded.hydrator.extractor.anchors), len(base_anchor_ids))
        removed = loaded.hydrator.reset()
        self.assertEqual(removed, [first.facts[0].id])
        self.assertFalse(loaded.hydrator.is_checked(door, key))
        self.assertTrue(loaded.hydrator.is_checked(door, "ifc:class"))
        self.assertEqual(set(loaded.hydrator.extractor.anchors), base_anchor_ids)
        second = loaded.hydrator.ensure_fields([door], [key])
        self.assertEqual(first.facts[0].id, second.facts[0].id)
        self.assertTrue(set(second.facts[0].provenance.anchor_ids) <= {anchor.id for anchor in second.anchors})

    def test_source_change_or_closed_session_never_becomes_missing_property(self):
        loaded = self.load()
        door = self.identifier(loaded, "D1")
        self.path.write_bytes(self.path.read_bytes() + b"\n")
        with self.assertRaises(HydrationError) as error:
            loaded.hydrator.ensure_fields([door], [attribute_key("Name")])
        self.assertEqual(error.exception.code, "conflicting_evidence")
        self.assertFalse(loaded.hydrator.is_checked(door, attribute_key("Name")))
        loaded.hydrator.close()
        with self.assertRaises(HydrationError) as error:
            loaded.hydrator.ensure_fields([door], [attribute_key("Name")])
        self.assertEqual(error.exception.code, "missing_source")

    def test_mixed_global_property_types_retain_ambiguity_when_hydrated_individually(self):
        for door, value in [(self.doors[0], self.model.createIfcInteger(7)), (self.doors[1], self.model.createIfcLabel("seven"))]:
            definition = self.root("IfcPropertySet", Name="Mixed", HasProperties=[self.model.createIfcPropertySingleValue("Value", None, value, None)])
            self.root("IfcRelDefinesByProperties", RelatedObjects=[door], RelatingPropertyDefinition=definition)
        loaded = self.load()
        key = property_key("Mixed", "Value")
        batch = loaded.hydrator.ensure_fields([self.identifier(loaded, "D1")], [key])
        self.assertEqual(batch.facts[0].status, "ambiguous")
        self.assertIsNone(batch.facts[0].value)

    def add_second_type(self, door):
        properties = [self.model.createIfcPropertySingleValue("FireRating", None, self.model.createIfcLabel("120 min"), None),
            self.model.createIfcPropertySingleValue("AdditionalClassification", None, self.model.createIfcLabel("B"), None)]
        definition = self.root("IfcPropertySet", Name="Pset_DoorCommon", HasProperties=properties)
        native_type = self.root("IfcDoorType", Name="Contradictory additional type", HasPropertySets=[definition])
        relation = self.root("IfcRelDefinesByType", RelatedObjects=[door], RelatingType=native_type)
        return relation

    def test_multiple_types_keep_all_values_typing_proof_and_eager_identity(self):
        relation = self.add_second_type(self.doors[1])
        loaded = self.load()
        eager = load_ifc(self.path, defer_properties=False)
        door = self.identifier(loaded, "D2")
        key = property_key("Pset_DoorCommon", "FireRating")
        batch = loaded.hydrator.ensure_fields([door], [key])
        self.assertEqual({fact.value.value.text for fact in batch.facts}, {"90 min", "120 min"})
        self.assertEqual({fact.id for fact in batch.facts}, {fact.id for fact in eager.bundle.facts if fact.subject_id == door and fact.property_key == key})
        proof = {anchor.id: anchor for anchor in batch.anchors}
        self.assertTrue(all(any(proof[identifier].selector.value == str(relation.id()) for identifier in fact.provenance.anchor_ids) for fact in batch.facts))

    def test_multiple_type_missing_key_is_ambiguous_instead_of_verified_inheritance(self):
        self.add_second_type(self.doors[1])
        loaded = self.load()
        key = property_key("Pset_DoorCommon", "AdditionalClassification")
        batch = loaded.hydrator.ensure_fields([self.identifier(loaded, "D2")], [key])
        self.assertEqual({fact.status for fact in batch.facts}, {"present", "ambiguous"})
        self.assertTrue(all(fact.provenance.anchor_ids for fact in batch.facts))

    def test_occurrence_override_survives_conflicting_type_candidates(self):
        self.add_second_type(self.doors[0])
        loaded = self.load()
        key = property_key("Pset_DoorCommon", "FireRating")
        batch = loaded.hydrator.ensure_fields([self.identifier(loaded, "D1")], [key])
        self.assertEqual(len(batch.facts), 1)
        self.assertEqual(batch.facts[0].value.value.text, "60 min")


if __name__ == "__main__":
    unittest.main()

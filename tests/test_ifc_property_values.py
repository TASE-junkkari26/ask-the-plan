"""Native list/enum values retain source spelling, ordering, units and absence."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_bundle, validate_result
from ifc_engine.engine import IfcQueryEngine
from ifc_engine.catalog import property_key
from ifc_engine.property_values import MAX_COLLECTION_VALUES, collection_property_value
from tests.test_ifc_engine import sample_model


class IfcCollectionPropertyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "collections.ifc"
        self.model, self.doors, _, _, _, _ = sample_model(self.path)

    def attach(self, properties):
        definition = self.model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
                                             Name="Specifications", HasProperties=properties)
        self.model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                                 RelatedObjects=[self.doors[0]], RelatingPropertyDefinition=definition)
        self.model.write(str(self.path))
        engine = IfcQueryEngine.open(self.path)
        validate_bundle(engine.bundle)
        return engine

    def fact(self, engine, name):
        return engine.facts[engine.resolve_entity("D1"), property_key("Specifications", name)][0]

    def test_enum_returns_recorded_selections_not_all_allowed_values(self):
        allowed = [self.model.create_entity("IfcLabel", text) for text in ["121.A", "7.16", "Fenêtre"]]
        vocabulary = self.model.create_entity("IfcPropertyEnumeration", Name="Original source labels", EnumerationValues=allowed)
        prop = self.model.create_entity("IfcPropertyEnumeratedValue", Name="Classification", EnumerationValues=allowed[:2], EnumerationReference=vocabulary)
        engine = self.attach([prop])
        fact = self.fact(engine, "Classification")
        self.assertEqual(fact.status, "present")
        self.assertEqual([item.value.text for item in fact.value.items], ["121.A", "7.16"])
        result = engine.query("door", entity="D1", operation="lookup", property="Specifications.Classification")
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(result.claims[0].value.rows[0][property_key("Specifications", "Classification")], fact.value)
        validate_result(result, engine.bundle)

    def test_list_keeps_order_duplicates_booleans_and_literal_source_text(self):
        values = [self.model.create_entity("IfcText", "Äänieristys 121.A"), self.model.create_entity("IfcBoolean", False),
                  self.model.create_entity("IfcText", "Äänieristys 121.A"), self.model.create_entity("IfcCountMeasure", 2)]
        prop = self.model.create_entity("IfcPropertyListValue", Name="Materials", ListValues=values)
        fact = self.fact(self.attach([prop]), "Materials")
        self.assertEqual([item.kind for item in fact.value.items], ["text", "boolean", "text", "count"])
        self.assertEqual(fact.value.items[0], fact.value.items[2])
        self.assertIs(fact.value.items[1].value, False)
        self.assertEqual(fact.value.items[3].value, 2)

    def test_explicit_list_unit_overrides_project_default_for_every_value(self):
        metre = self.model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
        prop = self.model.create_entity("IfcPropertyListValue", Name="Widths",
            ListValues=[self.model.create_entity("IfcLengthMeasure", 1.2), self.model.create_entity("IfcLengthMeasure", 0.9)], Unit=metre)
        fact = self.fact(self.attach([prop]), "Widths")
        self.assertEqual([Decimal(item.normalized.magnitude) for item in fact.value.items], [Decimal("1.2"), Decimal("0.9")])
        self.assertTrue(all(item.unit_resolution == "explicit" and item.unit_anchor_ids for item in fact.value.items))

    def test_each_declared_measure_uses_its_own_matching_project_unit(self):
        prop = self.model.create_entity("IfcPropertyListValue", Name="Measures", ListValues=[
            self.model.create_entity("IfcLengthMeasure", 1000.), self.model.create_entity("IfcAreaMeasure", 2.)])
        fact = self.fact(self.attach([prop]), "Measures")
        self.assertEqual([item.quantity_kind for item in fact.value.items], ["length", "area"])
        self.assertEqual([Decimal(item.normalized.magnitude) for item in fact.value.items], [Decimal(1), Decimal(2)])
        self.assertTrue(all(item.unit_resolution == "project_default" for item in fact.value.items))

    def test_enumeration_reference_can_establish_an_explicit_unit(self):
        metre = self.model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
        values = [self.model.create_entity("IfcLengthMeasure", 0.6), self.model.create_entity("IfcLengthMeasure", 0.9)]
        vocabulary = self.model.create_entity("IfcPropertyEnumeration", Name="Nominal widths", EnumerationValues=values, Unit=metre)
        prop = self.model.create_entity("IfcPropertyEnumeratedValue", Name="WidthChoices", EnumerationValues=values[1:], EnumerationReference=vocabulary)
        fact = self.fact(self.attach([prop]), "WidthChoices")
        self.assertEqual(Decimal(fact.value.items[0].normalized.magnitude), Decimal("0.9"))
        self.assertEqual(fact.value.items[0].unit_resolution, "explicit")

    def test_untyped_real_cost_has_no_fabricated_dimensionless_or_currency_unit(self):
        prop = self.model.create_entity("IfcPropertyListValue", Name="Cost", ListValues=[self.model.create_entity("IfcReal", 120.)])
        item = self.fact(self.attach([prop]), "Cost").value.items[0]
        self.assertEqual((item.unit_id, item.unit_resolution, item.source_value_type), (None, "unknown", "IfcReal"))

    def test_compound_measures_keep_their_meaning_without_invented_simple_units(self):
        prop = self.model.create_entity("IfcPropertyListValue", Name="MaterialData", ListValues=[
            self.model.create_entity("IfcMassDensityMeasure", 2400.),
            self.model.create_entity("IfcThermalConductivityMeasure", 0.15),
        ])
        values = self.fact(self.attach([prop]), "MaterialData").value.items
        self.assertEqual([value.quantity_kind for value in values], ["mass_density", "thermal_conductivity"])
        self.assertTrue(all(value.unit_id is None and value.unit_resolution == "unknown" for value in values))

    def test_null_empty_and_oversized_lists_remain_distinct(self):
        null = self.model.create_entity("IfcPropertyListValue", Name="Null", ListValues=None)
        empty = self.model.create_entity("IfcPropertyListValue", Name="Empty", ListValues=[])
        excessive = self.model.create_entity("IfcPropertyListValue", Name="Large", ListValues=[self.model.create_entity("IfcLabel", "A")] * (MAX_COLLECTION_VALUES + 1))
        engine = self.attach([null, empty, excessive])
        self.assertEqual((self.fact(engine, "Null").status, self.fact(engine, "Null").value), ("explicit_null", None))
        self.assertEqual((self.fact(engine, "Empty").status, self.fact(engine, "Empty").value.items), ("present", []))
        self.assertEqual((self.fact(engine, "Large").status, self.fact(engine, "Large").value), ("not_extracted", None))

    def test_complex_non_scalar_members_are_not_silently_flattened(self):
        prop = self.model.create_entity("IfcPropertyListValue", Name="Complex", ListValues=[self.model.create_entity("IfcComplexNumber", [1., 2.])])
        engine = self.attach([prop])
        self.assertEqual(self.fact(engine, "Complex").status, "not_extracted")

    def test_deferred_catalog_distinguishes_null_from_a_present_empty_collection(self):
        for door, values in [(self.doors[0], None), (self.doors[1], [])]:
            prop = self.model.create_entity("IfcPropertyListValue", Name="Shared", ListValues=values)
            definition = self.model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
                Name="Specifications", HasProperties=[prop])
            self.model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                RelatedObjects=[door], RelatingPropertyDefinition=definition)
        self.model.write(str(self.path))
        engine = IfcQueryEngine.open(self.path, defer_properties=True)
        self.addCleanup(engine.hydrator.close)
        key = property_key("Specifications", "Shared")
        self.assertEqual(engine.properties[key].value_kind, "list")
        result = engine.query("door", entity="D2", operation="lookup", property=key)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual(result.claims[0].value.rows[0][key].items, [])
        validate_bundle(engine.bundle)
        validate_result(result, engine.bundle)

    def test_deferred_catalog_preserves_count_value_shape_ambiguity(self):
        key = property_key("Specifications", "Shared")
        for door, value in [(self.doors[0], 2), (self.doors[1], -1)]:
            prop = self.model.create_entity("IfcPropertySingleValue", Name="Shared",
                NominalValue=self.model.create_entity("IfcCountMeasure", value))
            definition = self.model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
                Name="Specifications", HasProperties=[prop])
            self.model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                RelatedObjects=[door], RelatingPropertyDefinition=definition)
        self.model.write(str(self.path))
        outcomes = []
        for deferred in (False, True):
            engine = IfcQueryEngine.open(self.path, defer_properties=deferred)
            if engine.hydrator:
                self.addCleanup(engine.hydrator.close)
            result = engine.query("door", entity="D1", operation="lookup", property=key)
            outcomes.append(result.status)
            self.assertFalse(result.claims)
            validate_bundle(engine.bundle)
        self.assertEqual(outcomes[0], outcomes[1])

    def test_null_native_quantity_does_not_hide_a_later_typed_source_value(self):
        key = property_key("Qto_DoorBaseQuantities", "NetVolume")
        cubic_metre = self.model.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE")
        for door, value in [(self.doors[0], None), (self.doors[1], 2.5)]:
            prop = self.model.create_entity("IfcQuantityVolume", Name="NetVolume", VolumeValue=value, Unit=cubic_metre)
            definition = self.model.create_entity("IfcElementQuantity", GlobalId=ifcopenshell.guid.new(),
                Name="Qto_DoorBaseQuantities", Quantities=[prop])
            self.model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
                RelatedObjects=[door], RelatingPropertyDefinition=definition)
        self.model.write(str(self.path))
        for deferred in (False, True):
            engine = IfcQueryEngine.open(self.path, defer_properties=deferred)
            if engine.hydrator:
                self.addCleanup(engine.hydrator.close)
            self.assertEqual(engine.properties[key].quantity_kind, "volume")
            result = engine.query("door", entity="D2", operation="sum", property=key, unit="m3")
            self.assertEqual(result.status, "answered", result.model_dump_json())
            self.assertEqual(Decimal(result.claims[0].value.magnitude), Decimal("2.5"))
            engine.ensure_fields([engine.resolve_entity("D1")], [key])
            self.assertEqual(engine.facts[engine.resolve_entity("D1"), key][0].status, "explicit_null")
            validate_bundle(engine.bundle)


if __name__ == "__main__":
    unittest.main()

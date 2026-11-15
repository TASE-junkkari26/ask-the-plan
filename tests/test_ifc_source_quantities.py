"""Guarded source software semantics normalize quantities without QA lookup."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_bundle, validate_result
from ifc_engine.catalog import property_key
from ifc_engine.engine import IfcQueryEngine
from ifc_engine.source_quantities import AUTHORED_ROOM_NET_AREA, RAW_REVIT_AREA, RULE, native_quantity_basis
from tests.test_ifc_engine import sample_model


class SourceQuantityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "software-quantities.ifc"
        self.source, self.doors, self.rooms, _, _, _ = sample_model(self.path)
        self.source.header.file_name.originating_system = "Other authoring system"

    def author(self, name="Autodesk Revit Architecture 2011 - 1.0", identifier="Revit"):
        organization = self.source.create_entity("IfcOrganization", Name="Fixture organization")
        user = self.source.create_entity("IfcPersonAndOrganization",
            ThePerson=self.source.create_entity("IfcPerson", FamilyName="Fixture"), TheOrganization=organization)
        application = self.source.create_entity("IfcApplication", ApplicationDeveloper=organization,
            Version="2011", ApplicationFullName=name, ApplicationIdentifier=identifier)
        history = self.source.create_entity("IfcOwnerHistory", OwningUser=user, OwningApplication=application,
            ChangeAction="ADDED", CreationDate=1)
        for room in self.rooms:
            room.OwnerHistory = history
        return application

    def area(self, room, value, *, group="PSet_Revit_Dimensions", name="Area", measure="IfcAreaMeasure"):
        prop = self.source.create_entity("IfcPropertySingleValue", Name=name,
            NominalValue=self.source.create_entity(measure, value) if value is not None else None)
        definition = self.source.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name=group, HasProperties=[prop])
        self.source.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[room],
            RelatingPropertyDefinition=definition)
        return prop

    def engine(self, deferred=False):
        self.source.write(str(self.path))
        engine = IfcQueryEngine.open(self.path, defer_properties=deferred)
        if engine.hydrator:
            self.addCleanup(engine.hydrator.close)
        return engine

    def test_revit_room_area_normalizes_with_authoring_and_original_quantity_proof(self):
        self.author()
        for room, area in zip(self.rooms, [19., 21.]):
            self.area(room, area)
        for deferred in (False, True):
            with self.subTest(deferred=deferred):
                engine = self.engine(deferred)
                result = engine.query("space", operation="sum", property=AUTHORED_ROOM_NET_AREA, unit="m2")
                self.assertEqual(result.status, "answered", result.model_dump_json())
                self.assertEqual((Decimal(result.claims[0].value.magnitude), result.claims[0].value.basis), (Decimal(40), "net"))
                engine.ensure_fields([engine.resolve_entity("7.16")], [RAW_REVIT_AREA])
                raw = engine.facts[engine.resolve_entity("7.16"), RAW_REVIT_AREA][0]
                self.assertEqual(raw.value.basis, "modeled")
                source_paths = [engine.anchors[anchor].selector.property_path
                                for anchor in result.claims[0].evidence[0].anchor_ids]
                self.assertIn(["PSet_Revit_Dimensions", "Area"], source_paths)
                self.assertIn(["ApplicationFullName"], source_paths)
                definition = engine.properties[AUTHORED_ROOM_NET_AREA].definition
                self.assertIn(RULE, definition)
                self.assertIn("help.autodesk.com", definition)
                self.assertIn("boundary", definition)
                validate_bundle(engine.bundle)
                validate_result(result, engine.bundle)

    def test_file_origin_can_supply_signature_when_occurrence_has_no_owner_application(self):
        self.source.header.file_name.originating_system = "Autodesk Revit 2025"
        self.area(self.rooms[0], 19.)
        engine = self.engine()
        result = engine.query("space", entity="7.16", operation="sum", property=AUTHORED_ROOM_NET_AREA, unit="m2")
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertTrue(any(engine.anchors[anchor].selector.kind == "file_metadata" and
                            engine.anchors[anchor].selector.property_path == ["originating_system"]
                            for anchor in result.claims[0].evidence[0].anchor_ids))

    def test_unknown_software_never_turns_a_generic_or_revit_named_area_into_net_area(self):
        self.author("Other BIM", "OtherBIM")
        self.area(self.rooms[0], 19.)
        self.area(self.rooms[1], 21., group="Geometry")
        for deferred in (False, True):
            engine = self.engine(deferred)
            self.assertNotIn(AUTHORED_ROOM_NET_AREA, engine.properties)
            result = engine.query("space", operation="sum", property=AUTHORED_ROOM_NET_AREA, unit="m2")
            self.assertEqual(result.status, "missing_information")
            self.assertFalse(result.claims)

    def test_non_revit_occurrence_owner_blocks_a_conflicting_revit_file_header(self):
        self.author("Other BIM", "OtherBIM")
        self.source.header.file_name.originating_system = "Autodesk Revit 2025"
        self.area(self.rooms[0], 19.)
        self.assertNotIn(AUTHORED_ROOM_NET_AREA, self.engine().properties)

    def test_revit_wall_area_and_untyped_room_area_are_not_net_room_aliases(self):
        self.author()
        wall = self.source.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), Name="Wall")
        self.area(wall, 19.)
        self.area(self.rooms[0], 21., measure="IfcReal")
        self.assertNotIn(AUTHORED_ROOM_NET_AREA, self.engine().properties)

    def test_missing_source_area_units_remain_unknown_in_the_normalized_fact(self):
        self.author()
        self.area(self.rooms[0], 19.)
        project = self.source.by_type("IfcProject")[0]
        project.UnitsInContext.Units = [unit for unit in project.UnitsInContext.Units if unit.UnitType != "AREAUNIT"]
        engine = self.engine()
        fact = engine.facts[engine.resolve_entity("7.16"), AUTHORED_ROOM_NET_AREA][0]
        self.assertEqual((fact.value.unit_id, fact.value.unit_resolution, fact.value.basis), (None, "unknown", "net"))
        result = engine.query("space", entity="7.16", operation="sum", property=AUTHORED_ROOM_NET_AREA, unit="m2")
        self.assertEqual(result.status, "missing_information")

    def test_conflicting_room_area_records_remain_conflicts(self):
        self.author()
        self.area(self.rooms[0], 19.)
        self.area(self.rooms[0], 20.)
        engine = self.engine()
        result = engine.query("space", entity="7.16", operation="sum", property=AUTHORED_ROOM_NET_AREA, unit="m2")
        self.assertEqual(result.status, "conflicting_evidence", result.model_dump_json())

    def test_explicit_null_room_area_is_retained_without_a_zero(self):
        self.author()
        self.area(self.rooms[0], None)
        engine = self.engine()
        fact = engine.facts[engine.resolve_entity("7.16"), AUTHORED_ROOM_NET_AREA][0]
        self.assertEqual((fact.status, fact.value), ("explicit_null", None))
        self.assertEqual(engine.properties[AUTHORED_ROOM_NET_AREA].quantity_kind, "area")
        result = engine.query("space", entity="7.16", operation="sum", property=AUTHORED_ROOM_NET_AREA, unit="m2")
        self.assertEqual(result.status, "missing_information")

    def test_native_quantity_names_have_exact_physical_basis_rules(self):
        self.assertEqual(native_quantity_basis("NetFloorArea", "area"), "net")
        self.assertEqual(native_quantity_basis("NetSideArea", "area"), "net")
        self.assertEqual(native_quantity_basis("NetVolume", "volume"), "net")
        self.assertEqual(native_quantity_basis("NetVolume", "area"), "modeled")
        self.assertEqual(native_quantity_basis("NetworkLength", "length"), "modeled")
        self.assertEqual(native_quantity_basis("Area", "area"), "modeled")

    def test_native_network_length_quantity_is_not_misread_as_a_net_quantity(self):
        quantity = self.source.create_entity("IfcQuantityLength", Name="NetworkLength", LengthValue=1000.)
        definition = self.source.create_entity("IfcElementQuantity", GlobalId=ifcopenshell.guid.new(),
            Name="Network", Quantities=[quantity])
        self.source.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[self.rooms[0]], RelatingPropertyDefinition=definition)
        engine = self.engine()
        fact = engine.facts[engine.resolve_entity("7.16"), property_key("Network", "NetworkLength")][0]
        self.assertEqual(fact.value.basis, "modeled")


if __name__ == "__main__":
    unittest.main()

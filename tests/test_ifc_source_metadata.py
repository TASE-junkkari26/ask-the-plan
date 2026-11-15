"""Source identity comes from literal header/native records, never QA titles."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from contracts.validation import validate_bundle
from ifc_engine.catalog import attribute_key
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_engine import sample_model


class NativeSourceMetadataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "uploaded-random-name.ifc"
        self.model, *_ = sample_model(self.path)
        self.project = self.model.by_type("IfcProject")[0]
        self.model.header.file_name.name = r"C:\Native Model\Original-identifier.ifc"
        self.organization = self.model.create_entity("IfcOrganization", Name="Source organization")

    def application(self, identifier, name="Source application"):
        return self.model.create_entity("IfcApplication", ApplicationDeveloper=self.organization,
            Version="1.0", ApplicationFullName=name, ApplicationIdentifier=identifier)

    def engine(self, deferred):
        self.model.write(str(self.path))
        engine = IfcQueryEngine.open(self.path, defer_properties=deferred)
        if engine.hydrator:
            self.addCleanup(engine.hydrator.close)
        return engine

    def fact(self, engine, name):
        project = next(entity.id for entity in engine.entities.values() if "ifc:IfcProject" in entity.concept_ids)
        key = attribute_key(name)
        engine.ensure_fields([project], [key])
        facts = engine.facts[project, key]
        self.assertEqual(len(facts), 1)
        return facts[0]

    def test_header_filename_remains_literal_and_separate_from_uploaded_title(self):
        for deferred in (False, True):
            engine = self.engine(deferred)
            fact = self.fact(engine, "NativeFilename")
            self.assertEqual(fact.value.value.text, self.model.header.file_name.name)
            self.assertNotEqual(fact.value.value.text, engine.bundle.documents[0].title[0].text)
            anchors = [engine.anchors[identifier].selector for identifier in fact.provenance.anchor_ids]
            self.assertTrue(any(anchor.kind == "file_metadata" and anchor.value == "FILE_NAME"
                                and anchor.property_path == ["name"] for anchor in anchors))
            self.assertEqual(engine.properties[attribute_key("NativeFilename")].labels[0].text, "NativeFilename")
            validate_bundle(engine.bundle)

    def test_all_native_application_identifiers_do_not_replace_the_owning_application(self):
        primary = self.application("Primary.Native.App")
        secondary = self.application("IFC2SB", "Secondary source processor")
        person = self.model.create_entity("IfcPerson", FamilyName="Source user")
        owner = self.model.create_entity("IfcPersonAndOrganization", ThePerson=person, TheOrganization=self.organization)
        self.project.OwnerHistory = self.model.create_entity("IfcOwnerHistory", OwningUser=owner,
            OwningApplication=primary, ChangeAction="ADDED", CreationDate=0)
        signatures = []
        for deferred in (False, True):
            engine = self.engine(deferred)
            inventory = self.fact(engine, "ApplicationIdentifiers")
            self.assertEqual(inventory.provenance.method, "computed")
            rows = inventory.value.items
            self.assertEqual([row.fields["ApplicationIdentifier"].value.text for row in rows], ["Primary.Native.App", "IFC2SB"])
            self.assertEqual([row.fields["step_id"].value.text for row in rows], [str(primary.id()), str(secondary.id())])
            self.assertEqual(self.fact(engine, "ApplicationIdentifier").value.value.text, "Primary.Native.App")
            native = {engine.anchors[identifier].selector.value for identifier in inventory.provenance.anchor_ids
                      if engine.anchors[identifier].selector.property_path == ["ApplicationIdentifier"]}
            self.assertEqual(native, {str(primary.id()), str(secondary.id())})
            self.assertEqual(engine.properties[attribute_key("ApplicationIdentifiers")].value_kind, "list")
            signatures.append(inventory.value.model_dump())
            validate_bundle(engine.bundle)
        self.assertEqual(signatures[0], signatures[1])

    def test_explicit_null_application_identifier_keeps_its_record_and_known_other_values(self):
        missing = self.application(None)
        self.application("Known.Identifier")
        for deferred in (False, True):
            engine = self.engine(deferred)
            inventory = self.fact(engine, "ApplicationIdentifiers")
            self.assertEqual(inventory.status, "present")
            rows = inventory.value.items
            self.assertEqual(rows[0].fields["step_id"].value.text, str(missing.id()))
            self.assertEqual(rows[0].fields["status"].value.text, "explicit_null")
            self.assertNotIn("ApplicationIdentifier", rows[0].fields)
            self.assertEqual(rows[1].fields["ApplicationIdentifier"].value.text, "Known.Identifier")
            validate_bundle(engine.bundle)

    def test_no_application_records_are_a_known_empty_inventory(self):
        for deferred in (False, True):
            engine = self.engine(deferred)
            inventory = self.fact(engine, "ApplicationIdentifiers")
            self.assertEqual(inventory.status, "present")
            self.assertEqual(inventory.value.items, [])
            validate_bundle(engine.bundle)

    def test_inventory_budget_exhaustion_is_not_an_empty_or_partial_known_inventory(self):
        self.application("First")
        self.application("Second")
        for deferred in (False, True):
            with patch("ifc_engine.ingest.MAX_SOURCE_APPLICATIONS", 1):
                engine = self.engine(deferred)
                inventory = self.fact(engine, "ApplicationIdentifiers")
            self.assertEqual(inventory.status, "not_extracted")
            self.assertIsNone(inventory.value)
            self.assertEqual(engine.properties[attribute_key("ApplicationIdentifiers")].value_kind, "list")
            validate_bundle(engine.bundle)


if __name__ == "__main__":
    unittest.main()

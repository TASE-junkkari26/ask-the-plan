"""Descriptive titles require literal source identity and every qualifier."""
from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from contracts import models as m
from ifc_api.model_identity import assess_model, matches_model
from ifc_engine.catalog import attribute_key


def engine(*, name="Starlight Hall", filename="starlight-hall_arc_v1.ifc", metadata=None, schema="IFC4"):
    project = SimpleNamespace(id="project", kind="project", concept_ids=["concept:project"], labels=[m.LocalizedText(text=name)])
    facts, properties = {}, {}
    for key, value in (metadata or {}).items():
        properties[attribute_key(key)] = object()
        typed = (m.ListValue(kind="list", items=[m.RecordValue(kind="record", fields={
                     "step_id": m.TextValue(kind="text", value=m.LocalizedText(text=str(index + 1))),
                     "status": m.TextValue(kind="text", value=m.LocalizedText(text="present")),
                     "ApplicationIdentifier": m.TextValue(kind="text", value=m.LocalizedText(text=item))}) for index, item in enumerate(value)])
                 if isinstance(value, list) else m.TextValue(kind="text", value=m.LocalizedText(text=value)))
        facts["project", attribute_key(key)] = [SimpleNamespace(status="present", value=typed)]
    return SimpleNamespace(entities={"project": project}, properties=properties, facts=facts, schema=schema,
                           ensure_fields=Mock(), bundle=SimpleNamespace(documents=[SimpleNamespace(title=[m.LocalizedText(text=filename)])]))


class ModelIdentityTests(unittest.TestCase):
    def test_exact_source_identifiers_need_no_metadata_or_synthetic_project_name(self):
        source = engine()
        self.assertTrue(matches_model(source, "Starlight Hall"))
        self.assertTrue(matches_model(source, "starlight-hall_arc_v1"))
        source.ensure_fields.assert_not_called()
        self.assertFalse(matches_model(source, "Different Hospital"))

    def test_native_core_role_versions_and_source_filename_core_are_all_checked(self):
        source = engine()
        self.assertTrue(matches_model(source, "Starlight Hall - architectural"))
        self.assertFalse(matches_model(source, "Starlight Hall - plumbing"))
        self.assertFalse(matches_model(source, "Starlight Hall - architecture and HVAC"))
        source = engine(name="Project Number", filename="company_starlight-hall_fm-arc_v1.ifc")
        self.assertTrue(matches_model(source, "Starlight Hall v1 - Fachmodell Architektur"))
        self.assertFalse(matches_model(source, "Starlight Hall v2 - Fachmodell Architektur"))
        self.assertFalse(matches_model(source, "Different Hall v1 - architectural"))
        self.assertFalse(matches_model(source, "Hall v1 - architectural"))

    def test_source_trade_conflicts_or_unknown_identity_adjectives_do_not_match(self):
        source = engine(filename="starlight-hall_arc_plumbing_v1.ifc")
        self.assertFalse(matches_model(source, "Starlight Hall - architectural"))
        source = engine(filename="starlight-hall_arc_mep_v1.ifc")
        self.assertFalse(matches_model(source, "Starlight Hall - architectural"))
        source = engine(name="Medical Clinic", filename="clinic_architectural.ifc")
        self.assertFalse(matches_model(source, "Medical-Dental Clinic - architectural"))
        source = engine(filename="Starlight-Hall_MEP_Electrical.ifc")
        self.assertFalse(matches_model(source, "Starlight Hall - MEP"))
        self.assertTrue(matches_model(source, "Starlight Hall - electrical"))

    def test_native_header_filename_survives_upload_renaming(self):
        source = engine(name="Project Number", filename="renamed.ifc", metadata={"NativeFilename": r"C:\Original\Exported_Original.ifc"})
        self.assertTrue(matches_model(source, "Exported Original"))
        self.assertFalse(matches_model(source, "Different Original"))

    def test_single_letter_role_needs_independent_authoring_metadata(self):
        filename = "starlight-hall-a-20260101.ifc"
        self.assertFalse(matches_model(engine(filename=filename), "Starlight Hall - architectural"))
        source = engine(filename=filename, metadata={"PreprocessorVersion": "Autodesk Revit Architecture 2011 - 1.0"})
        self.assertTrue(matches_model(source, "Starlight Hall - architectural"))
        source = engine(filename=filename, metadata={"PreprocessorVersion": "Autodesk Revit MEP 2011 - 1.0"})
        self.assertFalse(matches_model(source, "Starlight Hall - architectural"))
        filename = "starlight-hall-m-20260101-rooms-and-spaces.ifc"
        source = engine(filename=filename, metadata={"PreprocessorVersion": "Autodesk Revit MEP 2011 - 1.0"})
        self.assertTrue(matches_model(source, "Starlight Hall - mechanical (rooms and spaces)"))
        self.assertFalse(matches_model(engine(filename="starlight-hall_mechanical.ifc"), "Starlight Hall - mechanical (rooms and spaces)"))
        self.assertFalse(matches_model(engine(filename="source.ifc", metadata={"PreprocessorVersion": "Autodesk Revit Architecture 2011"}),
                                       "Starlight Hall - architectural"))

    def test_space_boundary_software_variant_requires_actual_native_application_identifier(self):
        filename = "company_starlight-hall_fm-arc-with-sb-v1.ifc"
        title = "Starlight Hall v1 - Architektur mit Space Boundaries (IFC2SB)"
        self.assertFalse(matches_model(engine(name="Project Number", filename=filename), title))
        source = engine(name="Project Number", filename=filename, metadata={"ApplicationIdentifiers": ["Revit", "IFC2SB"]})
        self.assertTrue(matches_model(source, title))
        self.assertFalse(matches_model(engine(name="Project Number", filename="company_starlight-hall_fm-arc-v1.ifc",
                                            metadata={"ApplicationIdentifiers": ["IFC2SB"]}), title))

    def test_ifc_schema_descriptor_requires_exact_native_schema_and_strong_filename_identity(self):
        source = engine(name="Project Number", filename="cedar-river-bridge_4x3.ifc", schema="IFC4X3_ADD2")
        self.assertTrue(matches_model(source, "Cedar River Bridge IFC 4.3 test model"))
        self.assertFalse(matches_model(source, "Different River Bridge IFC 4.3 test model"))
        self.assertFalse(matches_model(source, "Cedar River Bridge IFC 2.3 test model"))

    def test_conflict_assessment_is_read_only_and_separates_unknown_descriptive_titles(self):
        source = engine()
        source.ensure_fields.side_effect = AssertionError("Default assessment must not hydrate")
        self.assertEqual(assess_model(source, "Starlight Hall - architectural")["status"], "MATCH")
        self.assertEqual(assess_model(source, "Starlight Hall - plumbing")["status"], "CONFLICTING")
        self.assertEqual(assess_model(source, "Different Hospital")["status"], "CONFLICTING")
        source.ensure_fields.assert_not_called()
        source = engine(name="Project Number", filename="library_starlight-hall-fm-arc-v1.ifc")
        self.assertEqual(assess_model(source, "Different Hospital")["status"], "CONFLICTING")
        for name in ["Project Number", "Projektname", "Medical Clinic"]:
            self.assertEqual(assess_model(engine(name=name, filename="clinic_architectural.ifc"),
                                         "Medical-Dental Clinic - architectural")["status"], "UNKNOWN")
        source = engine(name="Project Number", filename="company_starlight-hall_fm-arc_v1.ifc")
        self.assertEqual(assess_model(source, "Starlight Hall v2 - Fachmodell Architektur")["status"], "CONFLICTING")
        source = engine(name="Project Number", filename="company_starlight-hall_fm-arc-with-sb-v1.ifc")
        self.assertEqual(assess_model(source, "Starlight Hall v1 - Architektur mit Space Boundaries (IFC2SB)")["status"], "UNKNOWN")
        source = engine(name="Project Number", filename="cedar-river-bridge_4x3.ifc", schema="IFC4")
        self.assertEqual(assess_model(source, "Cedar River Bridge IFC 4.3 test model")["status"], "CONFLICTING")


if __name__ == "__main__":
    unittest.main()

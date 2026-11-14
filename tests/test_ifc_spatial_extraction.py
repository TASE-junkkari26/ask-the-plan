"""Source topology and descriptive metadata survive IFC extraction with anchors."""
from pathlib import Path
import tempfile
import unittest

import ifcopenshell
import ifcopenshell.guid

from contracts.validation import validate_bundle
from ifc_engine.catalog import attribute_key
from ifc_engine.engine import IfcQueryEngine


def topology_model(path, schema="IFC4"):
    model = ifcopenshell.file(schema=schema)

    def root(kind, **attributes):
        return model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **attributes)

    project = root("IfcProject", Name="Literal project name", Description="A teaching building")
    building = root("IfcBuilding", Name="Building")
    storey = root("IfcBuildingStorey", Name="First floor")
    rooms = [root("IfcSpace", Name="1B07", LongName="Büro"), root("IfcSpace", Name="1B08", LongName="Flur")]
    wall = root("IfcWall", Name="Partition")
    opening = root("IfcOpeningElement", Name="Opening")
    door = root("IfcDoor", Name="Tür-019")
    root("IfcRelAggregates", RelatingObject=project, RelatedObjects=[building])
    root("IfcRelAggregates", RelatingObject=building, RelatedObjects=[storey])
    root("IfcRelAggregates", RelatingObject=storey, RelatedObjects=rooms)
    root("IfcRelContainedInSpatialStructure", RelatingStructure=storey, RelatedElements=[wall, door])
    relations = [root("IfcRelVoidsElement", RelatingBuildingElement=wall, RelatedOpeningElement=opening),
                 root("IfcRelFillsElement", RelatingOpeningElement=opening, RelatedBuildingElement=door),
                 root("IfcRelConnectsElements", RelatingElement=wall, RelatedElement=door)]
    zone = root("IfcZone", Name="Literal zone A")
    relations.append(root("IfcRelAssignsToGroup", RelatingGroup=zone, RelatedObjects=rooms))
    boundary_kind = "IfcRelSpaceBoundary" if schema == "IFC2X3" else "IfcRelSpaceBoundary2ndLevel"
    boundaries = [root(boundary_kind, RelatingSpace=room, RelatedBuildingElement=wall,
                       PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="INTERNAL") for room in rooms]
    if schema != "IFC2X3":
        boundaries[0].CorrespondingBoundary = boundaries[1]
        boundaries[1].CorrespondingBoundary = boundaries[0]
    external = root("IfcRelSpaceBoundary", RelatingSpace=rooms[0], RelatedBuildingElement=door,
                    PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="EXTERNAL")
    # Neither a virtual boundary nor an unbound space-to-outside record proves
    # a physical exterior door; both must remain safe to parse.
    root("IfcRelSpaceBoundary", RelatingSpace=rooms[1], RelatedBuildingElement=door,
         PhysicalOrVirtualBoundary="VIRTUAL", InternalOrExternalBoundary="EXTERNAL")
    root("IfcRelSpaceBoundary", RelatingSpace=rooms[1], RelatedBuildingElement=None,
         PhysicalOrVirtualBoundary="VIRTUAL", InternalOrExternalBoundary="EXTERNAL")
    model.write(str(path))
    return model, project, rooms, wall, opening, door, zone, relations, boundaries, external


class IfcSpatialExtractionTests(unittest.TestCase):
    def test_native_spatial_relationships_keep_original_step_anchors_across_schemas(self):
        for schema in ("IFC2X3", "IFC4", "IFC4X3_ADD2"):
            with self.subTest(schema=schema), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "topology.ifc"
                source = topology_model(path, schema)
                engine = IfcQueryEngine.open(path)
                validate_bundle(engine.bundle)
                predicates = {relation.predicate for relation in engine.bundle.relations}
                self.assertTrue({"bounded_by", "has_opening", "filled_by", "connected_to", "assigned_to_zone"} <= predicates)
                original_ids = {str(record.id()) for record in [*source[7], *source[8], source[9]]}
                topology = [relation for relation in engine.bundle.relations if relation.predicate in
                            {"bounded_by", "has_opening", "filled_by", "connected_to", "assigned_to_zone"}]
                for relation in topology:
                    self.assertTrue(relation.native_predicate.startswith("IfcRel"))
                    self.assertTrue(relation.provenance.anchor_ids)
                    for anchor_id in relation.provenance.anchor_ids:
                        anchor = engine.anchors[anchor_id]
                        if anchor.selector.value in original_ids:
                            self.assertEqual(anchor.selector.kind, "step_id")
                counterpart = [relation for relation in engine.bundle.relations if relation.predicate == "corresponding_boundary"]
                self.assertEqual(len(counterpart), 0 if schema == "IFC2X3" else 2)
                if counterpart:
                    self.assertTrue(all(len(relation.provenance.anchor_ids) == 2 for relation in counterpart))
                # LongName is a source label and is kept in its original language.
                self.assertEqual(engine.resolve_entity("Büro"), engine.resolve_entity("1B07"))

    def test_exterior_boundary_requires_physical_and_external_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exterior.ifc"
            topology_model(path)
            engine = IfcQueryEngine.open(path)
            exterior = [relation for relation in engine.bundle.relations if relation.predicate == "external_boundary"]
            self.assertEqual(len(exterior), 1)
            self.assertEqual(exterior[0].subject_id, engine.resolve_entity("1B07"))
            self.assertEqual(exterior[0].object_id, engine.resolve_entity("Tür-019"))

    def test_descriptive_metadata_uses_file_header_and_native_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.ifc"
            source, project, *_ = topology_model(path)
            source.header.file_name.originating_system = "Literal authoring system 2026"
            source.header.file_description.description = ("ViewDefinition [CoordinationView]",)
            developer = source.create_entity("IfcOrganization", Name="Literal developer")
            application = source.create_entity("IfcApplication", ApplicationDeveloper=developer, Version="9.1",
                                               ApplicationFullName="Literal BIM software", ApplicationIdentifier="LBIM")
            person = source.create_entity("IfcPerson")
            user = source.create_entity("IfcPersonAndOrganization", ThePerson=person, TheOrganization=developer)
            project.OwnerHistory = source.create_entity("IfcOwnerHistory", OwningUser=user, OwningApplication=application,
                                                       ChangeAction="ADDED", CreationDate=0)
            address = source.create_entity("IfcPostalAddress", AddressLines=["Original street 12", "Building A"],
                                           Town="Helsinki", Country="FI")
            site = source.create_entity("IfcSite", GlobalId=ifcopenshell.guid.new(), Name="Site", SiteAddress=address)
            source.write(str(path))
            engine = IfcQueryEngine.open(path)
            project_id = engine.resolve_entity("Literal project name")
            schema = engine.facts[project_id, attribute_key("FILE_SCHEMA")][0]
            self.assertEqual(schema.value.value.text, "IFC4")
            anchor = engine.anchors[schema.provenance.anchor_ids[0]]
            self.assertEqual((anchor.selector.kind, anchor.selector.value), ("file_metadata", "FILE_SCHEMA"))
            app = engine.facts[project_id, attribute_key("ApplicationFullName")][0]
            self.assertEqual(app.value.value.text, "Literal BIM software")
            self.assertEqual(engine.anchors[app.provenance.anchor_ids[0]].selector.value, str(application.id()))
            self.assertEqual(engine.facts[project_id, attribute_key("OriginatingSystem")][0].value.value.text,
                             "Literal authoring system 2026")
            site_id = engine.resolve_entity("Site")
            self.assertEqual(engine.facts[site_id, attribute_key("Address.AddressLines")][0].value.value.text,
                             "Original street 12\nBuilding A")
            self.assertEqual(engine.facts[site_id, attribute_key("Address.PostalCode")][0].status, "explicit_null")
            # An absent owning application is not fabricated from the header.
            self.assertFalse(engine.facts[engine.resolve_entity("1B07"), attribute_key("ApplicationFullName")])
            self.assertTrue(all(anchor.selector.value != "0" for anchor in engine.bundle.anchors
                                if anchor.selector.kind == "step_id"))

    def test_site_coordinates_keep_compound_angles_and_source_elevation_units(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "site-coordinates.ifc"
            source, project, *_ = topology_model(path)
            project.Phase = "Literal design phase"
            metre = source.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
            project.UnitsInContext = source.create_entity("IfcUnitAssignment", Units=[metre])
            site = source.create_entity("IfcSite", GlobalId=ifcopenshell.guid.new(), Name="Located site",
                RefLatitude=(60, 10, 3, 250000), RefLongitude=(24, 56, 18), RefElevation=12.75,
                LandTitleNumber="Literal cadastral identifier 121.A")
            source.create_entity("IfcSite", GlobalId=ifcopenshell.guid.new(), Name="Unlocated site")
            source.write(str(path))
            engine = IfcQueryEngine.open(path)
            identifier = engine.resolve_entity("Located site")
            latitude = engine.facts[identifier, attribute_key("RefLatitude")][0]
            longitude = engine.facts[identifier, attribute_key("RefLongitude")][0]
            self.assertEqual(latitude.value.value.text, "(60, 10, 3, 250000)")
            self.assertEqual(longitude.value.value.text, "(24, 56, 18)")
            self.assertIn("not converted to decimal degrees", engine.properties[latitude.property_key].definition)
            anchor = engine.anchors[latitude.provenance.anchor_ids[0]]
            self.assertEqual((anchor.selector.value, anchor.selector.property_path), (str(site.id()), ["RefLatitude"]))
            elevation = engine.facts[identifier, attribute_key("RefElevation")][0]
            self.assertEqual(elevation.value.quantity_kind, "length")
            self.assertEqual(elevation.value.magnitude, "12.75")
            self.assertEqual(elevation.value.normalized.unit_id, "unit:m")
            self.assertEqual(engine.facts[identifier, attribute_key("LandTitleNumber")][0].value.value.text,
                             "Literal cadastral identifier 121.A")
            self.assertEqual(engine.facts[engine.resolve_entity("Literal project name"), attribute_key("Phase")][0].value.value.text,
                             "Literal design phase")
            missing = engine.facts[engine.resolve_entity("Unlocated site"), attribute_key("RefLatitude")][0]
            self.assertEqual(missing.status, "explicit_null")
            self.assertIsNone(missing.value)


if __name__ == "__main__":
    unittest.main()

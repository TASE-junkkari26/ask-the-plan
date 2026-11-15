"""Native occurrence context and material layer evidence, without QA lookups."""
from pathlib import Path
import tempfile
import unittest

import ifcopenshell.guid

from contracts import models as m
from ifc_engine.catalog import POLICIES, property_key
from ifc_engine.engine import IfcQueryEngine
from tests.test_ifc_engine import sample_model


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "source.ifc"
        self.model, self.doors, self.rooms, _, self.ground, self.upper = sample_model(self.path)

    def root(self, cls, **kwargs):
        return self.model.create_entity(cls, GlobalId=ifcopenshell.guid.new(), **kwargs)

    def load(self):
        self.model.write(str(self.path))
        return IfcQueryEngine.open(self.path)

    def fact(self, engine, obj, group, name):
        entity = engine.resolve_entity("#" + str(obj.id()))
        return engine.facts[entity, property_key(group, name)]

    def test_effective_native_context_groups_occurrences_without_losing_type_identity(self):
        engine = self.load()
        door = self.doors[0]
        self.assertEqual(self.fact(engine, door, "SourceContext", "TypeName")[0].value.value.text, "Door type")
        self.assertEqual(self.fact(engine, door, "SourceContext", "StoreyId")[0].value.value.text, self.ground.GlobalId)
        name = self.fact(engine, door, "SourceContext", "StoreyName")[0]
        self.assertEqual(name.value.value.text, "Ground")
        self.assertEqual(name.provenance.method, "computed")
        paths = [engine.anchors[a].selector for a in name.provenance.anchor_ids]
        self.assertTrue(any(s.value == str(self.ground.id()) and s.property_path == ["Name"] for s in paths))
        self.assertTrue(any(not s.property_path and s.value != str(self.ground.id()) for s in paths))
        plan = engine.plan("door")
        plan.steps[-1].operation.group_by = [m.FieldRef(kind="property", key=property_key("SourceContext", "StoreyName"))]
        result = engine.execute(plan)
        rows = result.claims[0].value.rows
        self.assertEqual({row[property_key("SourceContext", "StoreyName")].value.text: row["value"].value for row in rows},
                         {"Ground": 2, "Upper": 1})

    def add_layers(self, *, missing_material=False):
        brick = self.model.create_entity("IfcMaterial", Name="Original Brick")
        insulation = self.model.create_entity("IfcMaterial", Name="Dämmung 032")
        layers = [self.model.create_entity("IfcMaterialLayer", Material=material, LayerThickness=thickness)
                  for material, thickness in [(brick, 100.), (None if missing_material else insulation, 50.), (brick, 100.)]]
        layer_set = self.model.create_entity("IfcMaterialLayerSet", MaterialLayers=layers, LayerSetName="Außenwand W-01")
        wall_type = self.root("IfcWallType", Name="Original Wall Type", PredefinedType="NOTDEFINED")
        association = self.root("IfcRelAssociatesMaterial", RelatedObjects=[wall_type], RelatingMaterial=layer_set)
        wall = self.root("IfcWall", Name="W-01")
        self.root("IfcRelDefinesByType", RelatedObjects=[wall], RelatingType=wall_type)
        self.root("IfcRelContainedInSpatialStructure", RelatingStructure=self.ground, RelatedElements=[wall])
        return wall, layers, association

    def test_ordered_inherited_layers_repeated_material_thickness_and_units_are_preserved(self):
        wall, layers, association = self.add_layers()
        engine = self.load()
        composition = self.fact(engine, wall, "SourceMaterial", "Layers")[0]
        self.assertEqual([r.fields["material"].value.text for r in composition.value.items],
                         ["Original Brick", "Dämmung 032", "Original Brick"])
        self.assertEqual([r.fields["index"].value for r in composition.value.items], [1, 2, 3])
        total = self.fact(engine, wall, "SourceMaterial", "TotalLayerThickness")[0].value
        self.assertEqual(total.magnitude, "250.0")
        self.assertEqual(engine.units[total.unit_id].si_multiplier, "0.001")
        brick = self.fact(engine, wall, "SourceMaterialThickness", "Original Brick")[0].value
        self.assertEqual(brick.magnitude, "200.0")
        anchors = {engine.anchors[a].selector.value for a in composition.provenance.anchor_ids}
        self.assertTrue({str(layer.id()) for layer in layers} <= anchors)
        self.assertIn(str(association.id()), anchors)
        self.assertFalse(any(key.startswith(property_key("SourceMaterial", "")) and "Volume" in key for key in engine.properties))

    def test_occurrence_material_override_replaces_type_material(self):
        wall, _, _ = self.add_layers()
        concrete = self.model.create_entity("IfcMaterial", Name="Concrete override")
        self.root("IfcRelAssociatesMaterial", RelatedObjects=[wall], RelatingMaterial=concrete)
        engine = self.load()
        self.assertEqual(self.fact(engine, wall, "SourceMaterial", "Names")[0].value.value.text, "Concrete override")
        self.assertEqual(self.fact(engine, wall, "SourceMaterial", "Layers"), [])

    def test_incomplete_material_identity_stays_explicit_without_losing_native_thickness(self):
        wall, _, _ = self.add_layers(missing_material=True)
        engine = self.load()
        self.assertFalse(self.fact(engine, wall, "SourceMaterial", "CompositionComplete")[0].value.value)
        rows = self.fact(engine, wall, "SourceMaterial", "Layers")[0].value.items
        self.assertNotIn("material", rows[1].fields)
        self.assertEqual(rows[1].fields["thickness"].magnitude, "50.0")

    def test_conflicting_nearest_storeys_are_ambiguous(self):
        self.root("IfcRelContainedInSpatialStructure", RelatingStructure=self.upper, RelatedElements=[self.doors[0]])
        engine = self.load()
        fact = self.fact(engine, self.doors[0], "SourceContext", "StoreyName")[0]
        self.assertEqual(fact.status, "ambiguous")
        self.assertIsNone(fact.value)
        self.assertEqual(self.fact(engine, self.doors[0], "SourceContext", "StoreyId")[0].status, "ambiguous")

    def test_unnamed_building_has_a_stable_native_group_identity(self):
        building = self.model.by_type("IfcBuilding")[0]
        building.Name = None
        engine = self.load()
        name = self.fact(engine, self.ground, "SourceContext", "BuildingName")[0]
        identity = self.fact(engine, self.ground, "SourceContext", "BuildingId")[0]
        self.assertEqual(name.status, "explicit_null")
        self.assertEqual(identity.value.value.text, building.GlobalId)

    def test_nested_material_records_can_be_projected_with_occurrence_evidence(self):
        wall, _, _ = self.add_layers()
        engine = self.load()
        entity = engine.resolve_entity("#" + str(wall.id()))
        scope = engine.scope()
        scope.exact_entity_ids = [entity]
        plan = m.QueryPlan(id="plan:layers", request_id="request:layers", scope=scope,
            steps=[m.PlanStep(id="select", operation=m.SelectOperation(kind="select", concept_ids=["concept:wall"],
                   count_policy=POLICIES["all_matches"])),
                   m.PlanStep(id="layers", operation=m.ProjectOperation(kind="project", input_step_id="select",
                   fields=[m.FieldRef(kind="entity_id", key="entity"), m.FieldRef(kind="property", key=property_key("SourceMaterial", "Layers"))]))],
            outputs={"composition": "layers"})
        result = engine.execute(plan)
        self.assertEqual(result.status, "answered")
        self.assertEqual(len(result.claims[0].value.rows[0][property_key("SourceMaterial", "Layers")].items), 3)


if __name__ == "__main__":
    unittest.main()

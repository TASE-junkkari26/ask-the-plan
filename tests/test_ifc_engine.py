"""Regression tests for source semantics, query execution, and evidence links."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest

import ifcopenshell
import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from ifc_engine.catalog import POLICIES, attribute_key, property_key
from ifc_engine.cli import main
from ifc_engine.engine import IfcQueryEngine


def sample_model(path, schema="IFC4"):
    model = ifcopenshell.file(schema=schema)

    def root(cls, **kwargs):
        return model.create_entity(cls, GlobalId=ifcopenshell.guid.new(), **kwargs)

    length_unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE")
    area_unit = model.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE")
    explicit_area = model.create_entity("IfcSIUnit", UnitType="AREAUNIT", Prefix="MILLI", Name="SQUARE_METRE")
    project = root("IfcProject", Name="IFC query regression fixture",
                   UnitsInContext=model.create_entity("IfcUnitAssignment", Units=[length_unit, area_unit]))
    building = root("IfcBuilding", Name="Building")
    ground = root("IfcBuildingStorey", Name="Ground", Elevation=0)
    upper = root("IfcBuildingStorey", Name="Upper", Elevation=3000)
    root("IfcRelAggregates", RelatingObject=project, RelatedObjects=[building])
    root("IfcRelAggregates", RelatingObject=building, RelatedObjects=[ground, upper])
    doors = [root("IfcDoor", Name=name, OverallWidth=width) for name, width in [("D1", 900.), ("D2", 1100.), ("D3", None)]]
    rooms = [root("IfcSpace", Name=name) for name in ["7.16", "Office"]]
    stairs = [root("IfcStair", Name=name) for name in ["Stair assembly", "RISER", "TREAD"]]
    root("IfcRelAggregates", RelatingObject=stairs[0], RelatedObjects=stairs[1:])
    root("IfcRelContainedInSpatialStructure", RelatingStructure=ground, RelatedElements=[*doors[:2], stairs[0]])
    root("IfcRelContainedInSpatialStructure", RelatingStructure=upper, RelatedElements=doors[2:])
    root("IfcRelAggregates", RelatingObject=ground, RelatedObjects=rooms)

    def attach(obj, definition):
        root("IfcRelDefinesByProperties", RelatedObjects=[obj], RelatingPropertyDefinition=definition)

    for room, area, unit in [(rooms[0], 19000000., explicit_area), (rooms[1], 21., None)]:
        quantity = model.create_entity("IfcQuantityArea", Name="NetFloorArea", AreaValue=area, Unit=unit)
        attach(room, root("IfcElementQuantity", Name="Qto_SpaceBaseQuantities", Quantities=[quantity]))
    # Same logical quantity repeated in a different set must not be added twice.
    duplicate = model.create_entity("IfcQuantityArea", Name="NetFloorArea", AreaValue=19000000., Unit=explicit_area)
    attach(rooms[0], root("IfcElementQuantity", Name="Qto_SpaceBaseQuantities", Quantities=[duplicate]))

    def fire_set(value):
        prop = model.create_entity("IfcPropertySingleValue", Name="FireRating", NominalValue=model.create_entity("IfcLabel", value))
        return root("IfcPropertySet", Name="Pset_DoorCommon", HasProperties=[prop])

    door_type = root("IfcDoorType", Name="Door type", HasPropertySets=[fire_set("90 min")])
    root("IfcRelDefinesByType", RelatedObjects=doors[:2], RelatingType=door_type)
    attach(doors[0], fire_set("60 min"))
    timber = model.create_entity("IfcMaterial", Name="Timber")
    root("IfcRelAssociatesMaterial", RelatedObjects=[door_type], RelatingMaterial=timber)
    model.write(str(path))
    return model, doors, rooms, stairs, ground, upper


class IfcEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "fixture.ifc"
        cls.source = sample_model(cls.path)
        cls.loaded = IfcQueryEngine.open(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.engine = IfcQueryEngine(self.loaded.bundle.model_copy(deep=True), schema=self.loaded.schema)

    def answer(self, target, **kwargs):
        plan = self.engine.plan(target, **kwargs)
        validate_plan(plan, self.engine.bundle, self.engine.capabilities)
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        validate_bundle(self.engine.bundle)
        validate_result(result, self.engine.bundle, plan)
        return result.claims[0].value, result

    def test_model_count_and_storey_count_have_distinct_evidence(self):
        total, all_result = self.answer("door")
        floor, floor_result = self.answer("IfcDoor", storey="Ground")
        self.assertEqual(total.value, 3)
        self.assertEqual(floor.value, 2)
        self.assertEqual(all_result.entity_sets[-1].count, 3)
        self.assertEqual(floor_result.entity_sets[-1].count, 2)
        self.assertTrue(floor_result.claims[0].scope.entity_ids)

    def test_occurrence_type_properties_and_overrides_retain_source_anchors(self):
        value, result = self.answer("door", operation="lookup", storey="Ground", property="Pset_DoorCommon.FireRating")
        key = property_key("Pset_DoorCommon", "FireRating")
        self.assertEqual({row[key].value.text for row in value.rows}, {"60 min", "90 min"})
        source_properties = {self.engine.anchors[a].selector.property_path[-1]
                             for a in result.claims[0].evidence[0].anchor_ids if self.engine.anchors[a].selector.property_path}
        self.assertIn("FireRating", source_properties)
        self.assertEqual(len([f for f in self.engine.bundle.facts if f.id in result.claims[0].evidence[0].fact_ids]), 2)

    def test_explicit_square_millimetres_project_area_and_duplicates(self):
        value, result = self.answer("space", operation="sum", property="Qto_SpaceBaseQuantities.NetFloorArea", unit="m2")
        self.assertEqual(Decimal(value.magnitude), Decimal("40"))
        self.assertEqual(value.basis, "net")
        source_facts = [f for f in self.engine.bundle.facts if f.id in result.calculations[-1].fact_ids]
        self.assertEqual(len(source_facts), 3)  # Duplicate values retained as evidence, counted once per space.
        self.assertEqual({f.value.unit_resolution for f in source_facts}, {"explicit", "project_default"})
        conversions = [node for node in result.calculations if node.operation == "convert_unit"]
        self.assertEqual({Decimal(node.output.magnitude) for node in conversions}, {Decimal(19), Decimal(21)})

    def test_length_conversion_is_independent_of_area_units(self):
        value, _ = self.answer("door", operation="sum", property="OverallWidth", storey="Ground", unit="m")
        self.assertEqual(Decimal(value.magnitude), Decimal("2"))

    def test_topmost_assemblies_and_leaf_parts(self):
        all_stairs, _ = self.answer("stair")
        assemblies, result = self.answer("stair", hierarchy="topmost_matches", storey="Ground")
        leaves, _ = self.answer("stair", hierarchy="leaves")
        self.assertEqual((all_stairs.value, assemblies.value, leaves.value), (3, 1, 2))
        self.assertEqual(result.claims[0].count_policy.rule_key, "ifc.topmost.v1")

    def test_ranking_keeps_numeric_order_when_projecting_rows(self):
        table, _ = self.answer("door", operation="rank", property="OverallWidth", storey="Ground", limit=2)
        self.assertEqual([Decimal(row[attribute_key("OverallWidth")].magnitude) for row in table.rows], [Decimal(1100), Decimal(900)])

    def test_missing_value_prevents_a_complete_total(self):
        result = self.engine.query("door", operation="sum", property="OverallWidth", unit="m")
        self.assertEqual(result.status, "missing_information")
        self.assertFalse(result.claims)
        self.assertTrue(result.issues[0].entity_ids)

    def test_missing_catalog_property_is_not_zero(self):
        result = self.engine.query("door", operation="lookup", property="DoesNotExist")
        self.assertEqual(result.status, "missing_information")

    def test_unresolved_storey_is_not_model_wide_scope(self):
        result = self.engine.query("door", storey="Nonexistent")
        self.assertEqual(result.status, "needs_clarification")
        self.assertFalse(result.claims)

    def test_empty_supported_model_class_counts_zero_in_explicit_model_scope(self):
        value, result = self.answer("window")
        self.assertEqual(value.value, 0)
        self.assertEqual(result.entity_sets[-1].entity_ids, [])
        self.assertEqual(result.claims[0].scope.universe, "modeled_objects")

    def test_conflicting_duplicate_quantities_are_reported(self):
        engine = self.engine
        room = engine.resolve_entity("7.16")
        key = engine.resolve_property("Qto_SpaceBaseQuantities.NetFloorArea")
        facts = engine.facts[room, key]
        facts[-1].value.magnitude = "20000000"
        facts[-1].value.normalized.magnitude = "20"
        result = engine.query("space", operation="sum", property=key, unit="m2")
        self.assertEqual(result.status, "conflicting_evidence")

    def test_predicates_compare_units_and_preserve_missing_under_not(self):
        plan = self.engine.plan("door")
        width = m.FieldRef(kind="property", key=attribute_key("OverallWidth"))
        comparison = m.ComparePredicate(kind="compare", field=width, operator="gt", value=m.QuantityValue(
            kind="quantity", magnitude="1", unit_id="unit:m", quantity_kind="length", basis="modeled", unit_resolution="explicit"))
        plan.steps[0].operation.where = comparison
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "missing_information")
        self.assertFalse(result.claims)
        plan.steps[0].operation.where = m.BooleanPredicate(kind="not", operands=[comparison])
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "missing_information")
        self.assertFalse(result.claims)
        plan.steps[0].operation.where = m.BooleanPredicate(kind="all", operands=[
            m.PresentPredicate(kind="field_present", field=width),
            m.BooleanPredicate(kind="not", operands=[comparison]),
        ])
        result = self.engine.execute(plan)
        self.assertEqual(result.claims[0].value.value, 1)  # Explicitly scoped to known widths.
        excluded = next(s for s in result.entity_sets if s.id == result.calculations[0].excluded_set_id)
        self.assertEqual(excluded.count, 2)

    def test_grouped_counts_can_be_ranked_as_derived_columns(self):
        plan = self.engine.plan("door", storey="Ground")
        plan.steps[-1].operation.group_by = [m.FieldRef(kind="property", key=property_key("Pset_DoorCommon", "FireRating"))]
        plan.steps[-1].operation.value_key = "door_count"
        plan.steps.append(m.PlanStep(id="ranked", operation=m.RankOperation(kind="rank", input_step_id="answer",
                          field=m.FieldRef(kind="result_column", key="door_count"), direction="descending", limit=2)))
        plan.outputs = {"answer": "ranked"}
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        self.assertEqual([row["door_count"].value for row in result.claims[0].value.rows], [1, 1])
        cells = [binding for binding in result.claims[0].evidence if binding.value_path.endswith("door_count")]
        nodes = {node.id: node for node in result.calculations}
        self.assertEqual(len(cells), 2)
        self.assertTrue(all(nodes[b.calculation_id].operation == "count" for b in cells))

    def test_projected_cells_bind_to_their_own_source_facts(self):
        table, result = self.answer("door", operation="lookup", property="Pset_DoorCommon.FireRating", storey="Ground")
        bindings = [b for b in result.claims[0].evidence if b.value_path.endswith("FireRating")]
        self.assertEqual(len(bindings), 2)
        self.assertTrue(all("~1" in binding.value_path for binding in bindings))
        by_id = {f.id: f for f in self.engine.bundle.facts}
        key = property_key("Pset_DoorCommon", "FireRating")
        for row_index, binding in enumerate(bindings):
            self.assertEqual(len(binding.fact_ids), 1)
            self.assertEqual(by_id[binding.fact_ids[0]].value, table.rows[row_index][key])

    def test_ranking_groups_retains_only_their_members_in_the_output_set(self):
        plan = self.engine.plan("door", storey="Ground")
        plan.steps[-1].operation.group_by = [m.FieldRef(kind="property", key=property_key("Pset_DoorCommon", "FireRating"))]
        plan.steps.append(m.PlanStep(id="ranked", operation=m.RankOperation(kind="rank", input_step_id="answer",
                          field=m.FieldRef(kind="result_column", key="value"), direction="descending", limit=1)))
        plan.outputs = {"answer": "ranked"}
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered", result.model_dump_json())
        output_set = next(s for s in result.entity_sets if s.id == "set:ranked")
        self.assertEqual(output_set.count, 1)
        excluded = next(s for s in result.entity_sets if s.id == "set:ranked:excluded")
        self.assertEqual(excluded.count, 1)

    def test_material_traversal_cites_the_native_association(self):
        plan = self.engine.plan("door")
        plan.steps = plan.steps[:1] + [m.PlanStep(id="materials", operation=m.TraverseOperation(
            kind="traverse", input_step_id="objects", predicate="has_material", direction="outgoing"))]
        plan.outputs = {"materials": "materials"}
        result = self.engine.execute(plan)
        self.assertEqual(result.status, "answered")
        self.assertEqual(len(result.claims[0].value.entity_ids), 1)
        relationships = [r for r in self.engine.bundle.relations if r.predicate == "has_material"]
        anchors = {a for r in relationships for a in r.provenance.anchor_ids}
        self.assertTrue(anchors.intersection(result.calculations[-1].anchor_ids))
        self.assertTrue(all(r.native_predicate == "IfcRelAssociatesMaterial" for r in relationships))

    def test_guid_selection_remains_scoped_to_the_model(self):
        guid = self.source[1][0].GlobalId
        count, _ = self.answer("door", entity=guid)
        self.assertEqual(count.value, 1)

    def test_incompatible_output_units_are_rejected(self):
        result = self.engine.query("space", operation="sum", property="Qto_SpaceBaseQuantities.NetFloorArea", unit="m")
        self.assertEqual(result.status, "execution_error")
        self.assertFalse(result.claims)

    def test_spatial_predicate_is_rejected_even_for_an_empty_class(self):
        plan = self.engine.plan("window")
        plan.steps[0].operation.where = m.SpatialPredicate(kind="spatial", operator="within", geometry_id="geometry:unavailable")
        self.assertEqual(self.engine.execute(plan).status, "unsupported_operation")

    def test_traversal_and_scope_do_not_pull_in_external_entities(self):
        plan = self.engine.plan("door", storey="Ground")
        plan.steps = plan.steps[:1] + [m.PlanStep(id="types", operation=m.TraverseOperation(kind="traverse", input_step_id="objects",
                          predicate="typed_by", direction="outgoing"))]
        plan.outputs = {"types": "types"}
        result = self.engine.execute(plan)
        self.assertEqual(result.claims[0].value.entity_ids, [])
        plan.scope = self.engine.scope()
        result = self.engine.execute(plan)
        self.assertEqual(len(result.claims[0].value.entity_ids), 1)

    def test_unsupported_geometry_and_physical_building_scope(self):
        plan = self.engine.plan("space")
        plan.steps[-1].operation = m.MeasureOperation(kind="measure", input_step_id="objects", metric="area", output_unit_id="unit:m2", basis="net")
        self.assertEqual(self.engine.execute(plan).status, "unsupported_operation")
        plan = self.engine.plan("door")
        plan.scope.universe = "physical_building"
        self.assertEqual(self.engine.execute(plan).status, "unsupported_operation")

    def test_cache_invalidation_uses_source_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "revision.ifc"
            source, *_ = sample_model(path)
            cache = Path(directory) / "cache"
            first = IfcQueryEngine.open(path, cache_dir=cache)
            second = IfcQueryEngine.open(path, cache_dir=cache)
            self.assertFalse(first.cache_hit)
            self.assertTrue(second.cache_hit)
            source.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(), Name="New door")
            source.write(str(path))
            third = IfcQueryEngine.open(path, cache_dir=cache)
            self.assertFalse(third.cache_hit)
            self.assertEqual(third.query("door").claims[0].value.value, 4)
            self.assertNotEqual(first.bundle.assets[0].sha256, third.bundle.assets[0].sha256)

    def test_cli_exports_matching_plan_result_and_evidence_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle.json"
            plan = Path(directory) / "plan.json"
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["count", str(self.path), "door", "--storey", "Ground", "--bundle-out", str(bundle), "--plan-out", str(plan)])
            self.assertEqual(code, 0)
            result = m.QueryResult.model_validate_json(output.getvalue())
            exported = m.KnowledgeBundle.model_validate_json(bundle.read_text())
            validate_bundle(exported)
            validate_result(result, exported, m.QueryPlan.model_validate_json(plan.read_text()))

    def test_cli_refuses_to_overwrite_source(self):
        original = self.path.read_bytes()
        with redirect_stderr(io.StringIO()):
            code = main(["count", str(self.path), "door", "--output", str(self.path)])
        self.assertEqual(code, 2)
        self.assertEqual(self.path.read_bytes(), original)


class RealIfcIntegrationTests(unittest.TestCase):
    def test_esplanades_known_model_and_floor_counts(self):
        path = Path(__file__).resolve().parents[1] / "dataset/junction-dataset-preview/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc"
        if not path.exists():
            self.skipTest("Optional challenge dataset is not installed")
        engine = IfcQueryEngine.open(path)
        model = engine.query("door")
        floor = engine.query("door", storey="4.korrus")
        self.assertEqual(model.status, "answered", model.model_dump_json())
        self.assertEqual(floor.status, "answered", floor.model_dump_json())
        self.assertEqual(model.claims[0].value.value, 211)
        self.assertEqual(floor.claims[0].value.value, 42)


class IfcSchemaTests(unittest.TestCase):
    def test_ifc4x3_add2_basic_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "infrastructure.ifc"
            sample_model(path, schema="IFC4X3_ADD2")
            engine = IfcQueryEngine.open(path)
            self.assertEqual(engine.schema, "IFC4X3_ADD2")
            self.assertEqual(engine.query("door").claims[0].value.value, 3)

    def test_ifc2x3_semantic_class_from_assigned_type(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.ifc"
            model = ifcopenshell.file(schema="IFC2X3")
            model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="Typed fixtures")
            fixture = model.create_entity("IfcFlowTerminal", GlobalId=ifcopenshell.guid.new(), Name="Fixture")
            fixture_type = model.create_entity("IfcSanitaryTerminalType", GlobalId=ifcopenshell.guid.new(), Name="WC", PredefinedType="TOILETPAN")
            model.create_entity("IfcRelDefinesByType", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[fixture], RelatingType=fixture_type)
            model.write(str(path))
            engine = IfcQueryEngine.open(path)
            result = engine.query("sanitary_terminal")
            self.assertEqual(result.status, "answered", result.model_dump_json())
            self.assertEqual(result.claims[0].value.value, 1)


if __name__ == "__main__":
    unittest.main()

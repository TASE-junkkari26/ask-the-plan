"""Exterior-door grain, source coverage, inheritance and inspectable native proof."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import ifcopenshell
import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_plan, validate_result
from ifc_engine.catalog import POLICIES
from ifc_engine.engine import IfcQueryEngine
from ifc_engine.exterior import EXTERNAL_KEY


def exterior_source(path, *, flags=None, boundaries=True, type_flags=True):
    source = ifcopenshell.file(schema="IFC4")

    def root(kind, **attributes):
        return source.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **attributes)

    objects = {"project": root("IfcProject", Name="Exterior door fixture"),
        "ground": root("IfcBuildingStorey", Name="Ground"),
        "a": root("IfcSpace", Name="A"), "b": root("IfcSpace", Name="B"),
        "opening": root("IfcOpeningElement", Name="Outside opening")}
    for key in ("direct", "filled", "interior", "unknown", "inherited", "override", "null", "text"):
        objects[key] = root("IfcDoor", Name=key)
    root("IfcRelAggregates", RelatingObject=objects["project"], RelatedObjects=[objects["ground"]])
    root("IfcRelAggregates", RelatingObject=objects["ground"], RelatedObjects=[objects["a"], objects["b"]])
    root("IfcRelContainedInSpatialStructure", RelatingStructure=objects["ground"],
        RelatedElements=[objects[key] for key in ("direct", "filled", "interior", "unknown", "inherited", "override", "null", "text", "opening")])
    records = {}

    def pset(value):
        nominal = None if value is None else source.create_entity("IfcBoolean" if isinstance(value, bool) else "IfcLabel", value)
        prop = source.create_entity("IfcPropertySingleValue", Name="IsExternal", NominalValue=nominal)
        return root("IfcPropertySet", Name="Pset_DoorCommon", HasProperties=[prop]), prop

    for key, flag in (flags if flags is not None else {"direct": True, "filled": True, "interior": False, "null": None}).items():
        definition, records[key + "_flag"] = pset(flag)
        root("IfcRelDefinesByProperties", RelatedObjects=[objects[key]], RelatingPropertyDefinition=definition)
    if type_flags:
        type_pset, records["type_flag"] = pset(True)
        objects["type"] = root("IfcDoorType", Name="Exterior type", HasPropertySets=[type_pset])
        root("IfcRelDefinesByType", RelatingType=objects["type"], RelatedObjects=[objects["inherited"], objects["override"]])
        own, records["override_flag"] = pset(False)
        root("IfcRelDefinesByProperties", RelatedObjects=[objects["override"]], RelatingPropertyDefinition=own)
    if boundaries:
        records["fill"] = root("IfcRelFillsElement", RelatingOpeningElement=objects["opening"], RelatedBuildingElement=objects["filled"])
        for key, room, element, external, physical in [
            ("direct_a", "a", "direct", "EXTERNAL", "PHYSICAL"),
            ("direct_b", "b", "direct", "EXTERNAL", "PHYSICAL"),
            ("direct_dup", "a", "direct", "EXTERNAL", "PHYSICAL"),
            ("filled_a", "a", "opening", "EXTERNAL", "PHYSICAL"),
            ("interior_a", "a", "interior", "INTERNAL", "PHYSICAL"),
            ("virtual_unknown", "a", "unknown", "EXTERNAL", "VIRTUAL")]:
            records[key] = root("IfcRelSpaceBoundary", RelatingSpace=objects[room], RelatedBuildingElement=objects[element],
                PhysicalOrVirtualBoundary=physical, InternalOrExternalBoundary=external)
    source.write(str(path))
    return source, objects, records


class IfcExteriorQueryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "exterior.ifc"
        self.source, self.objects, self.records = exterior_source(self.path)
        self.engine = IfcQueryEngine.open(self.path)

    def entity(self, key):
        return self.engine.resolve_entity(self.objects[key].GlobalId)

    def plan(self, keys, *, basis="combined", count=True, scope=None):
        ids = [self.entity(key) for key in keys]
        predicate = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="entity_id"),
            operator="in", value=m.ListValue(kind="list", items=[m.ReferencesValue(kind="references", entity_ids=[identifier]) for identifier in ids]))
        steps = [m.PlanStep(id="doors", operation=m.SelectOperation(kind="select", concept_ids=["concept:door"],
                    where=predicate, count_policy=POLICIES["all_matches"])),
                 m.PlanStep(id="exterior", operation=m.SpatialQueryOperation(kind="spatial_query", input_step_id="doors",
                    relation="exterior_doors", exterior_basis=basis))]
        if count:
            steps.append(m.PlanStep(id="count", operation=m.AggregateOperation(kind="aggregate", input_step_id="exterior", method="count")))
        return m.QueryPlan(id="plan:exterior", request_id="request:exterior", scope=scope or self.engine.scope(),
            steps=steps, outputs={"answer": steps[-1].id})

    def execute(self, plan, expected="answered"):
        validate_plan(plan, self.engine.bundle, self.engine.capabilities)
        result = self.engine.execute(plan)
        self.assertEqual(result.status, expected, result.model_dump_json(indent=2))
        validate_result(result, self.engine.bundle, plan)
        return result

    def steps(self, result):
        anchors = {anchor for node in result.calculations for anchor in node.anchor_ids}
        anchors.update(anchor for issue in result.issues for anchor in issue.anchor_ids)
        return {int(self.engine.anchors[a].selector.value) for a in anchors
            if self.engine.anchors[a].selector.kind == "step_id"}

    def test_classification_honors_inheritance_and_occurrence_override_with_negative_proof(self):
        result = self.execute(self.plan(["direct", "interior", "inherited", "override"], basis="classification"))
        self.assertEqual(result.claims[0].value.value, 2)
        self.assertEqual(result.claims[0].quality, "exact")
        self.assertEqual(result.claims[0].count_policy.grain, "occurrence")
        expected = {self.records[key].id() for key in ("direct_flag", "interior_flag", "type_flag", "override_flag")}
        self.assertTrue(expected <= self.steps(result))
        sets = {row.id: row for row in result.entity_sets}
        excluded = sets["set:exterior:excluded"]
        self.assertEqual(set(excluded.entity_ids), {self.entity("interior"), self.entity("override")})

    def test_combined_normalizes_direct_and_opening_paths_and_deduplicates_doors(self):
        # A double-leaf occurrence still contributes once, regardless of its
        # number of leaves, room references or repeated boundary records.
        self.objects["direct"].ObjectType = "Double-leaf door"
        self.source.write(str(self.path))
        self.engine = IfcQueryEngine.open(self.path)
        result = self.execute(self.plan(["direct", "filled", "interior"]))
        self.assertEqual(result.claims[0].value.value, 2)
        self.assertTrue({self.records[key].id() for key in ("direct_a", "direct_b", "direct_dup", "filled_a", "fill", "interior_a")} <= self.steps(result))

    def test_missing_flags_can_be_resolved_by_positive_boundary_but_not_by_absence(self):
        self.source, self.objects, self.records = exterior_source(self.path, flags={})
        self.engine = IfcQueryEngine.open(self.path)
        result = self.execute(self.plan(["direct", "filled", "unknown"]), "partial")
        self.assertEqual(result.claims[0].value.value, 2)
        self.assertEqual(result.claims[0].quality, "lower_bound")
        self.assertEqual(result.issues[0].entity_ids, [self.entity("unknown")])
        coverage = next(c for c in self.engine.bundle.coverage if c.id in result.claims[0].coverage_ids)
        self.assertEqual(coverage.completeness, "partial")
        self.assertIn("lower bound", result.explanation.text)
        self.assertTrue(all(node.quality == "lower_bound" for node in result.calculations if node.plan_step_id in {"exterior", "count"}))

    def test_unknown_null_and_nonboolean_are_not_silently_false(self):
        self.source, self.objects, self.records = exterior_source(self.path,
            flags={"null": None, "text": "true"}, type_flags=False)
        self.engine = IfcQueryEngine.open(self.path)
        result = self.execute(self.plan(["direct", "null", "text", "unknown"]), "partial")
        self.assertEqual(result.claims[0].value.value, 1)
        self.assertEqual(set(result.issues[0].entity_ids), {self.entity(k) for k in ("null", "text", "unknown")})
        self.assertTrue({self.records["null_flag"].id(), self.records["text_flag"].id()} <= self.steps(result))

    def test_all_unknown_is_missing_information_and_not_zero(self):
        result = self.execute(self.plan(["unknown", "null"]), "missing_information")
        self.assertFalse(result.claims)
        self.assertEqual(set(result.issues[0].entity_ids), {self.entity("unknown"), self.entity("null")})

    def test_false_flag_and_positive_boundary_are_conflicting_with_both_proofs(self):
        self.source, self.objects, self.records = exterior_source(self.path, flags={"direct": False})
        self.engine = IfcQueryEngine.open(self.path)
        result = self.execute(self.plan(["direct"]), "conflicting_evidence")
        self.assertFalse(result.claims)
        self.assertTrue({self.records["direct_flag"].id(), self.records["direct_a"].id()} <= self.steps(result))
        self.assertEqual(result.issues[0].entity_ids, [self.entity("direct")])

    def test_contradictory_boolean_facts_are_not_resolved_by_picking_one(self):
        prop = self.source.create_entity("IfcPropertySingleValue", Name="IsExternal",
            NominalValue=self.source.create_entity("IfcBoolean", False))
        definition = self.source.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
            Name="Pset_DoorCommon", HasProperties=[prop])
        self.source.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[self.objects["direct"]], RelatingPropertyDefinition=definition)
        self.source.write(str(self.path))
        self.engine = IfcQueryEngine.open(self.path)
        result = self.execute(self.plan(["direct"], basis="classification"), "conflicting_evidence")
        self.assertTrue({prop.id(), self.records["direct_flag"].id()} <= self.steps(result))

    def test_explicit_null_occurrence_overrides_inherited_exterior_classification(self):
        prop = self.source.create_entity("IfcPropertySingleValue", Name="IsExternal", NominalValue=None)
        definition = self.source.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
            Name="Pset_DoorCommon", HasProperties=[prop])
        self.source.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[self.objects["inherited"]], RelatingPropertyDefinition=definition)
        self.source.write(str(self.path))
        self.engine = IfcQueryEngine.open(self.path)
        result = self.execute(self.plan(["direct", "inherited"], basis="classification"), "partial")
        self.assertEqual(result.claims[0].value.value, 1)
        self.assertEqual(result.issues[0].entity_ids, [self.entity("inherited")])
        self.assertIn(prop.id(), self.steps(result))

    def test_complete_false_classifications_can_establish_source_zero(self):
        result = self.execute(self.plan(["interior", "override"], basis="classification"))
        self.assertEqual(result.claims[0].value.value, 0)
        self.assertEqual(result.claims[0].quality, "exact")

    def test_coverage_does_not_reuse_an_unrelated_selection_proof(self):
        direct = self.execute(self.plan(["direct"], basis="classification"))
        inherited = self.execute(self.plan(["inherited"], basis="classification"))
        self.assertNotEqual(direct.claims[0].coverage_ids, inherited.claims[0].coverage_ids)
        coverage = next(c for c in self.engine.bundle.coverage if c.id in inherited.claims[0].coverage_ids)
        self.assertTrue(set(coverage.provenance.anchor_ids) >= set(inherited.claims[0].evidence[0].anchor_ids))

    def test_room_input_is_rejected_instead_of_counted_as_doors(self):
        plan = self.plan(["a"])
        plan.steps[0].operation.concept_ids = ["concept:space"]
        self.execute(plan, "needs_clarification")

    def test_boundary_basis_counts_recorded_paths_and_reports_its_limited_meaning(self):
        result = self.execute(self.plan(["direct", "filled", "interior", "unknown"], basis="boundary"))
        self.assertEqual(result.claims[0].value.value, 2)
        self.assertIn("counts supported source relationships", result.explanation.text)
        self.assertIn("Physical-building completeness", result.explanation.text)

    def test_no_boundary_records_cannot_establish_boundary_zero(self):
        self.source, self.objects, self.records = exterior_source(self.path, boundaries=False)
        self.engine = IfcQueryEngine.open(self.path)
        self.execute(self.plan(["direct"], basis="boundary"), "missing_information")
        result = self.execute(self.plan(["direct"], basis="classification"))
        self.assertEqual(result.claims[0].value.value, 1)

    def test_required_boundary_intermediates_cannot_escape_exact_scope(self):
        scope = self.engine.scope()
        scope.exact_entity_ids = [self.entity("filled"), self.entity("a")]
        self.execute(self.plan(["filled"], scope=scope), "incomplete_coverage")
        # Property-only questions need no source room or opening traversal.
        result = self.execute(self.plan(["filled"], basis="classification", scope=scope))
        self.assertEqual(result.claims[0].value.value, 1)

    def test_empty_exact_inventory_can_establish_zero(self):
        scope = self.engine.scope()
        scope.exact_entity_ids = []
        result = self.execute(self.plan(["direct"], scope=scope))
        self.assertEqual(result.claims[0].value.value, 0)

    def test_generic_relation_filter_retains_native_boundary_anchors(self):
        plan = self.engine.plan("door", operation="count")
        plan.steps[0].operation.where = m.RelationPredicate(kind="related_to", predicate="external_boundary",
            direction="incoming", entity_ids=[self.entity("a"), self.entity("b")])
        result = self.execute(plan)
        self.assertEqual(result.claims[0].value.value, 1)
        self.assertTrue({self.records[key].id() for key in ("direct_a", "direct_b", "direct_dup")} <= self.steps(result))

    def test_incomplete_membership_does_not_allow_unqualified_extrema(self):
        plan = self.plan(["direct", "unknown"], count=False)
        plan.steps.append(m.PlanStep(id="rank", operation=m.RankOperation(kind="rank", input_step_id="exterior",
            field=m.FieldRef(kind="label", key="label"), direction="ascending", limit=1)))
        plan.outputs = {"answer": "rank"}
        self.execute(plan, "unsupported_operation")


if __name__ == "__main__":
    unittest.main()

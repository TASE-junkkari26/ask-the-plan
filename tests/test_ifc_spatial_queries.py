"""Native IFC location/topology queries retain their limits and inspectable proof."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import ifcopenshell
import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from ifc_engine.catalog import POLICIES
from ifc_engine.engine import IfcQueryEngine


def spatial_source(path: Path, *, corresponding=False):
    source = ifcopenshell.file(schema="IFC4")

    def root(kind, **attributes):
        return source.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **attributes)

    objects = {
        "project": root("IfcProject", Name="Spatial regression fixture"),
        "site": root("IfcSite", Name="Site"),
        "building": root("IfcBuilding", Name="Building A"),
        "ground": root("IfcBuildingStorey", Name="Ground"),
        "upper": root("IfcBuildingStorey", Name="Upper"),
        "a": root("IfcSpace", Name="1B07", LongName="Büro"),
        "b": root("IfcSpace", Name="1B08", LongName="Flur"),
        "c": root("IfcSpace", Name="121.A", LongName="Separate room along a long wall"),
        "d": root("IfcSpace", Name="7.16", LongName="No extracted boundaries"),
        "equipment": root("IfcElectricDistributionBoard", Name="Panel-01"),
        "wall": root("IfcWall", Name="Long shared wall"),
        "direct_door": root("IfcDoor", Name="Tür-019"),
        "opening": root("IfcOpeningElement", Name="Internal opening"),
        "opening_door": root("IfcDoor", Name="Tür-018"),
        "outside_door": root("IfcDoor", Name="Exterior door A"),
        "second_outside_door": root("IfcDoor", Name="Exterior door A2"),
        "outside_opening": root("IfcOpeningElement", Name="Exterior opening B"),
        "outside_opening_door": root("IfcDoor", Name="Exterior door B"),
        "virtual_door": root("IfcDoor", Name="Virtual boundary door"),
    }
    relationships = {}

    def relation(key, kind, **attributes):
        relationships[key] = root(kind, **attributes)
        return relationships[key]

    for parent, children in [("project", ["site"]), ("site", ["building"]),
                             ("building", ["ground", "upper"]), ("ground", ["a", "b", "c", "d"])]:
        relation(parent, "IfcRelAggregates", RelatingObject=objects[parent],
                 RelatedObjects=[objects[child] for child in children])
    relation("equipment_location", "IfcRelContainedInSpatialStructure", RelatingStructure=objects["a"],
             RelatedElements=[objects["equipment"]])
    relation("element_floor", "IfcRelContainedInSpatialStructure", RelatingStructure=objects["ground"],
             RelatedElements=[objects[key] for key in ["wall", "direct_door", "opening", "opening_door",
                 "outside_door", "second_outside_door", "outside_opening", "outside_opening_door", "virtual_door"]])
    relation("internal_void", "IfcRelVoidsElement", RelatingBuildingElement=objects["wall"],
             RelatedOpeningElement=objects["opening"])
    relation("internal_fill", "IfcRelFillsElement", RelatingOpeningElement=objects["opening"],
             RelatedBuildingElement=objects["opening_door"])
    relation("outside_fill", "IfcRelFillsElement", RelatingOpeningElement=objects["outside_opening"],
             RelatedBuildingElement=objects["outside_opening_door"])

    def boundary(key, room, element, *, physical="PHYSICAL", external="INTERNAL", second=False):
        return relation(key, "IfcRelSpaceBoundary2ndLevel" if second else "IfcRelSpaceBoundary",
                        RelatingSpace=objects[room], RelatedBuildingElement=objects[element],
                        PhysicalOrVirtualBoundary=physical, InternalOrExternalBoundary=external)

    wall_a = boundary("wall_a", "a", "wall", second=corresponding)
    wall_b = boundary("wall_b", "b", "wall", second=corresponding)
    if corresponding:
        wall_a.CorrespondingBoundary = wall_b
        wall_b.CorrespondingBoundary = wall_a
    else:
        # Sharing a long wall is a deliberately insufficient geometric proof.
        boundary("wall_c", "c", "wall")
    boundary("direct_a", "a", "direct_door")
    boundary("direct_b", "b", "direct_door")
    boundary("direct_duplicate_a", "a", "direct_door")
    boundary("opening_b", "b", "opening")
    boundary("opening_c", "c", "opening")
    boundary("exterior_a", "a", "outside_door", external="EXTERNAL")
    boundary("exterior_a_duplicate", "a", "outside_door", external="EXTERNAL")
    boundary("exterior_a_second", "a", "second_outside_door", external="EXTERNAL")
    boundary("exterior_b", "b", "outside_opening", external="EXTERNAL")
    boundary("virtual_c", "c", "virtual_door", physical="VIRTUAL", external="EXTERNAL")
    source.write(str(path))
    return source, objects, relationships


class IfcSpatialQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        path = Path(cls.directory.name) / "spatial.ifc"
        _, cls.objects, cls.relationships = spatial_source(path)
        cls.loaded = IfcQueryEngine.open(path)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.engine = IfcQueryEngine(self.loaded.bundle.model_copy(deep=True), schema=self.loaded.schema)

    def entity(self, name):
        return self.engine.resolve_entity(name)

    def plan(self, names, relation, *, container_kind="storey", count=False, exact_names=None, method="auto"):
        entity_ids = [self.entity(name) for name in names]
        concepts = sorted({concept for entity_id in entity_ids for concept in self.engine.entities[entity_id].concept_ids
                           if concept.startswith("ifc:")})
        scope = self.engine.scope()
        if exact_names is not None:
            scope.exact_entity_ids = [self.entity(name) for name in exact_names]
        steps = [m.PlanStep(id="objects", operation=m.SelectOperation(kind="select", concept_ids=concepts,
            count_policy=POLICIES["all_matches"], where=m.BooleanPredicate(kind="any", operands=[
                m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="entity_id"),
                    operator="eq", value=m.ReferencesValue(kind="references", entity_ids=[entity_id]))
                for entity_id in entity_ids]))),
            m.PlanStep(id="locations", operation=m.SpatialQueryOperation(kind="spatial_query", input_step_id="objects",
                relation=relation, container_kind=container_kind, method=method))]
        if count:
            steps.append(m.PlanStep(id="count", operation=m.AggregateOperation(kind="aggregate", input_step_id="locations", method="count")))
        return m.QueryPlan(id="plan:spatial-test", request_id="request:spatial-test", scope=scope,
                           steps=steps, outputs={"answer": steps[-1].id})

    def execute(self, plan, status="answered"):
        validate_plan(plan, self.engine.bundle, self.engine.capabilities)
        result = self.engine.execute(plan)
        self.assertEqual(result.status, status, result.model_dump_json(indent=2))
        validate_bundle(self.engine.bundle)
        validate_result(result, self.engine.bundle, plan)
        return result

    def anchor_steps(self, anchor_ids):
        return {int(self.engine.anchors[anchor_id].selector.value) for anchor_id in anchor_ids
                if self.engine.anchors[anchor_id].selector.kind == "step_id"}

    def test_container_location_preserves_ancestry_proof_and_cell_evidence(self):
        for kind, name, relation_keys in [("space", "1B07", ["equipment_location"]),
                ("storey", "Ground", ["equipment_location", "ground"]),
                ("building", "Building A", ["equipment_location", "ground", "building"]),
                ("site", "Site", ["equipment_location", "ground", "building", "site"])]:
            with self.subTest(kind=kind):
                result = self.execute(self.plan(["Panel-01"], "containers", container_kind=kind))
                claim = result.claims[0]
                self.assertIsInstance(claim.value, m.TableValue)
                self.assertEqual(len(claim.value.rows), 1)
                row = claim.value.rows[0]
                self.assertEqual(row["subject"].entity_ids, [self.entity("Panel-01")])
                self.assertEqual(row["related"].entity_ids, [self.entity(name)])
                expected = {self.relationships[key].id() for key in relation_keys}
                self.assertTrue(expected <= self.anchor_steps(claim.evidence[0].anchor_ids))
                for column in ("subject", "related", "via", "basis"):
                    evidence = next(binding for binding in claim.evidence if binding.value_path == f"/rows/0/{column}")
                    self.assertTrue(expected <= self.anchor_steps(evidence.anchor_ids))
                    self.assertTrue(evidence.entity_set_ids)
                self.assertIn("native IFC containment", result.explanation.text)

    def test_shared_long_wall_yields_partial_adjacency_candidates_and_no_route_claim(self):
        result = self.execute(self.plan(["1B07"], "boundary_neighbors"), "partial")
        rows = result.claims[0].value.rows
        self.assertEqual({row["related"].entity_ids[0] for row in rows}, {self.entity("1B08"), self.entity("121.A")})
        self.assertEqual(len(rows), 2)
        candidate = next(row for row in rows if row["related"].entity_ids == [self.entity("121.A")])
        self.assertIn("candidate adjacency", candidate["basis"].value.text)
        self.assertTrue(any(issue.code == "incomplete_coverage" for issue in result.issues))
        self.assertIn("not verified geometric neighbors", result.issues[0].message.text)

    def test_direct_connections_require_doors_and_deduplicate_boundaries(self):
        result = self.execute(self.plan(["1B07"], "door_connections"))
        rows = result.claims[0].value.rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["related"].entity_ids, [self.entity("1B08")])
        self.assertEqual(rows[0]["via"].entity_ids, [self.entity("Tür-019")])
        evidence_steps = self.anchor_steps(result.claims[0].evidence[0].anchor_ids)
        self.assertTrue({self.relationships[key].id() for key in ["direct_a", "direct_b", "direct_duplicate_a"]} <= evidence_steps)
        self.assertIn("not a navigable route", result.explanation.text)

    def test_opening_filled_by_door_retains_boundary_and_fill_evidence(self):
        result = self.execute(self.plan(["1B08"], "door_connections"))
        rows = result.claims[0].value.rows
        self.assertEqual({row["related"].entity_ids[0] for row in rows}, {self.entity("1B07"), self.entity("121.A")})
        opening_row = next(row for row in rows if row["related"].entity_ids == [self.entity("121.A")])
        self.assertEqual(set(opening_row["via"].entity_ids), {self.entity("Internal opening"), self.entity("Tür-018")})
        self.assertTrue({self.relationships[key].id() for key in ["opening_b", "opening_c", "internal_fill"]}
                        <= self.anchor_steps(result.claims[0].evidence[0].anchor_ids))

    def test_outdoor_access_counts_distinct_rooms_with_explicit_physical_exterior_doors(self):
        plan = self.plan(["1B07", "1B08", "121.A"], "outdoor_access")
        result = self.execute(plan)
        self.assertEqual(set(result.claims[0].value.entity_ids), {self.entity("1B07"), self.entity("1B08")})
        self.assertIn("not a verified fire exit", result.explanation.text)
        evidence_steps = self.anchor_steps(result.claims[0].evidence[0].anchor_ids)
        self.assertTrue({self.relationships[key].id() for key in ["exterior_a", "exterior_a_duplicate", "exterior_a_second", "exterior_b", "outside_fill"]}
                        <= evidence_steps)
        count = self.execute(self.plan(["1B07", "1B08", "121.A"], "outdoor_access", count=True))
        self.assertEqual(count.claims[0].value.value, 2)
        self.assertEqual(count.claims[0].count_policy.grain, "occurrence")
        sets = {entity_set.id: entity_set for entity_set in count.entity_sets}
        included = sets[count.claims[0].evidence[0].entity_set_ids[0]]
        self.assertEqual(set(included.entity_ids), {self.entity("1B07"), self.entity("1B08")})

    def test_missing_topology_is_missing_information_for_neighbors_connections_and_access(self):
        for relation in ("boundary_neighbors", "door_connections", "outdoor_access"):
            with self.subTest(relation=relation):
                result = self.execute(self.plan(["7.16"], relation), "missing_information")
                self.assertFalse(result.claims)
                self.assertIn("Missing topology cannot establish zero", result.issues[0].message.text)

    def test_missing_containing_space_is_not_inferred_from_floor_membership(self):
        result = self.execute(self.plan(["Tür-019"], "containers", container_kind="space"), "missing_information")
        self.assertFalse(result.claims)

    def test_exact_scope_cannot_expand_to_hidden_neighbor_or_doorway(self):
        names = [element.labels[0].text for element in self.engine.entities.values() if element.labels]
        for omitted in ("1B08", "Tür-019"):
            with self.subTest(omitted=omitted):
                result = self.execute(self.plan(["1B07"], "door_connections",
                    exact_names=[name for name in names if name != omitted]), "incomplete_coverage")
                self.assertFalse(result.claims)
                self.assertIn("outside the captured view", result.issues[0].message.text)

    def test_exact_scope_cannot_skip_hidden_intermediate_containment(self):
        result = self.execute(self.plan(["Panel-01"], "containers", exact_names=["Panel-01", "Ground"]), "incomplete_coverage")
        self.assertFalse(result.claims)

    def test_native_corresponding_boundaries_establish_neighbor_without_long_wall_guess(self):
        path = Path(self.directory.name) / "corresponding.ifc"
        _, _, relationships = spatial_source(path, corresponding=True)
        self.engine = IfcQueryEngine.open(path)
        result = self.execute(self.plan(["1B07"], "boundary_neighbors"))
        self.assertEqual(len(result.claims[0].value.rows), 1)
        row = result.claims[0].value.rows[0]
        self.assertEqual(row["related"].entity_ids, [self.entity("1B08")])
        self.assertEqual(row["basis"].value.text, "Native corresponding space boundaries")
        self.assertTrue({relationships[key].id() for key in ["wall_a", "wall_b"]}
                        <= self.anchor_steps(result.claims[0].evidence[0].anchor_ids))

    def test_door_and_its_filled_opening_resolve_to_one_shared_doorway_in_both_directions(self):
        path = Path(self.directory.name) / "mixed-doorway.ifc"
        source, objects, relationships = spatial_source(path)
        opening = source.create_entity("IfcOpeningElement", GlobalId=ifcopenshell.guid.new(), Name="Door-019 opening")
        fill = source.create_entity("IfcRelFillsElement", GlobalId=ifcopenshell.guid.new(),
                                    RelatingOpeningElement=opening, RelatedBuildingElement=objects["direct_door"])
        relationships["direct_b"].RelatedBuildingElement = opening
        relationships["element_floor"].RelatedElements += (opening,)
        source.write(str(path))
        self.engine = IfcQueryEngine.open(path)
        for origin, related in [("1B07", "1B08"), ("1B08", "1B07")]:
            with self.subTest(origin=origin):
                result = self.execute(self.plan([origin], "door_connections"))
                matching = [row for row in result.claims[0].value.rows if row["related"].entity_ids == [self.entity(related)]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(set(matching[0]["via"].entity_ids), {self.entity("Tür-019"), self.entity("Door-019 opening")})
                self.assertTrue({relationships[key].id() for key in ["direct_a", "direct_b"]} | {fill.id()}
                                <= self.anchor_steps(result.claims[0].evidence[0].anchor_ids))

    def test_corresponding_boundary_is_usable_when_the_pointer_only_arrives_at_the_room(self):
        path = Path(self.directory.name) / "incoming-corresponding.ifc"
        source, _, relationships = spatial_source(path, corresponding=True)
        relationships["wall_a"].CorrespondingBoundary = None
        source.write(str(path))
        self.engine = IfcQueryEngine.open(path)
        origin, related = self.entity("1B07"), self.entity("1B08")
        self.assertNotIn(related, self.engine.graphs["corresponding_boundary", "outgoing"][origin])
        self.assertIn(related, self.engine.graphs["corresponding_boundary", "incoming"][origin])
        result = self.execute(self.plan(["1B07"], "boundary_neighbors"))
        rows = result.claims[0].value.rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["related"].entity_ids, [related])
        self.assertEqual(rows[0]["basis"].value.text, "Native corresponding space boundaries")
        self.assertTrue({relationships[key].id() for key in ["wall_a", "wall_b"]}
                        <= self.anchor_steps(result.claims[0].evidence[0].anchor_ids))

    def test_paired_virtual_boundaries_cannot_establish_missing_doors_or_outdoor_access(self):
        path = Path(self.directory.name) / "virtual-pair.ifc"
        source, objects, relationships = spatial_source(path, corresponding=True)
        relationships["wall_a"].PhysicalOrVirtualBoundary = "VIRTUAL"
        relationships["wall_b"].PhysicalOrVirtualBoundary = "VIRTUAL"
        for boundary in list(source.by_type("IfcRelSpaceBoundary")):
            if boundary.RelatingSpace == objects["a"] and boundary != relationships["wall_a"]:
                source.remove(boundary)
        source.write(str(path))
        self.engine = IfcQueryEngine.open(path)
        origin = self.entity("1B07")
        self.assertFalse(self.engine.graphs["bounded_by", "outgoing"][origin])
        self.assertTrue(self.engine.graphs["corresponding_boundary", "outgoing"][origin])
        for relation in ("door_connections", "outdoor_access"):
            with self.subTest(relation=relation):
                result = self.execute(self.plan(["1B07"], relation), "missing_information")
                self.assertFalse(result.claims)
                self.assertIn("Missing topology cannot establish zero", result.issues[0].message.text)

    def test_empty_recorded_door_connections_keep_inspected_boundary_evidence(self):
        path = Path(self.directory.name) / "wall-without-door.ifc"
        source, objects, relationships = spatial_source(path)
        for boundary in list(source.by_type("IfcRelSpaceBoundary")):
            if boundary.RelatingSpace == objects["a"] and boundary != relationships["wall_a"]:
                source.remove(boundary)
        source.write(str(path))
        self.engine = IfcQueryEngine.open(path)
        result = self.execute(self.plan(["1B07"], "door_connections"))
        self.assertEqual(result.claims[0].value.rows, [])
        self.assertTrue({relationships["wall_a"].id(), objects["wall"].id()}
                        <= self.anchor_steps(result.claims[0].evidence[0].anchor_ids))
        self.assertIn("Shared walls alone do not establish a connection", result.explanation.text)


    def test_mixed_known_and_missing_rooms_retain_proven_relationships(self):
        result = self.execute(self.plan(["1B07", "7.16"], "door_connections"), "partial")
        self.assertEqual(len(result.claims[0].value.rows), 1)
        self.assertEqual(result.claims[0].value.rows[0]["related"].entity_ids, [self.entity("1B08")])
        self.assertTrue(any(self.entity("7.16") in issue.entity_ids for issue in result.issues))
        coverage = next(item for item in self.engine.bundle.coverage if item.id in result.claims[0].coverage_ids)
        self.assertEqual(coverage.completeness, "partial")
        self.assertEqual(coverage.unresolved_entity_ids, [self.entity("7.16")])
        evaluations = [item for calculation in result.calculations for item in calculation.spatial_evidence]
        missing = next(item for item in evaluations if item.subject_id == self.entity("7.16"))
        self.assertEqual(missing.status, "unavailable")

    def test_partial_outdoor_access_cannot_be_promoted_to_an_exact_total(self):
        result = self.execute(self.plan(["1B07", "7.16"], "outdoor_access"), "partial")
        self.assertEqual(result.claims[0].value.entity_ids, [self.entity("1B07")])
        count = self.execute(self.plan(["1B07", "7.16"], "outdoor_access", count=True), "incomplete_coverage")
        self.assertFalse(count.claims)

    def test_candidate_evidence_and_relation_specific_coverage_survive_execution(self):
        neighbors = self.execute(self.plan(["1B07"], "boundary_neighbors"), "partial")
        self.assertEqual(neighbors.claims[0].quality, "estimated")
        row_index = next(index for index, value in enumerate(neighbors.claims[0].value.rows)
                         if value["related"].entity_ids == [self.entity("121.A")])
        binding = next(value for value in neighbors.claims[0].evidence if value.value_path == f"/rows/{row_index}/related")
        self.assertEqual(binding.evidence_kind, "candidate")
        connections = self.execute(self.plan(["1B07"], "door_connections"))
        self.assertNotEqual(neighbors.claims[0].coverage_ids, connections.claims[0].coverage_ids)

    def test_boundary_geometry_rejects_separated_long_wall_candidates(self):
        path = Path(self.directory.name) / "patches.ifc"
        source, objects, relationships = spatial_source(path)
        # A valid native surface connection record is enough for the executor
        # fixture; geometry mathematics is independently tested by its provider.
        point = source.create_entity("IfcCartesianPoint", Coordinates=(0., 0., 0.))
        placement = source.create_entity("IfcAxis2Placement3D", Location=point)
        surface = source.create_entity("IfcPlane", Position=placement)
        for key in ("wall_a", "wall_b", "wall_c"):
            relationships[key].ConnectionGeometry = source.create_entity("IfcConnectionSurfaceGeometry", SurfaceOnRelatingElement=surface)
        source.write(str(path))
        self.engine = IfcQueryEngine.open(path)
        calls = []

        class Geometry:
            def compare_boundaries(_, first, second, tolerance, *, timeout_seconds=None):
                calls.append((first, second))
                return {"status": "no_match", "method": "boundary_patch_overlap.v1", "unit": "m",
                        "frame": "ifc_world", "tolerance_m": tolerance,
                        "source_step_ids": [first, second], "reason": "Disjoint projected boundary patches"}

        self.engine.geometry = Geometry()
        result = self.execute(self.plan(["1B07"], "boundary_neighbors"))
        self.assertEqual({value["related"].entity_ids[0] for value in result.claims[0].value.rows}, {self.entity("1B08")})
        self.assertIn((relationships["wall_a"].id(), relationships["wall_c"].id()), calls)
        self.assertTrue({relationships["wall_a"].id(), relationships["wall_c"].id()}
                        <= self.anchor_steps(result.claims[0].evidence[0].anchor_ids))

    def test_native_and_geometric_disagreement_is_a_conflict(self):
        path = Path(self.directory.name) / "conflicting-patches.ifc"
        source, _, relationships = spatial_source(path, corresponding=True)
        point = source.create_entity("IfcCartesianPoint", Coordinates=(0., 0., 0.))
        placement = source.create_entity("IfcAxis2Placement3D", Location=point)
        surface = source.create_entity("IfcPlane", Position=placement)
        for key in ("wall_a", "wall_b"):
            relationships[key].ConnectionGeometry = source.create_entity("IfcConnectionSurfaceGeometry", SurfaceOnRelatingElement=surface)
        source.write(str(path))
        self.engine = IfcQueryEngine.open(path)

        class Geometry:
            def compare_boundaries(_, first, second, tolerance, *, timeout_seconds=None):
                return {"status": "no_match", "method": "boundary_patch_overlap.v1", "unit": "m",
                        "frame": "ifc_world", "tolerance_m": tolerance, "source_step_ids": [first, second]}

        self.engine.geometry = Geometry()
        result = self.execute(self.plan(["1B07"], "boundary_neighbors"), "conflicting_evidence")
        self.assertFalse(result.claims)

    def test_explicit_geometry_never_guesses_doors_from_proximity(self):
        result = self.execute(self.plan(["1B07"], "door_connections", method="geometry"), "unsupported_operation")
        self.assertFalse(result.claims)


    def test_geometry_containment_resolves_missing_native_room_with_inspectable_inputs(self):
        target = self.objects["b"].id()
        calls = []

        class Geometry:
            def locate_in_spaces(_, object_step, space_steps, tolerance, *, timeout_seconds=None):
                calls.append((object_step, space_steps, timeout_seconds))
                return {"status": "match", "method": "convex_room_containment.v1", "unit": "m",
                        "frame": "ifc_world", "tolerance_m": tolerance,
                        "source_step_ids": [object_step, *space_steps], "matched_step_ids": [target],
                        "unresolved_step_ids": []}

        self.engine.geometry = Geometry()
        result = self.execute(self.plan(["Tür-019"], "containers", container_kind="space"))
        self.assertEqual(result.claims[0].value.rows[0]["related"].entity_ids, [self.entity("1B08")])
        self.assertEqual(result.claims[0].value.rows[0]["basis"].value.text, "Geometry-verified space containment")
        self.assertEqual(calls[0][0], self.objects["direct_door"].id())
        self.assertTrue(0 < calls[0][2] <= 20)
        evaluation = next(item for node in result.calculations for item in node.spatial_evidence)
        self.assertEqual(evaluation.method, "convex_room_containment.v1")
        self.assertEqual(evaluation.metadata["source_step_ids"], [calls[0][0], *calls[0][1]])
        self.assertTrue(set(calls[0][1]) <= self.anchor_steps(evaluation.anchor_ids))

    def test_explicit_geometry_containment_cannot_override_conflicting_native_room(self):
        target = self.objects["b"].id()

        class Geometry:
            def locate_in_spaces(_, object_step, space_steps, tolerance, *, timeout_seconds=None):
                return {"status": "match", "method": "convex_room_containment.v1", "unit": "m",
                        "frame": "ifc_world", "tolerance_m": tolerance,
                        "source_step_ids": [object_step, *space_steps], "matched_step_ids": [target],
                        "unresolved_step_ids": []}

        self.engine.geometry = Geometry()
        result = self.execute(self.plan(["Panel-01"], "containers", container_kind="space", method="geometry"), "conflicting_evidence")
        self.assertFalse(result.claims)

    def test_geometry_containment_does_not_use_hidden_spaces_as_inputs(self):
        class Geometry:
            def locate_in_spaces(*args, **kwargs):
                raise AssertionError("Geometry must not inspect hidden source rooms")

        self.engine.geometry = Geometry()
        result = self.execute(self.plan(["Tür-019"], "containers", container_kind="space",
            exact_names=["Tür-019", "Ground", "Building A", "Site"]), "incomplete_coverage")
        self.assertFalse(result.claims)


    def test_undefined_boundary_flags_do_not_establish_complete_door_inventory(self):
        path = Path(self.directory.name) / "undefined-boundary.ifc"
        source, objects, _ = spatial_source(path)
        unknown = source.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(),
            RelatingSpace=objects["a"], RelatedBuildingElement=objects["virtual_door"],
            PhysicalOrVirtualBoundary="NOTDEFINED", InternalOrExternalBoundary="NOTDEFINED")
        source.write(str(path))
        self.engine = IfcQueryEngine.open(path)
        result = self.execute(self.plan(["1B07"], "door_connections"), "partial")
        self.assertEqual(len(result.claims[0].value.rows), 1)
        coverage = next(item for item in self.engine.bundle.coverage if item.id in result.claims[0].coverage_ids)
        self.assertEqual(coverage.completeness, "partial")
        self.assertEqual(coverage.unresolved_entity_ids, [self.entity("1B07")])
        self.assertIn(unknown.id(), self.anchor_steps(result.claims[0].evidence[0].anchor_ids))


    def test_undefined_external_classification_is_unknown_outdoor_access(self):
        path = Path(self.directory.name) / "undefined-outside.ifc"
        source, objects, _ = spatial_source(path)
        source.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(),
            RelatingSpace=objects["c"], RelatedBuildingElement=objects["virtual_door"],
            PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="NOTDEFINED")
        source.write(str(path))
        self.engine = IfcQueryEngine.open(path)
        result = self.execute(self.plan(["121.A"], "outdoor_access"), "partial")
        self.assertEqual(result.claims[0].value.entity_ids, [])
        count = self.execute(self.plan(["121.A"], "outdoor_access", count=True), "incomplete_coverage")
        self.assertFalse(count.claims)


if __name__ == "__main__":
    unittest.main()

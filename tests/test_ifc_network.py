"""Native network counts stay distinct from physical flow or inferred topology."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

import ifcopenshell
import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_plan, validate_result
from ifc_engine.catalog import POLICIES, attribute_key
from ifc_engine.engine import IfcQueryEngine


def network_source(path, *, schema="IFC4", ports=True):
    model = ifcopenshell.file(schema=schema)

    def root(kind, **values):
        return model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **values)

    root("IfcProject", Name="Recorded network fixture", UnitsInContext=model.createIfcUnitAssignment([
        model.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE")]))
    components = [root("IfcFlowSegment", Name=f"Pipe-{i}") for i in range(4)]
    objects = []
    if ports:
        objects = [root("IfcDistributionPort", Name=f"Port-{i}", FlowDirection="SOURCEANDSINK") for i in range(6)]
        for port, owner in zip(objects, [components[0], components[0], components[1], components[1], components[2], components[2]]):
            if schema == "IFC4":
                root("IfcRelNests", RelatingObject=owner, RelatedObjects=[port])
            else:
                root("IfcRelConnectsPortToElement", RelatingPort=port, RelatedElement=owner)
        for a, b in [(objects[0], objects[2]), (objects[1], objects[3]), (objects[4], objects[5])]:
            root("IfcRelConnectsPorts", RelatingPort=a, RelatedPort=b)
        # Native reverse duplicates do not create another edge or another port.
        root("IfcRelConnectsPorts", RelatingPort=objects[2], RelatedPort=objects[0])
    model.write(str(path))
    return model, components, objects, root


class IfcNetworkTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "network.ifc"
        self.model, self.components, self.ports, self.root = network_source(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def engine(self):
        self.model.write(str(self.path))
        return IfcQueryEngine.open(self.path)

    def plan(self, engine, *, port_names=None, component_names=None, exact=None):
        scope = engine.scope()
        if exact is not None:
            scope.exact_entity_ids = [engine.resolve_entity(name) for name in exact]

        def select(name, concepts, names):
            where = None
            if names is not None:
                where = m.BooleanPredicate(kind="any", operands=[
                    m.ComparePredicate(kind="compare", field=m.FieldRef(kind="entity_id", key="entity_id"),
                        operator="eq", value=m.ReferencesValue(kind="references", entity_ids=[engine.resolve_entity(label)]))
                    for label in names])
            return m.PlanStep(id=name, operation=m.SelectOperation(kind="select", concept_ids=concepts,
                count_policy=POLICIES["all_matches"], where=where))

        steps = [select("ports", ["ifc:IfcDistributionPort"], port_names)]
        if component_names is not None:
            steps.append(select("components", ["ifc:IfcFlowSegment"], component_names))
        steps.append(m.PlanStep(id="network", operation=m.NetworkQueryOperation(kind="network_query", input_step_id="ports",
            component_step_id="components" if component_names is not None else None)))
        return m.QueryPlan(id="plan:network", request_id="request:network", scope=scope, steps=steps, outputs={"answer": "network"})

    def execute(self, engine, plan, status="answered"):
        validate_plan(plan, engine.bundle, engine.capabilities)
        result = engine.execute(plan)
        self.assertEqual(result.status, status, result.model_dump_json(indent=2))
        validate_result(result, engine.bundle, plan)
        return result

    def test_native_ports_owner_links_and_direction_are_extracted_across_schemas(self):
        for schema in ["IFC2X3", "IFC4"]:
            with self.subTest(schema=schema):
                self.model, self.components, self.ports, self.root = network_source(self.path, schema=schema)
                engine = self.engine()
                port, owner = engine.resolve_entity("Port-0"), engine.resolve_entity("Pipe-0")
                self.assertEqual(engine.graphs["has_port", "incoming"][port], {owner})
                self.assertTrue(engine.edge_anchors["has_port", "incoming", port, owner])
                self.assertEqual(engine.facts[port, attribute_key("FlowDirection")][0].value.value.text, "SOURCEANDSINK")
                self.assertTrue(engine.graphs["port_connected_to", "outgoing"][port])

    def test_reversed_native_edges_deduplicate_and_owner_graph_is_separate(self):
        engine = self.engine()
        result = self.execute(engine, self.plan(engine, component_names=[f"Pipe-{i}" for i in range(4)]))
        values = result.claims[0].value.fields
        expected = {"total_ports": 6, "connected_ports": 6, "isolated_ports": 0, "unique_connections": 3,
            "port_components": 3, "largest_component_ports": 2, "total_components": 4,
            "components_with_ports": 3, "components_with_connected_ports": 3,
            "component_network_components": 3, "largest_component_network": 2}
        self.assertEqual({key: values[key].value for key in expected}, expected)
        self.assertEqual(Decimal(values["connectivity_rate"].magnitude), Decimal(100))
        self.assertEqual(Decimal(values["ports_per_component"].magnitude), Decimal("1.5"))
        self.assertEqual(Decimal(values["component_integration_rate"].magnitude), Decimal(75))
        evidence = next(node for node in result.calculations if node.plan_step_id == "network").network_evidence[0]
        self.assertEqual(evidence.unique_connection_count, 3)
        self.assertEqual(evidence.component_network_count, 3)
        self.assertEqual(len(evidence.connection_graph_sha256), 64)

    def test_isolated_ports_count_once_and_default_components_are_recorded_owners(self):
        for relationship in list(self.model.by_type("IfcRelConnectsPorts")):
            if relationship.RelatingPort == self.ports[4] or relationship.RelatedPort == self.ports[4]:
                self.model.remove(relationship)
        engine = self.engine()
        result = self.execute(engine, self.plan(engine))
        values = result.claims[0].value.fields
        self.assertEqual(values["connected_ports"].value, 4)
        self.assertEqual(values["isolated_ports"].value, 2)
        self.assertEqual(values["total_components"].value, 3)
        self.assertEqual(values["ports_per_component"].magnitude, "2")
        self.assertAlmostEqual(float(values["connectivity_rate"].magnitude), 100 * 4 / 6)

    def test_empty_recorded_inventory_has_zero_counts_and_undefined_ratio(self):
        self.model, self.components, self.ports, self.root = network_source(self.path, ports=False)
        engine = self.engine()
        result = self.execute(engine, self.plan(engine), "partial")
        values = result.claims[0].value.fields
        self.assertEqual(values["total_ports"].value, 0)
        self.assertEqual(values["unique_connections"].value, 0)
        self.assertEqual(values["port_components"].value, 0)
        self.assertIsInstance(values["connectivity_rate"], m.UnavailableValue)
        self.assertIsInstance(values["ports_per_component"], m.UnavailableValue)
        self.assertIn("undefined", values["connectivity_rate"].explanation)

    def test_selected_port_filter_produces_explicit_induced_graph_cut_count(self):
        engine = self.engine()
        result = self.execute(engine, self.plan(engine, port_names=["Port-0", "Port-1"]))
        values = result.claims[0].value.fields
        self.assertEqual(values["total_ports"].value, 2)
        self.assertEqual(values["connected_ports"].value, 0)
        self.assertEqual(values["cut_connections"].value, 2)
        self.assertIn("Cut connections", result.explanation.text)

    def test_outside_view_peer_is_incomplete_instead_of_disconnected(self):
        engine = self.engine()
        plan = self.plan(engine, port_names=["Port-0"], exact=["Port-0", "Pipe-0"])
        self.execute(engine, plan, "incomplete_coverage")

    def test_outside_view_owner_is_incomplete_instead_of_ignored(self):
        engine = self.engine()
        plan = self.plan(engine, port_names=["Port-0", "Port-2"], exact=["Port-0", "Port-2"])
        self.execute(engine, plan, "incomplete_coverage")

    def test_conflicting_owners_and_self_connected_ports_are_nonanswers(self):
        self.root("IfcRelNests", RelatingObject=self.components[1], RelatedObjects=[self.ports[0]])
        engine = self.engine()
        self.execute(engine, self.plan(engine), "conflicting_evidence")
        self.model, self.components, self.ports, self.root = network_source(self.path)
        self.root("IfcRelConnectsPorts", RelatingPort=self.ports[0], RelatedPort=self.ports[0])
        engine = self.engine()
        self.execute(engine, self.plan(engine), "conflicting_evidence")

    def test_ownerless_recorded_ports_preserve_connectivity_and_expose_missing_owner(self):
        for relationship in list(self.model.by_type("IfcRelNests")):
            if self.ports[0] in relationship.RelatedObjects:
                self.model.remove(relationship)
        engine = self.engine()
        result = self.execute(engine, self.plan(engine))
        self.assertEqual(result.claims[0].value.fields["ownerless_ports"].value, 1)
        self.assertEqual(result.claims[0].value.fields["connected_ports"].value, 6)


if __name__ == "__main__":
    unittest.main()

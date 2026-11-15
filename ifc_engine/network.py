"""Exact, bounded statistics of recorded native distribution-port graphs.

An IFC connection is source topology, not proof of real flow, commissioning,
capacity or a complete physical network. Owner-component and port-edge graphs
are reported separately; internal flow through a component is never invented.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
import hashlib
import json

from contracts import models as m
from .units import decimal_string

MAX_PORTS = 100000
MAX_CONNECTIONS = 200000


def _components(vertices, edges):
    parent = {vertex: vertex for vertex in vertices}
    sizes = {vertex: 1 for vertex in vertices}

    def root(vertex):
        while parent[vertex] != vertex:
            parent[vertex] = parent[parent[vertex]]
            vertex = parent[vertex]
        return vertex

    for a, b in edges:
        a, b = root(a), root(b)
        if a != b:
            if sizes[a] < sizes[b]:
                a, b = b, a
            parent[b] = a
            sizes[a] += sizes.pop(b)
    return len(sizes), max(sizes.values(), default=0)


def execute_network(engine, state, operation, scope_members, component_state=None):
    from .engine import QueryError

    if state.shape != "entities" or component_state is not None and component_state.shape != "entities":
        raise QueryError("unsupported_operation", "Network analysis requires selected native port and component sets.")
    inputs = [state, *([component_state] if component_state is not None else [])]
    if any(value.unresolved or value.candidate_members or not value.coverage_complete for value in inputs):
        raise QueryError("incomplete_coverage", "Candidate or unresolved selections cannot establish exact network connectivity.")
    ports = set(state.members)
    if len(ports) > MAX_PORTS:
        raise QueryError("unsupported_operation", "The selected network exceeds the bounded 100000-port work budget.")
    if any("ifc:IfcDistributionPort" not in engine.entities[identifier].concept_ids for identifier in ports):
        raise QueryError("needs_clarification", "Network analysis must start from native IfcDistributionPort occurrences.", ports)
    if not ports <= scope_members:
        raise QueryError("incomplete_coverage", "The selected ports must belong to the captured source/view scope.", ports)

    proof = set(state.anchors)
    owners, edges, cut_edges = {}, set(), set()
    for port in sorted(ports):
        native_owners = set(engine.graphs["has_port", "incoming"].get(port, ()))
        if not native_owners <= scope_members:
            raise QueryError("incomplete_coverage", "The recorded port owner is outside the captured view. Show the owner or choose Entire IFC model.", [port, *sorted(native_owners)])
        if len(native_owners) > 1:
            raise QueryError("conflicting_evidence", "The source assigns one distribution port to multiple distinct component owners.", [port, *sorted(native_owners)])
        owners[port] = next(iter(native_owners), None)
        for owner in native_owners:
            proof.update(engine.edge_anchors["has_port", "incoming", port, owner])
            proof.update(engine.entity_anchors[owner])
        for direction in ("outgoing", "incoming"):
            peers = set(engine.graphs["port_connected_to", direction].get(port, ()))
            if not peers <= scope_members:
                raise QueryError("incomplete_coverage", "A recorded network connection needs a port outside the captured view. Show both endpoints or choose Entire IFC model.", [port, *sorted(peers - scope_members)])
            for peer in peers:
                if "ifc:IfcDistributionPort" not in engine.entities[peer].concept_ids:
                    raise QueryError("conflicting_evidence", "A native port connection does not terminate at a distribution port.", [port, peer])
                if peer == port:
                    raise QueryError("conflicting_evidence", "A native distribution port is connected to itself.", [port])
                pair = tuple(sorted((port, peer)))
                if peer in ports:
                    edges.add(pair)
                    proof.update(engine.edge_anchors["port_connected_to", direction, port, peer])
                else:
                    cut_edges.add(pair)
                    proof.update(engine.edge_anchors["port_connected_to", direction, port, peer])
                    proof.update(engine.entity_anchors[peer])
                if len(edges) + len(cut_edges) > MAX_CONNECTIONS:
                    raise QueryError("unsupported_operation", "The selected network exceeds the bounded 200000-connection work budget.")
    connected = {identifier for edge in edges for identifier in edge}
    isolated = ports - connected
    owner_components = {owner for owner in owners.values() if owner is not None}
    components = set(component_state.members) if component_state is not None else owner_components
    if not components <= scope_members:
        raise QueryError("incomplete_coverage", "The selected component inventory includes objects outside the captured source/view scope.", components)
    if any(engine.entities[identifier].kind in {"type", "material", "system", "zone"}
           or "ifc:IfcDistributionPort" in engine.entities[identifier].concept_ids for identifier in components):
        raise QueryError("needs_clarification", "The component inventory must contain physical occurrences, separately from ports, types, systems and materials.", components)
    if len(components) > MAX_PORTS:
        raise QueryError("unsupported_operation", "The component inventory exceeds the bounded 100000-object work budget.")
    if component_state is not None:
        state.facts.update(component_state.facts)
        proof.update(component_state.anchors)
        state.concepts.update(component_state.concepts)
        state.properties.update(component_state.properties)
        state.operation_keys.extend(component_state.operation_keys)
    with_ports = owner_components & components
    with_connections = {owners[port] for port in connected if owners[port] in components}
    owned_ports = {port for port, owner in owners.items() if owner in components}
    ownerless = {port for port, owner in owners.items() if owner is None}
    component_edges = {tuple(sorted((owners[a], owners[b]))) for a, b in edges
        if owners[a] in components and owners[b] in components and owners[a] != owners[b]}
    port_component_count, largest_port_component = _components(ports, edges)
    component_network_count, largest_component_network = _components(components, component_edges)

    def count(value):
        return m.CountValue(kind="count", value=value)

    def ratio(numerator, denominator, *, percent=False, basis):
        if denominator == 0:
            return m.UnavailableValue(kind="unavailable", reason="unknown",
                explanation="The recorded denominator is zero; this ratio is undefined rather than zero percent.")
        with localcontext() as context:
            context.prec = 80
            number = Decimal(numerator) * (100 if percent else 1) / Decimal(denominator)
        return m.QuantityValue(kind="quantity", magnitude=decimal_string(number),
            unit_id="unit:%" if percent else "unit:1", quantity_kind="ratio", basis=basis,
            unit_resolution="derived")

    fields = {
        "total_ports": count(len(ports)), "connected_ports": count(len(connected)),
        "isolated_ports": count(len(isolated)), "unique_connections": count(len(edges)),
        "cut_connections": count(len(cut_edges)), "port_components": count(port_component_count),
        "largest_component_ports": count(largest_port_component), "total_components": count(len(components)),
        "components_with_ports": count(len(with_ports)),
        "components_with_connected_ports": count(len(with_connections)),
        "ownerless_ports": count(len(ownerless)), "ports_owned_by_selected_components": count(len(owned_ports)),
        "component_network_components": count(component_network_count),
        "largest_component_network": count(largest_component_network),
        "connectivity_rate": ratio(len(connected), len(ports), percent=True,
            basis="selected ports with at least one recorded edge to another selected port / selected ports"),
        "ports_per_component": ratio(len(owned_ports), len(components),
            basis="selected ports owned by a selected component / selected physical components"),
        "component_integration_rate": ratio(len(with_connections), len(components), percent=True,
            basis="selected components owning at least one connected selected port / selected physical components"),
    }
    state.value, state.shape, state.cells = m.RecordValue(kind="record", fields=fields), "scalar", []
    if any(isinstance(value, m.UnavailableValue) for value in fields.values()):
        state.issues.append(m.Issue(code="missing_information", message=m.LocalizedText(text=
            "Recorded zero counts are valid; connectivity or component ratios with a zero denominator remain undefined.")))
    state.members = ports | components | owner_components | {identifier for edge in cut_edges for identifier in edge}
    state.anchors.update(proof)
    state.quality = "exact"
    state.network_records.append({
        "method": "native_distribution_port_graph.v1",
        "counting_basis": "Distinct selected native port occurrences, deduplicated undirected recorded port edges, and a separate owner-component graph.",
        "selected_port_count": len(ports), "selected_component_count": len(components),
        "connected_port_count": len(connected), "isolated_port_count": len(isolated),
        "unique_connection_count": len(edges), "cut_edge_count": len(cut_edges),
        "port_component_count": port_component_count, "largest_component_port_count": largest_port_component,
        "components_with_ports_count": len(with_ports), "components_with_connected_ports_count": len(with_connections),
        "component_network_count": component_network_count, "largest_component_network_count": largest_component_network,
        "connection_graph_sha256": hashlib.sha256(json.dumps({"ports": sorted(ports), "edges": sorted(edges),
            "cut_edges": sorted(cut_edges), "owners": sorted(owners.items()),
            "selected_components": sorted(components)}, separators=(",", ":")).encode()).hexdigest(),
    })
    state.notes.append("Connectivity describes only recorded native distribution-port relationships in the selected set. A port is connected when a recorded undirected edge reaches another selected port; duplicate or reverse records count once. Cut connections reach an in-scope port excluded by the selected network filter and do not contribute to the induced graph's connectivity rate. Missing physical connections, operational flow, capacity and commissioning cannot be inferred from this inventory.")
    state.notes.append("Port components use only recorded port-to-port edges. The separate component network has selected owner occurrences as vertices and an edge when a recorded port pair connects two distinct selected owners; it does not assume internal flow through every port of an owner. The physical component denominator is the separately selected component set when supplied, otherwise the distinct recorded owners of the selected ports. Average ports per component counts only selected ports owned by those components. A zero denominator leaves ratios undefined.")

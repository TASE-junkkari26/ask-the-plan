"""Bounded, source-backed material volumes with explicit allocation methods.

A homogeneous native assignment may qualify a recorded same-occurrence net
volume. Layer fractions require an independently verified uniform source prism;
neither host bounding boxes nor nominal thicknesses alone establish volumes.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
import json
import math
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.unit as unit_util

from contracts import models as m
from .catalog import property_key
from .ingest import _id, file_sha256
from .type_candidates import assignment_materials
from .units import convert, decimal_string, source_unit

MAX_HOSTS = 10000
MAX_LAYERS = 256
MAX_OUTPUT_ROWS = 20000
MAX_GEOMETRY_HOSTS = 2000


def _anchor(engine, record, path=()):
    asset = engine.bundle.assets[0].id
    native = str(record.id()) if record.id() else record.is_a().upper()
    identifier = _id("anchor", asset + native + json.dumps(path))
    if identifier not in engine.anchors:
        anchor = m.EvidenceAnchor(id=identifier, asset_id=asset, selector=m.NativeSelector(
            kind="step_id" if record.id() else "file_metadata", value=native, property_path=list(path)))
        engine.anchors[identifier] = anchor
        engine.bundle.anchors.append(anchor)
    return identifier


def _native_step(engine, identifier):
    values = {int(engine.anchors[anchor].selector.value) for anchor in engine.entity_anchors[identifier]
              if engine.anchors[anchor].selector.kind == "step_id" and not engine.anchors[anchor].selector.property_path}
    return next(iter(values)) if len(values) == 1 else None


def _native_model(engine):
    from .engine import QueryError
    provider = getattr(engine, "geometry", None)
    path = getattr(provider, "path", None)
    hydrator = getattr(engine, "hydrator", None)
    path = path or getattr(getattr(hydrator, "extractor", None), "path", None)
    if path is None or not Path(path).is_file():
        raise QueryError("missing_source", "Material quantities require the retained original IFC source.")
    if file_sha256(Path(path)) != engine.bundle.assets[0].sha256:
        raise QueryError("conflicting_evidence", "The retained IFC source differs from the requested revision.")
    model = getattr(getattr(hydrator, "extractor", None), "model", None)
    return model if model is not None else ifcopenshell.open(str(path))


def _typing(obj):
    records = getattr(obj, "IsTypedBy", ()) or ()
    return records or [relation for relation in (getattr(obj, "IsDefinedBy", ()) or ()) if relation.is_a("IfcRelDefinesByType")]


def _assignment(engine, model, obj):
    """One effective, unambiguous assignment and its complete native proof."""
    proof = {_anchor(engine, obj)}
    own = [relation for relation in (getattr(obj, "HasAssociations", ()) or ()) if relation.is_a("IfcRelAssociatesMaterial")]
    relations = own
    if not own:
        types = {relation.RelatingType.id(): relation.RelatingType for relation in _typing(obj)}
        groups = [[relation for relation in (getattr(native_type, "HasAssociations", ()) or ())
                   if relation.is_a("IfcRelAssociatesMaterial")] for native_type in types.values()]
        signatures = {tuple(sorted({relation.RelatingMaterial.id() for relation in group})) for group in groups}
        proof.update(_anchor(engine, relation, ["RelatingType"]) for relation in _typing(obj))
        proof.update(_anchor(engine, native_type, ["HasAssociations"]) for native_type in types.values())
        if len(signatures) > 1:
            return {"complete": False, "reason": "Conflicting native type assignments do not establish one material composition.", "anchors": proof}
        relations = [relation for group in groups for relation in group]
    proof.update(_anchor(engine, relation, ["RelatingMaterial"]) for relation in relations)
    assignments = {relation.RelatingMaterial.id(): relation.RelatingMaterial for relation in relations}
    if len(assignments) != 1:
        return {"complete": False, "reason": "A single complete native material assignment is unavailable.", "anchors": proof}
    assignment = next(iter(assignments.values()))
    proof.add(_anchor(engine, assignment))
    leaves = assignment_materials(assignment)
    material_records = {material.id(): material for material in leaves}
    proof.update(_anchor(engine, material, ["Name"]) for material in material_records.values())
    info = {"anchors": proof, "assignment_ids": sorted({*assignments, *[relation.id() for relation in relations]}),
            "materials": material_records, "layers": [], "usage_id": None, "complete": False}
    layer_set = assignment.ForLayerSet if assignment.is_a() == "IfcMaterialLayerSetUsage" else assignment
    if layer_set.is_a() == "IfcMaterialLayerSet":
        native_layers = list(layer_set.MaterialLayers or ())
        if not native_layers or len(native_layers) > MAX_LAYERS:
            return {**info, "reason": "The native layer list is empty or exceeds the bounded 256-layer limit."}
        info["usage_id"] = assignment.id() if assignment.is_a() == "IfcMaterialLayerSetUsage" else None
        proof.add(_anchor(engine, layer_set, ["MaterialLayers"]))
        native_unit = unit_util.get_project_unit(model, "LENGTHUNIT")
        parsed = None
        if native_unit is not None:
            proof.add(_anchor(engine, native_unit))
            try:
                parsed = source_unit(native_unit)
                if parsed.dimension != engine.units["unit:m"].dimension:
                    parsed = None
                elif parsed.id not in engine.units:
                    engine.units[parsed.id] = parsed
                    engine.bundle.units.append(parsed)
            except (ValueError, KeyError):
                pass
        for index, layer in enumerate(native_layers, 1):
            material = layer.Material
            proof.add(_anchor(engine, layer, ["LayerThickness"]))
            thickness = None
            if layer.LayerThickness is not None:
                thickness = m.QuantityValue(kind="quantity", magnitude=decimal_string(layer.LayerThickness),
                    unit_id=parsed.id if parsed else None, unit_resolution="project_default" if parsed else "unknown",
                    unit_anchor_ids=[_anchor(engine, native_unit)] if native_unit is not None else [],
                    quantity_kind="length", basis="specified", source_value_type="IfcNonNegativeLengthMeasure")
            info["layers"].append(m.MaterialLayerInput(index=index, layer_step_id=layer.id(),
                material_step_id=material.id() if material is not None else None,
                material_name=material.Name if material is not None else None, thickness=thickness))
        info["complete"] = all(layer.material_name is not None and layer.material_name.strip() and layer.material_step_id is not None for layer in info["layers"])
    elif assignment.is_a() == "IfcMaterial":
        info["complete"] = bool(assignment.Name is not None and assignment.Name.strip())
    elif assignment.is_a() == "IfcMaterialList":
        info["complete"] = bool(assignment.Materials) and len(leaves) == len(assignment.Materials) and all(material.Name is not None and material.Name.strip() for material in leaves)
    else:
        info["reason"] = "This native material composition has no supported complete volume allocation rule."
        return info
    if not info["complete"]:
        info["reason"] = "Some native material identities are missing; a complete matching-material inventory cannot be established."
    return info


def _recorded_net(engine, identifier, obj, state):
    """Only explicit same-occurrence base/Qto net volumes, never gross values."""
    native_ids, keys = set(), set()
    for relation in getattr(obj, "IsDefinedBy", ()) or ():
        if not relation.is_a("IfcRelDefinesByProperties"):
            continue
        raw = relation.RelatingPropertyDefinition
        for definition in raw if isinstance(raw, tuple) else [raw]:
            if definition is None or not (definition.Name == "BaseQuantities" or (definition.Name or "").startswith("Qto_")):
                continue
            records = getattr(definition, "Quantities", ()) or getattr(definition, "HasProperties", ()) or ()
            for record in records:
                if record is not None and record.Name in {"NetVolume", "Net Volume", "Netto-Volumen"}:
                    key = property_key(definition.Name, record.Name)
                    if key in engine.properties:
                        keys.add(key)
                        native_ids.add(str(record.id()))
    engine.ensure_fields([identifier], keys)
    values, facts, unresolved_record = [], [], False
    for key in keys:
        for fact in engine.facts.get((identifier, key), ()):
            if not any(engine.anchors[anchor].selector.value in native_ids for anchor in fact.provenance.anchor_ids):
                continue
            if fact.status != "present" or not isinstance(fact.value, m.QuantityValue):
                unresolved_record = True
                continue
            value = fact.value
            if value.quantity_kind != "volume" or value.basis != "net" or value.unit_id not in engine.units:
                unresolved_record = True
                continue
            try:
                number = convert(value.magnitude, engine.units[value.unit_id], engine.units["unit:m3"])
            except ValueError:
                unresolved_record = True
                continue
            if number < 0 or not math.isfinite(float(number)):
                unresolved_record = True
                continue
            values.append((number, value))
            facts.append(fact)
    if unresolved_record or not values or len({number for number, _ in values}) != 1:
        return None
    for fact in facts:
        state.properties.add(fact.property_key)
    return values[0][0], values[0][1], facts


def _mesh_verified(record):
    value = record.get("value")
    return (record.get("status") == "verified" and record.get("unit") == "m3" and record.get("frame") == "ifc_world"
            and record.get("metric") == "volume" and isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _prism_verified(record, info):
    if (record.get("status") != "verified" or record.get("method") != "uniform_layered_prism.v1"
            or record.get("unit") != "m3" or record.get("frame") != "ifc_world"):
        return False
    if record.get("usage_step_id") != info.get("usage_id"):
        return False
    for field in ("volume_m3", "axis_thickness_m", "specified_total_thickness_m"):
        value = record.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            return False
    expected = {(layer.layer_step_id, layer.material_step_id, layer.material_name) for layer in info.get("layers", [])}
    observed = {(layer.get("layer_step_id"), layer.get("material_step_id"), layer.get("name")) for layer in record.get("layers", [])}
    return bool(expected) and expected == observed and all(isinstance(layer.get("thickness_m"), (int, float))
        and not isinstance(layer["thickness_m"], bool) and math.isfinite(layer["thickness_m"]) and layer["thickness_m"] >= 0
        for layer in record.get("layers", []))


def execute_material_quantity(engine, state, operation, scope_members):
    from .engine import QueryError, _Support

    if state.shape != "entities" or state.unresolved or state.candidate_members or not state.coverage_complete:
        raise QueryError("incomplete_coverage", "Material quantities require a complete authorized occurrence selection.")
    hosts = sorted(state.members)
    if len(hosts) > MAX_HOSTS:
        raise QueryError("unsupported_operation", "Material quantities are bounded to 10000 source occurrences per question.")
    if not set(hosts) <= scope_members:
        raise QueryError("incomplete_coverage", "Material quantity subjects must belong to the captured scope.")
    model = _native_model(engine)
    requested = set(operation.material_names)
    descriptions, nets, mesh_hosts, layered_hosts = {}, {}, {}, {}
    for identifier in hosts:
        step = _native_step(engine, identifier)
        obj = model.by_id(step) if step is not None else None
        if obj is None or not obj.is_a("IfcElement"):
            raise QueryError("needs_clarification", "Select physical element occurrences for material quantities, separately from material/type/spatial records.", [identifier])
        info = _assignment(engine, model, obj)
        info["host_step"] = step
        descriptions[identifier] = info
        if not info.get("complete"):
            continue
        materials = info["materials"]
        selected = {record.Name for record in materials.values()} & requested if requested else {record.Name for record in materials.values()}
        info["selected"] = selected
        if not selected:
            continue
        homogeneous = len(materials) == 1
        info["homogeneous"] = homogeneous
        if homogeneous:
            recorded = _recorded_net(engine, identifier, obj, state)
            if recorded is not None:
                nets[identifier] = recorded
            if operation.method == "geometry" or operation.method == "auto" and recorded is None:
                mesh_hosts[identifier] = [step]
        elif operation.method != "recorded_net" and info.get("usage_id") is not None:
            layered_hosts[identifier] = step

    geometry = getattr(engine, "geometry", None)
    meshes, prisms, requested_meshes, requested_prisms = {}, {}, set(), set()
    if geometry is not None and mesh_hosts:
        subset = dict(list(mesh_hosts.items())[:MAX_GEOMETRY_HOSTS])
        requested_meshes = set(subset)
        batch = geometry.measure_many("volume", subset, basis="solid", tolerance_m=operation.tolerance_m,
                                      explicit_root_steps=[steps[0] for steps in subset.values()])
        meshes = {record["subject_id"]: record for record in batch.get("records", [])}
    if geometry is not None and layered_hosts and hasattr(geometry, "verify_layered_volumes"):
        remaining = max(0, MAX_GEOMETRY_HOSTS - len(mesh_hosts))
        subset = dict(list(layered_hosts.items())[:remaining])
        if subset:
            requested_prisms = set(subset)
            batch = geometry.verify_layered_volumes(subset, tolerance_m=operation.tolerance_m)
            prisms = {record["subject_id"]: record for record in batch.get("records", [])}

    rows, cells, unknown = [], [], set()
    state.material_records = []
    estimated = state.quality == "estimated"
    for identifier in hosts:
        info = descriptions[identifier]
        proof = set(info.get("anchors", engine.entity_anchors[identifier]))
        groups = {}
        for native_id, material in info.get("materials", {}).items():
            groups.setdefault(material.Name, []).append(native_id)
        selected = info.get("selected", set())
        # A complete negative assignment establishes zero for every requested
        # literal name. Do not mark a known negative identity unavailable: the
        # wire contract correctly reserves that marker for partial answers.
        names = sorted(selected) if info.get("complete") and selected else sorted(requested) if info.get("complete") else [None]
        for name in names:
            native_ids = sorted(groups.get(name, []))
            method, number, host_volume, chosen, total, raw, used_facts = "unavailable", None, None, None, None, None, []
            metadata = {"reason": info.get("reason", "A supported complete material-volume method is unavailable."),
                        "source_sha256": engine.bundle.assets[0].sha256, "requested_material_names": operation.material_names,
                        "native_materials": [{"step_id": native_id, "name": material.Name}
                                             for native_id, material in info.get("materials", {}).items()]}
            attempted = meshes.get(identifier) if info.get("homogeneous") else prisms.get(identifier)
            if attempted is not None and attempted.get("status") != "verified":
                metadata["unverified_geometry"] = attempted
                metadata["reason"] = "The modeled source geometry did not pass the required closed-solid or uniform-layer verification."
            elif ((identifier in mesh_hosts and identifier not in requested_meshes)
                  or (identifier in layered_hosts and identifier not in requested_prisms)):
                metadata["reason"] = "The bounded geometric host budget was exhausted before this source occurrence could be inspected; its material volume remains unknown."
                metadata["uninspected_work_budget"] = True
            elif ((identifier in requested_meshes and identifier not in meshes)
                  or (identifier in requested_prisms and identifier not in prisms)):
                metadata["reason"] = "The bounded native worker returned no per-occurrence geometric proof; this input remains unresolved, not absent."
            quality = "exact"
            if info.get("complete") and not selected:
                method, number = "recorded_not_used", Decimal(0)
                metadata["reason"] = "No requested literal material name occurs in the complete recorded native assignment; this is a modeled-source zero, not physical absence."
            elif info.get("complete") and info.get("homogeneous") and identifier in nets and operation.method != "geometry":
                number, raw, used_facts = nets[identifier]
                host_volume, method, quality = number, "recorded_net_homogeneous", raw.quality
                metadata["reason"] = "The explicit same-occurrence recorded net volume is assigned to its one complete native material; no mesh equivalence is asserted."
            elif info.get("complete") and info.get("homogeneous") and _mesh_verified(meshes.get(identifier, {})):
                record = meshes[identifier]
                number = host_volume = Decimal(str(record["value"]))
                method, quality = "closed_mesh_homogeneous", "estimated"
                metadata["geometry"] = record
            elif info.get("complete") and _prism_verified(prisms.get(identifier, {}), info):
                record = prisms[identifier]
                matching = [layer for layer in record["layers"] if layer["material_step_id"] in native_ids]
                chosen = sum((Decimal(str(layer["thickness_m"])) for layer in matching), Decimal(0))
                total = Decimal(str(record["specified_total_thickness_m"]))
                host_volume = Decimal(str(record["volume_m3"]))
                if total > 0 and matching:
                    with localcontext() as context:
                        context.prec = 80
                        number = host_volume * chosen / total
                    method, quality = "verified_uniform_layers", "estimated"
                    metadata["geometry"] = record
            if identifier in nets and raw is None:
                _, raw, comparison_facts = nets[identifier]
                used_facts.extend(comparison_facts)
                metadata["recorded_comparison"] = "Recorded host net volume is retained separately; the selected geometry method does not assume they agree."
            fact_ids = {fact.id for fact in used_facts}
            proof.update(anchor for fact in used_facts for anchor in fact.provenance.anchor_ids)
            proof.update(anchor for fact in used_facts if isinstance(fact.value, m.QuantityValue) for anchor in fact.value.unit_anchor_ids)
            geometry_record = metadata.get("geometry", metadata.get("unverified_geometry", {}))
            geometry_steps = set(geometry_record.get("source_step_ids", [])) | set(geometry_record.get("representation_step_ids", []))
            for step in geometry_steps:
                native_record = model.by_id(step)
                if native_record is not None:
                    proof.add(_anchor(engine, native_record))
            state.facts.update(fact_ids)
            state.anchors.update(proof)
            available = number is not None
            if not available:
                unknown.add(identifier)
                value = m.UnavailableValue(kind="unavailable", reason="unknown", explanation=metadata["reason"])
            else:
                converted = convert(decimal_string(number), engine.units["unit:m3"], engine.units[operation.output_unit_id])
                value = m.QuantityValue(kind="quantity", magnitude=decimal_string(converted), unit_id=operation.output_unit_id,
                    quantity_kind="volume", basis="modeled_material", unit_resolution="derived", quality=quality)
                estimated |= quality == "estimated"
            row = {"subject": m.ReferencesValue(kind="references", entity_ids=[identifier]),
                   "material": m.TextValue(kind="text", value=m.LocalizedText(text=name)) if name is not None else
                    m.UnavailableValue(kind="unavailable", reason="not_in_source" if method == "recorded_not_used" else "unknown",
                        explanation="None of the requested literal names occurs in this complete assignment; zero applies to their union." if method == "recorded_not_used" else
                                    "The material identity cannot be resolved from the recorded assignment."),
                   "volume": value, "method": m.TextValue(kind="text", value=m.LocalizedText(text=method))}
            rows.append(row)
            support = _Support({identifier}, fact_ids, proof, "material_quantity", "verified" if available else "unavailable")
            cells.append({key: support for key in row})
            state.material_records.append({"subject_id": identifier, "material_name": name,
                "material_step_ids": native_ids, "layer_step_ids": [layer.layer_step_id for layer in info.get("layers", [])],
                "assignment_step_ids": info.get("assignment_ids", []), "source_step_ids": sorted({info["host_step"], *geometry_steps}),
                "method": method, "status": "recorded_not_used" if method == "recorded_not_used" else "verified" if available else "unavailable",
                "frame": "native_quantity" if method in {"recorded_net_homogeneous", "recorded_not_used"} else "ifc_world",
                "volume_m3": float(number) if available else None, "host_volume_m3": float(host_volume) if host_volume is not None else None,
                "selected_thickness_m": float(chosen) if chosen is not None else None, "total_thickness_m": float(total) if total is not None and total > 0 else None,
                "tolerance_m": operation.tolerance_m, "recorded_quantity": raw,
                "specified_layers": info.get("layers", []), "metadata": metadata})
            if len(rows) > MAX_OUTPUT_ROWS:
                raise QueryError("unsupported_operation", "The material detail table exceeds its bounded 20000-row output budget.")
    if unknown:
        state.unresolved.update(unknown)
        state.coverage_complete = False
        state.issues.append(m.Issue(code="missing_information", entity_ids=sorted(unknown), message=m.LocalizedText(text=
            "Some selected material volumes could not be established from complete source assignments and verified volume methods. Known values are separate from unresolved inputs; no complete total is established.")))
    state.quality = "estimated" if estimated or unknown else "exact"
    for index, cell in enumerate(cells):
        cell["volume"].source_record = ("material", index, 0, len(state.material_records))
    state.value = m.TableValue(kind="table", columns=[m.TableColumn(key=key, label=m.LocalizedText(text=label)) for key, label in
        [("subject", "Source occurrence"), ("material", "Literal material name"), ("volume", "Material volume"), ("method", "Source method")]], rows=rows)
    state.cells, state.shape = cells, "table"
    state.notes.append("Material volumes use explicit native assignments. Recorded homogeneous net quantities retain their authored source basis; closed-mesh homogeneous estimates and verified uniform-layer prism allocations retain separate method/proof records. Missing composition or unverified geometry is unknown, never zero. Geometric allocation is not based on bounding boxes or an unverified thickness fraction.")

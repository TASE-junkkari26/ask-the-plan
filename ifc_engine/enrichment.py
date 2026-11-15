"""Reusable source-derived occurrence context and native material composition.

No challenge questions or reference answers enter extraction. Relationships and
layer records remain inspectable inputs rather than being reduced to guesses
about an object's name or material volume.
"""
from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal
import hashlib

import ifcopenshell.util.unit as unit_util

from contracts import models as m
from .catalog import property_key
from .units import decimal_string
from .type_candidates import type_candidates, assignment_materials


def _text(value):
    return m.TextValue(kind="text", value=m.LocalizedText(text=str(value)))


def _fact(extractor, obj, group, name, value, records, *, status="present"):
    """Attach a derived field to an occurrence with all native input anchors."""
    key = property_key(group, name)
    requested = getattr(extractor, "requested_property_keys", None)
    if requested is not None and key not in requested:
        return
    anchors = sorted({extractor.anchor(record, path) for record, path in records})
    signature = extractor.entity_id(obj) + key + "|".join(anchors)
    identifier = "fact:" + hashlib.sha256(signature.encode()).hexdigest()[:32]
    extractor.property_labels[key] = group + "." + name
    extractor.facts.append(m.Fact(id=identifier, subject_id=extractor.entity_id(obj),
        property_key=key, original_property_path=[], status=status, value=value,
        provenance=extractor.provenance(*anchors, method="computed")))


def enrichment_indexes(model):
    """Native immutable indexes shared by eager and on-demand extraction."""
    ancestors = defaultdict(list)
    for root, parent_field, child_field in (
        ("IfcRelAggregates", "RelatingObject", "RelatedObjects"),
        ("IfcRelNests", "RelatingObject", "RelatedObjects"),
        ("IfcRelContainedInSpatialStructure", "RelatingStructure", "RelatedElements"),
    ):
        for relation in model.by_type(root):
            for child in getattr(relation, child_field):
                ancestors[child.id()].append((getattr(relation, parent_field), relation))
    typing = defaultdict(list)
    for relation in model.by_type("IfcRelDefinesByType"):
        for obj in relation.RelatedObjects:
            typing[obj.id()].append(relation)
    material_associations = defaultdict(list)
    for relation in model.by_type("IfcRelAssociatesMaterial"):
        for obj in relation.RelatedObjects:
            material_associations[obj.id()].append(relation)
    return ancestors, typing, material_associations


def enrich_occurrences(extractor, objects, types, *, indexes=None, property_keys=None):
    model = extractor.model
    ancestors, typing, material_associations = indexes if indexes is not None else enrichment_indexes(model)
    extractor.requested_property_keys = None if property_keys is None else set(property_keys)
    wants_context = property_keys is None or any(key.startswith("ifc:property/SourceContext/") for key in property_keys)
    wants_material = property_keys is None or any(key.startswith(("ifc:property/SourceMaterial/", "ifc:property/SourceMaterialThickness/")) for key in property_keys)
    wants_quantities = property_keys is None or any(key.startswith("ifc:property/SourceQuantity/") for key in property_keys)

    for obj in objects.values():
        if not obj.is_a("IfcObject"):
            continue
        if wants_quantities:
            from .source_quantities import normalize_source_quantities
            normalize_source_quantities(extractor, obj)
        if wants_context and obj.id() in types:
            native_types = type_candidates(types, obj.id())
            records = [(relation, []) for relation in typing[obj.id()]]
            records.extend((native_type, ["Name"]) for native_type in native_types)
            if len(native_types) > 1:
                for field in ("TypeId", "TypeName", "TypeClass"):
                    _fact(extractor, obj, "SourceContext", field, None, records, status="ambiguous")
            else:
                native_type = native_types[0]
                name = native_type.Name
                native_id = getattr(native_type, "GlobalId", None)
                _fact(extractor, obj, "SourceContext", "TypeId", _text(native_id or "#" + str(native_type.id())),
                      [*records, (native_type, ["GlobalId"])] if native_id else records)
                _fact(extractor, obj, "SourceContext", "TypeName", _text(name) if name is not None else None,
                      records, status="present" if name is not None else "explicit_null")
                _fact(extractor, obj, "SourceContext", "TypeClass", _text(native_type.is_a()), records)

        # The nearest native container of each kind is effective occurrence
        # context, similar to inherited type properties. It does not select or
        # count every object in that container or expand the query's scope.
        pending = deque([(obj, [], 0)]) if wants_context else deque()
        seen, found, found_depth = set(), defaultdict(dict), {}
        while pending:
            current, path, depth = pending.popleft()
            if current.id() in seen or depth > 32:
                continue
            seen.add(current.id())
            for kind, cls in (("Storey", "IfcBuildingStorey"), ("Building", "IfcBuilding")):
                if current.is_a(cls) and depth <= found_depth.get(kind, 33):
                    found_depth[kind] = depth
                    found[kind][current.id()] = (current, path)
            for parent, relation in ancestors[current.id()]:
                pending.append((parent, [*path, relation], depth + 1))
        for kind, candidates in found.items():
            records = [(relation, []) for _, path in candidates.values() for relation in path]
            records.extend((container, ["Name"]) for container, _ in candidates.values())
            if len(candidates) != 1:
                _fact(extractor, obj, "SourceContext", kind + "Name", None, records, status="ambiguous")
                _fact(extractor, obj, "SourceContext", kind + "Id", None, records, status="ambiguous")
                continue
            container, _ = next(iter(candidates.values()))
            name = container.Name
            native_id = getattr(container, "GlobalId", None)
            _fact(extractor, obj, "SourceContext", kind + "Id", _text(native_id or "#" + str(container.id())),
                  [*records, (container, ["GlobalId"])] if native_id else records)
            _fact(extractor, obj, "SourceContext", kind + "Name", _text(name) if name is not None else None,
                  records, status="present" if name is not None else "explicit_null")
            if kind == "Storey":
                elevation = container.Elevation
                elevation_records = [*records, (container, ["Elevation"])]
                unit = unit_util.get_project_unit(model, "LENGTHUNIT")
                value = extractor.quantity(elevation, "length", container, unit=unit,
                    measure_class="IfcLengthMeasure") if elevation is not None else None
                _fact(extractor, obj, "SourceContext", "StoreyElevation", value, elevation_records,
                      status="present" if value is not None else "explicit_null")

        associations = material_associations[obj.id()] if wants_material else []
        if wants_material and not associations and obj.id() in types:
            native_types = type_candidates(types, obj.id())
            groups = [material_associations[native_type.id()] for native_type in native_types]
            signatures = {tuple(sorted({relation.RelatingMaterial.id() for relation in group})) for group in groups}
            if len(signatures) > 1:
                records = [(relation, []) for relation in typing[obj.id()]]
                records.extend((native_type, ["HasAssociations"]) for native_type in native_types)
                records.extend((relation, ["RelatingMaterial"]) for group in groups for relation in group)
                for field in ("Names", "Layers", "LayerSetName", "TotalLayerThickness", "CompositionComplete"):
                    _fact(extractor, obj, "SourceMaterial", field, None, records, status="ambiguous")
                names = {material.Name for group in groups for relation in group
                         for material in assignment_materials(relation.RelatingMaterial) if material.Name is not None}
                for name in names:
                    _fact(extractor, obj, "SourceMaterialThickness", name, None, records, status="ambiguous")
                continue
            associations = [relation for group in groups for relation in group]
        if associations:
            _materials(extractor, obj, associations, typing.get(obj.id(), []))


def _materials(extractor, obj, associations, typing):
    """Preserve ordered native layers; never allocate host volume by guesswork."""
    for association in associations:
        material = association.RelatingMaterial
        sources = [(association, []), *[(relation, []) for relation in typing]]
        if material.is_a() == "IfcMaterialLayerSetUsage":
            sources.append((material, ["ForLayerSet"]))
            material = material.ForLayerSet
        if material.is_a() == "IfcMaterialLayerSet":
            layers = list(material.MaterialLayers)
            unit = unit_util.get_project_unit(extractor.model, "LENGTHUNIT")
            records, names, thicknesses = [], [], defaultdict(list)
            base_sources = list(sources)
            missing_thickness = set()
            complete = bool(layers)
            for index, layer in enumerate(layers, 1):
                native_material = layer.Material
                layer_sources = [*base_sources, (material, ["MaterialLayers"]), (layer, ["LayerThickness"])]
                fields = {"index": m.CountValue(kind="count", value=index)}
                if native_material is not None:
                    layer_sources.append((native_material, ["Name"]))
                    if native_material.Name is not None:
                        fields["material"] = _text(native_material.Name)
                        names.append(native_material.Name)
                if layer.LayerThickness is not None:
                    quantity = extractor.quantity(layer.LayerThickness, "length", layer, unit=unit,
                        measure_class="IfcNonNegativeLengthMeasure")
                    fields["thickness"] = quantity
                    if native_material is not None and native_material.Name is not None:
                        thicknesses[native_material.Name].append((quantity, layer_sources))
                else:
                    complete = False
                    if native_material is not None and native_material.Name is not None:
                        missing_thickness.add(native_material.Name)
                if native_material is None or native_material.Name is None:
                    complete = False
                records.append(m.RecordValue(kind="record", fields=fields))
                sources.extend(layer_sources)
            _fact(extractor, obj, "SourceMaterial", "Layers", m.ListValue(kind="list", items=records), sources)
            _fact(extractor, obj, "SourceMaterial", "CompositionComplete", m.BooleanValue(kind="boolean", value=complete), sources)
            names_complete = all(layer.Material is not None and layer.Material.Name is not None for layer in layers)
            if names_complete and names:
                _fact(extractor, obj, "SourceMaterial", "Names", _text("; ".join(dict.fromkeys(names))), sources)
            elif layers:
                _fact(extractor, obj, "SourceMaterial", "Names", None, sources, status="unknown")
            if material.LayerSetName is not None:
                _fact(extractor, obj, "SourceMaterial", "LayerSetName", _text(material.LayerSetName),
                      [*sources, (material, ["LayerSetName"])])
            if layers and all(layer.LayerThickness is not None for layer in layers):
                total = sum((Decimal(str(layer.LayerThickness)) for layer in layers), Decimal(0))
                value = extractor.quantity(decimal_string(total), "length", material, unit=unit,
                    measure_class="IfcLengthMeasure", basis="specified")
                _fact(extractor, obj, "SourceMaterial", "TotalLayerThickness", value, sources)
            for name, entries in thicknesses.items():
                if name in missing_thickness:
                    _fact(extractor, obj, "SourceMaterialThickness", name, None, sources, status="unknown")
                    continue
                # Repeated material layers are added once each in source order.
                total = sum((Decimal(q.magnitude) for q, _ in entries), Decimal(0))
                value = entries[0][0].model_copy(update={"magnitude": decimal_string(total), "normalized": None,
                                                        "basis": "specified"})
                _fact(extractor, obj, "SourceMaterialThickness", name, value,
                      [record for _, evidence in entries for record in evidence])
        elif material.is_a() == "IfcMaterial":
            if material.Name is not None:
                _fact(extractor, obj, "SourceMaterial", "Names", _text(material.Name), [*sources, (material, ["Name"])])
            else:
                _fact(extractor, obj, "SourceMaterial", "Names", None, [*sources, (material, ["Name"])], status="explicit_null")
            _fact(extractor, obj, "SourceMaterial", "CompositionComplete", m.BooleanValue(kind="boolean", value=material.Name is not None), sources)
        else:
            # Constituent/profile/list structures remain native records until
            # their measures and ordering have an explicit extractor.
            _fact(extractor, obj, "SourceMaterial", "CompositionComplete", m.BooleanValue(kind="boolean", value=False), sources)

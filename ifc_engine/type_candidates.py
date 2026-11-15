"""Retain contradictory native typing without choosing an arbitrary type."""
from __future__ import annotations


def type_candidates(types, native_id):
    value = types.get(native_id)
    return tuple(value) if isinstance(value, (tuple, list)) else (value,) if value is not None else ()


def typing_relations(extractor, obj):
    if hasattr(extractor, "typing_relations"):
        return extractor.typing_relations.get(obj.id(), ())
    direct = getattr(obj, "IsTypedBy", ()) or ()
    return direct or [rel for rel in (getattr(obj, "IsDefinedBy", ()) or ()) if rel.is_a("IfcRelDefinesByType")]


def typing_anchor_ids(extractor, obj, types):
    anchors = {extractor.anchor(rel, ["RelatingType"]) for rel in typing_relations(extractor, obj)}
    anchors.update(extractor.anchor(native_type, ["HasPropertySets"]) for native_type in type_candidates(types, obj.id()))
    return sorted(anchors)


def inherited_property_records(extractor, types, native_id):
    merged, seen = {}, set()
    for native_type in type_candidates(types, native_id):
        for key, entries in extractor.property_records(getattr(native_type, "HasPropertySets", ()) or ()).items():
            for path, record in entries:
                if (key, record.id()) not in seen:
                    merged.setdefault(key, []).append((path, record))
                    seen.add((key, record.id()))
    return merged


def absent_candidate_keys(extractor, types, native_id):
    candidates = type_candidates(types, native_id)
    if len(candidates) < 2:
        return set()
    keys = [set(extractor.property_records(getattr(native_type, "HasPropertySets", ()) or ())) for native_type in candidates]
    return set.union(*keys) - set.intersection(*keys)


def emit_ambiguous_inheritance(extractor, obj, key, entries, types):
    label = extractor.property_labels.get(key)
    anchors = typing_anchor_ids(extractor, obj, types)
    anchors.extend(extractor.anchor(record, path) for path, record in entries)
    extractor.add_fact(extractor.entity_id(obj), key, ["IsTypedBy"] if hasattr(obj, "IsTypedBy") else ["IsDefinedBy"],
                       obj, None, "ambiguous", extra_anchors=anchors)
    if label is not None:
        extractor.property_labels[key] = label


def assignment_materials(assignment, seen=None):
    """Source leaves of one material association, preserving its exact branch."""
    seen = set() if seen is None else seen
    if assignment is None or assignment.id() in seen:
        return []
    seen.add(assignment.id())
    if assignment.is_a() == "IfcMaterial":
        return [assignment]
    children = []
    for field in ("ForLayerSet", "ForProfileSet", "MaterialLayers", "MaterialProfiles", "MaterialConstituents", "Materials", "Material"):
        value = getattr(assignment, field, None)
        if value is not None:
            children.extend(value if isinstance(value, tuple) else [value])
    return [material for child in children for material in assignment_materials(child, seen)]

"""Guarded interpretation of source-specific quantity semantics.

Revit documents a room's Area as net area from its room-bounding elements. The
rule below needs both that exact native property context and source authoring
evidence; an arbitrary property named Area is never a NetFloorArea alias.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache

from contracts import models as m
from .catalog import property_key

RAW_REVIT_AREA = property_key("PSet_Revit_Dimensions", "Area")
AUTHORED_ROOM_NET_AREA = property_key("SourceQuantity", "AuthoredRoomNetArea")
REVIT_AREA_DOCUMENTATION = "https://help.autodesk.com/cloudhelp/2025/ENU/Revit-ArchDesign/files/GUID-21326970-0037-41C6-A996-980C24EE019F.htm"
REVIT_BOUNDARY_DOCUMENTATION = "https://help.autodesk.com/cloudhelp/2025/ENU/RevitLT-ArchDes/files/GUID-9348929C-18CA-40AC-BB64-71D01CC52F2B.htm"
RULE = "ifc.source_quantity.revit_authored_room_net_area.v1"
DEFINITION = (
    "Guarded Revit room Area normalization: IfcSpace with recorded PSet_Revit_Dimensions.Area "
    "and a recognized actual Revit owning application, or Revit file originating system when no informative owning application exists. "
    "Autodesk defines room Area as net area computed from room-bounding elements. The original raw Area remains unchanged; "
    "this field retains its source values, units and all room/property/authoring anchors with basis net. "
    "The project's room-boundary placement/computation setting is not assumed or independently verified; this is the author's computed room area, "
    "which may differ from the modeled space solid's footprint and must not silently replace measured or Qto NetFloorArea. "
    "not an assertion of DIN measurement rules, as-built area or geometry completeness. "
    f"Rule: {RULE}. Sources: {REVIT_AREA_DOCUMENTATION} ; {REVIT_BOUNDARY_DOCUMENTATION}"
)


@lru_cache(maxsize=512)
def native_quantity_basis(name: str | None, quantity_kind: str | None) -> str:
    """Exact physical property names only; NetworkLength stays modeled."""
    # These are quantity names present in the native source schemas, not QA
    # strings or quantity aliases. Full keys retain side/core/veneer meaning.
    net = {
        "area": {"NetArea", "Net Area", "NetFloorArea", "NetSideArea", "NetSideAreaLeft", "NetSideAreaRight",
            "NetSurfaceArea", "NetSurfaceAreaExtrudedSides", "NetFootprintArea", "NetCeilingArea", "NetWallArea",
            "Net Surface Area of the Edges", "Net Surface Area on the Inside Face", "Net Surface Area on the Outside Face",
            "Net Surface Area of the Core Bottom", "Net Surface Area of the Core (without Top/Bottom)", "Net Surface Area of the Core Top",
            "Net Surface Area of the Veneer Bottom", "Net Surface Area of the Veneer Top", "Nettofläche",
            "Netto-Oberflächenbereich an der Außenseite", "Netto-Oberflächenbereich an der Innenseite",
            "Netto-Oberflächenbereich an den Kanten", "Netto-Oberflächenbereich Unterseite", "Netto-Oberflächenbereich Oberseite",
            "Netto-Oberflächenbereich der Kante", "Netto-Oberflächenbereich des Kerns (ohne Oberseite/Unterseite)",
            "Netto-Oberflächenbereich des Kerns oben", "Netto-Oberflächenbereich des Kerns unten",
            "Netto-Oberflächenbereich der Ummantelung oben", "Netto-Oberflächenbereich der Ummantelung unten"},
        "volume": {"NetVolume", "Net Volume", "Net Volume of the Core", "Net Volume of the Veneer", "Netto-Volumen",
            "Netto-Volumen des Kerns", "Netto-Volumen der Ummantelung"},
        "length": {"NetPerimeter", "Net Perimeter", "Nettoumfang", "NetHeight"},
    }
    gross = {
        "area": {"GrossArea", "GrossFloorArea", "GrossSideArea", "GrossSurfaceArea", "GrossFootprintArea", "GrossCeilingArea", "GrossWallArea",
            "Gross Surface Area of the Wall on the Inside Face", "Gross Surface Area of the Wall on the Outside Face",
            "Gross Surface Area of the Slab Bottom", "Gross Surface Area of the Slab Bottom with Holes",
            "Gross Surface Area of the Slab Edges", "Gross Surface Area of the Slab Edges with Holes",
            "Gross Surface Area of the Slab Top", "Gross Surface Area of the Slab Top with Holes",
            "Gross Surface Area of the Core (without Top/Bottom)", "Gross Surface Area of the Core Top (or Bottom)",
            "Gross Surface Area of the Veneer (without Top/Bottom)", "Gross Surface Area of the Veneer Top (or Bottom)"},
        "volume": {"GrossVolume", "Gross Volume of the Wall", "Gross Volume of the Slab", "Gross Volume of the Slab with Holes",
            "Gross Volume of the Core", "Gross Volume of the Veneer", "Gross Volume of the Column"},
        "length": {"GrossPerimeter", "GrossHeight"},
    }
    return "net" if name in net.get(quantity_kind, ()) else "gross" if name in gross.get(quantity_kind, ()) else "modeled"


def source_quantity_definition():
    return m.PropertyDefinition(key=AUTHORED_ROOM_NET_AREA, labels=[m.LocalizedText(text="SourceQuantity.AuthoredRoomNetArea")],
        value_kind="quantity", quantity_kind="area", dimension=(2, 0, 0, 0, 0, 0, 0), definition=DEFINITION)


def _is_revit(value):
    # Accept native Autodesk/Revit application signatures and version suffixes,
    # not arbitrary metadata that merely mentions Revit in a longer sentence.
    return isinstance(value, str) and re.match(r"^(?:Autodesk\s+)?Revit(?:\b|\d)", value.strip(), re.IGNORECASE) is not None


def _authoring_records(extractor, obj):
    history = getattr(obj, "OwnerHistory", None)
    application = getattr(history, "OwningApplication", None)
    if application is not None:
        names = [getattr(application, field, None) for field in ("ApplicationFullName", "ApplicationIdentifier")]
        if any(isinstance(name, str) and name.strip() for name in names):
            if not any(_is_revit(name) for name in names):
                return None
            return [(obj, ["OwnerHistory"]), (history, ["OwningApplication"]),
                    *[(application, [field]) for field in ("ApplicationFullName", "ApplicationIdentifier", "Version")]]
    header = extractor.model.header.file_name
    if _is_revit(header.originating_system):
        return [(header, ["originating_system"])]
    return None


def _area_records(obj):
    own, inherited = [], []
    for relation in getattr(obj, "IsDefinedBy", ()) or ():
        if relation.is_a("IfcRelDefinesByProperties"):
            value = relation.RelatingPropertyDefinition
            for definition in value if isinstance(value, tuple) else [value]:
                own.append((definition, [(relation, ["RelatingPropertyDefinition"])]))
    typing = [relation for relation in (getattr(obj, "IsTypedBy", ()) or ())]
    if not typing:
        typing = [relation for relation in (getattr(obj, "IsDefinedBy", ()) or ()) if relation.is_a("IfcRelDefinesByType")]
    per_type = {}
    for relation in typing:
        native_type = relation.RelatingType
        per_type.setdefault(native_type.id(), [])
        for definition in getattr(native_type, "HasPropertySets", ()) or ():
            entry = (definition, [(relation, ["RelatingType"]), (native_type, ["HasPropertySets"])])
            inherited.append(entry)
            per_type[native_type.id()].append(entry)

    def matching(definitions):
        return [(record, [*proof, (definition, ["Name"])]) for definition, proof in definitions
                if definition is not None and definition.Name == "PSet_Revit_Dimensions"
                for record in (getattr(definition, "HasProperties", ()) or ())
                if record is not None and record.Name == "Area"]
    occurrence = matching(own)
    if occurrence:
        return occurrence
    result = matching(inherited)
    if len(per_type) > 1 and result and any(not matching(entries) for entries in per_type.values()):
        proof = [source for _, sources in result for source in sources]
        proof.extend((relation, ["RelatingType"]) for relation in typing)
        proof.extend((relation.RelatingType, ["HasPropertySets"]) for relation in typing)
        proof.extend((record, ["PSet_Revit_Dimensions", "Area"]) for record, _ in result)
        result.append((None, proof))
    return result


def source_quantity_definitions(extractor, objects):
    """Declare potential native aliases without materializing per-room facts."""
    for obj in objects.values():
        if obj.is_a("IfcSpace") and _authoring_records(extractor, obj) is not None:
            for record, _ in _area_records(obj):
                if record is None:
                    return [source_quantity_definition()]
                value, status = extractor.property_value(record)
                if status == "explicit_null" or (status == "present" and isinstance(value, m.QuantityValue) and value.quantity_kind == "area"):
                    return [source_quantity_definition()]
    return []


def normalize_source_quantities(extractor, obj):
    if not obj.is_a("IfcSpace"):
        return
    requested = getattr(extractor, "requested_property_keys", None)
    if requested is not None and AUTHORED_ROOM_NET_AREA not in requested:
        return
    authoring = _authoring_records(extractor, obj)
    if authoring is None:
        return
    seen = set()
    for record, bindings in _area_records(obj):
        if record is not None and record.id() in seen:
            continue
        if record is not None:
            seen.add(record.id())
        value, status = extractor.property_value(record) if record is not None else (None, "ambiguous")
        if status == "present":
            if not isinstance(value, m.QuantityValue) or value.quantity_kind != "area":
                continue
            value = value.model_copy(deep=True, update={"basis": "net"})
        elif status not in {"explicit_null", "ambiguous"}:
            continue
        records = [(obj, []), *([(record, ["PSet_Revit_Dimensions", "Area"])] if record is not None else []), *bindings, *authoring]
        anchors = sorted({extractor.anchor(source, path) for source, path in records})
        identity = extractor.entity_id(obj) + AUTHORED_ROOM_NET_AREA + "|".join(anchors)
        extractor.property_labels[AUTHORED_ROOM_NET_AREA] = "SourceQuantity.AuthoredRoomNetArea"
        extractor.facts.append(m.Fact(id="fact:" + hashlib.sha256(identity.encode()).hexdigest()[:32],
            subject_id=extractor.entity_id(obj), property_key=AUTHORED_ROOM_NET_AREA,
            original_property_path=["PSet_Revit_Dimensions", "Area"], status=status, value=value,
            provenance=extractor.provenance(*anchors, method="computed")))

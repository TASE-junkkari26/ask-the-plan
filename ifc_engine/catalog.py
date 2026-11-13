"""Small, explicit vocabulary; original IFC classes and paths stay available."""
from __future__ import annotations

from urllib.parse import quote

from contracts.models import CountPolicy

# These concepts apply to occurrences, including IFC2X3 occurrences whose
# semantic class is carried by an IfcRelDefinesByType relationship.
CONCEPT_CLASSES = {
    "door": "IfcDoor", "window": "IfcWindow", "wall": "IfcWall",
    "space": "IfcSpace", "storey": "IfcBuildingStorey", "building": "IfcBuilding",
    "site": "IfcSite", "slab": "IfcSlab", "stair": "IfcStair",
    "stair_flight": "IfcStairFlight", "sanitary_terminal": "IfcSanitaryTerminal",
    "light_fixture": "IfcLightFixture", "pipe_segment": "IfcPipeSegment",
    "duct_segment": "IfcDuctSegment", "column": "IfcColumn", "beam": "IfcBeam",
}

POLICIES = {
    "all_matches": CountPolicy(grain="occurrence", hierarchy="all_matches", rule_key="ifc.occurrence.v1"),
    "topmost_matches": CountPolicy(grain="assembly", hierarchy="topmost_matches", rule_key="ifc.topmost.v1"),
    "leaves": CountPolicy(grain="part", hierarchy="leaves", rule_key="ifc.leaf.v1"),
}


def attribute_key(name: str) -> str:
    return "ifc:attribute/" + quote(name, safe="")


def property_key(pset: str, name: str) -> str:
    return "ifc:property/" + quote(pset, safe="") + "/" + quote(name, safe="")


CLASS_KEY = "ifc:class"
ATTRIBUTES = ("Name", "LongName", "Description", "Tag", "PredefinedType", "ObjectType")
LENGTH_ATTRIBUTES = ("OverallWidth", "OverallHeight", "Elevation")
RELATIONS = ("contains", "aggregates", "typed_by", "assigned_to_system", "has_material")

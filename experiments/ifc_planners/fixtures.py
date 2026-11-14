"""Small deterministic IFC sources, independent of challenge reference answers."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import uuid

import ifcopenshell
import ifcopenshell.guid

VERSION = "ifc-planner-fixtures-v1"
GROUPS = ("classified", "topology", "missing", "floors", "partial", "conflicting")
_ABSENT = object()


@dataclass(frozen=True)
class Fixture:
    group: str
    path: Path
    sha256: str
    steps: dict[str, int]


def build_fixture(directory: Path, group: str) -> Fixture:
    if group not in GROUPS:
        raise ValueError("Unknown synthetic fixture group.")
    source = ifcopenshell.file(schema="IFC4")
    source.header.file_name.name = group + ".ifc"
    source.header.file_name.time_stamp = "2026-11-14T00:00:00"
    source.header.file_name.author = ("Ask the Plan synthetic evaluation",)
    source.header.file_name.organization = ()
    source.header.file_name.preprocessor_version = VERSION
    source.header.file_name.originating_system = VERSION
    source.header.file_name.authorization = ""
    objects = {}

    def root(kind, key, **values):
        guid = ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_URL, VERSION + "/" + group + "/" + key).hex)
        obj = source.create_entity(kind, GlobalId=guid, **values)
        objects[key] = obj
        return obj

    def aggregate(parent, children, key):
        root("IfcRelAggregates", key, RelatingObject=parent, RelatedObjects=children)

    project = root("IfcProject", "project", Name="Synthetic planner comparison / " + group)
    project.UnitsInContext = source.create_entity("IfcUnitAssignment", Units=[
        source.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")])
    building = root("IfcBuilding", "building", Name="Building A")
    ground = root("IfcBuildingStorey", "ground", Name="Ground", Elevation=0.)
    upper = root("IfcBuildingStorey", "upper", Name="Upper", Elevation=3.)
    aggregate(project, [building], "project-building")
    aggregate(building, [ground, upper], "building-storeys")
    rooms = [root("IfcSpace", key, Name=name, LongName=function)
             for key, name, function in [("room-a", "R-A", "Entrance"),
                                        ("room-b", "R-B", "Hall"),
                                        ("room-c", "R-C", "Office")]]
    aggregate(ground, rooms, "ground-rooms")
    ground_elements, upper_elements = [], []

    def flag(subject, key, value):
        prop = source.create_entity("IfcPropertySingleValue", Name="IsExternal",
            NominalValue=source.create_entity("IfcBoolean", value))
        pset = root("IfcPropertySet", key + "-pset", Name="Pset_DoorCommon", HasProperties=[prop])
        if subject.is_a("IfcTypeObject"):
            subject.HasPropertySets = [pset]
        else:
            root("IfcRelDefinesByProperties", key + "-properties", RelatedObjects=[subject], RelatingPropertyDefinition=pset)

    def door(key, name, value=_ABSENT, *, upper_floor=False):
        obj = root("IfcDoor", key, Name=name, OverallWidth=1.2, OverallHeight=2.1)
        (upper_elements if upper_floor else ground_elements).append(obj)
        if value is not _ABSENT:
            flag(obj, key, value)
        return obj

    def boundary(key, room, element, *, external=False):
        return root("IfcRelSpaceBoundary", key, RelatingSpace=objects[room],
                    RelatedBuildingElement=element, PhysicalOrVirtualBoundary="PHYSICAL",
                    InternalOrExternalBoundary="EXTERNAL" if external else "INTERNAL")

    if group == "classified":
        entry = door("entry", "D-01 Double-leaf entrance")
        door("patio", "D-02 Terrace", True)
        internal = door("internal", "D-03 Office", False)
        door("service", "D-04 Store", False)
        door_type = root("IfcDoorType", "external-type", Name="Exterior fitted doorway",
                         PredefinedType="DOOR", OperationType="DOUBLE_DOOR_SINGLE_SWING")
        flag(door_type, "external-type", True)
        root("IfcRelDefinesByType", "entry-type", RelatingType=door_type, RelatedObjects=[entry, internal])
    elif group == "topology":
        entry = door("entry", "D-01 Entrance")
        patio = door("patio", "D-02 Terrace")
        internal = door("internal", "D-03 Between hall and office", False)
        opening = root("IfcOpeningElement", "patio-opening", Name="O-02 Terrace opening")
        ground_elements.append(opening)
        root("IfcRelFillsElement", "patio-fill", RelatingOpeningElement=opening, RelatedBuildingElement=patio)
        boundary("entry-boundary", "room-a", entry, external=True)
        boundary("entry-duplicate", "room-a", entry, external=True)
        boundary("patio-boundary", "room-b", opening, external=True)
        boundary("internal-b", "room-b", internal)
        boundary("internal-c", "room-c", internal)
    elif group == "missing":
        door("entry", "D-01 Unclassified entrance")
        door("internal", "D-02 Unclassified hall")
        door("service", "D-03 Unclassified store")
    elif group == "floors":
        door("entry", "D-G1 Entrance", True)
        door("internal", "D-G2 Office", False)
        door("upper-entry", "D-U1 Balcony", True, upper_floor=True)
        door("upper-internal", "D-U2 Hall", False, upper_floor=True)
        door("upper-service", "D-U3 Store", False, upper_floor=True)
    elif group == "partial":
        entry = door("entry", "D-01 Entrance", True)
        door("internal", "D-02 Office", False)
        door("unknown", "D-03 Unclassified doorway")
        boundary("entry-boundary", "room-a", entry, external=True)
    else:
        entry = door("entry", "D-01 Conflicting doorway", False)
        door("patio", "D-02 Recorded exterior doorway", True)
        door("internal", "D-03 Office", False)
        boundary("entry-boundary", "room-a", entry, external=True)
    root("IfcRelContainedInSpatialStructure", "ground-elements", RelatingStructure=ground, RelatedElements=ground_elements)
    if upper_elements:
        root("IfcRelContainedInSpatialStructure", "upper-elements", RelatingStructure=upper, RelatedElements=upper_elements)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (group + ".ifc")
    source.write(str(path))
    return Fixture(group, path, hashlib.sha256(path.read_bytes()).hexdigest(),
                   {key: obj.id() for key, obj in objects.items()})

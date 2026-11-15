"""Conservative grammar-to-query compilation with no inference or QA lookup.

Only complete, unambiguous grammatical forms compile. Literal source identifiers
are resolved against this immutable engine revision; everything else returns
None for the bounded planner. This module never imports service, experiments,
dataset questions, classification taxonomies or reference answers.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
import threading
import unicodedata
from urllib.parse import unquote
import weakref

from contracts import models as m
from ifc_engine.catalog import POLICIES, attribute_key, property_key
from ifc_engine.units import convert
from .model_identity import matches_model

VERSION = "ifc-grammar-v1"
_QUOTED = r"(?:'[^\r\n]{1,300}?'|\"[^\r\n]{1,300}?\"|„[^\r\n]{1,300}?“|“[^\r\n]{1,300}?”|«[^\r\n]{1,300}?»)"
_FLAGS = re.IGNORECASE

# Semantic category vocabulary, not question strings or answer values. Ambiguous
# 'toilets' and Finnish 'porrasta' (a stair versus a step) deliberately stay out.
_EN_CATEGORIES = {
    "doors": "door", "windows": "window", "walls": "wall", "rooms": "space",
    "spaces": "space", "rooms (spaces)": "space", "rooms and spaces": "space",
    "stairs": "stair", "staircases": "stair", "stair occurrences": "stair_occurrence",
    "columns": "column", "beams": "beam", "sanitary fixtures": "sanitary_terminal",
    "light fixtures": "light_fixture", "slabs": "slab", "buildings": "building",
    "storeys": "storey", "stories": "storey", "building levels": "storey",
    "stair flights": "stair_flight", "pipe segments": "pipe_segment", "duct segments": "duct_segment",
}
_FI_CATEGORIES = {
    "ovea": "door", "ikkunaa": "window", "seinää": "wall", "huonetta": "space",
    "tilaa": "space", "huonetta (tilaa)": "space", "portaikkoa": "stair",
    "pilaria": "column", "palkkia": "beam", "saniteettikalustetta": "sanitary_terminal",
    "valaisinta": "light_fixture", "rakennusta": "building", "kerrosta": "storey",
    "porrassyöksyä": "stair_flight", "putkisegmenttiä": "pipe_segment", "kanavasegmenttiä": "duct_segment",
}
_DE_CATEGORIES = {"türen": "door", "fenster": "window", "räume": "space", "räume (spaces)": "space",
                  "wände": "wall", "stützen": "column", "träger": "beam", "treppen": "stair",
                  "sanitärobjekte": "sanitary_terminal", "leuchten": "light_fixture"}
_TYPE_CATEGORIES = {
    "door": "door", "window": "window", "wall": "wall", "stair": "stair", "staircase": "stair",
    "column": "column", "beam": "beam", "slab": "slab", "railing": "railing", "furniture": "furniture",
    "pipe": "pipe_segment", "pipe fitting": "pipe_fitting", "duct": "duct_segment", "duct fitting": "duct_fitting",
    "valve": "valve", "pump": "pump", "fan": "fan", "damper": "damper", "coil": "coil",
    "air terminal": "air_terminal", "sanitary terminal": "sanitary_terminal", "waste terminal": "waste_terminal",
    "light fixture": "light_fixture", "lighting fixture": "light_fixture", "curtain wall": "curtain_wall",
    "footing": "footing", "pile": "pile", "tank": "tank", "filter": "filter",
}
_EN_CATEGORY = "(?:" + "|".join(re.escape(value) for value in sorted(_EN_CATEGORIES, key=len, reverse=True)) + ")"
_FI_CATEGORY = "(?:" + "|".join(re.escape(value) for value in sorted(_FI_CATEGORIES, key=len, reverse=True)) + ")"

# metric phrase -> (concept, native terminal property name, quantity kind, unit)
_EN_METRICS = {
    "total net floor area of all rooms (spaces)": ("space", "NetFloorArea", "area", "unit:m2"),
    "total net floor area of all rooms": ("space", "NetFloorArea", "area", "unit:m2"),
    "total net floor area of all spaces": ("space", "NetFloorArea", "area", "unit:m2"),
    "total net side area of all walls": ("wall", "NetSideArea", "area", "unit:m2"),
    "total length of all walls": ("wall", "Length", "length", "unit:m"),
    "total net volume of all walls": ("wall", "NetVolume", "volume", "unit:m3"),
    "total net volume of all slabs": ("slab", "NetVolume", "volume", "unit:m3"),
}
_UNITS = {
    "area": r"(?:m²|m2|square metres|square meters|neliömetreinä)",
    "length": r"(?:m|metres|meters|metreinä)",
    "volume": r"(?:m³|m3|cubic metres|cubic meters|kuutiometreinä)",
}


def _fold(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _literal(value: str) -> str:
    return value[1:-1]


def _terminal(value: str) -> str:
    return re.sub(r"[ _-]", "", value).casefold()


def _model_matches(engine, title):
    return matches_model(engine, title)


def _text(engine, identifier, key):
    engine.ensure_fields([identifier], [key])
    facts = engine.facts.get((identifier, key), [])
    if not facts or any(fact.status != "present" or not isinstance(fact.value, m.TextValue) for fact in facts):
        return None
    values = {fact.value.value.text for fact in facts}
    return next(iter(values)) if len(values) == 1 else None


def _locator(engine, identifier):
    selectors = [engine.anchors[anchor].selector for anchor in engine.entity_anchors.get(identifier, ())]
    guids = {selector.value for selector in selectors if selector.kind == "ifc_guid" and not selector.property_path}
    if len(guids) == 1:
        return next(iter(guids))
    steps = {selector.value for selector in selectors if selector.kind == "step_id" and not selector.property_path}
    return "#" + next(iter(steps)) if len(steps) == 1 else None


class _Index:
    def __init__(self, engine):
        self.floor_names = defaultdict(set)
        self.floor_ids = defaultdict(set)
        self.rooms = defaultdict(set)
        self.room_ids = defaultdict(set)
        self.floor_native = {}
        self.entities_by_concept = {}
        self.property_names = defaultdict(set)
        for identifier, entity in engine.entities.items():
            if entity.kind not in {"space", "storey"}:
                continue
            # Source labels are immutable search candidates in lean models;
            # their roles are verified from hydrated native facts only for the
            # particular rooms a question names.
            labels = [label.text for label in entity.labels]
            locator = _locator(engine, identifier)
            if entity.kind == "storey":
                self.floor_native[identifier] = locator
                for label in labels:
                    self.floor_names[_fold(label)].add(identifier)
                if locator is not None:
                    self.floor_ids[locator].add(identifier)
                continue
            for label in labels:
                self.rooms[_fold(label)].add(identifier)
            if locator is not None:
                self.room_ids[locator].add(identifier)
            if len(labels) == 2:
                self.rooms[_fold(f"{labels[1]} ({labels[0]})")].add(identifier)
                self.rooms[_fold(f"{labels[0]} ({labels[1]})")].add(identifier)
        for key, definition in engine.properties.items():
            if key.startswith("ifc:property/") and definition.value_kind == "quantity":
                self.property_names[_terminal(unquote(key.rsplit("/", 1)[1]))].add(key)

    def entities(self, engine, concept):
        if concept not in self.entities_by_concept:
            allowed, pending = set(), [concept]
            while pending:
                value = pending.pop()
                if value not in allowed:
                    allowed.add(value)
                    pending.extend(engine.concept_children.get(value, ()))
            self.entities_by_concept[concept] = {identifier for identifier, entity in engine.entities.items()
                                                 if allowed.intersection(entity.concept_ids)}
        return self.entities_by_concept[concept]


_INDEX = weakref.WeakKeyDictionary()
_LOCK = threading.RLock()


def _index(engine):
    with _LOCK:
        if engine not in _INDEX:
            _INDEX[engine] = _Index(engine)
        return _INDEX[engine]


@dataclass(frozen=True)
class _Scope:
    entire: bool = False
    floor: str | None = None
    model_title: str | None = None


def _scope(text: str, language="en"):
    if not text:
        return _Scope()
    if language == "en":
        if re.fullmatch(r"(?:in (?:this|the current) view|on (?:this|the current) (?:drawing|floor plan)|in total)", text, _FLAGS):
            return _Scope()
        if re.fullmatch(r"in (?:this|the|the entire|the whole) (?:model|building|IFC file)", text, _FLAGS):
            return _Scope(entire=True)
        match = re.fullmatch(r"in the model (?P<title>" + _QUOTED + ")", text, _FLAGS)
        if match:
            return _Scope(entire=True, model_title=_literal(match["title"]))
        match = re.fullmatch(r"(?:on the floor plan of|on (?:the )?(?:floor|level)|on) (?P<floor>" + _QUOTED + ")", text, _FLAGS)
    else:
        if re.fullmatch(r"(?:tässä|nykyisessä) näkymässä", text, _FLAGS):
            return _Scope()
        if re.fullmatch(r"(?:(?:koko|tässä) )?(?:mallissa|rakennuksessa)", text, _FLAGS):
            return _Scope(entire=True)
        match = re.fullmatch(r"mallissa (?P<title>" + _QUOTED + ")", text, _FLAGS)
        if match:
            return _Scope(entire=True, model_title=_literal(match["title"]))
        match = re.fullmatch(r"(?:kerroksessa|tasolla) (?P<floor>" + _QUOTED + ")", text, _FLAGS)
        if not match:
            match = re.fullmatch(r"(?P<floor>" + _QUOTED + r")-kerroksessa", text, _FLAGS)
    return _Scope(floor=_literal(match["floor"])) if match else None


def _count_scope(tail, language):
    if language == "en":
        if re.fullmatch(r"does (?:this|the) model contain", tail, _FLAGS):
            return _Scope(entire=True)
        match = re.fullmatch(r"(?:are there|are shown|are visible|are modeled|are modelled)(?: (?P<scope>.+))?", tail, _FLAGS)
        return _scope(match["scope"] or "") if match else _scope(tail)
    if re.fullmatch(r"(?:on|näkyy|on näkyvissä)", tail, _FLAGS):
        return _Scope()
    for pattern in (r"(?:on|näkyy|on näkyvissä) (?P<scope>.+)", r"(?P<scope>.+) (?:on|näkyy)"):
        match = re.fullmatch(pattern, tail, _FLAGS)
        if match:
            result = _scope(match["scope"], "fi")
            if result is not None:
                return result
    return _scope(tail, "fi")


def _equal(field, value):
    return {"kind": "compare", "field": {"kind": "property", "key": field},
            "operator": "eq", "value": {"kind": "text", "value": {"text": value}}}


def _floor(engine, index, name, members, allowed):
    if name is None:
        return None
    candidates = set(index.floor_names.get(_fold(name), ())) | index.floor_ids.get(name, set())
    if len(candidates) > 1 and allowed is not None and len(allowed) != len(engine.entities):
        engine.ensure_fields(members, [property_key("SourceContext", "StoreyId")])
        observed = {_text(engine, identifier, property_key("SourceContext", "StoreyId")) for identifier in members}
        candidates = {identifier for identifier in candidates if index.floor_native[identifier] in observed}
    if len(candidates) != 1:
        return None
    identifier = next(iter(candidates))
    native = index.floor_native[identifier]
    return (identifier, native) if native is not None else None


def _where(engine, index, scope, members, allowed):
    if scope.floor is None:
        return True, None, None
    floor = _floor(engine, index, scope.floor, members, allowed)
    key = property_key("SourceContext", "StoreyId")
    if floor is None or key not in engine.properties:
        return False, None, None
    return True, _equal(key, floor[1]), floor[1]


def _proposal(steps, scope, interpretation):
    return {"status": "ready", "interpretation": interpretation,
            "explicitly_requests_entire_model": scope.entire,
            "steps": steps, "output_step_id": steps[-1]["id"], "outputs": {}, "requests": []}


def _scope_change(engine, scope, allowed):
    if scope.entire and allowed is not None and len(allowed) != len(engine.entities):
        return {"status": "needs_clarification", "interpretation": "The question explicitly requests the entire model; authorize whole-model scope before source inspection.",
                "explicitly_requests_entire_model": True, "steps": [], "output_step_id": None, "outputs": {}, "requests": []}
    return None


def _floor_scope_change(engine, index, scope, native_floor, allowed):
    """Do not turn an explicitly different unseen floor into physical zero."""
    if scope.floor is None or native_floor is None or not allowed or len(allowed) == len(engine.entities):
        return None
    visible_floors = {index.floor_native[identifier] for identifier in allowed
                      if identifier in index.floor_native and index.floor_native[identifier] is not None}
    occurrence_ids = {identifier for identifier in allowed
                      if engine.entities[identifier].kind in {"space", "element", "assembly", "part"}}
    key = property_key("SourceContext", "StoreyId")
    engine.ensure_fields(occurrence_ids, [key])
    contexts = [_text(engine, identifier, key) for identifier in occurrence_ids]
    known = visible_floors | {value for value in contexts if value is not None}
    if known and native_floor not in known and all(value is not None for value in contexts):
        return {"status": "needs_clarification", "interpretation":
                f"Source floor {scope.floor!r} exists, but the captured view contains objects from other floors. Switch to the requested floor or authorize the entire model; an empty intersection is not its physical object total.",
                "explicitly_requests_entire_model": False, "steps": [], "output_step_id": None, "outputs": {}, "requests": []}
    return None


def _selection(concept, where=None, *, stairs=False):
    return {"id": "selected", "operation": {"kind": "select", "concept_ids": [concept],
            "where": where, "count_policy": POLICIES["topmost_matches" if stairs else "all_matches"].model_dump(mode="json")}}


def _count(engine, index, category, scope, grouped, allowed):
    wider = _scope_change(engine, scope, allowed)
    if wider is not None:
        return wider
    if not _model_matches(engine, scope.model_title):
        return None
    concept = "concept:" + ("stair" if category == "stair_occurrence" else category)
    if concept not in engine.concept_ids:
        return None
    members = index.entities(engine, concept)
    if allowed is not None:
        members = members & allowed
    okay, where, native_floor = _where(engine, index, scope, members, allowed)
    if not okay:
        return None
    wider = _floor_scope_change(engine, index, scope, native_floor, allowed)
    if wider is not None:
        return wider
    group_by = []
    if grouped:
        for name in ("TypeId", "TypeName"):
            key = property_key("SourceContext", name)
            if key not in engine.properties:
                return None
            group_by.append({"kind": "property", "key": key})
    steps = [_selection(concept, where, stairs=category == "stair")]
    aggregate = {"kind": "aggregate", "input_step_id": "selected", "method": "count", "group_by": group_by}
    if grouped:
        aggregate["missing_groups"] = "unclassified"
    steps.append({"id": "answer", "operation": aggregate})
    grain = "topmost stair assemblies" if category == "stair" else "source occurrences"
    return _proposal(steps, scope, f"Count {category} {grain}" + (" grouped by native type identity" if grouped else "") +
                     (f" on source floor {scope.floor!r}." if scope.floor is not None else " in the captured scope."))


def _quantity_key(engine, index, members, terminal, kind, unit, *, allow_missing=True):
    keys = sorted(key for key in index.property_names.get(_terminal(terminal), ())
                  if engine.properties[key].quantity_kind == kind
                  and not (terminal == "NetFloorArea" and key.startswith(property_key("SourceQuantity", ""))))
    if not keys or unit not in engine.units:
        return None
    engine.ensure_fields(members, keys)
    observations = {}
    for key in keys:
        observed = {}
        for identifier in members:
            facts = engine.facts.get((identifier, key), ())
            if not facts:
                continue
            if any(fact.status != "present" or not isinstance(fact.value, m.QuantityValue) for fact in facts):
                # An explicit missing/unknown value remains available to the
                # executor; it must never be changed to a numerical zero.
                if len(keys) == 1 and allow_missing:
                    return key
                return None
            values = set()
            for fact in facts:
                value = fact.value
                if value.unit_id not in engine.units or value.quantity_kind != kind or value.quality != "exact":
                    return None
                if terminal.startswith("Net") and value.basis not in {"net", "modeled"}:
                    return None
                try:
                    magnitude = convert(value.magnitude, engine.units[value.unit_id], engine.units[unit])
                except ValueError:
                    return None
                values.add((magnitude, value.basis))
            if len(values) != 1:
                return None
            observed[identifier] = next(iter(values))
        observations[key] = observed
    for identifier in members:
        alternatives = {values[identifier] for values in observations.values() if identifier in values}
        if len(alternatives) > 1:
            return None
    complete = [key for key, values in observations.items() if set(values) == set(members)]
    if complete:
        return complete[0]
    # A unique known typed property can be executed to demonstrate the exact
    # missing input. Multiple incomplete aliases need the bounded planner.
    return keys[0] if len(keys) == 1 and allow_missing else None


def _room(engine, index, text, floor_native, allowed):
    candidates = set(index.rooms.get(_fold(text), ())) | index.room_ids.get(text, set())
    if allowed is not None:
        candidates &= allowed
    if floor_native is not None:
        engine.ensure_fields(candidates, [property_key("SourceContext", "StoreyId")])
        candidates = {identifier for identifier in candidates
                      if _text(engine, identifier, property_key("SourceContext", "StoreyId")) == floor_native}
    engine.ensure_fields(candidates, [attribute_key("Name"), attribute_key("LongName")])
    verified, source_fields = set(), {}
    for identifier in candidates:
        fields = {name: value for name in ("Name", "LongName")
                  if (value := _text(engine, identifier, attribute_key(name))) is not None}
        aliases = list(fields.values())
        if fields.get("Name") and fields.get("LongName"):
            aliases += [f"{fields['LongName']} ({fields['Name']})", f"{fields['Name']} ({fields['LongName']})"]
        if _locator(engine, identifier) == text or any(_fold(alias) == _fold(text) for alias in aliases):
            verified.add(identifier)
            source_fields[identifier] = fields
    candidates = verified
    if len(candidates) != 1:
        return None
    identifier = next(iter(candidates))
    predicates = [{"kind": "compare", "field": {"kind": "entity_id", "key": "entity_id"},
                   "operator": "eq", "value": {"kind": "references", "entity_ids": [identifier]}}]
    for name, value in source_fields[identifier].items():
        # Original values give the resolution an inspectable source trail even
        # when the user's capitalization differs or a combined label was used.
        predicates.append(_equal(attribute_key(name), value))
    return identifier, predicates


def _quantity(engine, index, metric, scope, room=None, allowed=None):
    wider = _scope_change(engine, scope, allowed)
    if wider is not None:
        return wider
    if not _model_matches(engine, scope.model_title):
        return None
    category, terminal, kind, unit = metric
    concept = "concept:" + category
    if concept not in engine.concept_ids:
        return None
    members = (set(index.rooms.get(_fold(room), ())) | index.room_ids.get(room, set())) if room is not None else set(index.entities(engine, concept))
    if allowed is not None:
        members &= allowed
    okay, where, floor_native = _where(engine, index, scope, members, allowed)
    if not okay:
        return None
    wider = _floor_scope_change(engine, index, scope, floor_native, allowed)
    if wider is not None:
        return wider
    if room is not None:
        resolved = _room(engine, index, room, floor_native, allowed)
        if resolved is None:
            return None
        identifier, predicates = resolved
        if where:
            predicates.append(where)
        where = {"kind": "all", "operands": predicates}
        members = {identifier}
    else:
        if floor_native is not None:
            engine.ensure_fields(members, [property_key("SourceContext", "StoreyId")])
            members = {identifier for identifier in members
                       if _text(engine, identifier, property_key("SourceContext", "StoreyId")) == floor_native}
    net_room_area = category == "space" and terminal == "NetFloorArea"
    key = _quantity_key(engine, index, members, terminal, kind, unit, allow_missing=not net_room_area)
    if key is None and net_room_area:
        if "measure.area" not in engine.capabilities.operations:
            return None
        # Source-authored room Area may use a different boundary convention
        # from the represented space. It is never silently substituted for
        # what the selected floor/view depicts. Geometry remains estimated,
        # explicitly footprint-based and bounded by the captured membership.
        steps = [_selection(concept, where), {"id": "footprints", "operation": {
            "kind": "measure", "input_step_id": "selected", "metric": "area", "basis": "footprint",
            "output_unit_id": unit}}, {"id": "answer", "operation": {
            "kind": "aggregate", "input_step_id": "footprints", "method": "sum",
            "field": {"kind": "result_column", "key": "value"}, "output_unit_id": unit}}]
        return _proposal(steps, scope, "Measure the represented IfcSpace footprint area for " +
            (f"source room {room!r}" if room is not None else "the captured spaces") +
            (f" on source floor {scope.floor!r}" if scope.floor is not None else " in the captured scope") +
            "; estimated modeled floor-plan area in world XY, rather than an authored Room.Area with an unspecified boundary setting or an as-built measurement.")
    if key is None:
        return None
    steps = [_selection(concept, where), {"id": "answer", "operation": {
        "kind": "aggregate", "input_step_id": "selected", "method": "sum",
        "field": {"kind": "property", "key": key}, "output_unit_id": unit}}]
    return _proposal(steps, scope, f"Read stored {terminal} for " + (f"source room {room!r}" if room is not None else f"{category} occurrences") +
                     (f" on source floor {scope.floor!r}" if scope.floor is not None else " in the captured scope") + "; preserve source units and quantity basis.")


def _unit_suffix(kind, language="en"):
    lead = r",? in " if language == "en" else r",? (?:yksikössä )?"
    return "(?:" + lead + _UNITS[kind] + ")?"


def _parse_level_heights(engine, index, question, allowed):
    patterns = [
        ("en", r"(?:What are|List|Give me) the (?:floor-to-floor heights|floor to floor heights|storey-to-storey heights|story-to-story heights|elevation differences) "
         r"between (?P<all>all )?consecutive (?:levels|floors|storeys|stories)(?: (?P<scope>.+?))?[?.]?"),
        ("fi", r"(?:Mitkä ovat|Luettele|Laske) (?P<all>kaikkien )?peräkkäisten (?:kerrosten|tasojen) (?:väliset )?(?:kerroskorkeudet|korkeuserot)"
         r"(?: (?P<scope>.+?))?[?.]?"),
    ]
    for language, pattern in patterns:
        unit_prefix = r",? in " if language == "en" else r",? (?:yksikössä )?"
        unitless = re.sub(unit_prefix + _UNITS["length"] + r"(?=[?.]?$)", "", question, flags=_FLAGS)
        match = re.fullmatch(pattern, unitless, _FLAGS)
        if not match:
            continue
        suffix = match["scope"] or ""
        scope = _scope(suffix, language)
        current_view = re.fullmatch(r"in (?:this|the current) view" if language == "en" else r"(?:tässä|nykyisessä) näkymässä", suffix, _FLAGS)
        if scope is None or scope.floor is not None or (suffix and not scope.entire and not current_view):
            return None
        if not suffix and match["all"]:
            scope = _Scope(entire=True)
        wider = _scope_change(engine, scope, allowed)
        if wider is not None:
            return wider
        if not _model_matches(engine, scope.model_title):
            return None
        concept = "concept:storey"
        if concept not in engine.concept_ids or "table_calculate.consecutive_difference" not in engine.capabilities.operations:
            return None
        members = index.entities(engine, concept)
        if allowed is not None:
            members = members & allowed
        if len(members) < 2:
            return {"status": "missing_information", "interpretation":
                    "At least two native level records must belong to the captured source scope to calculate consecutive floor-to-floor heights. Include those records or choose entire-model scope.",
                    "explicitly_requests_entire_model": scope.entire, "steps": [], "output_step_id": None, "outputs": {}, "requests": []}
        elevation, building = attribute_key("Elevation"), property_key("SourceContext", "BuildingId")
        if elevation not in engine.properties or building not in engine.properties or "unit:m" not in engine.units:
            return None
        steps = [_selection(concept), {"id": "levels", "operation": {"kind": "project", "input_step_id": "selected", "fields": [
            {"kind": "entity_id", "key": "level_id"}, {"kind": "label", "key": "level"},
            {"kind": "property", "key": elevation}, {"kind": "property", "key": building}]}},
            {"id": "heights", "operation": {"kind": "table_calculate", "input_step_id": "levels", "operator": "consecutive_difference",
             "fields": [{"kind": "result_column", "key": elevation}], "order_by": {"kind": "result_column", "key": elevation},
             "group_by": [{"kind": "result_column", "key": building}], "value_key": "floor_to_floor", "next_key": "next_level", "output_unit_id": "unit:m"}}]
        return _proposal(steps, scope, "Calculate differences between consecutive recorded storey elevations, separately for each native building identity, preserving level names and metre units. These are level-to-level heights, not clear room heights.")
    return None


def _parse_quantity(engine, index, question, allowed):
    # Try the floor-qualified room form first, so quoted names containing
    # apostrophes or parentheses retain their literal source spelling.
    for language, prefix in [
        ("en", r"What is the net floor area of (?:the )?room "),
        ("fi", r"(?:Mikä on|Kuinka suuri on) huoneen "),
    ]:
        fi_metric = r" (?:nettolattiapinta-ala|nettopinta-ala|nettoala)" if language == "fi" else ""
        for with_floor in (True, False):
            floor = (r" on " if language == "en" else r" (?:kerroksessa|tasolla) ") + "(?P<floor>" + _QUOTED + ")" if with_floor else ""
            pattern = prefix + "(?P<room>" + _QUOTED + ")" + fi_metric + floor + _unit_suffix("area", language) + r"\?"
            match = re.fullmatch(pattern, question, _FLAGS)
            if match:
                scope = _Scope(floor=_literal(match["floor"]) if with_floor else None)
                return _quantity(engine, index, ("space", "NetFloorArea", "area", "unit:m2"), scope, _literal(match["room"]), allowed)
    for phrase, metric in _EN_METRICS.items():
        match = re.fullmatch("What is the " + re.escape(phrase) + r"(?: (?P<scope>.+?))?" + _unit_suffix(metric[2]) + r"\?", question, _FLAGS)
        if match:
            scope = _scope(match["scope"] or "")
            if scope is not None:
                return _quantity(engine, index, metric, scope, allowed=allowed)
    # Compositional Finnish totals: the noun and requested dimension must agree.
    match = re.fullmatch(r"(?:Mikä on|Kuinka suuri on) (?:kaikkien )?(?P<noun>huoneiden|tilojen|seinien|laattojen) "
                         r"(?:yhteenlaskettu )?(?P<metric>nettolattiapinta-ala|nettopinta-ala|nettosivupinta-ala|nettotilavuus|pituus)"
                         r"(?: (?P<scope>.+?))?" + r"(?:,? (?P<unit>neliömetreinä|kuutiometreinä|metreinä|m²|m2|m³|m3|m))?\?", question, _FLAGS)
    if match:
        noun, metric_name = match["noun"].casefold(), match["metric"].casefold()
        category = {"huoneiden": "space", "tilojen": "space", "seinien": "wall", "laattojen": "slab"}[noun]
        metrics = {("space", "nettolattiapinta-ala"): ("NetFloorArea", "area", "unit:m2"),
                   ("space", "nettopinta-ala"): ("NetFloorArea", "area", "unit:m2"),
                   ("wall", "nettosivupinta-ala"): ("NetSideArea", "area", "unit:m2"),
                   ("wall", "nettotilavuus"): ("NetVolume", "volume", "unit:m3"),
                   ("wall", "pituus"): ("Length", "length", "unit:m"),
                   ("slab", "nettotilavuus"): ("NetVolume", "volume", "unit:m3")}
        metric = metrics.get((category, metric_name))
        scope = _scope(match["scope"] or "", "fi")
        if metric and scope is not None and (match["unit"] is None or re.fullmatch(_UNITS[metric[1]], match["unit"], _FLAGS)):
            return _quantity(engine, index, (category, *metric), scope, allowed=allowed)
    return None


def _topology(engine, index, relation, scope, room, count, allowed):
    wider = _scope_change(engine, scope, allowed)
    if wider is not None:
        return wider
    if not _model_matches(engine, scope.model_title):
        return None
    if "concept:space" not in engine.concept_ids:
        return None
    members = set(index.entities(engine, "concept:space"))
    if allowed is not None:
        members &= allowed
    okay, where, native_floor = _where(engine, index, scope, members, allowed)
    if not okay:
        return None
    wider = _floor_scope_change(engine, index, scope, native_floor, allowed)
    if wider is not None:
        return wider
    if room is not None:
        resolved = _room(engine, index, room, native_floor, allowed)
        if resolved is None:
            return None
        predicates = ([where] if where else []) + resolved[1]
        where = predicates[0] if len(predicates) == 1 else {"kind": "all", "operands": predicates}
    steps = [_selection("concept:space", where), {"id": "topology", "operation": {
        "kind": "spatial_query", "input_step_id": "selected", "relation": relation, "method": "auto"}}]
    if count:
        source = "topology"
        if relation != "outdoor_access":
            steps.append({"id": "neighbors", "operation": {"kind": "related_entities", "input_step_id": source, "column": "related"}})
            source = "neighbors"
        steps.append({"id": "answer", "operation": {"kind": "aggregate", "input_step_id": source, "method": "count"}})
    meaning = {"door_connections": "direct modeled connections through physical door boundaries",
               "boundary_neighbors": "native corresponding boundaries or qualified boundary adjacency; unresolved geometric candidates remain partial",
               "outdoor_access": "modeled direct outdoor access through physical external door boundaries"}[relation]
    return _proposal(steps, scope, ("Count distinct source spaces with " if count else "Inspect ") + meaning +
                     (f" for literal room {room!r}." if room is not None else " in the captured scope. Missing topology never establishes physical absence."))


def _parse_topology(engine, index, question, allowed):
    # Bare names are single literal identifiers; multiword names must be
    # quoted. Complete grammar matching rejects appended clauses/instructions.
    name = r"(?P<room>" + _QUOTED + r"|[\w][\w.\-/:]*)"
    patterns = [
        ("en", r"(?P<ask>Which|What|How many) (?:rooms|spaces) (?:are )?(?P<relation>adjacent to|next to|directly connected to|connected to) (?:the )?(?:room|space) " + name + r"(?: (?:via|through|by) doors)?(?: (?P<scope>.+?))?\?"),
        ("fi", r"(?P<ask>Mitkä|Kuinka monet) (?:huoneet|tilat) (?:ovat )?(?P<relation>suoraan yhteydessä|yhteydessä) (?:huoneeseen|tilaan) " + name + r"(?: ovien kautta)?(?: (?P<scope>.+?))?\?"),
        ("fi", r"(?P<ask>Mitkä|Kuinka monet) (?:huoneet|tilat) ovat (?:huoneen|tilan) " + name + r" (?P<relation>vieressä|naapurissa)(?: (?P<scope>.+?))?\?"),
    ]
    for language, pattern in patterns:
        match = re.fullmatch(pattern, question, _FLAGS)
        if not match:
            continue
        scope = _scope(match["scope"] or "", language)
        if scope is None:
            return None
        room = _literal(match["room"]) if match["room"].startswith(("'", '"', "„", "“", "«")) else match["room"]
        relation = "boundary_neighbors" if match["relation"].casefold() in {"adjacent to", "next to", "vieressä", "naapurissa"} else "door_connections"
        if relation == "boundary_neighbors" and re.search(r" (?:via|through|by) doors\b| ovien kautta\b", question, _FLAGS):
            return None
        return _topology(engine, index, relation, scope, room, match["ask"].casefold() in {"how many", "kuinka monet"}, allowed)
    for language, pattern in [
        ("en", r"(?P<ask>Which|What|How many) (?:rooms|spaces) have (?:direct )?access to outdoor (?:space|spaces|areas)(?: (?P<scope>.+?))?\?"),
        ("fi", r"(?P<ask>Millä|Kuinka monella) (?:huoneilla|tiloilla) on (?:suora )?käynti ulos(?: (?P<scope>.+?))?\?"),
        ("fi", r"(?P<ask>Mistä|Kuinka monesta) (?:huoneesta|tilasta) on (?:suora )?käynti ulos(?: (?P<scope>.+?))?\?"),
    ]:
        match = re.fullmatch(pattern, question, _FLAGS)
        if match:
            scope = _scope(match["scope"] or "", language)
            return _topology(engine, index, "outdoor_access", scope, None,
                             match["ask"].casefold() in {"how many", "kuinka monella", "kuinka monesta"}, allowed) if scope is not None else None
    return None


def _parse_type_inventory(engine, index, question, allowed):
    singular = "(?:" + "|".join(re.escape(name) for name in sorted(_TYPE_CATEGORIES, key=len, reverse=True)) + ")"
    plural_names = {name + ("" if name == "furniture" else "s"): category for name, category in _TYPE_CATEGORIES.items()}
    plural = "(?:" + "|".join(re.escape(name) for name in sorted(plural_names, key=len, reverse=True)) + ")"
    noun = r"(?:(?P<single>" + singular + r") types|(?:different )?types of (?P<plural>" + plural + r"))"
    trailer = (r"(?:,? (?:(?:with|including|along with|and) (?:their )?(?:respective )?"
               r"(?P<quantity>quantities|counts|quantity distribution|element counts)(?P<percent> and percentages)?"
               r"|and how many of each(?: type)?(?: are there)?))?")
    patterns = [r"(?:What|Which) " + noun + r" are (?:used|present|installed)(?: (?P<scope>.+?))?" + trailer + r"\?",
                r"What are (?:the )?" + noun + r" (?:used|present|installed)(?: (?P<scope>.+?))?" + trailer + r"\?"]
    for pattern in patterns:
        match = re.fullmatch(pattern, question, _FLAGS)
        if not match:
            continue
        category = (_TYPE_CATEGORIES.get(match["single"].casefold()) if match["single"] else plural_names.get(match["plural"].casefold()))
        scope_text = match["scope"] or ""
        scope = _scope("" if scope_text.casefold() == "here" else scope_text)
        if scope is None:
            return None
        proposal = _count(engine, index, category, scope, True, allowed)
        if proposal is not None and proposal["status"] == "ready" and match["percent"]:
            previous = proposal["output_step_id"]
            proposal["steps"].append({"id": "percentages", "operation": {"kind": "table_calculate", "input_step_id": previous,
                "operator": "percent_of_total", "fields": [{"kind": "result_column", "key": "value"}],
                "value_key": "percentage", "output_unit_id": "unit:%"}})
            proposal["output_step_id"] = "percentages"
            proposal["interpretation"] += " Percentages use the captured source occurrence count as denominator."
        return proposal
    return None


def _parse_loadbearing_volume(engine, index, question, allowed):
    patterns = [
        ("en", r"What is the (?P<metric>percentage|proportion) of wall volume that is load-bearing(?: (?P<scope>in .+?))?(?:,? including (?:the )?volume breakdown)?\?"),
        ("en", r"What (?P<metric>percentage|proportion) of (?:the )?(?:total )?wall volume is load-bearing(?: (?P<scope>in .+?))?(?:,? including (?:the )?volume breakdown)?\?"),
        ("fi", r"Mikä (?P<metric>prosenttiosuus|osuus) seinien (?:kokonais)?tilavuudesta on kantavaa(?: (?P<scope>.+?))?(?:,? mukaan lukien tilavuusjakauma)?\?"),
    ]
    for language, pattern in patterns:
        match = re.fullmatch(pattern, question, _FLAGS)
        if not match:
            continue
        scope = _scope(match["scope"] or "", language)
        if scope is None:
            return None
        wider = _scope_change(engine, scope, allowed)
        if wider is not None:
            return wider
        if not _model_matches(engine, scope.model_title):
            return None
        if "concept:wall" not in engine.concept_ids:
            return None
        members = set(index.entities(engine, "concept:wall"))
        if allowed is not None:
            members &= allowed
        okay, where, native_floor = _where(engine, index, scope, members, allowed)
        if not okay:
            return None
        wider = _floor_scope_change(engine, index, scope, native_floor, allowed)
        if wider is not None:
            return wider
        loadbearing = property_key("Pset_WallCommon", "LoadBearing")
        if loadbearing not in engine.properties or engine.properties[loadbearing].value_kind != "boolean":
            return None
        # Generic volume is retained as source-stored modeled volume. It is
        # never relabeled net/gross; prefer the literal Volume semantics when
        # present, otherwise an explicit native NetVolume may answer with its
        # narrower basis made visible in the interpretation and result units.
        generic_keys = [key for key in index.property_names.get(_terminal("Volume"), ())
                        if engine.properties[key].quantity_kind == "volume"]
        engine.ensure_fields(members, generic_keys)
        has_generic = any(engine.facts.get((identifier, key)) for identifier in members for key in generic_keys)
        terminal = "Volume" if has_generic else "NetVolume"
        volume = _quantity_key(engine, index, members, terminal, "volume", "unit:m3")
        if volume is None:
            return None
        steps = [_selection("concept:wall", where), {"id": "volumes", "operation": {
            "kind": "aggregate", "input_step_id": "selected", "method": "sum", "field": {"kind": "property", "key": volume},
            "group_by": [{"kind": "property", "key": loadbearing}], "value_key": "volume", "output_unit_id": "unit:m3",
            "missing_values": "fail", "missing_groups": "fail"}}, {"id": "shares", "operation": {
            "kind": "table_calculate", "input_step_id": "volumes", "operator": "percent_of_total",
            "fields": [{"kind": "result_column", "key": "volume"}], "value_key": "percentage", "output_unit_id": "unit:%"}}]
        meaning = "source-stored modeled wall volume (not a net/gross conversion)" if terminal == "Volume" else "explicit native net wall volume"
        return _proposal(steps, scope, f"Sum {meaning} from {volume}, grouped by the recorded boolean Pset_WallCommon.LoadBearing, then compute each group's percentage of that captured total. Missing volume or classification prevents a complete percentage; no null is treated as false or zero.")
    return None


def _route(engine, index, scope, room, mode, width, allowed):
    wider = _scope_change(engine, scope, allowed)
    if wider is not None:
        return wider
    if not _model_matches(engine, scope.model_title) or "route_query" not in engine.capabilities.operations:
        return None
    if "concept:space" not in engine.concept_ids:
        return None
    members = set(index.entities(engine, "concept:space"))
    if allowed is not None:
        members &= allowed
    okay, where, native_floor = _where(engine, index, scope, members, allowed)
    if not okay:
        return None
    wider = _floor_scope_change(engine, index, scope, native_floor, allowed)
    if wider is not None:
        return wider
    if room is not None:
        resolved = _room(engine, index, room, native_floor, allowed)
        if resolved is None:
            return None
        predicates = ([where] if where else []) + resolved[1]
        where = predicates[0] if len(predicates) == 1 else {"kind": "all", "operands": predicates}
    steps = [_selection("concept:space", where), {"id": "route", "operation": {
        "kind": "route_query", "input_step_id": "selected", "mode": mode,
        "start_basis": "farthest_sampled" if mode == "farthest" else "modeled_interior_point",
        "target_basis": "certified_fire_exit", "include_stairs": True}}]
    if width:
        interpretation = ("Inspect nearest-exit modeled paths from each authorized source room, including source nominal door widths, geometric opening/corridor widths and unknown actual clear width. "
                          "These are qualified source/model measurements, not a certified emergency-route width or a claim that every possible escape path was modeled.")
    elif mode == "farthest":
        interpretation = ("Estimate the longest nearest-exit modeled walking path among bounded sampled points in authorized source spaces, retaining the physical path and modeled stair transitions. "
                          "Sampling does not prove the mathematical farthest point or a code-compliant escape route.")
    else:
        interpretation = (f"Resolve literal source room {room!r} and estimate its nearest-exit modeled walking path from a native interior point, retaining physical XYZ path points and source room/opening/stair inputs. "
                          "The room's functional description is not inferred from its name.")
    interpretation += " Request emergency-exit classification; any fallback to a recorded exterior boundary remains explicitly uncertified/partial. All prerequisites remain within the captured scope."
    return _proposal(steps, scope, interpretation)


def _parse_route(engine, index, question, allowed):
    room = r"(?P<room>" + _QUOTED + r"|[\w][\w.\-/:]*)"
    ending_en = r"(?: (?P<scope>.+?))?(?:,? including (?:the )?path(?: taken)?(?: for this estimation)?)?\?"
    ending_fi = r"(?: (?P<scope>.+?))?(?:,? mukaan lukien (?:kuljettu )?reitti)?\?"
    patterns = [
        ("en", r"What is the (?:estimated )?(?:walking |route )?distance from (?:the )?(?:treatment )?(?:room|space) " + room + r" to the nearest (?:emergency|fire) exit" + ending_en),
        ("en", r"How far is the nearest (?:emergency|fire) exit from (?:the )?(?:room|space) " + room + ending_en),
        ("fi", r"Mikä on (?:arvioitu )?(?:kävely)?etäisyys (?:huoneesta|tilasta) " + room + r" lähimmälle (?:hätäuloskäynnille|hätäpoistumistielle)" + ending_fi),
    ]
    for language, pattern in patterns:
        match = re.fullmatch(pattern, question, _FLAGS)
        if match:
            scope = _scope(match["scope"] or "", language)
            name = _literal(match["room"]) if match["room"].startswith(("'", '"', "„", "“", "«")) else match["room"]
            return _route(engine, index, scope, name, "shortest", False, allowed) if scope is not None else None
    for language, pattern in [
        ("en", r"What is the (?:estimated )?(?:walking |route )?distance from the (?:furthest|farthest) point to the nearest (?:emergency|fire) exit" + ending_en),
        ("fi", r"Mikä on (?:arvioitu )?etäisyys kauimmaisesta pisteestä lähimmälle (?:hätäuloskäynnille|hätäpoistumistielle)" + ending_fi),
    ]:
        match = re.fullmatch(pattern, question, _FLAGS)
        if match:
            scope = _scope(match["scope"] or "", language)
            return _route(engine, index, scope, None, "farthest", False, allowed) if scope is not None else None
    for language, pattern in [
        ("en", r"What is the (?:modeled |modelled )?width of (?:the )?emergency escape routes(?: (?P<scope>.+?))?\?"),
        ("fi", r"Mikä on hätäpoistumisreittien (?:mallinnettu )?leveys(?: (?P<scope>.+?))?\?"),
    ]:
        match = re.fullmatch(pattern, question, _FLAGS)
        if match:
            scope = _scope(match["scope"] or "", language)
            return _route(engine, index, scope, None, "shortest", True, allowed) if scope is not None else None
    return None


def try_plan(engine, question: str, allowed_entity_ids=None) -> dict | None:
    """Compile one complete, unambiguous source-grounded grammatical question.

    Pass the captured allowed entity IDs before name/property resolution; None
    permits inspection across this engine's complete source inventory. The
    caller must still apply the production captured-scope/model gate and
    validate/execute this proposal. Matching syntax never authorizes a wider
    scope, changes the source or establishes a correct answer by itself.
    """
    if not isinstance(question, str) or not question or len(question) > 1200 or any(ord(c) < 32 or ord(c) == 127 for c in question):
        return None
    question = question.strip()
    allowed = (allowed_entity_ids if isinstance(allowed_entity_ids, (set, frozenset)) else set(allowed_entity_ids)) if allowed_entity_ids is not None else None
    if allowed is not None and not allowed <= engine.entities.keys():
        return None
    index = _index(engine)
    german_category = "(?:" + "|".join(re.escape(name) for name in sorted(_DE_CATEGORIES, key=len, reverse=True)) + ")"
    match = re.fullmatch(r"Wie viele (?P<category>" + german_category + r") enthält (?:das|dieses) Modell (?P<title>" + _QUOTED + r")\?", question, _FLAGS)
    if match:
        return _count(engine, index, _DE_CATEGORIES[match["category"].casefold()],
                      _Scope(entire=True, model_title=_literal(match["title"])), False, allowed)
    match = re.fullmatch(r"Wie viele (?P<category>" + german_category + r") sind in (?:dieser|der aktuellen) Ansicht (?:sichtbar|vorhanden)\?", question, _FLAGS)
    if match:
        return _count(engine, index, _DE_CATEGORIES[match["category"].casefold()], _Scope(), False, allowed)
    route = _parse_route(engine, index, question, allowed)
    if route is not None:
        return route
    heights = _parse_level_heights(engine, index, question, allowed)
    if heights is not None:
        return heights
    topology = _parse_topology(engine, index, question, allowed)
    if topology is not None:
        return topology
    loadbearing = _parse_loadbearing_volume(engine, index, question, allowed)
    if loadbearing is not None:
        return loadbearing
    inventory = _parse_type_inventory(engine, index, question, allowed)
    if inventory is not None:
        return inventory
    for language, vocabulary, pattern in [
        ("en", _EN_CATEGORIES, r"How many (?P<category>" + _EN_CATEGORY + r")(?P<tail>[^?]*)\?"),
        ("fi", _FI_CATEGORIES, r"Kuinka monta (?P<category>" + _FI_CATEGORY + r")(?P<tail>[^?]*)\?"),
    ]:
        match = re.fullmatch(pattern, question, _FLAGS)
        if not match:
            continue
        category = vocabulary.get(match["category"].casefold())
        if category is None:
            return None
        tail, grouped = match["tail"].strip(), False
        if language == "en":
            # Grouping is expressed explicitly; it never counts unused type
            # definitions or merges separate types that happen to share a name.
            for suffix in (" by type", " of each type"):
                if tail.casefold().endswith(suffix):
                    tail, grouped = tail[:-len(suffix)], True
                    break
            if tail.casefold().startswith("of each type "):
                tail, grouped = tail[len("of each type "):], True
        scope = _count_scope(tail, language)
        return _count(engine, index, category, scope, grouped, allowed) if scope is not None else None
    return _parse_quantity(engine, index, question, allowed)

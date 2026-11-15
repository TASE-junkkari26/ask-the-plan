"""Bounded native enumeration/list properties; no executable references.

The recorded selected enumeration values are facts. The optional enumeration
vocabulary is never substituted for those selections or interpreted as an
exhaustive object inventory.
"""
from __future__ import annotations

import math

import ifcopenshell.util.unit as unit_util

from contracts import models as m
from .units import MEASURE_KINDS, UNIT_TYPES
from .source_quantities import native_quantity_basis

MAX_COLLECTION_VALUES = 256
MAX_COLLECTION_TEXT = 65536


def collection_property_value(extractor, prop):
    if prop.is_a("IfcPropertyEnumeratedValue"):
        raw_values = prop.EnumerationValues
        reference = prop.EnumerationReference
        explicit_unit = reference.Unit if reference is not None else None
    elif prop.is_a("IfcPropertyListValue"):
        raw_values = prop.ListValues
        explicit_unit = prop.Unit
    else:
        return None, "not_extracted"
    if raw_values is None:
        return None, "explicit_null"
    if len(raw_values) > MAX_COLLECTION_VALUES:
        extractor.warnings.add("A native list/enumerated property exceeded the bounded 256-value extraction limit.")
        return None, "not_extracted"
    values, text_size = [], 0
    for raw in raw_values:
        # IFC simple/measure values expose wrappedValue; arbitrary entity or
        # nested property references are deliberately outside this adapter.
        if raw is None or not hasattr(raw, "wrappedValue"):
            return None, "not_extracted"
        value, measure_class = raw.wrappedValue, raw.is_a()
        if isinstance(value, bool):
            parsed = m.BooleanValue(kind="boolean", value=value)
        elif isinstance(value, str):
            text_size += len(value)
            if text_size > MAX_COLLECTION_TEXT:
                extractor.warnings.add("A native list/enumerated property exceeded the bounded text extraction limit.")
                return None, "not_extracted"
            parsed = m.TextValue(kind="text", value=m.LocalizedText(text=value))
        elif isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                return None, "not_extracted"
            if measure_class == "IfcCountMeasure" and value >= 0 and float(value).is_integer():
                parsed = m.CountValue(kind="count", value=int(value))
            else:
                unit = explicit_unit
                if unit is None:
                    # Resolve each member's declared IFC measure separately;
                    # the unit of the first list member cannot establish the
                    # dimensions of a later, differently typed member.
                    unit_type = unit_util.get_measure_unit_type(measure_class)
                    if unit_type is not None:
                        unit = unit_util.get_project_unit(extractor.model, unit_type)
                kind = UNIT_TYPES.get(getattr(unit, "UnitType", None))
                if measure_class in MEASURE_KINDS:
                    kind = MEASURE_KINDS[measure_class]
                else:
                    for term, candidate in [("Length", "length"), ("Area", "area"), ("Volume", "volume"),
                                            ("Mass", "mass"), ("Time", "time"), ("Angle", "angle"), ("Ratio", "ratio")]:
                        if term in measure_class:
                            kind = candidate
                            break
                parsed = extractor.quantity(value, kind or "number", prop, unit=unit,
                    measure_class=measure_class, explicit=explicit_unit is not None,
                    basis=native_quantity_basis(prop.Name, kind))
        else:
            return None, "not_extracted"
        values.append(parsed)
    return m.ListValue(kind="list", items=values), "present"

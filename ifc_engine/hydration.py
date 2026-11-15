"""Bounded on-demand property extraction from a retained immutable IFC model.

An empty fact list means source absence only after its entity/key pair has been
checked. Callers merge returned evidence atomically and reset only between
questions, after the previous answer has captured its source facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
import threading

import ifcopenshell.util.unit as unit_util

from contracts import models as m
from .catalog import ATTRIBUTES, CLASS_KEY, LENGTH_ATTRIBUTES, attribute_key, property_key
from .type_candidates import absent_candidate_keys, emit_ambiguous_inheritance, inherited_property_records, typing_anchor_ids

DERIVED_GROUPS = ("SourceContext", "SourceMaterial", "SourceMaterialThickness", "SourceQuantity")


class HydrationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class HydrationBatch:
    facts: list[m.Fact] = field(default_factory=list)
    anchors: list[m.EvidenceAnchor] = field(default_factory=list)
    units: list[m.Unit] = field(default_factory=list)
    checked_pairs: set[tuple[str, str]] = field(default_factory=set)


class _Facts(list):
    """Collect only requested facts and enforce the live-question memory bound."""

    def __init__(self, requested, remaining, ambiguous_keys=()):
        super().__init__()
        self.requested, self.remaining, self.ids = requested, remaining, set()
        self.ambiguous_keys = ambiguous_keys

    def append(self, value):
        if (value.subject_id, value.property_key) not in self.requested or value.id in self.ids:
            return
        if len(self) >= self.remaining:
            raise HydrationError("unsupported_operation", "The bounded property-fact budget for this question was exhausted.")
        if value.property_key in self.ambiguous_keys:
            value = value.model_copy(update={"status": "ambiguous", "value": None})
        self.ids.add(value.id)
        super().append(value)

    def extend(self, values):
        for value in values:
            self.append(value)


class NativeHydrator:
    def __init__(self, extractor, objects, definitions, types, *, max_pairs=200000, max_facts=200000):
        if max_pairs < 1 or max_facts < 1:
            raise ValueError("Hydration budgets must be positive")
        self.extractor, self.objects = extractor, objects
        self.definitions, self.types = definitions, types
        self.max_pairs, self.max_facts = max_pairs, max_facts
        self.by_entity = {extractor.entity_id(obj): obj for obj in objects.values()}
        self._core_pairs = {(fact.subject_id, fact.property_key) for fact in extractor.facts}
        self._core_fact_ids = {fact.id for fact in extractor.facts}
        self._base_anchor_ids = set(extractor.anchors)
        self._checked, self._emitted = set(), set()
        self._source_checked = False
        self._enrichment_indexes = None
        self._lock = threading.RLock()
        self._closed = False
        # This is IfcOpenShell's native cache of explicit project-unit records;
        # it does not infer area or volume units from a length unit.
        unit_util.cache_units(extractor.model)

    def reset(self):
        """Return removable fact IDs; never call during an active question."""
        with self._lock:
            removed = sorted(self._emitted - self._core_fact_ids)
            self._checked.clear()
            self._emitted.clear()
            self._source_checked = False
            for identifier in set(self.extractor.anchors) - self._base_anchor_ids:
                del self.extractor.anchors[identifier]
            return removed

    def is_checked(self, entity_id, property_key):
        return (entity_id, property_key) in self._core_pairs or (entity_id, property_key) in self._checked

    def close(self):
        """Release native source indexes when the bounded model session ends."""
        with self._lock:
            self._closed = True
            self._enrichment_indexes = None
            self.by_entity.clear()
            self.objects.clear()
            self.definitions.clear()
            self.types.clear()
            getattr(self.extractor, "typing_relations", {}).clear()
            if self.extractor.model is not None:
                getattr(self.extractor.model, "unit_cache", {}).clear()
            self.extractor.model = None

    def ensure_fields(self, entity_ids, property_keys):
        with self._lock:
            return self._ensure_fields(set(entity_ids), set(property_keys))

    def _ensure_fields(self, entities, keys):
        if self._closed:
            raise HydrationError("missing_source", "The retained IFC source session has been closed.")
        if not entities or not keys:
            return HydrationBatch()
        if entities - self.by_entity.keys():
            raise HydrationError("missing_source", "A requested property object is not in the retained IFC revision.")
        if len(entities) * len(keys) > self.max_pairs:
            raise HydrationError("unsupported_operation", "The requested entity/property batch exceeds the bounded hydration work budget.")
        requested = {(identifier, key) for identifier in entities for key in keys
                     if not self.is_checked(identifier, key)}
        if not requested:
            return HydrationBatch()
        if len(self._checked) + len(requested) > self.max_pairs:
            raise HydrationError("unsupported_operation", "The bounded property-inspection budget for this question was exhausted.")
        extractor = self.extractor
        if not self._source_checked:
            from .ingest import file_sha256
            try:
                digest = file_sha256(extractor.path)
            except OSError:
                raise HydrationError("missing_source", "The original IFC source revision is unavailable for property inspection.") from None
            if digest != extractor.digest:
                raise HydrationError("conflicting_evidence", "The original source bytes differ from the retained IFC revision.")
            self._source_checked = True

        original_facts = extractor.facts
        collector = _Facts(requested, self.max_facts - len(self._emitted), getattr(extractor, "ambiguous_property_keys", set()))
        extractor.facts = collector
        original_filter = getattr(extractor, "requested_property_keys", None)
        extractor.requested_property_keys = keys
        old_anchors = set(extractor.anchors)
        needed_by_entity = defaultdict(set)
        for identifier, key in requested:
            needed_by_entity[identifier].add(key)
        try:
            for identifier in sorted(entities):
                obj = self.by_entity[identifier]
                needed = needed_by_entity[identifier]
                if CLASS_KEY in needed:
                    extractor.add_fact(identifier, CLASS_KEY, ["class"], obj,
                        m.TextValue(kind="text", value=m.LocalizedText(text=obj.is_a())))
                for name in ATTRIBUTES:
                    key = attribute_key(name)
                    if key not in needed or not hasattr(obj, name):
                        continue
                    value = getattr(obj, name)
                    extractor.add_fact(identifier, key, [name], obj,
                        m.TextValue(kind="text", value=m.LocalizedText(text=str(value))) if value is not None else None,
                        "present" if value is not None else "explicit_null")
                for name in LENGTH_ATTRIBUTES:
                    key = attribute_key(name)
                    if key not in needed or not hasattr(obj, name):
                        continue
                    value = getattr(obj, name)
                    extractor.add_fact(identifier, key, [name], obj,
                        extractor.quantity(value, "length", obj,
                            unit=unit_util.get_project_unit(extractor.model, "LENGTHUNIT"), measure_class="IfcLengthMeasure") if value is not None else None,
                        "present" if value is not None else "explicit_null")
                other_attributes = needed - {CLASS_KEY, *(attribute_key(name) for name in (*ATTRIBUTES, *LENGTH_ATTRIBUTES))}
                if any(key.startswith("ifc:attribute/") for key in other_attributes):
                    extractor.metadata_facts(obj, identifier)
                pset_keys = {key for key in needed if key.startswith("ifc:property/") and not any(
                    key.startswith(property_key(group, "")) for group in DERIVED_GROUPS)}
                if pset_keys:
                    own = extractor.property_records([*self.definitions.get(obj.id(), []), *(getattr(obj, "HasPropertySets", None) or [])])
                    inherited = inherited_property_records(extractor, self.types, obj.id())
                    inherited_anchors = typing_anchor_ids(extractor, obj, self.types) if inherited else []
                    # Occurrence values override type values by full property
                    # path, including explicit nulls and unsupported structures.
                    for key, entries in (inherited | own).items():
                        if key not in pset_keys:
                            continue
                        for path, record in entries:
                            value, status = extractor.property_value(record)
                            extractor.add_fact(identifier, key, path, record, value, status,
                                extra_anchors=inherited_anchors if key not in own else [])
                    for key in (absent_candidate_keys(extractor, self.types, obj.id()) - own.keys()) & pset_keys:
                        emit_ambiguous_inheritance(extractor, obj, key, inherited[key], self.types)
            derived = {key for key in keys if any(key.startswith(property_key(group, ""))
                for group in DERIVED_GROUPS)}
            if derived:
                from .enrichment import enrich_occurrences, enrichment_indexes
                if self._enrichment_indexes is None:
                    self._enrichment_indexes = enrichment_indexes(extractor.model)
                subset = {self.by_entity[identifier].id(): self.by_entity[identifier] for identifier in entities
                          if any((identifier, key) in requested for key in derived)}
                enrich_occurrences(extractor, subset, self.types, indexes=self._enrichment_indexes, property_keys=derived)
            facts = list(collector)
            anchor_ids = {anchor for fact in facts for anchor in fact.provenance.anchor_ids}
            for fact in facts:
                if fact.value is not None:
                    anchor_ids.update(anchor for value in m.walk_values(fact.value)
                        if isinstance(value, m.QuantityValue) for anchor in value.unit_anchor_ids)
            result = HydrationBatch(facts=facts,
                anchors=[extractor.anchors[identifier] for identifier in sorted(anchor_ids)],
                units=list(extractor.units.values()), checked_pairs=requested)
        except HydrationError:
            for identifier in set(extractor.anchors) - old_anchors:
                del extractor.anchors[identifier]
            raise
        except Exception:
            for identifier in set(extractor.anchors) - old_anchors:
                del extractor.anchors[identifier]
            raise HydrationError("incomplete_coverage", "Requested IFC properties could not be inspected unambiguously from the retained source.") from None
        finally:
            extractor.facts = original_facts
            if original_filter is None:
                try:
                    del extractor.requested_property_keys
                except AttributeError:
                    pass
            else:
                extractor.requested_property_keys = original_filter
        self._checked.update(requested)
        self._emitted.update(fact.id for fact in result.facts)
        return result

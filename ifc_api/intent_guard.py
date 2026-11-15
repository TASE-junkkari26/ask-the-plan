"""Conservative source-identity binding for explicitly named singular rooms.

This rejects a demonstrably ignored literal anchor; it does not certify natural
language interpretation or source topology. Only authorized source labels are
examined, and only a unique native Name/LongName identity activates the guard.
"""
from __future__ import annotations

import re

from contracts import models as m
from ifc_engine.catalog import attribute_key
from .fast_plans import _fold, _index, _room, _text

_NOUN = r"(?:room|space|huone(?:en|esta|eseen|essa|tta)?|tila(?:n|sta|an|ssa)?)"
_PREFIX = re.compile(r"\b" + _NOUN + r"\s+(?:(?:named|labelled|labeled|nimeltä)\s+)?", re.IGNORECASE)
_REASON = ("The question names one uniquely identified source room, but an answer output does not depend on that room. "
           "Bind the literal room using an exact source identity, a relation target, or a measurement reference before deriving the answer.")


def _mentioned(engine, question, allowed):
    index = _index(engine)
    candidates = set()
    # Candidate labels are immutable source text. Hydrate native fields only
    # for authorized rooms whose literal alias follows an explicit singular noun.
    for match in _PREFIX.finditer(question):
        tail = question[match.end():]
        if tail.startswith(("'", '"', "„", "“", "«")):
            quote = {"„": "“", "“": "”", "«": "»"}.get(tail[0], tail[0])
            end = tail.find(quote, 1)
            aliases = [tail[1:end]] if end > 1 else []
        else:
            folded = _fold(tail)
            aliases = [alias for alias, identifiers in index.rooms.items()
                       if identifiers & allowed and folded.startswith(alias)
                       and (len(folded) == len(alias) or not (folded[len(alias)].isalnum() or folded[len(alias)] in "._-"))]
            # Longest literal prevents a Name prefix from binding a different
            # combined room label. It never guesses a room function.
            if aliases:
                aliases = [max(aliases, key=len)]
        for alias in aliases:
            resolved = _room(engine, index, alias, None, allowed)
            if resolved is not None:
                candidates.add(resolved[0])
    return next(iter(candidates)) if len(candidates) == 1 else None


def _predicate_binds(predicate, anchor, texts, native, space_selection):
    if predicate is None:
        return False
    if predicate.kind == "all":
        return any(_predicate_binds(item, anchor, texts, native, space_selection) for item in predicate.operands)
    if predicate.kind == "any":
        return all(_predicate_binds(item, anchor, texts, native, space_selection) for item in predicate.operands)
    if predicate.kind == "related_to":
        return set(predicate.entity_ids) == {anchor}
    if predicate.kind != "compare" or predicate.operator != "eq":
        return False
    field, value = predicate.field, predicate.value
    if field.kind == "entity_id" and isinstance(value, m.ReferencesValue):
        return value.entity_ids == [anchor]
    if not isinstance(value, m.TextValue):
        return False
    if field.kind == "native_identifier":
        return (field.key != "ifc_guid" or space_selection) and field.key in native and value.value.text == native[field.key]
    if not space_selection:
        return False
    if field.kind == "property":
        return field.key in texts and value.value.text == texts[field.key]
    if field.kind == "label":
        return value.value.text == texts.get("primary_label")
    return False


def check_room_binding(engine, question, proposal, allowed_entity_ids=None):
    """Return a safe repair reason for ignored unique literal room anchors.

    Call after model aliases are decoded and before canonical plan validation.
    Each output must depend on the named room; unrelated unused steps cannot
    satisfy the check. OR predicates bind only when every alternative binds.
    This is a narrow intent guard, not an accuracy or completeness validator.
    """
    if proposal.status != "ready":
        return None
    allowed = set(engine.entities) if allowed_entity_ids is None else set(allowed_entity_ids)
    anchor = _mentioned(engine, question, allowed)
    if anchor is None:
        return None
    texts = {}
    for name in ("Name", "LongName"):
        value = _text(engine, anchor, attribute_key(name))
        if value is not None:
            resolved = _room(engine, _index(engine), value, None, allowed)
            if resolved is not None and resolved[0] == anchor:
                texts[attribute_key(name)] = value
    labels = engine.entities[anchor].labels
    if labels and sum(bool(engine.entities[identifier].labels and engine.entities[identifier].labels[0].text == labels[0].text)
                      for identifier in allowed if engine.entities[identifier].kind == "space") == 1:
        texts["primary_label"] = labels[0].text
    native = {}
    for anchor_id in engine.entity_anchors.get(anchor, ()):
        selector = engine.anchors[anchor_id].selector
        if selector.kind in {"step_id", "ifc_guid"} and not selector.property_path:
            native[selector.kind] = selector.value
    guid = native.get("ifc_guid")
    if guid is not None:
        matches = {identifier for identifier in allowed if engine.entities[identifier].kind == "space" and any(
            engine.anchors[anchor_id].selector.kind == "ifc_guid" and not engine.anchors[anchor_id].selector.property_path
            and engine.anchors[anchor_id].selector.value == guid for anchor_id in engine.entity_anchors.get(identifier, ()))}
        if matches != {anchor}:
            native.pop("ifc_guid", None)
    bound = {}
    for step in proposal.steps:
        operation = step.operation
        if operation.kind == "select":
            space_selection = bool(operation.concept_ids) and set(operation.concept_ids) <= {"concept:space", "ifc:IfcSpace"}
            bound[step.id] = _predicate_binds(operation.where, anchor, texts, native, space_selection)
        else:
            inputs = getattr(operation, "input_step_ids", []) or [getattr(operation, "input_step_id", None)]
            component = getattr(operation, "component_step_id", None)
            if component:
                inputs = [*inputs, component]
            target = getattr(operation, "target_step_id", None)
            if target:
                inputs = [*inputs, target]
            bound[step.id] = any(bound.get(identifier, False) for identifier in inputs)
            if operation.kind == "measure" and operation.reference_entity_ids == [anchor]:
                bound[step.id] = True
    outputs = list(proposal.outputs.values()) or [proposal.output_step_id]
    return None if all(bound.get(identifier, False) for identifier in outputs) else _REASON

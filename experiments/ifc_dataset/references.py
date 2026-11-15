"""Evaluation-only reference loading, imported after predictions are durable.

This module must never be imported by the runtime planner or executor. Text
references are not automatically judged: a phrase match is not source truth.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from contracts.models import Unit
from ifc_engine.units import convert, standard_units


def load_references(dataset: Path, lines: set[int]) -> dict[int, dict]:
    result = {}
    with (dataset / "questions.jsonl").open(encoding="utf-8-sig") as stream:
        for line, raw in enumerate(stream, 1):
            if line in lines:
                value = json.loads(raw)
                result[line] = {name: value.get(name) for name in ("answer", "unit", "type")}
    if lines - result.keys():
        raise ValueError("A selected reference line disappeared.")
    return result


def numeric_grade(prediction: dict, reference: dict) -> dict:
    if prediction.get("request", {}).get("scope") == "view":
        return {"status": "ungraded_scope_variant", "accuracy_verified": False,
                "reason": "The supplied reference is not bound to this custom visible-object inventory."}
    answer_type = reference["type"]
    if answer_type not in {"count", "area", "length", "volume"}:
        return {"status": "ungraded_text", "accuracy_verified": False,
                "reason": "Free-form and multipart Bench answers require source-backed human/independent review."}
    response = prediction.get("response")
    if not response:
        return {"status": "unanswered", "accuracy_verified": False}
    result = response["result"]
    claims = result.get("claims", [])
    if result.get("status") != "answered" or len(claims) != 1 or claims[0].get("quality") not in {"exact", "estimated"}:
        return {"status": "unanswered_or_nonexact", "accuracy_verified": False}
    value = claims[0]["value"]
    estimated = claims[0].get("quality") == "estimated" or value.get("quality") == "estimated"
    try:
        expected = Decimal(str(reference["answer"]))
        if not expected.is_finite() or expected < 0:
            raise ValueError
        if answer_type == "count":
            if estimated:
                return {"status": "unanswered_or_nonexact", "accuracy_verified": False}
            if value.get("kind") != "count" or type(value.get("value")) is not int:
                return {"status": "wrong_value_kind", "accuracy_verified": False}
            actual, tolerance = Decimal(value["value"]), Decimal(0)
            unit = "count"
        else:
            units = {entry["id"]: Unit.model_validate(entry) for entry in response.get("units", [])}
            targets = {"m": "unit:m", "metre": "unit:m", "metres": "unit:m", "m2": "unit:m2",
                       "m²": "unit:m2", "m3": "unit:m3", "m³": "unit:m3"}
            target = standard_units()[targets[str(reference["unit"]).strip()]]
            if value.get("kind") != "quantity" or value.get("unit_id") not in units:
                return {"status": "unresolved_units", "accuracy_verified": False}
            expected_kind = {"area": "area", "length": "length", "volume": "volume"}[answer_type]
            if value.get("quantity_kind") != expected_kind:
                return {"status": "wrong_quantity_kind", "accuracy_verified": False}
            if value.get("quality", "exact") not in {"exact", "estimated"}:
                return {"status": "unanswered_or_nonexact", "accuracy_verified": False}
            actual = convert(value["magnitude"], units[value["unit_id"]], target)
            tolerance = abs(expected) * Decimal("0.02")
            unit = target.symbol
        agreement = abs(actual - expected) <= tolerance
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return {"status": "ungradable_reference_or_units", "accuracy_verified": False}
    return {"status": ("numeric_agreement_estimated" if estimated else "numeric_agreement") if agreement else "numeric_disagreement",
            "accuracy_verified": False, "numeric_agreement": agreement,
            "quality": "estimated" if estimated else "exact",
            "actual": str(actual), "expected": str(expected), "unit": unit,
            "absolute_tolerance": str(tolerance),
            "reason": "Numeric agreement only; source membership and complete question interpretation require independent review."}

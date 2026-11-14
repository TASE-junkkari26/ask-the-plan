"""Decimal scalar arithmetic with explicit dimensions and conservative quality.

This does not evaluate geometry, infer factors or convert currencies. Every
operand must already be an executed numeric result backed by source evidence.
"""
from __future__ import annotations

from decimal import Decimal, Inexact, localcontext

from contracts import models as m
from .units import decimal_string

ZERO_DIMENSION = (0, 0, 0, 0, 0, 0, 0)
KINDS = {(1, 0, 0, 0, 0, 0, 0): "length", (2, 0, 0, 0, 0, 0, 0): "area",
         (3, 0, 0, 0, 0, 0, 0): "volume", (0, 1, 0, 0, 0, 0, 0): "mass",
         (0, 0, 1, 0, 0, 0, 0): "time"}
MONEY = {"currency", "cost", "price", "money"}


class ScalarArithmeticError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _quality(qualities, operator, numbers):
    if all(item == "exact" for item in qualities):
        return "exact"
    if "estimated" in qualities:
        return "estimated"
    uncertain = [index for index, item in enumerate(qualities) if item != "exact"]
    if operator == "add":
        kinds = {qualities[index] for index in uncertain}
        return next(iter(kinds)) if len(kinds) == 1 else "estimated"
    if operator == "subtract":
        kinds = {quality if index == 0 else {"lower_bound": "upper_bound", "upper_bound": "lower_bound"}[quality]
                 for index, quality in enumerate(qualities) if quality != "exact"}
        return next(iter(kinds)) if len(kinds) == 1 else "estimated"
    # General bound multiplication needs interval/sign information. Support the
    # safe common case of one uncertain operand and exact positive factors.
    if len(uncertain) == 1:
        index = uncertain[0]
        if all(value > 0 for offset, value in enumerate(numbers) if offset != index):
            quality = qualities[index]
            if operator == "divide" and index > 0:
                # A lower-bounded positive denominator stays away from zero;
                # an upper bound alone does not establish nonzero division.
                if quality != "lower_bound" or numbers[index] <= 0:
                    return "estimated"
                return "upper_bound"
            return quality
    return "estimated"


def scalar_arithmetic(values: list[m.Value], operator: str, units: dict[str, m.Unit],
                      output_unit_id: str | None = None, qualities: list[str] | None = None) -> tuple[m.Value, str]:
    if len(values) < 2 or operator not in {"add", "subtract", "multiply", "divide"}:
        raise ScalarArithmeticError("unsupported_operation", "Scalar arithmetic needs at least two numeric inputs and a supported operator.")
    if not all(isinstance(value, (m.CountValue, m.QuantityValue)) for value in values):
        raise ScalarArithmeticError("missing_information", "Every arithmetic input must be an available numeric source result.")
    dimensions, numbers, quantities = [], [], []
    with localcontext() as context:
        context.prec = max(80, sum(len(value.magnitude) if isinstance(value, m.QuantityValue) else len(str(value.value)) for value in values) + 32)
        for value in values:
            if isinstance(value, m.CountValue):
                dimensions.append(ZERO_DIMENSION)
                numbers.append(Decimal(value.value))
                continue
            quantities.append(value)
            unit = units.get(value.unit_id)
            if unit is None:
                raise ScalarArithmeticError("missing_information", "An arithmetic input has unresolved units.")
            if unit.kind != "physical" or unit.dimension is None:
                raise ScalarArithmeticError("insufficient_calibration", "Presentation units do not establish arithmetic dimensions.")
            if Decimal(unit.si_offset) != 0:
                raise ScalarArithmeticError("unsupported_operation", "Offset-unit arithmetic requires an explicit quantity definition.")
            dimensions.append(unit.dimension)
            numbers.append(Decimal(value.magnitude) * Decimal(unit.si_multiplier))
        if operator in {"add", "subtract"}:
            if len(set(dimensions)) != 1 or (quantities and len(quantities) != len(values)):
                raise ScalarArithmeticError("conflicting_evidence", "Addition and subtraction require matching numeric kinds and dimensions.")
            if len({(value.quantity_kind, value.basis) for value in quantities}) > 1:
                raise ScalarArithmeticError("conflicting_evidence", "Addition and subtraction cannot combine different quantity definitions or net/gross bases.")
            dimension = dimensions[0]
            number = numbers[0]
            for other in numbers[1:]:
                number = number + other if operator == "add" else number - other
        elif operator == "multiply":
            dimension = tuple(sum(items) for items in zip(*dimensions))
            number = Decimal(1)
            for other in numbers:
                number *= other
        else:
            dimension = tuple(items[0] - sum(items[1:]) for items in zip(*dimensions))
            number = numbers[0]
            for other in numbers[1:]:
                if other == 0:
                    raise ScalarArithmeticError("missing_information", "Division by a zero source value is undefined.")
                number /= other
        money = [value for value in quantities if value.quantity_kind in MONEY]
        if money:
            if len({value.unit_id for value in money}) > 1:
                raise ScalarArithmeticError("missing_information", "Currency conversion requires a source-backed exchange rate.")
            if operator in {"multiply", "divide"} and len(quantities) > 1:
                raise ScalarArithmeticError("unsupported_operation", "Currency products or rates require explicitly supported currency dimensions.")
            if output_unit_id is not None and output_unit_id != money[0].unit_id:
                raise ScalarArithmeticError("missing_information", "Currency conversion requires a source-backed exchange rate.")
        input_qualities = qualities or [value.quality if isinstance(value, m.QuantityValue) else "exact" for value in values]
        quality = _quality(input_qualities, operator, numbers)
        if not quantities and output_unit_id is None and operator in {"add", "subtract"} and number >= 0:
            return m.CountValue(kind="count", value=int(number)), quality
        target = units.get(output_unit_id) if output_unit_id else None
        if output_unit_id and target is None:
            raise ScalarArithmeticError("missing_information", "The requested output unit is not registered.")
        if target is None:
            if money:
                target = units[money[0].unit_id]
            elif len(quantities) == 1 and dimensions[values.index(quantities[0])] == dimension:
                target = units[quantities[0].unit_id]
            else:
                matching = [unit for unit in units.values() if unit.kind == "physical" and unit.dimension == dimension
                            and Decimal(unit.si_offset) == 0]
                target = next((unit for unit in matching if unit.si_multiplier == "1"), matching[0] if matching else None)
        if target is None:
            raise ScalarArithmeticError("missing_information", "No registered unit represents the resulting arithmetic dimension.")
        if target.kind != "physical" or target.dimension != dimension or Decimal(target.si_offset) != 0:
            raise ScalarArithmeticError("conflicting_evidence", "The output unit is incompatible with the calculated arithmetic dimension.")
        magnitude = number / Decimal(target.si_multiplier)
        if context.flags[Inexact]:
            quality = 'estimated'
        if operator in {"add", "subtract"} and quantities:
            kind, basis = quantities[0].quantity_kind, quantities[0].basis
        elif len(quantities) == 1 and dimension == units[quantities[0].unit_id].dimension:
            kind, basis = quantities[0].quantity_kind, quantities[0].basis
        else:
            kind = "ratio" if dimension == ZERO_DIMENSION and operator == "divide" else KINDS.get(dimension, "number" if dimension == ZERO_DIMENSION else "derived")
            basis = "calculated: " + (" / " if operator == "divide" else " × ").join(
                value.basis if isinstance(value, m.QuantityValue) else "modeled count" for value in values)
        return m.QuantityValue(kind="quantity", magnitude=decimal_string(magnitude), unit_id=target.id,
            quantity_kind=kind, basis=basis, unit_resolution="derived", quality=quality,
            unit_anchor_ids=sorted({anchor for value in quantities for anchor in value.unit_anchor_ids})), quality

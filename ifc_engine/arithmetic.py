"""Typed decimal arithmetic for source-derived scalar values.

No expressions or constants are evaluated. Every operand is an earlier query
step, so the caller retains its source facts, entity sets and calculation tree.
"""
from __future__ import annotations

from decimal import Decimal, localcontext

from contracts import models as m
from .units import DIMENSIONS, SI_TARGETS, convert, decimal_string


class ArithmeticError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def evaluate(values: list, operation: m.ArithmeticOperation,
             units: dict[str, m.Unit]) -> tuple[m.Value, list[tuple[int, m.QuantityValue]]]:
    """Return a scalar and any explicit source-to-working-unit conversions."""
    if not 2 <= len(values) <= 32:
        raise ArithmeticError("unsupported_operation", "Arithmetic supports between two and 32 scalar operands.")
    if not all(isinstance(value, (m.QuantityValue, m.CountValue)) for value in values):
        raise ArithmeticError("unsupported_operation", "Arithmetic requires source-derived numeric scalar inputs.")
    for value in values:
        if isinstance(value, m.QuantityValue):
            if value.quality not in {"exact", "estimated"}:
                raise ArithmeticError("unsupported_operation", "Arithmetic on inexact quantities requires explicit uncertainty propagation.")
            if value.unit_id is None or value.unit_id not in units:
                raise ArithmeticError("missing_information", "An arithmetic operand has unresolved units.")
            if units[value.unit_id].kind != "physical":
                raise ArithmeticError("unsupported_operation", "Arithmetic cannot use presentation units.")
    result, conversions = (_additive(values, operation, units) if operation.operator in {"add", "subtract"}
                           else _multiplicative(values, operation, units))
    if any(isinstance(value, m.QuantityValue) and value.quality == "estimated" for value in values):
        if isinstance(result, m.QuantityValue):
            result.quality = "estimated"
    for index, converted in conversions:
        converted.quality = values[index].quality
    return result, conversions


def _quantity(number, target, kind, basis):
    return m.QuantityValue(kind="quantity", magnitude=decimal_string(number), unit_id=target.id,
                           quantity_kind=kind, basis=basis, unit_resolution="derived")


def _target(operation, units, dimension, kind):
    target_id = operation.output_unit_id or SI_TARGETS.get(kind)
    if target_id is None or target_id not in units:
        raise ArithmeticError("unsupported_operation", "The arithmetic result has no supported output unit; select an explicit compatible unit.")
    target = units[target_id]
    if target.kind != "physical" or target.dimension != dimension:
        raise ArithmeticError("conflicting_evidence", "The arithmetic output unit has incompatible dimensions.")
    return target


def _additive(values, operation, units):
    counts = all(isinstance(value, m.CountValue) for value in values)
    if not counts and any(isinstance(value, m.CountValue) for value in values):
        raise ArithmeticError("conflicting_evidence", "Counts and physical quantities cannot be added or subtracted together.")
    conversions = []
    if counts:
        if operation.output_unit_id is not None:
            raise ArithmeticError("conflicting_evidence", "Adding or subtracting counts cannot assign a physical output unit.")
        numbers = [Decimal(value.value) for value in values]
    else:
        first = values[0]
        dimension = units[first.unit_id].dimension
        if any(Decimal(units[value.unit_id].si_offset) for value in values):
            raise ArithmeticError("unsupported_operation", "Addition and subtraction of offset units need an explicit absolute-versus-difference convention.")
        signatures = {(value.quantity_kind, value.basis, units[value.unit_id].dimension) for value in values}
        if len(signatures) != 1:
            raise ArithmeticError("conflicting_evidence", "Addition and subtraction require matching quantity meanings, bases and dimensions.")
        target = _target(operation, units, dimension, first.quantity_kind)
        numbers = [convert(value.magnitude, units[value.unit_id], target) for value in values]
        conversions = [(index, _quantity(number, target, value.quantity_kind, value.basis))
                       for index, (value, number) in enumerate(zip(values, numbers)) if value.unit_id != target.id]
    with localcontext() as context:
        context.prec = max(80, sum(len(str(number)) for number in numbers) + 32)
        number = sum(numbers, Decimal(0)) if operation.operator == "add" else numbers[0] - sum(numbers[1:], Decimal(0))
    if counts:
        if number >= 0:
            return m.CountValue(kind="count", value=int(number)), conversions
        return _quantity(number, units["unit:1"], "number", "calculated"), conversions
    return _quantity(number, target, first.quantity_kind, first.basis), conversions


def _multiplicative(values, operation, units):
    dimensions, numbers, conversions = [], [], []
    for index, value in enumerate(values):
        if isinstance(value, m.CountValue):
            dimensions.append(DIMENSIONS["number"])
            numbers.append(Decimal(value.value))
            continue
        unit = units[value.unit_id]
        if Decimal(unit.si_offset):
            raise ArithmeticError("unsupported_operation", "Products and ratios of offset units are not supported.")
        dimensions.append(unit.dimension)
        with localcontext() as context:
            context.prec = max(80, len(value.magnitude) + len(unit.si_multiplier) + 32)
            number = Decimal(value.magnitude) * Decimal(unit.si_multiplier)
        numbers.append(number)
        working_id = SI_TARGETS.get(value.quantity_kind)
        if working_id in units and working_id != value.unit_id:
            working = units[working_id]
            if working.dimension == unit.dimension:
                conversions.append((index, _quantity(number, working, value.quantity_kind, value.basis)))
    divide = operation.operator == "divide"
    dimension = tuple(dimensions[0])
    for other in dimensions[1:]:
        dimension = tuple(a - b if divide else a + b for a, b in zip(dimension, other))
    with localcontext() as context:
        context.prec = max(80, sum(len(str(number)) for number in numbers) + 32)
        number = numbers[0]
        for operand in numbers[1:]:
            if divide and operand == 0:
                raise ArithmeticError("missing_information", "A ratio cannot be calculated because a source-derived denominator is zero.")
            number = number / operand if divide else number * operand
        # Retain a quantity's meaning/basis when only scaling it by
        # dimensionless factors; other products/ratios explicitly derive it.
        quantities = [value for value in values if isinstance(value, m.QuantityValue)]
        dimensional = [value for value in quantities if value.quantity_kind not in {"number", "ratio"}]
        kind = None
        basis = "calculated"
        if len(dimensional) == 1 and (not divide or dimensional[0] is values[0]):
            kind, basis = dimensional[0].quantity_kind, dimensional[0].basis
        if kind is None:
            kind = next((name for name in ("length", "area", "volume", "mass", "time")
                         if DIMENSIONS[name] == dimension), None)
        if dimension == DIMENSIONS["number"] and kind != "angle":
            if any(value.quantity_kind == "angle" for value in quantities) and not divide:
                raise ArithmeticError("unsupported_operation", "Products of multiple angular quantities need an explicit result convention.")
            kind = "ratio" if divide or any(value.quantity_kind == "ratio" for value in quantities) else "number"
        target = _target(operation, units, dimension, kind)
        number = (number - Decimal(target.si_offset)) / Decimal(target.si_multiplier)
    return _quantity(number, target, kind or "derived", basis), conversions

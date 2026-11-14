"""Decimal source-value parsing and dimension-aware, anchored schedule arithmetic."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, Inexact, localcontext
import re
from typing import Iterable

from .store import DocumentError

# Dimensions for this bounded catalog: length, mass, currency. EUR and USD use
# different currency exponents, so no implicit exchange-rate conversion is possible.
UNITS = {
    "1": ((0, 0, 0), Decimal(1)), "%": ((0, 0, 0), Decimal("0.01")),
    "mm": ((1, 0, 0), Decimal("0.001")), "cm": ((1, 0, 0), Decimal("0.01")),
    "m": ((1, 0, 0), Decimal(1)), "in": ((1, 0, 0), Decimal("0.0254")),
    "ft": ((1, 0, 0), Decimal("0.3048")),
    "mm2": ((2, 0, 0), Decimal("0.000001")), "cm2": ((2, 0, 0), Decimal("0.0001")),
    "m2": ((2, 0, 0), Decimal(1)), "ft2": ((2, 0, 0), Decimal("0.09290304")),
    "in2": ((2, 0, 0), Decimal("0.00064516")),
    "mm3": ((3, 0, 0), Decimal("0.000000001")), "m3": ((3, 0, 0), Decimal(1)),
    "ft3": ((3, 0, 0), Decimal("0.028316846592")),
    "kg": ((0, 1, 0), Decimal(1)), "g": ((0, 1, 0), Decimal("0.001")),
    "t": ((0, 1, 0), Decimal(1000)),
    "EUR": ((0, 0, 1), Decimal(1)), "USD": ((0, 0, 2), Decimal(1)),
}
ALIASES = {"m²": "m2", "m^2": "m2", "sq m": "m2", "sqm": "m2", "sf": "ft2",
           "SF": "ft2", "S.F.": "ft2", "sq ft": "ft2", "SQ FT": "ft2", "SQ. FT.": "ft2", "SqFt": "ft2",
           "ft²": "ft2", "ft^2": "ft2", "m³": "m3", "m^3": "m3",
           "ft³": "ft3", "ft^3": "ft3", "mm²": "mm2", "cm²": "cm2", "in²": "in2",
           "inches": "in", "inch": "in", '"': "in", "′": "ft", "'": "ft", "feet": "ft",
           "ea": "1", "each": "1", "pcs": "1", "€": "EUR", "$": "USD"}


@dataclass(frozen=True)
class SourceQuantity:
    magnitude: Decimal
    unit: str
    source_text: str
    anchor_ids: tuple[str, ...]
    basis: str = "specified"
    quality: str = "exact"

    @property
    def dimension(self):
        return UNITS[self.unit][0]

    def public(self):
        return {"magnitude": decimal_string(self.magnitude), "unit": self.unit,
                "source_text": self.source_text, "anchor_ids": list(self.anchor_ids),
                "basis": self.basis, "quality": self.quality}


@dataclass(frozen=True)
class Calculation:
    operation: str
    inputs: tuple[SourceQuantity, ...]
    result: SourceQuantity
    rule: str

    def public(self):
        return {"operation": self.operation, "inputs": [item.public() for item in self.inputs],
                "result": self.result.public(), "rule": self.rule}


def decimal_string(value: Decimal) -> str:
    if not value.is_finite():
        raise DocumentError("invalid_quantity", "Nonfinite source quantities are invalid.")
    return format(value, "f")


def _number(text: str) -> Decimal:
    text = text.strip().replace("−", "-").replace("–", "-")
    match = re.fullmatch(r"([+-]?)(?:(\d+)\s+)?(\d+)\s*/\s*(\d+)", text)
    if match:
        sign, whole, numerator, denominator = match.groups()
        denominator = Decimal(denominator)
        if not denominator:
            raise DocumentError("division_by_zero", "A printed fraction has a zero denominator.")
        with localcontext() as context:
            context.prec = 40
            result = Decimal(whole or 0) + Decimal(numerator) / denominator
        return -result if sign == "-" else result
    # Comma is a decimal mark only when dot is absent and no grouping ambiguity.
    if "," in text:
        if "." in text or text.count(",") != 1 or not re.fullmatch(r"[+-]?\d+,\d{1,2}", text):
            raise DocumentError("ambiguous_number", "The printed separator could be decimal or thousands grouping.")
        text = text.replace(",", ".")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", text):
        raise DocumentError("unparsed_quantity", "The source cell is not one unambiguous scalar quantity.")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise DocumentError("unparsed_quantity", "The source quantity could not be parsed.") from exc
    if not result.is_finite():
        raise DocumentError("invalid_quantity", "The source quantity is not finite.")
    return result


def normalize_unit(unit: str) -> str:
    normalized = ALIASES.get(unit.strip(), ALIASES.get(unit.strip().lower(), unit.strip()))
    if normalized not in UNITS:
        raise DocumentError("unknown_unit", "The source unit is not supported by the deterministic unit catalog.")
    return normalized


def parse_quantity(text: str, *, default_unit: str | None = None,
                   anchor_ids: Iterable[str] = (), basis: str = "specified") -> SourceQuantity:
    """Parse a single cell, preserving the exact original string and anchors.

    A default unit must come from an anchored header/native unit definition; callers
    supply its anchor along with cell anchors. No default metric unit is guessed.
    """
    if not isinstance(text, str) or not text.strip() or len(text) > 1024:
        raise DocumentError("unparsed_quantity", "A scalar source cell must contain a bounded nonempty string.")
    original = text
    value = text.strip().replace("’", "'").replace("′", "'").replace("”", '"').replace("″", '"')
    imperial = re.fullmatch(r"([+-]?\d+)\s*'\s*(?:-\s*)?((?:\d+\s+)?\d+(?:\s*/\s*\d+)?|\d+\.\d+)\s*\"", value)
    if imperial:
        feet, inches = map(_number, imperial.groups())
        if inches < 0 or inches >= 12:
            raise DocumentError("ambiguous_quantity", "An imperial feet/inches cell has an invalid inches component.")
        magnitude = feet * 12 + (-inches if feet < 0 or imperial.group(1).startswith("-") else inches)
        unit = "in"
    else:
        # Longest suffix first prevents m2 from being interpreted as a bare number.
        options = sorted((set(UNITS) | set(ALIASES)) - {"1"}, key=len, reverse=True)
        unit = None
        number_text = value
        for suffix in options:
            if value.endswith(suffix) and len(value) > len(suffix):
                possible = value[:-len(suffix)].strip()
                try:
                    magnitude = _number(possible)
                except DocumentError:
                    continue
                unit = normalize_unit(suffix)
                number_text = possible
                break
        if unit is None:
            magnitude = _number(number_text)
            if default_unit is None:
                raise DocumentError("missing_unit", "The source cell has no unit and no anchored header/native unit was supplied.")
            unit = normalize_unit(default_unit)
    anchors = tuple(dict.fromkeys(anchor_ids))
    if not anchors:
        raise DocumentError("missing_evidence", "Source quantities need their cell/header or native-unit evidence anchors.")
    # Nonterminating fractions are rounded by Decimal; preserve that qualification.
    denominators = re.findall(r"/\s*(\d+)", original)
    estimated = False
    for denominator_text in denominators:
        denominator = int(denominator_text)
        if denominator:
            for divisor in (2, 5):
                while denominator % divisor == 0:
                    denominator //= divisor
            estimated |= denominator != 1
    return SourceQuantity(magnitude, unit, original, anchors, basis, "estimated" if estimated else "exact")


def convert(value: SourceQuantity, unit: str) -> Calculation:
    unit = normalize_unit(unit)
    if value.dimension != UNITS[unit][0]:
        raise DocumentError("incompatible_dimensions", "Cannot convert between different quantity dimensions or currencies.")
    with localcontext() as context:
        context.prec = 40
        magnitude = value.magnitude * UNITS[value.unit][1] / UNITS[unit][1]
        inexact = context.flags[Inexact]
    quality = "estimated" if inexact else value.quality
    result = SourceQuantity(magnitude, unit, "", value.anchor_ids, value.basis, quality)
    return Calculation("convert", (value,), result, f"{value.unit} × {UNITS[value.unit][1]} ÷ {UNITS[unit][1]} -> {unit}")


def calculate(operation: str, values: Iterable[SourceQuantity], *, output_unit: str | None = None) -> Calculation:
    inputs = tuple(values)
    if not inputs:
        raise DocumentError("missing_inputs", "A calculation needs independently supported source inputs; an empty set is not zero.")
    if operation not in {"sum", "subtract", "multiply", "divide", "min", "max"}:
        raise DocumentError("unsupported_calculation", "The requested scalar operation is not supported.")
    if operation in {"subtract", "divide"} and len(inputs) != 2:
        raise DocumentError("invalid_calculation", "Subtraction and division each require two inputs.")
    if len({value.basis for value in inputs if value.unit != "1"}) > 1:
        raise DocumentError("incompatible_basis", "Different source quantity bases cannot be silently combined.")
    basis = next((value.basis for value in inputs if value.unit != "1"), inputs[0].basis)
    quality = "estimated" if any(value.quality != "exact" for value in inputs) else "exact"
    anchors = tuple(dict.fromkeys(anchor for value in inputs for anchor in value.anchor_ids))
    with localcontext() as context:
        context.prec = 40
        if operation in {"sum", "subtract", "min", "max"}:
            unit = normalize_unit(output_unit or inputs[0].unit)
            converted = [convert(item, unit).result for item in inputs]
            if any(item.quality != "exact" for item in converted):
                quality = "estimated"
            amounts = [item.magnitude for item in converted]
            magnitude = {"sum": lambda: sum(amounts, Decimal(0)), "subtract": lambda: amounts[0] - amounts[1],
                         "min": lambda: min(amounts), "max": lambda: max(amounts)}[operation]()
        else:
            dimension = tuple(a + b if operation == "multiply" else a - b for a, b in zip(inputs[0].dimension, inputs[1].dimension)) if len(inputs) == 2 else None
            if operation == "multiply":
                dimension = tuple(sum(value.dimension[index] for value in inputs) for index in range(3))
                magnitude = Decimal(1)
                for value in inputs:
                    magnitude *= value.magnitude * UNITS[value.unit][1]
            else:
                denominator = inputs[1].magnitude * UNITS[inputs[1].unit][1]
                if denominator == 0:
                    raise DocumentError("division_by_zero", "The source-backed denominator is zero; the ratio is undefined.")
                magnitude = inputs[0].magnitude * UNITS[inputs[0].unit][1] / denominator
            unit = normalize_unit(output_unit) if output_unit is not None else next((key for key, (dim, factor) in UNITS.items() if dim == dimension and factor == 1), None)
            if unit is None or UNITS[unit][0] != dimension:
                raise DocumentError("incompatible_dimensions", "No compatible output unit was supplied for the calculated dimension.")
            magnitude /= UNITS[unit][1]
        if context.flags[Inexact]:
            quality = "estimated"
    result = SourceQuantity(magnitude, unit, "", anchors, basis, quality)
    return Calculation(operation, inputs, result, "Decimal arithmetic; explicit compatible units and source quantity basis; all source anchors retained.")

"""Bounded table-operand adapter around the shared scalar arithmetic engine.

Scalar queries and derived table cells deliberately use the same dimensional,
currency, rounding and uncertainty semantics from scalar_math.
"""
from contracts import models as m
from .scalar_math import ScalarArithmeticError, scalar_arithmetic


class ArithmeticError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def evaluate(values: list, operation: m.ArithmeticOperation,
             units: dict[str, m.Unit]) -> tuple[m.Value, list[tuple[int, m.QuantityValue]]]:
    """Preserve the table helper API while delegating arithmetic semantics."""
    if not 2 <= len(values) <= 32:
        raise ArithmeticError("unsupported_operation", "Table arithmetic supports between two and 32 operands per node.")
    try:
        value, _ = scalar_arithmetic(values, operation.operator, units, operation.output_unit_id)
    except ScalarArithmeticError as error:
        raise ArithmeticError(error.code, str(error)) from None
    # Table calculation DAGs retain original numeric cells and their units;
    # scalar_math also retains the input unit anchors on its derived quantity.
    return value, []

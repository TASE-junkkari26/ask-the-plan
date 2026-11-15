"""Bounded table arithmetic with explicit cell and denominator calculations."""
from __future__ import annotations

from contracts import models as m
from .arithmetic import ArithmeticError, evaluate


def execute_table_calculation(engine, state, operation, step_id):
    from .engine import QueryError, _Support

    if state.shape != "table" or not isinstance(state.value, m.TableValue):
        raise QueryError("unsupported_operation", "Table calculations require a source-derived table.")
    if state.unresolved or state.candidate_members or not state.coverage_complete:
        raise QueryError("incomplete_coverage", "Table arithmetic cannot establish totals from unresolved or candidate inputs.")
    if len(state.value.rows) > 2000:
        raise QueryError("unsupported_operation", "A table calculation is limited to 2000 source-derived rows.")
    columns = {column.key for column in state.value.columns}
    if operation.value_key in columns or (operation.operator == "consecutive_difference" and operation.next_key in columns):
        raise QueryError("needs_clarification", "Choose new output column keys for the table calculation.")
    for ref in [*operation.fields, *operation.group_by, *([operation.order_by] if operation.order_by else [])]:
        if ref.kind != "result_column" or ref.key not in columns:
            raise QueryError("needs_clarification", "A table calculation field is not an existing result column.")
    rows, cells = state.value.rows, state.cells
    serial = 0

    def combine(supports, method="lookup"):
        return _Support(set().union(*(support.members for support in supports)),
                        set().union(*(support.facts for support in supports)),
                        set().union(*(support.anchors for support in supports)), method,
                        evidence_kind="candidate" if any(s.evidence_kind == "candidate" for s in supports) else "verified")

    def node(value, support, method, inputs):
        nonlocal serial
        serial += 1
        identifier = f"calculation:{step_id}:cell-input:{serial}"
        state.internal_nodes.append(m.CalculationNode(id=identifier, operation=method,
            input_node_ids=list(inputs), fact_ids=sorted(support.facts), anchor_ids=sorted(support.anchors),
            output=value, quality=state.quality, rule_key="ifc.table-arithmetic.v1"))
        return identifier

    def source(index, key):
        value, support = rows[index][key], cells[index][key]
        if not isinstance(value, (m.CountValue, m.QuantityValue)):
            raise QueryError("missing_information", "A table arithmetic operand is unavailable or nonnumeric.", sorted(support.members))
        return value, support, node(value, support, "lookup", support.input_node_ids or ["calculation:" + operation.input_step_id])

    def calculate(operands, operator, output_unit_id=None):
        values, supports, identifiers = zip(*operands)
        support = combine(supports)
        try:
            value, _ = evaluate(list(values), m.ArithmeticOperation(kind="arithmetic",
                input_step_ids=list(identifiers), operator=operator, output_unit_id=output_unit_id), engine.units)
        except ArithmeticError as error:
            raise QueryError(error.code, str(error), sorted(support.members), sorted(support.facts)) from None
        identifier = node(value, support, operator, identifiers)
        support.input_node_ids = [identifier]
        return value, support, identifier

    groups = {}
    for index, row in enumerate(rows):
        key = tuple(engine._value_key(row[ref.key]) for ref in operation.group_by)
        groups.setdefault(key, []).append(index)
    output_rows, output_cells = [], []
    for indices in groups.values():
        if operation.operator == "percent_of_total":
            operands = {index: source(index, operation.fields[0].key) for index in indices}
            if any(engine._scalar(value) < 0 for value, _, _ in operands.values()):
                raise QueryError("conflicting_evidence", "A percentage distribution requires nonnegative source inputs.")
            # Bounded fan-in keeps large inventories useful without allowing an
            # unbounded expression or thousands of scalar planner steps.
            totals = list(operands.values())
            while len(totals) > 1:
                totals = [calculate(totals[offset:offset + 32], "add") if len(totals[offset:offset + 32]) > 1
                          else totals[offset] for offset in range(0, len(totals), 32)]
            denominator = totals[0]
            for index in indices:
                value, support, _ = calculate([operands[index], denominator], "divide", operation.output_unit_id or "unit:%")
                output_rows.append({**rows[index], operation.value_key: value})
                output_cells.append({**cells[index], operation.value_key: support})
        elif operation.operator == "consecutive_difference":
            signatures = {engine._comparison_signature(rows[index][operation.order_by.key]) for index in indices}
            if len(signatures) != 1:
                raise QueryError("conflicting_evidence", "Consecutive rows need compatible ordering values.")
            ordered = sorted(indices, key=lambda index: engine._scalar(rows[index][operation.order_by.key]))
            keys = [engine._scalar(rows[index][operation.order_by.key]) for index in ordered]
            if len(set(keys)) != len(keys):
                raise QueryError("needs_clarification", "Consecutive rows have duplicate ordering values; choose an unambiguous source group.")
            for index, following in zip(ordered, ordered[1:]):
                value, support, _ = calculate([source(following, operation.fields[0].key), source(index, operation.fields[0].key)],
                                               "subtract", operation.output_unit_id)
                following_value = m.RecordValue(kind="record", fields=rows[following])
                following_support = combine(list(cells[following].values()))
                following_support.input_node_ids = ["calculation:" + operation.input_step_id]
                output_rows.append({**rows[index], operation.next_key: following_value, operation.value_key: value})
                output_cells.append({**cells[index], operation.next_key: following_support, operation.value_key: support})
        else:
            for index in indices:
                value, support, _ = calculate([source(index, ref.key) for ref in operation.fields],
                                               operation.operator, operation.output_unit_id)
                output_rows.append({**rows[index], operation.value_key: value})
                output_cells.append({**cells[index], operation.value_key: support})
    additions = ([m.TableColumn(key=operation.next_key, label=m.LocalizedText(text="Following row"))]
                 if operation.operator == "consecutive_difference" else [])
    state.value = m.TableValue(kind="table", columns=[*state.value.columns, *additions,
        m.TableColumn(key=operation.value_key, label=m.LocalizedText(text=operation.value_key))], rows=output_rows)
    state.cells = output_cells
    state.members = set().union(*(support.members for row in output_cells for support in row.values())) if output_cells else set()

"""Conservative native table reconstruction from explicitly anchored headers.

No column-index guesses or language-model numbers enter arithmetic. Ambiguous
layout/cells remain explicit; native text enumeration is not table completeness.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
from typing import Iterable

from .pdf import NativePage, NativeSpan
from .quantities import Calculation, SourceQuantity, calculate, parse_quantity
from .store import DocumentError


@dataclass(frozen=True)
class TableColumn:
    key: str
    header_span_ids: tuple[str, ...]
    label: str
    left: float
    right: float
    unit: str | None = None


@dataclass(frozen=True)
class TableCell:
    id: str
    row_id: str
    column_key: str
    text: str
    span_ids: tuple[str, ...]
    header_span_ids: tuple[str, ...]
    bbox: tuple[float, float, float, float] | None
    status: str  # present, missing, ambiguous


@dataclass(frozen=True)
class TableRow:
    id: str
    index: int
    cells: dict[str, TableCell]


@dataclass(frozen=True)
class NativeTable:
    id: str
    columns: tuple[TableColumn, ...]
    rows: tuple[TableRow, ...]
    bbox: tuple[float, float, float, float]
    enumeration_complete: bool
    unresolved_span_ids: tuple[str, ...]
    warnings: tuple[str, ...]

    def filter_rows(self, column_key: str, literal: str, *, case_sensitive: bool = True) -> tuple[TableRow, ...]:
        if column_key not in {column.key for column in self.columns}:
            raise DocumentError("unknown_column", "The requested source table column was not established from its headers.")
        needle = literal if case_sensitive else literal.casefold()
        return tuple(row for row in self.rows if row.cells[column_key].status == "present" and
                     ((row.cells[column_key].text if case_sensitive else row.cells[column_key].text.casefold()) == needle))

    def quantity(self, row: TableRow, column_key: str, *, basis: str = "specified") -> SourceQuantity:
        columns = {column.key: column for column in self.columns}
        if column_key not in columns or row.id not in {item.id for item in self.rows}:
            raise DocumentError("unknown_cell", "Select a registered row and anchored source column.")
        cell = row.cells[column_key]
        if cell.status != "present":
            raise DocumentError("unresolved_cell", "A required source cell is missing or ambiguous; no value was inferred.")
        return parse_quantity(cell.text, default_unit=columns[column_key].unit,
                              anchor_ids=(*cell.span_ids, *cell.header_span_ids), basis=basis)

    def aggregate(self, operation: str, value_column: str, *, multiplier_column: str | None = None,
                  rows: Iterable[TableRow] | None = None, output_unit: str | None = None,
                  basis: str = "specified") -> tuple[Calculation, tuple[Calculation, ...]]:
        if not self.enumeration_complete:
            raise DocumentError("incomplete_table", "The selected native table has unresolved extraction or row/cell associations.")
        chosen = tuple(self.rows if rows is None else rows)
        values, row_calculations = [], []
        for row in chosen:
            value = self.quantity(row, value_column, basis=basis)
            if multiplier_column is not None:
                multiplier = self.quantity(row, multiplier_column, basis=basis)
                calculation = calculate("multiply", (value, multiplier), output_unit=output_unit)
                row_calculations.append(calculation)
                value = calculation.result
            values.append(value)
        return calculate(operation, values, output_unit=output_unit), tuple(row_calculations)


def extract_table(page: NativePage, headers: dict[str, list[str]], *,
                  bbox: tuple[float, float, float, float], units: dict[str, str] | None = None,
                  row_tolerance: float | None = None) -> NativeTable:
    """Reconstruct a declared table rectangle using source span header identities.

    A header can contain several multiline/merged spans. Distinct header groups
    must not overlap; colspans crossing declared columns become unresolved cells.
    Repeated complete headers inside the same rectangle are skipped explicitly.
    The rectangle must isolate the table body, excluding unrelated footer text.
    Returned completeness concerns this bounded native reconstruction only.
    """
    if not page.mapping_verified:
        raise DocumentError("missing_mapping", "Table reconstruction needs a verified source-to-display transform.")
    if not headers or len(headers) > 128 or len(bbox) != 4 or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        raise DocumentError("invalid_table", "Supply bounded table geometry and at least one anchored header.")
    spans = {span.id: span for span in page.spans}
    declared = []
    header_ids = set()
    for key, identifiers in headers.items():
        if not key or not identifiers or any(identifier not in spans for identifier in identifiers):
            raise DocumentError("invalid_header", "Every declared source column needs valid native header span IDs.")
        group = [spans[identifier] for identifier in identifiers]
        if any(span.display_bbox is None for span in group):
            raise DocumentError("missing_mapping", "A table header has no verified display coordinates.")
        if header_ids.intersection(identifiers):
            raise DocumentError("ambiguous_header", "A native header span cannot define two independent source columns.")
        header_ids.update(identifiers)
        left = min(span.display_bbox[0] for span in group)
        right = max(span.display_bbox[2] for span in group)
        top = min(span.display_bbox[1] for span in group)
        bottom = max(span.display_bbox[3] for span in group)
        if left < bbox[0] or right > bbox[2] or top < bbox[1] or bottom > bbox[3]:
            raise DocumentError("invalid_header", "Source headers must lie within the declared table rectangle.")
        declared.append((left, right, bottom, key, tuple(identifiers), " ".join(span.text for span in group)))
    declared.sort()
    if any(a[1] >= b[0] for a, b in zip(declared, declared[1:])):
        raise DocumentError("ambiguous_header", "Overlapping/merged source headers need resolved column groups before table arithmetic.")
    centers = [(left + right) / 2 for left, right, *_ in declared]
    boundaries = [bbox[0], *((a + b) / 2 for a, b in zip(centers, centers[1:])), bbox[2]]
    columns = tuple(TableColumn(item[3], item[4], item[5], boundaries[index], boundaries[index + 1], (units or {}).get(item[3]))
                    for index, item in enumerate(declared))
    body_top = max(item[2] for item in declared)
    body = []
    unresolved = []
    for span in page.spans:
        if span.id in header_ids or span.display_bbox is None:
            continue
        left, top, right, bottom = span.display_bbox
        intersects = left < bbox[2] and right > bbox[0] and top < bbox[3] and bottom > body_top
        if not intersects:
            continue
        matrix = span.display_transform
        horizontal = not span.vertical and matrix is not None and abs(matrix[1]) < 1e-6 and abs(matrix[2]) < 1e-6
        if left < bbox[0] or right > bbox[2] or top < body_top or bottom > bbox[3] or not horizontal:
            unresolved.append(span.id)
            continue
        body.append(span)
    tolerance = row_tolerance if row_tolerance is not None else max(1, min((span.display_bbox[3] - span.display_bbox[1] for span in body), default=4) * 0.35)
    if tolerance <= 0:
        raise DocumentError("invalid_table", "Native row tolerance must be positive.")
    groups = []
    for span in sorted(body, key=lambda item: (item.display_transform[5], item.display_bbox[0])):
        baseline = span.display_transform[5]
        if groups and abs(groups[-1][0] - baseline) <= tolerance:
            groups[-1][1].append(span)
        else:
            groups.append((baseline, [span]))
    table_id = "table-" + hashlib.sha256((str(page.source_sha256) + str(page.page_index) + repr(headers) + repr(bbox)).encode()).hexdigest()[:20]
    rows = []
    repeated = 0
    for _, group in groups:
        by_column = {column.key: [] for column in columns}
        ambiguous = set()
        for span in group:
            left, _, right, _ = span.display_bbox
            matching = [column for column in columns if left < column.right and right > column.left]
            if len(matching) != 1:
                unresolved.append(span.id)
                ambiguous.update(column.key for column in matching)
            else:
                by_column[matching[0].key].append(span)
        combined = {column.key: " ".join(span.text for span in sorted(by_column[column.key], key=lambda item: item.display_bbox[0])) for column in columns}
        if combined == {column.key: column.label for column in columns}:
            repeated += 1
            continue
        row_id = f"{table_id}:row{len(rows)}"
        cells = {}
        for column in columns:
            items = by_column[column.key]
            box = (min(item.display_bbox[0] for item in items), min(item.display_bbox[1] for item in items),
                   max(item.display_bbox[2] for item in items), max(item.display_bbox[3] for item in items)) if items else None
            status = "ambiguous" if column.key in ambiguous else "present" if items else "missing"
            cells[column.key] = TableCell(f"{row_id}:{column.key}", row_id, column.key, combined[column.key],
                                         tuple(item.id for item in items), column.header_span_ids, box, status)
        rows.append(TableRow(row_id, len(rows), cells))
    warnings = ["Table enumeration concerns the declared native table rectangle; object/assembly meaning still requires a source-backed counting policy."]
    if repeated:
        warnings.append(f"Skipped {repeated} repeated complete source-header rows.")
    if unresolved:
        warnings.append("Some source text crosses unresolved row/column/rectangle boundaries; exact table aggregates are disabled.")
    complete = page.text_enumeration_complete and not unresolved
    return NativeTable(table_id, columns, tuple(rows), tuple(bbox), complete, tuple(unresolved), tuple(warnings))

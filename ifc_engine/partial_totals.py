"""Explicit known subtotals of proven nonnegative native quantity tables."""
from decimal import Decimal, localcontext
import math

from contracts import models as m
from .units import DIMENSIONS, convert, decimal_string

RULE = "ifc.partial-nonnegative-sum.v1"
MAX_ROWS = 20000


def execute_partial_sum(engine, state, operation, step_id, scope_members):
    from .engine import QueryError

    def reject(message, code="unsupported_operation"):
        raise QueryError(code, message)

    if (state.shape != "table" or operation.method != "sum" or operation.group_by
            or operation.field.kind != "result_column" or state.candidate_members
            or state.quality not in {"exact", "estimated"}):
        reject("Partial SUM requires a native material-volume or measured-area table with supported source membership.")
    key = operation.field.key
    family = {"volume": "material", "value": "measurement"}.get(key)
    rows = state.value.rows
    if family is None or not rows or len(rows) > MAX_ROWS or len(state.cells) != len(rows):
        reject("Partial SUM requires a nonempty bounded source-quantity table.")
    records = state.material_records if family == "material" else state.measurement_records
    batches, seen, identities, known, missing = set(), set(), set(), [], []
    kind, basis = ("volume", "modeled_material") if family == "material" else ("area", None)
    si_id = "unit:m3" if family == "material" else "unit:m2"
    si_unit = engine.units[si_id]
    target = engine.units[operation.output_unit_id or si_id]
    if (target.kind != "physical" or target.dimension != DIMENSIONS[kind]
            or Decimal(target.si_offset) != 0 or Decimal(target.si_multiplier) <= 0):
        reject("Partial extensive quantities require compatible physical units without offsets.", "conflicting_evidence")

    for index, (row, cells) in enumerate(zip(rows, state.cells)):
        support = cells.get(key)
        pointer = support.source_record if support is not None else None
        if (pointer is None or len(pointer) != 4 or pointer[0] != family
                or support.operation != ("material_quantity" if family == "material" else "measure")
                or not support.anchors or not support.members <= scope_members):
            reject("A partial SUM cell has no authorized native quantity-record lineage.")
        _, record_index, start, count = pointer
        if (not all(isinstance(value, int) and not isinstance(value, bool) for value in (record_index, start, count))
                or start < 0 or count < 1 or start + count > len(records)
                or not start <= record_index < start + count or record_index in seen):
            reject("Partial SUM source records were duplicated or have an invalid batch identity.")
        batches.add((start, count))
        seen.add(record_index)
        raw = records[record_index]
        subject = raw["subject_id"]
        if subject not in support.members or subject not in scope_members:
            reject("A partial SUM subject is outside its source-cell scope.", "incomplete_coverage")
        if "subject" in row and (row["subject"].kind != "references" or row["subject"].entity_ids != [subject]):
            reject("A partial SUM row does not identify its native quantity subject.", "conflicting_evidence")
        if family == "material":
            record = m.MaterialEvaluation(**raw)
            identity = subject, record.material_name
            available = record.status in {"verified", "recorded_not_used"}
            allowed = {"recorded_net_homogeneous", "closed_mesh_homogeneous", "verified_uniform_layers"}
            if ((record.status == "verified" and record.method not in allowed)
                    or (record.status == "recorded_not_used" and (record.method != "recorded_not_used" or record.volume_m3 != 0))
                    or (record.status == "unavailable" and record.method != "unavailable")):
                reject("A material cell lacks an applicable nonnegative source-volume proof.")
            number = record.volume_m3
        else:
            record = m.MeasurementEvaluation(**raw)
            identity = subject
            if record.metric != "area" or record.reference_entity_ids or record.unit != "m2":
                reject("Partial measured SUM supports area cells only, with their original geometric basis.")
            record_basis = record.metadata.get("basis")
            if not isinstance(record_basis, str) or not record_basis:
                reject("The source area record does not preserve its measurement basis.")
            if basis is None:
                basis = record_basis
            if basis != record_basis:
                reject("Partial SUM source areas use incompatible measurement bases.", "conflicting_evidence")
            available = record.status == "verified"
            number = record.value
        if identity in identities:
            reject("Partial SUM cannot count the same native material/area cell twice.", "conflicting_evidence")
        identities.add(identity)
        value = row.get(key)
        if not available:
            if not isinstance(value, m.UnavailableValue) or support.evidence_kind != "unavailable" or number is not None:
                reject("An unavailable native record cannot supply a numeric partial-SUM operand.", "conflicting_evidence")
            missing.append((index, value, support, raw))
            continue
        if (not isinstance(value, m.QuantityValue) or value.quantity_kind != kind or value.basis != basis
                or value.quality not in {"exact", "estimated"} or support.evidence_kind != "verified"
                or value.unit_id not in engine.units or number is None or not math.isfinite(number)):
            reject("A partial SUM operand is not its proven original nonnegative quantity.", "conflicting_evidence")
        unit = engine.units[value.unit_id]
        if Decimal(unit.si_offset) != 0 or Decimal(unit.si_multiplier) <= 0:
            reject("Partial SUM cannot use affine or nonpositive extensive-quantity units.", "conflicting_evidence")
        numeric = convert(value.magnitude, unit, si_unit)
        if numeric < 0 or number < 0:
            reject("Partial SUM cannot assume a lower bound from negative source quantities.", "conflicting_evidence")
        # Record evidence serializes SI values as doubles; table quantities can
        # retain longer exact decimal unit conversions. Permit only that small
        # serialization round-off when verifying that they are the same input.
        if abs(numeric - Decimal(str(number))) > Decimal.from_float(2 * math.ulp(number)):
            reject("The partial SUM cell disagrees with its native numeric evidence.", "conflicting_evidence")
        known.append((index, value, support, raw, convert(value.magnitude, unit, target)))

    if len(batches) != 1:
        reject("Partial SUM requires one complete source-quantity batch.")
    start, count = next(iter(batches))
    if seen != set(range(start, start + count)):
        reject("Partial SUM cannot silently drop source rows or unresolved quantity records.", "incomplete_coverage")
    unknown_members = {raw["subject_id"] for _, _, _, raw in missing}
    if state.unresolved - unknown_members or (not state.coverage_complete and not missing):
        reject("Unresolved source membership is not a nonnegative omitted-quantity proof.", "incomplete_coverage")
    if not known:
        raise QueryError("missing_information", "No selected quantity cell could be established. No zero or subtotal is inferred from unavailable inputs.",
            sorted(unknown_members), anchor_ids=sorted({anchor for _, _, support, _ in missing for anchor in support.anchors}))

    quality = "estimated" if missing or state.quality == "estimated" or any(
        value.quality == "estimated" for _, value, _, _, _ in known) else "exact"
    def quantity(number, quality=quality):
        return m.QuantityValue(kind="quantity", magnitude=decimal_string(number), unit_id=target.id,
            quantity_kind=kind, basis=basis, unit_resolution="derived", quality=quality)
    known_nodes, unknown_nodes = [], []
    for index, value, support, raw in [(i, v, s, r) for i, v, s, r, _ in known] + missing:
        identifier = f"calculation:{step_id}:source-cell:{index}"
        state.internal_nodes.append(m.CalculationNode(id=identifier, operation="lookup",
            input_node_ids=support.input_node_ids or ["calculation:" + operation.input_step_id],
            fact_ids=sorted(support.facts), anchor_ids=sorted(support.anchors), output=value,
            quality=quality if isinstance(value, m.QuantityValue) else "estimated", rule_key=RULE,
            material_evidence=[m.MaterialEvaluation(**raw)] if family == "material" else [],
            measurement_evidence=[m.MeasurementEvaluation(**raw)] if family == "measurement" else []))
        if isinstance(value, m.UnavailableValue):
            unknown_nodes.append((identifier, set(support.members)))
        else:
            number = convert(value.magnitude, engine.units[value.unit_id], target)
            if value.unit_id != target.id:
                converted = identifier + ":convert"
                state.internal_nodes.append(m.CalculationNode(id=converted, operation="convert_unit", input_node_ids=[identifier],
                    fact_ids=sorted(support.facts), anchor_ids=sorted(support.anchors), output=quantity(number, value.quality),
                    quality=quality, rule_key="ifc.units.v1"))
                identifier = converted
            known_nodes.append((identifier, number))
    with localcontext() as context:
        context.prec = max(80, sum(len(str(number)) for _, number in known_nodes) + 32)
        total = sum((number for _, number in known_nodes), Decimal(0))
        level = 0
        while len(known_nodes) > 1:
            following = []
            for offset in range(0, len(known_nodes), 32):
                chunk = known_nodes[offset:offset + 32]
                identifier = f"calculation:{step_id}:known-sum:{level}:{offset}"
                number = sum((value for _, value in chunk), Decimal(0))
                state.internal_nodes.append(m.CalculationNode(id=identifier, operation="sum", input_node_ids=[key for key, _ in chunk],
                    output=quantity(number), quality=quality, rule_key=RULE))
                following.append((identifier, number))
            known_nodes, level = following, level + 1
    level = 0
    while len(unknown_nodes) > 1:
        following = []
        for offset in range(0, len(unknown_nodes), 32):
            chunk = unknown_nodes[offset:offset + 32]
            identifier = f"calculation:{step_id}:unresolved:{level}:{offset}"
            members = set().union(*(members for _, members in chunk))
            state.internal_nodes.append(m.CalculationNode(id=identifier, operation="project", input_node_ids=[key for key, _ in chunk],
                output=m.ReferencesValue(kind="references", entity_ids=sorted(members)), quality="estimated", rule_key=RULE))
            following.append((identifier, members))
        unknown_nodes, level = following, level + 1
    if missing:
        state.quality, state.completeness, state.coverage_complete = "lower_bound", "partial", False
        state.unresolved.update(unknown_members)
        explanation = (f"Known subtotal from {len(known)} proven nonnegative source cells; {len(missing)} quantity cells remain unresolved. "
            "This lower bound sums the available recorded/model-estimated values, retaining their source methods. It is not a complete total or a certified physical minimum; a zero subtotal does not establish physical absence.")
        state.coverage_explanation = explanation
        state.notes.append(explanation)
        state.issues.append(m.Issue(code="missing_information", entity_ids=sorted(unknown_members), message=m.LocalizedText(text=explanation)))
    else:
        state.quality = quality
    return quantity(total, state.quality), [known_nodes[0][0], *[identifier for identifier, _ in unknown_nodes]]

"""Compact source evidence by reference closure without truncating result members.

IFC extraction contains many unrelated property facts. An answer retains all
entities, relations and representations so source scope/hierarchy and object
selection remain inspectable, but includes only the facts, values, metadata and
geometry required by the supplied results/plans and their provenance.
"""
from __future__ import annotations

from collections import defaultdict, deque

from contracts import models as m
from contracts.validation import TABLES, validate_bundle, validate_plan, validate_result


def prune_ifc_context(bundle: m.KnowledgeBundle, results: list[m.QueryResult],
                      plans: list[m.QueryPlan]) -> m.KnowledgeBundle:
    """Return an independent minimal evidence closure for a union of IFC parts.

    Materialized sets and output values are never sampled or rewritten. Missing
    references fail explicitly instead of producing an apparently valid export.
    Source assets/links and the full semantic entity/relation skeleton survive;
    unused property facts and native property anchors do not cross the wire.
    All supplied source-valid plans and results are validated before returning.
    """
    indexes = {name: {getattr(item, "key" if name == "properties" else "id"): item
                      for item in getattr(bundle, name)} for name in TABLES}
    # AssetLink has no ID; retain all links and seed their source provenance.
    selected: dict[str, set[str]] = defaultdict(set)
    pending = deque()

    def keep(table, identifiers):
        for identifier in identifiers:
            if identifier is None:
                continue
            if identifier not in indexes[table]:
                raise ValueError(f"answer evidence references unknown {table}: {identifier}")
            if identifier not in selected[table]:
                selected[table].add(identifier)
                pending.append((table, identifier))

    def provenance(value):
        keep("runs", [value.run_id])
        keep("anchors", value.anchor_ids)

    def scope(value):
        keep("projects", [value.project_id])
        keep("documents", value.document_ids)
        keep("entities", [*value.entity_ids, *(value.exact_entity_ids or [])])
        keep("views", value.view_ids)

    def values(value):
        if value is None:
            return
        for item in m.walk_values(value):
            if isinstance(item, m.QuantityValue):
                keep("units", [item.unit_id])
                keep("anchors", item.unit_anchor_ids)
                if item.normalized is not None:
                    keep("units", [item.normalized.unit_id])
            elif isinstance(item, m.ReferencesValue):
                keep("entities", item.entity_ids)

    def field(value):
        if value.kind == "property":
            keep("properties", [value.key])

    def predicate(value):
        if value is None:
            return
        if value.kind in {"all", "any", "not"}:
            for operand in value.operands:
                predicate(operand)
        elif value.kind in {"compare", "field_present"}:
            field(value.field)
            if value.kind == "compare":
                values(value.value)
        elif value.kind == "related_to":
            keep("entities", value.entity_ids)
        elif value.kind == "spatial":
            keep("geometries", [value.geometry_id])
            values(value.distance)

    # Preserve the exact source revision and the entity/relation graph used by
    # plan validation, grain, inclusion/exclusion, and inheritance inspection.
    for table in ("projects", "documents", "assets", "entities", "relations", "representations"):
        keep(table, indexes[table])
    for link in bundle.asset_links:
        keep("assets", [link.source_asset_id, link.target_asset_id])
        provenance(link.provenance)

    for result in results:
        for claim in result.claims:
            scope(claim.scope)
            keep("concepts", claim.concept_ids)
            keep("properties", claim.property_keys)
            keep("coverage", claim.coverage_ids)
            values(claim.value)
            for binding in claim.evidence:
                keep("facts", binding.fact_ids)
                keep("anchors", binding.anchor_ids)
        for entity_set in result.entity_sets:
            scope(entity_set.scope)
            keep("entities", entity_set.entity_ids or [])
        for calculation in result.calculations:
            keep("facts", calculation.fact_ids)
            keep("anchors", calculation.anchor_ids)
            keep("calibrations", calculation.calibration_ids)
            values(calculation.output)
            for spatial in calculation.spatial_evidence:
                keep("entities", [spatial.subject_id, *spatial.related_ids])
                keep("anchors", spatial.anchor_ids)
            for measurement in calculation.measurement_evidence:
                keep("entities", [measurement.subject_id, *measurement.reference_entity_ids])
            for material in calculation.material_evidence:
                keep("entities", [material.subject_id])
                values(material.recorded_quantity)
                for layer in material.specified_layers:
                    values(layer.thickness)
            for route in calculation.route_evidence:
                keep("entities", [route.subject_id, route.target_id, *route.room_ids, *route.door_ids, *route.stair_ids])
                keep("anchors", route.anchor_ids)
        for issue in result.issues:
            keep("entities", issue.entity_ids)
            keep("facts", issue.fact_ids)
            keep("anchors", issue.anchor_ids)
    for plan in plans:
        scope(plan.scope)
        for step in plan.steps:
            operation = step.operation
            if isinstance(operation, m.SelectOperation):
                keep("concepts", operation.concept_ids)
                predicate(operation.where)
                predicate(operation.exclude)
            for reference in getattr(operation, "fields", []):
                field(reference)
            if getattr(operation, "field", None) is not None:
                field(operation.field)
            for reference in getattr(operation, "group_by", []):
                field(reference)
            if getattr(operation, "order_by", None) is not None:
                field(operation.order_by)
            keep("units", [getattr(operation, "output_unit_id", None)])
            keep("calibrations", getattr(operation, "calibration_ids", []))
            keep("entities", getattr(operation, "reference_entity_ids", []))

    # Anchor-to-boundary reverse index preserves the actual native boundary
    # record behind topology evidence, including its parent/corresponding links.
    boundary_anchors = defaultdict(list)
    for boundary in bundle.space_boundaries:
        for identifier in boundary.provenance.anchor_ids:
            boundary_anchors[identifier].append(boundary.id)

    def follow(table, identifier):
        item = indexes[table][identifier]
        if hasattr(item, "provenance"):
            provenance(item.provenance)
        if table == "documents":
            keep("projects", [item.project_id])
            keep("documents", [item.supersedes_document_id])
        elif table == "assets":
            keep("documents", [item.document_id])
        elif table == "runs":
            keep("assets", item.input_asset_ids)
        elif table == "concepts":
            keep("concepts", item.parent_ids)
        elif table == "frames":
            keep("assets", [item.asset_id])
            keep("units", [item.unit_id])
        elif table == "transforms":
            keep("frames", [item.from_frame_id, item.to_frame_id])
        elif table == "views":
            keep("assets", [item.asset_id])
            keep("frames", [item.frame_id])
            keep("views", [item.parent_view_id])
            keep("geometries", [item.boundary_geometry_id])
            keep("entities", item.depicts_entity_ids)
        elif table == "geometries":
            keep("frames", [item.frame_id])
        elif table == "anchors":
            keep("assets", [item.asset_id])
            keep("views", [item.view_id])
            keep("geometries", [item.geometry_id])
            keep("space_boundaries", boundary_anchors[identifier])
        elif table == "calibrations":
            keep("views", [item.view_id])
            keep("transforms", [item.transform_id])
        elif table == "features":
            keep("assets", [item.asset_id])
            keep("views", [item.view_id])
            keep("anchors", item.anchor_ids)
            keep("features", [item.table_id, *item.header_feature_ids])
        elif table == "entities":
            keep("projects", [item.project_id])
            keep("documents", [item.document_id])
            keep("concepts", item.concept_ids)
        elif table == "representations":
            keep("entities", [item.entity_id])
            keep("assets", [item.asset_id])
            keep("views", [item.view_id])
            keep("features", item.feature_ids)
            keep("anchors", item.anchor_ids)
            keep("geometries", item.geometry_ids)
        elif table == "facts":
            keep("entities", [item.subject_id])
            keep("properties", [item.property_key])
            keep("facts", [item.supersedes_fact_id])
            values(item.value)
        elif table == "relations":
            keep("entities", [item.subject_id, item.object_id])
        elif table == "coverage":
            scope(item.scope)
            keep("concepts", item.concept_ids)
            keep("properties", item.property_keys)
            keep("entities", [*item.examined_entity_ids, *item.unresolved_entity_ids, *item.candidate_entity_ids])
        elif table == "space_boundaries":
            keep("entities", [item.space_id, item.element_id])
            keep("space_boundaries", [item.parent_boundary_id, item.corresponding_boundary_id])

    while True:
        while pending:
            follow(*pending.popleft())
        # Preserve transformations between retained evidence frames, including
        # their provenance. New provenance can introduce more frames, so repeat
        # until the reference graph reaches a fixed point.
        for transform in bundle.transforms:
            if transform.from_frame_id in selected["frames"] and transform.to_frame_id in selected["frames"]:
                keep("transforms", [transform.id])
        if not pending:
            break

    retained = {name: [item.model_copy(deep=True) for item in getattr(bundle, name)
                       if getattr(item, "key" if name == "properties" else "id") in selected[name]]
                for name in TABLES}
    compact = m.KnowledgeBundle(**retained,
        asset_links=[link.model_copy(deep=True) for link in bundle.asset_links])
    validate_bundle(compact)
    plans_by_id = {plan.id: plan for plan in plans}
    for plan in plans:
        validate_plan(plan, compact)
    for result in results:
        validate_result(result, compact, plans_by_id.get(result.plan_id))
    return compact

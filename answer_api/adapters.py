"""Adapters from existing observations to typed, conservatively qualified parts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result


def candidate_part(candidate: m.ImageCandidateResponse, source: m.AnswerSourceBinding,
                   request_id: str, part_key: str = "answer") -> tuple[m.AnswerPart, m.AnswerEvidenceContext]:
    """Count source-bound *proposals*, never promote them to a physical total.

    Empty detections create a non-answer without a numeric claim. Even detections
    marked confident by the provider retain candidate evidence and unknown
    omission coverage; they cannot establish an exact count or a lower bound.
    """
    if candidate.request_id != request_id or candidate.image.sha256 != source.display_sha256:
        raise ValueError("candidate observations do not match the captured request and raster")
    if (candidate.image.width, candidate.image.height) != (source.display_width, source.display_height):
        raise ValueError("candidate observations use another display frame")
    prefix = f"drawing:{source.source_id}:{part_key}"
    project_id, document_id = prefix + ":project", prefix + ":document"
    original_id, display_id, run_id = prefix + ":original", prefix + ":display", prefix + ":run"
    frame_id, view_id = prefix + ":frame", prefix + ":view"
    provenance = m.Provenance(run_id=run_id, method="detected")
    asset_format = {"image": "other", "pdf": "pdf", "svg": "svg", "dxf": "dxf", "ifc": "ifc"}[source.kind]
    source_media = {"image": "application/octet-stream", "pdf": "application/pdf", "svg": "image/svg+xml", "dxf": "application/dxf", "ifc": "application/x-step"}[source.kind]
    bundle = m.KnowledgeBundle(
        projects=[m.Project(id=project_id, name="Imported drawing")],
        documents=[m.Document(id=document_id, project_id=project_id, logical_key=source.source_id,
                              revision=source.source_revision)],
        assets=[m.Asset(id=original_id, document_id=document_id, uri=f"/api/v1/sources/{source.source_id}",
                        sha256=source.source_sha256, format=asset_format, media_type=source_media,
                        source_collection="local_import", attribution="User-provided source", license="not supplied"),
                m.Asset(id=display_id, document_id=document_id, uri=f"/api/v1/sources/{source.source_id}/display",
                        sha256=candidate.image.sha256, format="png", media_type="image/png",
                        source_collection="local_import", attribution="Displayed source snapshot", license="not supplied")],
        asset_links=[m.AssetLink(source_asset_id=display_id, target_asset_id=original_id,
                                kind="rendered_from", provenance=provenance)],
        runs=[m.ExtractionRun(id=run_id, tool="image_candidate_adapter", version="1.0.0",
                             model_revision=candidate.provenance.returned_model,
                             config_sha256=hashlib.sha256(candidate.provenance.prompt_version.encode()).hexdigest(),
                             input_asset_ids=[original_id, display_id], started_at=datetime.now(timezone.utc))],
        concepts=[], properties=[], units=[],
        frames=[m.CoordinateFrame(id=frame_id, asset_id=display_id, dimension=2,
                                 space="presentation", axes=["right", "down"])],
        views=[m.View(id=view_id, asset_id=display_id, frame_id=frame_id, kind="page",
                      page_index=source.page_index, labels=[m.LocalizedText(text=source.scope_label)])])
    scope = m.Scope(project_id=project_id, document_ids=[document_id], view_ids=[view_id], universe="depicted_objects")
    policy = m.CountPolicy(grain="logical_object", hierarchy="all_matches", rule_key="drawing.unverified_hypotheses.v1")
    concepts: dict[str, str] = {}
    for item in candidate.candidates:
        concept_id = concepts.setdefault(item.category, prefix + ":concept:" + hashlib.sha256(item.category.encode()).hexdigest()[:16])
        entity_id = prefix + ":entity:" + item.id
        geometry_id, anchor_id = prefix + ":geometry:" + item.id, prefix + ":anchor:" + item.id
        observed = m.Provenance(run_id=run_id, method="detected", anchor_ids=[anchor_id])
        bundle.geometries.append(m.Geometry(id=geometry_id, frame_id=frame_id, shape=item.geometry))
        bundle.anchors.append(m.EvidenceAnchor(id=anchor_id, asset_id=display_id, view_id=view_id,
            selector=m.NativeSelector(kind="image_region", value=item.id), geometry_id=geometry_id,
            quote=m.LocalizedText(text=item.source_label) if item.source_label else None))
        feature_id = prefix + ":feature:" + item.id
        bundle.features.append(m.SourceFeature(id=feature_id, asset_id=display_id, view_id=view_id,
            kind="detection", anchor_ids=[anchor_id], provenance=observed))
        bundle.entities.append(m.Entity(id=entity_id, project_id=project_id, document_id=document_id,
            kind="element", concept_ids=[concept_id], labels=[m.LocalizedText(text=item.source_label or item.category)], provenance=observed))
        bundle.representations.append(m.Representation(id=prefix + ":representation:" + item.id,
            entity_id=entity_id, asset_id=display_id, view_id=view_id, feature_ids=[feature_id],
            anchor_ids=[anchor_id], geometry_ids=[geometry_id], provenance=observed))
    bundle.concepts.extend(m.Concept(id=identifier, labels=[m.LocalizedText(text=category)],
        definition="Unverified source-bound visual hypothesis; not a validated physical object.")
        for category, identifier in concepts.items())
    entity_ids = [entity.id for entity in bundle.entities]
    anchor_ids = [anchor.id for anchor in bundle.anchors]
    coverage_id = prefix + ":coverage"
    limitations = ["Visual detections have unresolved omission and membership coverage. The total is not confirmed.", *candidate.limitations]
    if candidate.detail:
        limitations.extend(candidate.detail.selection_limitations)
        if candidate.detail.deferred_observations:
            limitations.append("Additional observations remain unresolved after bounded detail inspection.")
    bundle.coverage.append(m.Coverage(id=coverage_id, scope=scope, concept_ids=list(concepts.values()),
        count_policy=policy, completeness="unknown", explanation=" ".join(limitations),
        provenance=provenance, operation_keys=["aggregate.count"],
        examined_entity_ids=entity_ids, candidate_entity_ids=entity_ids, unresolved_entity_ids=entity_ids))
    context = m.AnswerEvidenceContext(id=prefix + ":context", bundle=bundle,
        source_snapshot=m.AnswerSnapshot(**{key: getattr(source, key) for key in m.AnswerSnapshot.model_fields}))
    if not candidate.candidates:
        status = "unsupported_operation" if candidate.status == "unsupported" else "incomplete_coverage"
        message = ("The selected analysis cannot execute the requested operation." if status == "unsupported_operation"
                   else "The scan did not establish a reliable total. An empty candidate list does not establish that no objects are present.")
        result = m.QueryResult(id=prefix + ":result", request_id=request_id, status=status,
            issues=[m.Issue(code=status, message=m.LocalizedText(text=message + " " + " ".join(candidate.limitations)))],
            executor_version="drawing-observations-1")
        part = m.AnswerPart(key=part_key, status=status, result=result, evidence_context_id=context.id)
    else:
        plan = m.QueryPlan(id=prefix + ":plan", request_id=request_id, scope=scope, steps=[
            m.PlanStep(id="select", operation=m.SelectOperation(kind="select", concept_ids=list(concepts.values()), count_policy=policy)),
            m.PlanStep(id="count", operation=m.AggregateOperation(kind="aggregate", input_step_id="select", method="count"))],
            outputs={"observations": "count"}, required_capabilities=["select", "aggregate.count"])
        members = m.EntitySet(id=prefix + ":members", scope=scope, count_policy=policy,
                             count=len(entity_ids), entity_ids=entity_ids)
        value = m.CountValue(kind="count", value=len(entity_ids))
        node = m.CalculationNode(id=prefix + ":calculation", plan_step_id="count", operation="count",
                                included_set_id=members.id, anchor_ids=anchor_ids, output=value,
                                quality="estimated", rule_key=policy.rule_key)
        result = m.QueryResult(id=prefix + ":result", request_id=request_id, plan_id=plan.id, status="partial",
            claims=[m.Claim(id=prefix + ":claim", output_key="observations", name=", ".join(concepts), scope=scope,
                concept_ids=list(concepts.values()), value=value, quality="estimated", coverage_ids=[coverage_id],
                count_policy=policy, evidence=[m.EvidenceBinding(calculation_id=node.id, anchor_ids=anchor_ids,
                    entity_set_ids=[members.id], evidence_kind="candidate")])],
            entity_sets=[members], calculations=[node],
            issues=[m.Issue(code="incomplete_coverage", message=m.LocalizedText(text=" ".join(limitations)))],
            executor_version="drawing-observations-1")
        part = m.AnswerPart(key=part_key, status="partial", result=result, plan=plan, evidence_context_id=context.id)
        validate_plan(plan, bundle)
    validate_bundle(bundle)
    validate_result(result, bundle, part.plan)
    return part, context

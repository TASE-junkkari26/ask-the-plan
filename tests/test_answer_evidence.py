"""Compact evidence retains complete result sets, typed inputs and source closure."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from answer_api.evidence import prune_ifc_context
from answer_api.realize import realize_answer
from contracts import models as m
from contracts.validation import validate_answer, validate_bundle, validate_plan, validate_result
from tests.fixtures import bundle_data, plan_data, result_data


def large_source(count=3000):
    asset_id, run_id = "asset:source", "run:native"
    bundle = m.KnowledgeBundle(
        projects=[m.Project(id="project:source", name="Large source fixture")],
        documents=[m.Document(id="document:source", project_id="project:source", logical_key="model", revision="a" * 64)],
        assets=[m.Asset(id=asset_id, document_id="document:source", uri="ifc-session://source/model.ifc", sha256="a" * 64,
                        format="ifc", media_type="application/x-step", source_collection="fixture", attribution="Synthetic", license="CC0")],
        runs=[m.ExtractionRun(id=run_id, tool="synthetic_native_source", version="1", config_sha256="0" * 64,
                             input_asset_ids=[asset_id], started_at=datetime.now(timezone.utc))],
        concepts=[m.Concept(id="concept:door", labels=[m.LocalizedText(text="Door")], definition="Modeled door occurrence")],
        properties=[m.PropertyDefinition(key=f"property:unused:{index}", labels=[m.LocalizedText(text=f"Unrelated property {index}")],
            value_kind="text", definition="Unrelated source property retained in extraction, unused by the answer.") for index in range(8)],
        units=[])
    for index in range(count):
        entity_id, native_anchor, guid_anchor = f"door:{index}", f"anchor:step:{index}", f"anchor:guid:{index}"
        provenance = m.Provenance(run_id=run_id, anchor_ids=[native_anchor], method="native")
        bundle.entities.append(m.Entity(id=entity_id, project_id="project:source", document_id="document:source", kind="element",
            concept_ids=["concept:door"], labels=[m.LocalizedText(text="7.16" if index == 0 else f"Door {index}")], provenance=provenance))
        bundle.anchors.extend([
            m.EvidenceAnchor(id=native_anchor, asset_id=asset_id, selector=m.NativeSelector(kind="step_id", value=str(index + 1))),
            m.EvidenceAnchor(id=guid_anchor, asset_id=asset_id, selector=m.NativeSelector(kind="ifc_guid", value=f"source-guid-{index}"))])
        bundle.representations.append(m.Representation(id=f"representation:{index}", entity_id=entity_id, asset_id=asset_id,
            anchor_ids=[native_anchor, guid_anchor], provenance=provenance))
        for field in range(8):
            anchor_id = f"anchor:unused:{index}:{field}"
            bundle.anchors.append(m.EvidenceAnchor(id=anchor_id, asset_id=asset_id,
                selector=m.NativeSelector(kind="step_id", value=str(index + 1), property_path=[f"UnusedProperty{field}"])))
            bundle.facts.append(m.Fact(id=f"fact:unused:{index}:{field}", subject_id=entity_id, property_key=f"property:unused:{field}",
                status="present", value=m.TextValue(kind="text", value=m.LocalizedText(text="Unrelated extracted source text " * 20)),
                provenance=m.Provenance(run_id=run_id, anchor_ids=[anchor_id], method="native")))
    scope = m.Scope(project_id="project:source", document_ids=["document:source"], universe="modeled_objects")
    policy = m.CountPolicy(grain="occurrence", hierarchy="all_matches", rule_key="ifc.occurrence.v1")
    bundle.coverage.append(m.Coverage(id="coverage:doors", scope=scope, concept_ids=["concept:door"],
        count_policy=policy, completeness="complete", explanation="Complete native occurrence inventory for synthetic source.",
        provenance=m.Provenance(run_id=run_id, method="native"), examined_entity_ids=[entity.id for entity in bundle.entities]))
    plans, results = [], []
    for index, key in enumerate(("doors", "door_occurrences")):
        plan = m.QueryPlan(id=f"plan:{index}", request_id="request:compound", scope=scope, steps=[
            m.PlanStep(id="select", operation=m.SelectOperation(kind="select", concept_ids=["concept:door"], count_policy=policy)),
            m.PlanStep(id="count", operation=m.AggregateOperation(kind="aggregate", input_step_id="select", method="count"))], outputs={key: "count"})
        entity_set = m.EntitySet(id=f"set:{index}", scope=scope, count_policy=policy,
            count=count, entity_ids=[entity.id for entity in bundle.entities])
        value = m.CountValue(kind="count", value=count)
        anchors = [entity.provenance.anchor_ids[0] for entity in bundle.entities]
        node = m.CalculationNode(id=f"calculation:{index}", plan_step_id="count", operation="count", included_set_id=entity_set.id,
            anchor_ids=anchors, output=value, quality="exact", rule_key=policy.rule_key)
        result = m.QueryResult(id=f"result:{index}", request_id=plan.request_id, plan_id=plan.id, status="answered",
            claims=[m.Claim(id=f"claim:{index}", output_key=key, name="Door occurrences", scope=scope, concept_ids=["concept:door"], value=value,
                quality="exact", coverage_ids=["coverage:doors"], count_policy=policy,
                evidence=[m.EvidenceBinding(calculation_id=node.id, entity_set_ids=[entity_set.id], anchor_ids=anchors)])],
            entity_sets=[entity_set], calculations=[node], executor_version="fixture")
        plans.append(plan)
        results.append(result)
    return bundle, plans, results


class AnswerEvidenceTests(unittest.TestCase):
    def test_native_ifc_count_quantity_and_inherited_property_share_valid_compact_context(self):
        from ifc_engine.engine import IfcQueryEngine
        from tests.test_ifc_engine import sample_model

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.ifc"
            sample_model(path)
            engine = IfcQueryEngine.open(path)
            plans = [engine.plan("door"),
                     engine.plan("space", operation="sum", property="Qto_SpaceBaseQuantities.NetFloorArea", unit="m2"),
                     engine.plan("door", operation="lookup", storey="Ground", property="Pset_DoorCommon.FireRating")]
            results = [engine.execute(plan) for plan in plans]
            self.assertTrue(all(result.status == "answered" for result in results))
            compact = prune_ifc_context(engine.bundle, results, plans)
        self.assertLess(len(compact.facts), len(engine.bundle.facts))
        self.assertEqual(len(compact.facts), 5)
        self.assertEqual({fact.value.value.text for fact in compact.facts if isinstance(fact.value, m.TextValue)}, {"60 min", "90 min"})
        self.assertEqual({claim.coverage_ids[0] for result in results for claim in result.claims},
                         {coverage.id for coverage in compact.coverage})
        for result, plan in zip(results, plans):
            validate_result(result, compact, plan)

    def test_three_thousand_doors_two_parts_export_below_client_limit_without_dropping_members(self):
        bundle, plans, results = large_source()
        self.assertEqual(len(bundle.facts), 24000)
        compact = prune_ifc_context(bundle, results, plans)
        self.assertEqual(len(compact.entities), 3000)
        self.assertEqual(len(compact.representations), 3000)
        self.assertEqual(len(compact.anchors), 6000)
        self.assertFalse(compact.facts)
        self.assertFalse(compact.properties)
        self.assertEqual(compact.assets[0].sha256, "a" * 64)
        self.assertEqual(compact.entities[0].labels[0].text, "7.16")
        for result in results:
            self.assertEqual(len(result.entity_sets[0].entity_ids), 3000)
            self.assertEqual(result.claims[0].value.value, 3000)
            validate_result(result, compact, next(plan for plan in plans if plan.id == result.plan_id))
        question = "Count all modeled door occurrences twice."
        response = m.AnswerResponse(request_id="request:compound", question=question,
            question_sha256=hashlib.sha256(question.encode()).hexdigest(),
            source=m.AnswerSourceBinding(source_id="source:fixture", kind="ifc", source_sha256="a" * 64,
                                         source_revision="a" * 64, scope_label="Entire model"),
            interpretation=m.AnswerIntent(scope_label="Entire model", requested_parts=[
                m.AnswerRequestedPart(key=result.claims[0].output_key, question=question) for result in results]),
            parts=[m.AnswerPart(key=result.claims[0].output_key, status="answered", result=result, plan=plan, evidence_context_id="context:shared")
                   for result, plan in zip(results, plans)],
            evidence_contexts=[m.AnswerEvidenceContext(id="context:shared", bundle=compact)], metrics=m.AnswerMetrics(elapsed_ms=0))
        response.narrative = realize_answer(response)
        validate_answer(response)
        encoded = response.model_dump_json().encode()
        self.assertLess(len(encoded), 32 * 1024 * 1024)
        self.assertLess(len(encoded), 5 * 1024 * 1024)

    def test_quantity_supersession_units_geometry_calibration_and_frames_close_recursively(self):
        bundle = m.KnowledgeBundle.model_validate(bundle_data())
        plan = m.QueryPlan.model_validate(plan_data())
        result = m.QueryResult.model_validate(result_data())
        prior = bundle.facts[0].model_copy(deep=True)
        prior.id = "fact:prior_area"
        bundle.facts[0].supersedes_fact_id = prior.id
        bundle.facts.append(prior)
        result.calculations[0].calibration_ids = ["calibration:1"]
        compact = prune_ifc_context(bundle, [result], [plan])
        self.assertEqual({fact.id for fact in compact.facts}, {"fact:area", "fact:prior_area"})
        self.assertEqual({unit.id for unit in compact.units}, {"unit:m", "unit:m2", "unit:mm2", "unit:px"})
        self.assertEqual({item.id for item in compact.calibrations}, {"calibration:1"})
        self.assertEqual({item.id for item in compact.transforms}, {"transform:pixel_to_metric"})
        self.assertEqual({item.id for item in compact.geometries}, {"geometry:room", "geometry:scale"})
        self.assertEqual({item.id for item in compact.frames}, {"frame:metric", "frame:pixel"})
        self.assertEqual(compact.asset_links, bundle.asset_links)
        validate_bundle(compact)
        validate_plan(plan, compact)
        validate_result(result, compact, plan)

    def test_plan_predicate_property_survives_without_unrelated_fact_inventory(self):
        bundle = m.KnowledgeBundle.model_validate(bundle_data())
        plan = m.QueryPlan.model_validate(plan_data())
        result = m.QueryResult.model_validate(result_data())
        unrelated = m.PropertyDefinition(key="property:unused_filter", labels=[], value_kind="text", definition="An unused filter definition.")
        bundle.properties.append(unrelated)
        plan.steps[0].operation.where = m.ComparePredicate(kind="compare", field=m.FieldRef(kind="property", key=unrelated.key),
            operator="eq", value=m.TextValue(kind="text", value=m.LocalizedText(text="literal")))
        compact = prune_ifc_context(bundle, [result], [plan])
        self.assertIn(unrelated.key, {item.key for item in compact.properties})
        self.assertEqual(len(compact.facts), 1)

    def test_snapshot_is_independent_and_unknown_evidence_fails_explicitly(self):
        bundle = m.KnowledgeBundle.model_validate(bundle_data())
        plan = m.QueryPlan.model_validate(plan_data())
        result = m.QueryResult.model_validate(result_data())
        compact = prune_ifc_context(bundle, [result], [plan])
        bundle.coverage[0].explanation = "Later mutable engine state"
        bundle.facts[0].provenance.anchor_ids.clear()
        self.assertNotEqual(compact.coverage[0].explanation, bundle.coverage[0].explanation)
        self.assertTrue(compact.facts[0].provenance.anchor_ids)
        result.calculations[0].anchor_ids.append("anchor:stale")
        with self.assertRaisesRegex(ValueError, "unknown anchors"):
            prune_ifc_context(bundle, [result], [plan])


if __name__ == "__main__":
    unittest.main()

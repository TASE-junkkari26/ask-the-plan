"""Semantic regression cases for cross-format extraction and answer contracts."""
from copy import deepcopy
import unittest

from pydantic import ValidationError

from contracts.models import (
    CapabilityManifest, Claim, CountValue, EntitySet, Fact, KnowledgeBundle,
    PolygonPart, QuantityValue, QueryPlan, QueryResult, TableValue, Unit,
)
from contracts.validation import validate_bundle, validate_plan, validate_result
from tests.fixtures import (
    area_value, bundle_data, count_plan_data, count_result_data, plan_data,
    provenance, result_data,
)


class StructuralContractTests(unittest.TestCase):
    def test_roundtrip_preserves_decimal_strings_and_literal_room_id(self):
        data = KnowledgeBundle.model_validate(bundle_data())
        restored = KnowledgeBundle.model_validate_json(data.model_dump_json())
        self.assertEqual(restored, data)
        self.assertEqual(restored.facts[0].value.magnitude, "19000000")
        self.assertEqual(restored.entities[1].labels[0].text, "7.16")

    def test_unknown_unit_cannot_carry_normalized_number(self):
        data = area_value()
        data.update(unit_id=None, unit_resolution="unknown")
        with self.assertRaises(ValidationError):
            QuantityValue.model_validate(data)

    def test_unknown_and_dimensionless_are_not_the_same(self):
        data = area_value()
        data.update(unit_id=None, unit_resolution="unknown", normalized=None)
        self.assertIsNone(QuantityValue.model_validate(data).unit_id)
        dimensionless = Unit(id="unit:1", symbol="1", kind="physical", dimension=(0, 0, 0, 0, 0, 0, 0), si_multiplier="1")
        self.assertEqual(dimensionless.symbol, "1")

    def test_count_rejects_float_and_boolean(self):
        for value in (1.5, 1.0, True, -1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                CountValue(kind="count", value=value)

    def test_absence_cannot_have_a_numeric_value(self):
        data = bundle_data()["facts"][0]
        data["status"] = "not_in_source"
        with self.assertRaises(ValidationError):
            Fact.model_validate(data)
        data["value"] = None
        self.assertEqual(Fact.model_validate(data).status, "not_in_source")

    def test_present_fact_requires_value(self):
        data = bundle_data()["facts"][0]
        data["value"] = None
        with self.assertRaises(ValidationError):
            Fact.model_validate(data)

    def test_missing_table_cell_is_explicit_in_partial_answer(self):
        result = result_data()
        result["status"] = "partial"
        result["issues"] = [{"code": "missing_information", "message": {"text": "A room property is missing."}}]
        missing = {"kind": "unavailable", "reason": "not_in_source", "explanation": "Room occupancy not recorded."}
        value = {"kind": "record", "fields": {"area": area_value(), "occupancy": missing}}
        result["claims"][0]["value"] = value
        result["calculations"][0]["output"] = deepcopy(value)
        self.assertEqual(QueryResult.model_validate(result).status, "partial")
        result["status"] = "answered"
        result["issues"] = []
        with self.assertRaises(ValidationError):
            QueryResult.model_validate(result)

    def test_polygon_holes_must_have_closed_rings(self):
        valid = bundle_data()["geometries"][0]["shape"]["polygons"][0]
        self.assertEqual(len(PolygonPart.model_validate(valid).holes), 1)
        valid["holes"][0].pop()
        with self.assertRaises(ValidationError):
            PolygonPart.model_validate(valid)

    def test_non_answer_has_issue_and_no_successful_claim(self):
        data = {"id": "result:missing", "request_id": "request:area", "status": "missing_information",
                "executor_version": "fixture-1", "issues": [{"code": "missing_information", "message": {"text": "No occupancy property."}}]}
        QueryResult.model_validate(data)
        data["claims"] = result_data()["claims"]
        with self.assertRaises(ValidationError):
            QueryResult.model_validate(data)

    def test_non_answer_requires_matching_issue_code(self):
        data = {"id": "result:missing", "request_id": "request:area", "status": "missing_information",
                "executor_version": "fixture-1", "issues": [{"code": "execution_error", "message": {"text": "Different failure."}}]}
        with self.assertRaises(ValidationError):
            QueryResult.model_validate(data)

    def test_table_rows_match_explicit_columns(self):
        table = {"kind": "table", "columns": [{"key": "width", "label": {"text": "Width"}}],
                 "rows": [{"width": {"kind": "text", "value": {"text": "5'-10 3/8\""}}}]}
        TableValue.model_validate(table)
        table["rows"][0]["height"] = {"kind": "count", "value": 1}
        with self.assertRaises(ValidationError):
            TableValue.model_validate(table)

    def test_step_dag_rejects_forward_reference(self):
        data = plan_data()
        data["steps"].reverse()
        with self.assertRaises(ValidationError):
            QueryPlan.model_validate(data)

    def test_entity_set_count_cannot_disagree_with_members(self):
        data = count_result_data()["entity_sets"][0]
        data["count"] = 2
        with self.assertRaises(ValidationError):
            EntitySet.model_validate(data)

    def test_count_claim_requires_semantic_count_policy(self):
        data = count_result_data()["claims"][0]
        data.pop("count_policy")
        with self.assertRaises(ValidationError):
            Claim.model_validate(data)


class SemanticContractTests(unittest.TestCase):
    def setUp(self):
        self.bundle = KnowledgeBundle.model_validate(bundle_data())

    def test_complete_area_example_validates(self):
        validate_bundle(self.bundle)
        plan = QueryPlan.model_validate(plan_data())
        validate_plan(plan, self.bundle)
        validate_result(QueryResult.model_validate(result_data()), self.bundle, plan)

    def test_exact_count_with_materialized_evidence_validates(self):
        plan = QueryPlan.model_validate(count_plan_data())
        validate_plan(plan, self.bundle)
        validate_result(QueryResult.model_validate(count_result_data()), self.bundle, plan)

    def test_duplicate_canonical_ids_rejected(self):
        data = bundle_data()
        data["entities"].append(deepcopy(data["entities"][1]))
        with self.assertRaises(ValueError):
            validate_bundle(KnowledgeBundle.model_validate(data))

    def test_unresolved_evidence_reference_rejected(self):
        data = bundle_data()
        data["facts"][0]["provenance"]["anchor_ids"] = ["missing:anchor"]
        with self.assertRaises(ValueError):
            validate_bundle(KnowledgeBundle.model_validate(data))

    def test_area_conversion_uses_square_millimetre_scale(self):
        validate_bundle(self.bundle)  # 19,000,000 mm2 = 19 m2, not 19,000 m2.
        data = bundle_data()
        data["facts"][0]["value"]["normalized"]["magnitude"] = "19000"
        with self.assertRaises(ValueError):
            validate_bundle(KnowledgeBundle.model_validate(data))

    def test_area_cannot_normalize_to_length(self):
        data = bundle_data()
        data["facts"][0]["value"]["normalized"] = {"magnitude": "19", "unit_id": "unit:m"}
        with self.assertRaises(ValueError):
            validate_bundle(KnowledgeBundle.model_validate(data))

    def test_frame_physical_axes_require_length_unit(self):
        data = bundle_data()
        data["frames"][0]["unit_id"] = "unit:m2"
        with self.assertRaises(ValueError):
            validate_bundle(KnowledgeBundle.model_validate(data))

    def test_aggregation_cycle_rejected(self):
        data = bundle_data()
        data["relations"] += [
            {"id": "relation:a", "subject_id": "floor:1", "predicate": "aggregates", "object_id": "room:1", "provenance": provenance("anchor:room")},
            {"id": "relation:b", "subject_id": "room:1", "predicate": "aggregates", "object_id": "floor:1", "provenance": provenance("anchor:room")},
        ]
        with self.assertRaises(ValueError):
            validate_bundle(KnowledgeBundle.model_validate(data))

    def test_calibration_cannot_apply_to_an_unrelated_view(self):
        data = bundle_data()
        data["calibrations"][0]["view_id"] = "view:cad"
        with self.assertRaises(ValueError):
            validate_bundle(KnowledgeBundle.model_validate(data))

    def test_geometry_dimension_must_match_coordinate_frame(self):
        data = bundle_data()
        data["geometries"][1]["shape"]["minimum"] = [0, 400, 0]
        data["geometries"][1]["shape"]["maximum"] = [500, 420, 1]
        with self.assertRaises(ValueError):
            validate_bundle(KnowledgeBundle.model_validate(data))

    def test_unknown_plan_property_rejected(self):
        data = plan_data()
        data["steps"][1]["operation"]["field"]["key"] = "missing:property"
        with self.assertRaises(ValueError):
            validate_plan(QueryPlan.model_validate(data), self.bundle)

    def test_sum_area_cannot_request_length_output(self):
        data = plan_data()
        data["steps"][1]["operation"] = {"kind": "aggregate", "input_step_id": "select", "method": "sum",
                                          "field": {"kind": "property", "key": "property:net_area"}, "output_unit_id": "unit:m"}
        with self.assertRaises(ValueError):
            validate_plan(QueryPlan.model_validate(data), self.bundle)

    def test_unknown_document_in_scope_rejected(self):
        data = plan_data()
        data["scope"]["document_ids"] = ["missing:document"]
        with self.assertRaises(ValueError):
            validate_plan(QueryPlan.model_validate(data), self.bundle)

    def test_pixel_area_without_view_calibration_rejected(self):
        data = bundle_data()
        data["calibrations"] = []
        data["geometries"][0]["frame_id"] = "frame:pixel"
        room_anchor = data["anchors"][0]
        room_anchor.update(asset_id="png:a", view_id="view:pixel", selector={"kind": "image_region", "value": "room"})
        data["representations"][0].update(asset_id="png:a", view_id="view:pixel")
        bundle = KnowledgeBundle.model_validate(data)
        validate_bundle(bundle)
        plan = plan_data()
        plan["steps"][1]["operation"] = {"kind": "measure", "input_step_id": "select", "metric": "area", "output_unit_id": "unit:m2", "basis": "net"}
        with self.assertRaises(ValueError):
            validate_plan(QueryPlan.model_validate(plan), bundle)

    def test_incomplete_inventory_cannot_prove_exact_zero(self):
        data = bundle_data()
        data["coverage"][0]["completeness"] = "partial"
        result = QueryResult.model_validate(count_result_data(members=()))
        with self.assertRaises(ValueError):
            validate_result(result, KnowledgeBundle.model_validate(data), QueryPlan.model_validate(count_plan_data()))

    def test_partial_lower_bound_count_can_report_incomplete_coverage(self):
        data = bundle_data()
        data["coverage"][0]["completeness"] = "partial"
        result = count_result_data()
        result["status"] = "partial"
        result["issues"] = [{"code": "incomplete_coverage", "message": {"text": "Only one room was resolved."}}]
        result["claims"][0]["quality"] = "lower_bound"
        result["calculations"][0]["quality"] = "lower_bound"
        validate_result(QueryResult.model_validate(result), KnowledgeBundle.model_validate(data))

    def test_count_does_not_include_both_assembly_and_its_part(self):
        data = bundle_data()
        parent = data["entities"][1]
        parent["kind"] = "assembly"
        child = deepcopy(parent)
        child.update(id="room:part", kind="part")
        data["entities"].append(child)
        data["relations"].append({"id": "relation:assembly_part", "subject_id": "room:1", "predicate": "aggregates",
                                  "object_id": "room:part", "provenance": provenance("anchor:room")})
        result = count_result_data(members=("room:1", "room:part"))
        with self.assertRaises(ValueError):
            validate_result(QueryResult.model_validate(result), KnowledgeBundle.model_validate(data))

    def test_calculation_dag_cannot_reference_itself(self):
        result = result_data()
        result["calculations"][0]["input_node_ids"] = ["calculation:area"]
        with self.assertRaises(ValueError):
            validate_result(QueryResult.model_validate(result), self.bundle)

    def test_claim_output_key_must_name_a_plan_output(self):
        result = result_data()
        result["claims"][0]["output_key"] = "not_requested"
        with self.assertRaises(ValueError):
            validate_result(QueryResult.model_validate(result), self.bundle, QueryPlan.model_validate(plan_data()))

    def test_root_calculation_must_bind_requested_plan_step(self):
        result = result_data()
        result["calculations"][0]["plan_step_id"] = "select"
        with self.assertRaises(ValueError):
            validate_result(QueryResult.model_validate(result), self.bundle, QueryPlan.model_validate(plan_data()))

    def test_claim_value_cannot_disagree_with_root_calculation(self):
        result = result_data()
        result["claims"][0]["value"]["magnitude"] = "20"
        result["claims"][0]["value"]["normalized"]["magnitude"] = "20"
        with self.assertRaises(ValueError):
            validate_result(QueryResult.model_validate(result), self.bundle, QueryPlan.model_validate(plan_data()))

    def test_grouped_counts_can_be_ranked_by_their_derived_column(self):
        data = count_plan_data()
        data["steps"][1]["operation"].update(group_by=[{"kind": "concept", "key": "concept:room"}], value_key="room_count")
        data["steps"].append({"id": "rank", "operation": {"kind": "rank", "input_step_id": "count",
                                                       "field": {"kind": "result_column", "key": "room_count"},
                                                       "direction": "descending", "limit": 1}})
        data["outputs"] = {"largest_group": "rank"}
        capabilities = CapabilityManifest(executor_version="fixture-1", operations=["select", "aggregate.count", "rank"],
                                         relation_predicates=["contains", "aggregates"], property_keys=["property:net_area"],
                                         concept_ids=["concept:room", "concept:storey"], supported_formats=["dxf", "png"], limitations=[])
        validate_plan(QueryPlan.model_validate(data), self.bundle, capabilities)

    def test_runtime_must_advertise_actual_aggregate_capability(self):
        capabilities = CapabilityManifest(executor_version="fixture-1", operations=["select", "project"],
                                         relation_predicates=[], property_keys=["property:net_area"],
                                         concept_ids=["concept:room", "concept:storey"], supported_formats=["dxf", "png"], limitations=[])
        with self.assertRaises(ValueError):
            validate_plan(QueryPlan.model_validate(plan_data()), self.bundle, capabilities)


if __name__ == "__main__":
    unittest.main()

"""Wire invariants for unreviewed, image-bound candidate proposals."""
from copy import deepcopy
import unittest

from pydantic import ValidationError

from contracts.models import ImageCandidateError, ImageCandidateResponse


def candidate_response_data():
    """Synthetic proposal fixture; it is not a detection from source drawings."""
    return {
        "request_id": "request:test",
        "image": {
            "sha256": "a" * 64,
            "inference_sha256": "b" * 64,
            "width": 1600,
            "height": 1200,
        },
        "status": "ok",
        "candidates": [{
            "id": "candidate-001",
            "category": "window",
            "source_label": "121.A",
            "geometry": {"kind": "box", "minimum": [200, 300], "maximum": [280, 330]},
            "uncertain": False,
            "uncertainty_reason": None,
            "visual_cue": "Parallel window lines within an exterior wall.",
        }],
        "limitations": [],
        "provenance": {
            "requested_model": "test-model",
            "returned_model": "test-model-revision",
            "prompt_version": "test-prompt-v1",
        },
        "metrics": {"elapsed_ms": 12.5, "prompt_tokens": None, "completion_tokens": None},
    }


class ImageCandidateContractTests(unittest.TestCase):
    def test_round_trip_keeps_source_identity_and_literal_label(self):
        result = ImageCandidateResponse.model_validate(candidate_response_data())
        self.assertEqual(ImageCandidateResponse.model_validate_json(result.model_dump_json()), result)
        self.assertEqual(result.candidates[0].source_label, "121.A")
        self.assertNotEqual(result.image.sha256, result.image.inference_sha256)
        self.assertEqual(result.inventory_completeness, "unverified")

    def test_empty_detections_are_not_a_final_zero_count(self):
        data = candidate_response_data()
        data["candidates"] = []
        result = ImageCandidateResponse.model_validate(data)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.inventory_completeness, "unverified")
        data["count"] = 0
        with self.assertRaises(ValidationError):
            ImageCandidateResponse.model_validate(data)

    def test_geometry_rejects_nonfinite_negative_3d_zero_area_and_outside_image(self):
        for minimum, maximum in (
            ([float("nan"), 10], [20, 30]),
            ([10, 10], [float("inf"), 30]),
            ([-1, 10], [20, 30]),
            ([10, 10, 0], [20, 30, 0]),
            ([10, 10], [10, 30]),
            ([10, 10], [1601, 30]),
            ([10, 10], [20, 1201]),
        ):
            with self.subTest(minimum=minimum, maximum=maximum):
                data = candidate_response_data()
                data["candidates"][0]["geometry"].update(minimum=minimum, maximum=maximum)
                with self.assertRaises(ValidationError):
                    ImageCandidateResponse.model_validate(data)

    def test_duplicate_ids_and_exact_proposals_are_rejected_but_overlap_is_allowed(self):
        data = candidate_response_data()
        second = deepcopy(data["candidates"][0])
        data["candidates"].append(second)
        with self.assertRaises(ValidationError):
            ImageCandidateResponse.model_validate(data)
        second["id"] = "candidate-002"
        with self.assertRaises(ValidationError):
            ImageCandidateResponse.model_validate(data)
        second["geometry"]["maximum"][0] += 1
        self.assertEqual(len(ImageCandidateResponse.model_validate(data).candidates), 2)

    def test_uncertainty_requires_a_nonblank_reason(self):
        data = candidate_response_data()
        data["candidates"][0]["uncertain"] = True
        for reason in (None, "", "  "):
            data["candidates"][0]["uncertainty_reason"] = reason
            with self.subTest(reason=reason), self.assertRaises(ValidationError):
                ImageCandidateResponse.model_validate(data)
        data["candidates"][0]["uncertainty_reason"] = "The symbol partly overlaps a wall line."
        self.assertTrue(ImageCandidateResponse.model_validate(data).candidates[0].uncertain)

    def test_non_ok_statuses_require_explanations_and_non_detection_statuses_are_empty(self):
        for status in ("partial", "unreadable", "unsupported"):
            data = candidate_response_data()
            data["status"] = status
            with self.subTest(status=status), self.assertRaises(ValidationError):
                ImageCandidateResponse.model_validate(data)
            data["limitations"] = ["The requested information is not fully visible."]
            if status != "partial":
                with self.assertRaises(ValidationError):
                    ImageCandidateResponse.model_validate(data)
                data["candidates"] = []
            self.assertEqual(ImageCandidateResponse.model_validate(data).status, status)

    def test_candidate_limit_requires_partial_and_does_not_allow_silent_overflow(self):
        data = candidate_response_data()
        first = data["candidates"][0]
        data["candidates"] = []
        for index in range(100):
            item = deepcopy(first)
            item["id"] = f"candidate-{index + 1:03d}"
            item["geometry"]["minimum"][0] += index
            item["geometry"]["maximum"][0] += index
            data["candidates"].append(item)
        with self.assertRaises(ValidationError):
            ImageCandidateResponse.model_validate(data)
        data.update(status="partial", limitations=["Candidate limit reached."])
        self.assertEqual(len(ImageCandidateResponse.model_validate(data).candidates), 100)
        data["candidates"].append(deepcopy(first))
        with self.assertRaises(ValidationError):
            ImageCandidateResponse.model_validate(data)

    def test_unknown_coverage_scope_bad_hashes_and_nonfinite_metrics_are_rejected(self):
        for patch in (
            {"inventory_completeness": "complete"},
            {"scope": "whole_building"},
            {"image": {**candidate_response_data()["image"], "sha256": "not-a-hash"}},
            {"metrics": {"elapsed_ms": float("inf")}},
            {"metrics": {"elapsed_ms": 0, "prompt_tokens": True}},
        ):
            data = candidate_response_data()
            data.update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                ImageCandidateResponse.model_validate(data)

    def test_error_contract_round_trip(self):
        data = {"request_id": "request:test", "code": "invalid_image", "message": "Image could not be decoded.", "retryable": False}
        error = ImageCandidateError.model_validate(data)
        self.assertEqual(ImageCandidateError.model_validate_json(error.model_dump_json()), error)

    def test_preprocessing_metadata_keeps_display_frame_and_original_payload_compatibility(self):
        original = ImageCandidateResponse.model_validate(candidate_response_data())
        self.assertIsNone(original.provenance.preprocessing)
        self.assertIsNone(original.metrics.preparation_ms)
        self.assertIsNone(original.metrics.preparation_cache_hit)
        data = candidate_response_data()
        data["provenance"]["preprocessing"] = {
            "mode": "overview", "pipeline_version": "test-pipeline",
            "prepared_id": "prepared:test", "input_width": 800, "input_height": 600,
        }
        data["metrics"].update(preparation_ms=14.25, preparation_cache_hit=True)
        result = ImageCandidateResponse.model_validate(data)
        self.assertEqual(result.image.width, 1600)
        self.assertEqual(result.image.height, 1200)
        self.assertEqual(result.provenance.preprocessing.input_width, 800)
        self.assertEqual(result.candidates[0].geometry.minimum, [200.0, 300.0])
        self.assertEqual(ImageCandidateResponse.model_validate_json(result.model_dump_json()), result)

    def test_preprocessing_metadata_rejects_bad_mode_dimensions_and_timing(self):
        for patch in ({"mode": "largest_region"}, {"input_width": 0},
                      {"input_height": True}, {"input_width": 2.5}, {"prepared_id": ""}):
            data = candidate_response_data()
            data["provenance"]["preprocessing"] = {
                "mode": "original", "input_width": 1600, "input_height": 1200, **patch,
            }
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                ImageCandidateResponse.model_validate(data)
        for timing in (-1, float("inf"), float("nan")):
            data = candidate_response_data()
            data["metrics"]["preparation_ms"] = timing
            with self.subTest(timing=timing), self.assertRaises(ValidationError):
                ImageCandidateResponse.model_validate(data)


if __name__ == "__main__":
    unittest.main()

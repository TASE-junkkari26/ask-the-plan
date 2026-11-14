"""Artifact-boundary regressions for source pixel identity and crop evidence."""
from __future__ import annotations

import copy
import unittest

from pydantic import ValidationError

from contracts.models import InspectRegionArgs, PreparedDrawing


def _manifest() -> dict:
    return {
        "id": "prepared:test", "source_sha256": "1" * 64,
        "config_sha256": "2" * 64, "pipeline_version": "test",
        "source_uri": "drawing.png", "original_uri": "original.png",
        "source_image_uri": "source.png", "source_width": 240, "source_height": 120,
        "source_frame_id": "source",
        "regions": [
            {
                "id": "full", "role": "full_source", "source_bbox": (0, 0, 240, 120),
                "frame_id": "full-pixels", "image_uri": "source.png", "width": 240, "height": 120,
                "overview_uri": "regions/full-overview.png", "overview_width": 120, "overview_height": 60,
                "overview_frame_id": "full-overview", "reason": "Retained source",
                "to_source": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "overview_to_source": [[2, 0, 0], [0, 2, 0], [0, 0, 1]],
            },
            {
                "id": "room-candidate", "role": "drawing_candidate", "source_bbox": (30, 20, 210, 100),
                "frame_id": "candidate-pixels", "image_uri": "regions/candidate.png", "width": 180, "height": 80,
                "overview_uri": "regions/candidate-overview.png", "overview_width": 90, "overview_height": 40,
                "overview_frame_id": "candidate-overview", "reason": "Layout proposal",
                "to_source": [[1, 0, 30], [0, 1, 20], [0, 0, 1]],
                "overview_to_source": [[2, 0, 30], [0, 2, 20], [0, 0, 1]],
            },
        ],
        "ocr": {"status": "complete", "engine": "test", "spans": [
            {"id": "word:1", "text": "5.10", "frame_id": "source", "bbox": (50, 45, 75, 57),
             "engine": "test", "confidence": 0.8},
        ]},
    }


class PreprocessContractTests(unittest.TestCase):
    def test_roundtrip_keeps_literal_ocr_and_offset_overview_mapping(self):
        manifest = PreparedDrawing.model_validate(_manifest())
        restored = PreparedDrawing.model_validate_json(manifest.model_dump_json())
        self.assertEqual(restored.ocr.spans[0].text, "5.10")
        region = restored.regions[1]
        # Opposite overview corners must map onto the original crop boundary.
        matrix = region.overview_to_source
        mapped = (matrix[0][2], matrix[1][2],
                  matrix[0][0] * region.overview_width + matrix[0][2],
                  matrix[1][1] * region.overview_height + matrix[1][2])
        self.assertEqual(mapped, region.source_bbox)

    def test_wrong_transform_cannot_appear_as_valid_source_evidence(self):
        for field, value in (
            ("to_source", [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            ("overview_to_source", [[1, 0, 30], [0, 1, 20], [0, 0, 1]]),
            ("to_source", [[1, 0, 30], [0, 1, 20]]),
            ("to_source", [[1, 0, float("nan")], [0, 1, 20], [0, 0, 1]]),
        ):
            with self.subTest(field=field, value=value):
                data = _manifest()
                data["regions"][1][field] = value
                with self.assertRaises(ValidationError):
                    PreparedDrawing.model_validate(data)

    def test_crop_and_overview_sizes_cannot_disagree_with_pixels(self):
        for updates in ({"width": 179}, {"overview_width": 181}, {"width": True},
                        {"source_bbox": (30, 20, 250, 100), "width": 220,
                         "overview_to_source": [[220 / 90, 0, 30], [0, 2, 20], [0, 0, 1]]}):
            with self.subTest(updates=updates):
                data = _manifest()
                data["regions"][1].update(updates)
                with self.assertRaises(ValidationError):
                    PreparedDrawing.model_validate(data)

    def test_frame_aliases_cannot_silently_change_coordinate_meaning(self):
        for alias in ("source", "full-pixels", "full-overview", "candidate-pixels"):
            with self.subTest(alias=alias):
                data = _manifest()
                data["regions"][1]["overview_frame_id"] = alias
                with self.assertRaises(ValidationError):
                    PreparedDrawing.model_validate(data)

    def test_ocr_cannot_claim_crop_pixels_as_source_pixels(self):
        for change in ({"frame_id": "candidate-pixels"}, {"bbox": (50, 45, 241, 57)},
                       {"confidence": 1.1}, {"bbox": (50, 45, 50, 57)}):
            with self.subTest(change=change):
                data = _manifest()
                data["ocr"]["spans"][0].update(change)
                with self.assertRaises(ValidationError):
                    PreparedDrawing.model_validate(data)

    def test_ocr_status_and_span_identity_are_explicit(self):
        for status in ("not_requested", "unavailable", "failed"):
            with self.subTest(status=status):
                data = _manifest()
                data["ocr"]["status"] = status
                with self.assertRaises(ValidationError):
                    PreparedDrawing.model_validate(data)
        data = _manifest()
        data["ocr"]["spans"].append(copy.deepcopy(data["ocr"]["spans"][0]))
        with self.assertRaises(ValidationError):
            PreparedDrawing.model_validate(data)

    def test_artifacts_cannot_name_absolute_or_traversing_files(self):
        for uri in ("../source.png", "/source.png", "C:/source.png", "regions\\source.png"):
            with self.subTest(uri=uri):
                data = _manifest()
                data["regions"][1]["image_uri"] = uri
                with self.assertRaises(ValidationError):
                    PreparedDrawing.model_validate(data)

    def test_exactly_one_complete_source_region_must_remain_available(self):
        missing = _manifest()
        missing["regions"].pop(0)
        duplicate = _manifest()
        extra = copy.deepcopy(duplicate["regions"][0])
        extra.update(id="full-copy", frame_id="full-copy-pixels", overview_frame_id="full-copy-overview")
        duplicate["regions"].append(extra)
        wrong_artifact = _manifest()
        wrong_artifact["source_image_uri"] = "other-source.png"
        truncated = _manifest()
        truncated["regions"][0].update(source_bbox=(0, 0, 238, 120), width=238,
                                         overview_to_source=[[238 / 120, 0, 0], [0, 2, 0], [0, 0, 1]])
        for name, data in (("missing", missing), ("duplicate", duplicate),
                           ("wrong artifact", wrong_artifact), ("truncated", truncated)):
            with self.subTest(case=name), self.assertRaises(ValidationError):
                PreparedDrawing.model_validate(data)

    def test_inspection_arguments_reject_nonfinite_empty_and_reversed_boxes(self):
        for bbox in ((0, 0, float("inf"), 2), (0, 0, 0, 2), (2, 0, 1, 2), (-1, 0, 1, 2)):
            with self.subTest(bbox=bbox), self.assertRaises(ValidationError):
                InspectRegionArgs(view_id="full", bbox=bbox)
        self.assertEqual(InspectRegionArgs(view_id="full", bbox=(0, 0, 1, 1)).coordinate_space, "view")


if __name__ == "__main__":
    unittest.main()

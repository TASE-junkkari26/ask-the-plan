"""Source preservation, coordinate and cache regressions for raster preparation.

Synthetic marks are deliberately not a floor-plan accuracy benchmark. These tests
check that derived crops remain traceable and that inexpensive previews do not
replace the source pixels used for evidence.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from pydantic import ValidationError

from drawing_preprocessor import inspect_region, prepare_drawing
from drawing_preprocessor.core import PreparationError, PreprocessConfig, load_manifest
from drawing_preprocessor.ocr import data_directory, find_tesseract, language_fingerprint
from drawing_preprocessor.tools import execute_inspection_tool, inspection_tool_spec


class DrawingPreprocessorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "drawing.png"
        self.output = self.root / "prepared"

    def image(self, size=(809, 613), background="white", draw=None):
        image = Image.new("RGB", size, background)
        if draw is not None:
            draw(ImageDraw.Draw(image))
        image.save(self.source)
        return image

    def prepare(self, **kwargs):
        return prepare_drawing(self.source, self.output, **kwargs)

    def manifest_path(self, prepared):
        return self.output / prepared.id / "manifest.json"

    def artifact(self, prepared, uri):
        path = self.manifest_path(prepared).parent / uri
        self.assertTrue(path.resolve().is_relative_to(self.manifest_path(prepared).parent.resolve()))
        return path

    def full_region(self, prepared):
        full = [region for region in prepared.regions if region.role == "full_source"]
        self.assertEqual(len(full), 1)
        return full[0]

    def test_preserves_original_bytes_and_source_pixels(self):
        source = self.image(draw=lambda d: d.rectangle((213, 149, 481, 378), fill=(4, 7, 11)))
        before = self.source.read_bytes()
        prepared = self.prepare(source_uri="asset:example-revision")
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.artifact(prepared, prepared.original_uri).read_bytes(), before)
        self.assertEqual(prepared.source_sha256, hashlib.sha256(before).hexdigest())
        self.assertEqual(prepared.source_uri, "asset:example-revision")
        with Image.open(self.artifact(prepared, prepared.source_image_uri)) as restored:
            self.assertEqual(restored.size, source.size)
            self.assertEqual(restored.convert("RGB").tobytes(), source.tobytes())

    def test_full_source_is_always_available_with_identity_mapping(self):
        self.image()
        prepared = self.prepare()
        full = self.full_region(prepared)
        self.assertEqual(tuple(full.source_bbox), (0, 0, 809, 613))
        self.assertEqual(full.width, 809)
        self.assertEqual(full.height, 613)
        self.assertEqual(full.to_source, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])

    def test_small_images_are_not_upscaled(self):
        self.image(size=(67, 43))
        prepared = self.prepare(config=PreprocessConfig(overview_long_edge=1600))
        for region in prepared.regions:
            self.assertLessEqual(region.overview_width, region.width)
            self.assertLessEqual(region.overview_height, region.height)
            with Image.open(self.artifact(prepared, region.overview_uri)) as overview:
                self.assertEqual(overview.size, (region.overview_width, region.overview_height))

    def test_overview_mapping_uses_actual_rounded_dimensions(self):
        self.image()
        prepared = self.prepare(config=PreprocessConfig(overview_long_edge=257))
        for region in prepared.regions:
            x0, y0, x1, y1 = region.source_bbox
            transform = region.overview_to_source
            self.assertAlmostEqual(transform[0][0] * region.overview_width + transform[0][2], x1)
            self.assertAlmostEqual(transform[1][1] * region.overview_height + transform[1][2], y1)
            self.assertEqual((transform[0][2], transform[1][2]), (x0, y0))
            self.assertLessEqual(max(region.overview_width, region.overview_height), 257)

    def test_clean_margin_crop_preserves_detached_footer_and_note(self):
        def draw(canvas):
            canvas.rectangle((180, 120, 600, 420), outline="black", width=5)
            canvas.line((350, 120, 350, 420), fill="black", width=4)
            canvas.rectangle((90, 560, 650, 590), fill="black")
            canvas.rectangle((710, 260, 730, 280), fill="black")
        self.image(size=(900, 700), draw=draw)
        prepared = self.prepare()
        candidates = [r for r in prepared.regions if r.role != "full_source"]
        self.assertTrue(candidates)
        self.assertTrue(any(r.width * r.height < 900 * 700 * 0.8 for r in candidates))
        for point in ((180, 120), (600, 420), (90, 560), (650, 590), (710, 260), (730, 280)):
            with self.subTest(point=point):
                self.assertTrue(any(r.source_bbox[0] <= point[0] < r.source_bbox[2]
                                    and r.source_bbox[1] <= point[1] < r.source_bbox[3]
                                    for r in candidates))

    def test_page_border_can_be_ignored_for_layout_but_is_preserved(self):
        def draw(canvas):
            canvas.rectangle((2, 2, 897, 697), outline="black", width=1)
            canvas.rectangle((250, 190, 580, 490), outline="black", width=6)
        self.image(size=(900, 700), draw=draw)
        prepared = self.prepare()
        candidates = [r for r in prepared.regions if r.role != "full_source"]
        self.assertTrue(any(r.width * r.height < 900 * 700 * 0.8 for r in candidates))
        with Image.open(self.artifact(prepared, prepared.source_image_uri)) as source:
            self.assertEqual(source.convert("RGB").getpixel((2, 2)), (0, 0, 0))

    def test_near_white_background_is_not_rewritten(self):
        background = (247, 246, 242)
        self.image(background=background, draw=lambda d: d.rectangle((250, 150, 550, 450), fill="black"))
        prepared = self.prepare()
        with Image.open(self.artifact(prepared, prepared.source_image_uri)) as source:
            self.assertEqual(source.convert("RGB").getpixel((0, 0)), background)
        self.assertTrue(any(r.role != "full_source" and r.width < 809 for r in prepared.regions))

    def test_blank_page_is_a_valid_source_without_fake_text(self):
        self.image()
        prepared = self.prepare()
        self.full_region(prepared)
        self.assertEqual(prepared.ocr.status, "not_requested")
        self.assertEqual(prepared.ocr.spans, [])

    def test_identical_inputs_reuse_manifest_and_artifacts(self):
        self.image(draw=lambda d: d.rectangle((250, 150, 550, 450), fill="black"))
        first = self.prepare()
        path = self.manifest_path(first)
        first_bytes = path.read_bytes()
        first_mtime = path.stat().st_mtime_ns
        second = self.prepare()
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertEqual(path.read_bytes(), first_bytes)
        self.assertEqual(path.stat().st_mtime_ns, first_mtime)

    def test_changed_source_and_overview_setting_invalidate_cache(self):
        self.image()
        original = self.prepare()
        different_config = self.prepare(config=PreprocessConfig(overview_long_edge=257))
        self.assertNotEqual(original.id, different_config.id)
        self.assertNotEqual(original.config_sha256, different_config.config_sha256)
        self.image(background="ivory")
        different_source = self.prepare()
        self.assertNotEqual(original.id, different_source.id)
        self.assertNotEqual(original.source_sha256, different_source.source_sha256)
        self.assertTrue(self.manifest_path(original).exists())

    def test_missing_cached_artifact_is_regenerated(self):
        self.image()
        first = self.prepare()
        artifact = self.artifact(first, self.full_region(first).overview_uri)
        artifact.unlink()
        second = self.prepare()
        self.assertEqual(first.id, second.id)
        with Image.open(artifact) as restored:
            restored.verify()

    def test_corrupt_manifest_is_regenerated(self):
        self.image()
        first = self.prepare()
        path = self.manifest_path(first)
        path.write_text("not JSON", encoding="utf-8")
        second = self.prepare()
        self.assertEqual(first.id, second.id)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["id"], first.id)

    def test_modified_valid_png_artifact_is_regenerated(self):
        self.image(draw=lambda d: d.rectangle((123, 77, 245, 177), fill="black"))
        first = self.prepare()
        artifact = self.artifact(first, first.source_image_uri)
        before = artifact.read_bytes()
        Image.new("RGB", (first.source_width, first.source_height), "red").save(artifact)
        second = self.prepare()
        self.assertEqual(first.id, second.id)
        self.assertEqual(artifact.read_bytes(), before)

    def test_file_replaced_during_decode_does_not_mix_source_revision(self):
        source_image = self.image(draw=lambda d: d.rectangle((123, 77, 245, 177), fill="black"))
        original_bytes = self.source.read_bytes()
        replacement = io.BytesIO()
        Image.new("RGB", source_image.size, "red").save(replacement, format="PNG")
        original_open = Image.open
        replaced = False

        def replacing_open(file, *args, **kwargs):
            nonlocal replaced
            if not replaced:
                self.source.write_bytes(replacement.getvalue())
                replaced = True
            return original_open(file, *args, **kwargs)

        with patch("drawing_preprocessor.core.Image.open", side_effect=replacing_open):
            prepared = self.prepare()
        self.assertTrue(replaced)
        self.assertEqual(prepared.source_sha256, hashlib.sha256(original_bytes).hexdigest())
        self.assertEqual(self.artifact(prepared, prepared.original_uri).read_bytes(), original_bytes)
        with original_open(self.artifact(prepared, prepared.source_image_uri)) as canonical:
            self.assertEqual(canonical.tobytes(), source_image.tobytes())
        self.assertNotEqual(self.source.read_bytes(), original_bytes)

    def test_artifact_symlink_cannot_escape_prepared_directory(self):
        self.image()
        prepared = self.prepare()
        artifact = self.artifact(prepared, self.full_region(prepared).overview_uri)
        outside = self.root / "outside.png"
        outside.write_bytes(artifact.read_bytes())
        probe = self.root / "symlink-probe"
        try:
            probe.symlink_to(outside)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symlink creation unavailable on this platform: {error}")
        probe.unlink()
        artifact.unlink()
        artifact.symlink_to(outside)
        with self.assertRaisesRegex(PreparationError, "escapes"):
            load_manifest(self.manifest_path(prepared))

    def test_exif_orientation_keeps_explicit_stored_pixel_coordinates(self):
        self.source = self.root / "oriented.jpg"
        image = Image.new("RGB", (80, 40), "white")
        ImageDraw.Draw(image).rectangle((0, 0, 20, 39), fill="red")
        exif = Image.Exif()
        exif[274] = 6
        image.save(self.source, exif=exif)
        with Image.open(self.source) as raw:
            expected = raw.convert("RGB").tobytes()
        prepared = self.prepare()
        self.assertEqual((prepared.source_width, prepared.source_height), (80, 40))
        self.assertTrue(any("EXIF" in message for message in prepared.warnings))
        with Image.open(self.artifact(prepared, prepared.source_image_uri)) as canonical:
            self.assertEqual(canonical.size, (80, 40))
            self.assertEqual(canonical.tobytes(), expected)

    def test_manifest_and_artifacts_are_portable_within_output_directory(self):
        self.image()
        prepared = self.prepare(source_uri="asset:test")
        self.assertNotIn(str(self.root), self.manifest_path(prepared).read_text(encoding="utf-8"))
        for region in prepared.regions:
            for uri in (region.image_uri, region.overview_uri):
                self.assertFalse(Path(uri).is_absolute())
                self.assertTrue(self.artifact(prepared, uri).is_file())

    def test_inspect_native_crop_matches_source_pixels(self):
        self.image(draw=lambda d: d.rectangle((123, 77, 245, 177), fill=(8, 31, 119)))
        prepared = self.prepare()
        full = self.full_region(prepared)
        crop = inspect_region(self.manifest_path(prepared), full.id, [123, 77, 246, 178])
        self.assertEqual(tuple(crop["source_bbox"]), (123, 77, 246, 178))
        self.assertEqual((crop["width"], crop["height"]), (123, 101))
        self.assertEqual(crop["to_source"], [[1, 0, 123], [0, 1, 77], [0, 0, 1]])
        with Image.open(self.artifact(prepared, crop["image_uri"])) as image:
            self.assertEqual(image.convert("RGB").getpixel((0, 0)), (8, 31, 119))

    def test_inspect_overview_edges_map_back_to_whole_source(self):
        self.image()
        prepared = self.prepare(config=PreprocessConfig(overview_long_edge=257))
        full = self.full_region(prepared)
        crop = inspect_region(self.manifest_path(prepared), full.id,
                              [0, 0, full.overview_width, full.overview_height],
                              coordinate_space="overview", output_long_edge=111)
        self.assertEqual(tuple(crop["source_bbox"]), (0, 0, 809, 613))
        self.assertEqual(max(crop["width"], crop["height"]), 111)
        self.assertAlmostEqual(crop["to_source"][0][0] * crop["width"], 809)
        self.assertAlmostEqual(crop["to_source"][1][1] * crop["height"], 613)

    def test_inspect_rejects_unknown_view_and_coordinate_space(self):
        self.image()
        prepared = self.prepare()
        for view, space in (("view:does-not-exist", "view"), (self.full_region(prepared).id, "world")):
            with self.subTest(view=view, space=space), self.assertRaises(PreparationError):
                inspect_region(self.manifest_path(prepared), view, [0, 0, 10, 10], coordinate_space=space)

    def test_inspect_rejects_empty_outside_and_nonfinite_bounds(self):
        self.image()
        prepared = self.prepare()
        view = self.full_region(prepared).id
        invalid = ([0, 0, 0, 10], [20, 0, 10, 10], [-1, 0, 10, 10],
                   [0, 0, 810, 10], [0, 0, math.nan, 10], [0, 0, math.inf, 10])
        for bounds in invalid:
            with self.subTest(bounds=bounds), self.assertRaises(PreparationError):
                inspect_region(self.manifest_path(prepared), view, bounds)

    def test_invalid_image_and_missing_file_have_actionable_error(self):
        self.source.write_text("this is not an image", encoding="utf-8")
        with self.assertRaises(PreparationError):
            self.prepare()
        self.source.unlink()
        with self.assertRaises(PreparationError):
            self.prepare()

    def test_unavailable_requested_ocr_does_not_claim_empty_complete_text(self):
        self.image(draw=lambda d: d.text((250, 200), "Room 5.10", fill="black"))
        with patch("drawing_preprocessor.ocr.find_tesseract", return_value=None):
            prepared = self.prepare(config=PreprocessConfig(ocr="tesseract"))
        self.assertEqual(prepared.ocr.status, "unavailable")
        self.assertEqual(prepared.ocr.spans, [])
        self.assertTrue(prepared.ocr.warnings or prepared.warnings)

    def prepare_ocr(self, rows, *, error=None):
        self.image()
        header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"

        def run(arguments, **options):
            if "--version" in arguments:
                return subprocess.CompletedProcess(arguments, 0, "tesseract 5.5.1\n", "")
            if error is not None:
                raise error
            return subprocess.CompletedProcess(arguments, 0, header + rows, "")

        with patch("drawing_preprocessor.ocr.find_tesseract", return_value="fake-tesseract"), \
                patch("drawing_preprocessor.ocr.subprocess.run", side_effect=run):
            return self.prepare(config=PreprocessConfig(ocr="tesseract", ocr_languages="eng+fin"))

    def test_ocr_preserves_literal_identifiers_nonascii_and_source_boxes(self):
        prepared = self.prepare_ocr(
            "5\t1\t1\t1\t1\t1\t125\t85\t31\t12\t93.0\t5.10\n"
            "5\t1\t1\t1\t1\t2\t180\t85\t50\t12\t81.5\tSéjour\n"
        )
        self.assertEqual(prepared.ocr.status, "complete")
        self.assertEqual(prepared.ocr.version, "tesseract 5.5.1")
        self.assertEqual(prepared.ocr.languages, ["eng", "fin"])
        self.assertEqual([span.text for span in prepared.ocr.spans], ["5.10", "Séjour"])
        first = prepared.ocr.spans[0]
        self.assertEqual(first.frame_id, prepared.source_frame_id)
        self.assertEqual(first.bbox, (125, 85, 156, 97))
        self.assertAlmostEqual(first.confidence, 0.93)

    def test_ocr_omits_invalid_records_and_marks_partial(self):
        prepared = self.prepare_ocr(
            "5\t1\t1\t1\t1\t1\t125\t85\t31\t12\t93\t5.10\n"
            "5\t1\t1\t1\t1\t2\t800\t600\t80\t40\t90\toutside\n"
            "5\t1\t1\t1\t1\t3\t200\t100\t80\t40\tnan\tbad confidence\n"
        )
        self.assertEqual(prepared.ocr.status, "partial")
        self.assertEqual([span.text for span in prepared.ocr.spans], ["5.10"])
        self.assertTrue(prepared.ocr.warnings)

    def test_ocr_timeout_and_process_error_are_failed_with_artifacts_retained(self):
        failures = (subprocess.TimeoutExpired("tesseract", 30),
                    subprocess.CalledProcessError(1, "tesseract"))
        for error in failures:
            with self.subTest(error=type(error).__name__):
                # A fresh output root prevents a cached failure hiding this run.
                self.output = self.root / type(error).__name__
                prepared = self.prepare_ocr("", error=error)
                self.assertEqual(prepared.ocr.status, "failed")
                self.assertEqual(prepared.ocr.spans, [])
                self.assertTrue(prepared.ocr.warnings)
                self.assertTrue(self.artifact(prepared, prepared.source_image_uri).is_file())

    def test_transient_failed_ocr_is_retried_on_next_prepare(self):
        self.image()
        calls = 0
        tsv = ("level\tleft\ttop\twidth\theight\tconf\ttext\n"
               "5\t20\t20\t20\t10\t93\t5.10\n")

        def run(arguments, **options):
            nonlocal calls
            if "--version" in arguments:
                return subprocess.CompletedProcess(arguments, 0, "tesseract 5.5.1\n", "")
            calls += 1
            if calls == 1:
                raise subprocess.TimeoutExpired("tesseract", 30)
            return subprocess.CompletedProcess(arguments, 0, tsv, "")

        with patch("drawing_preprocessor.ocr.find_tesseract", return_value="fake-tesseract"), \
                patch("drawing_preprocessor.ocr.subprocess.run", side_effect=run):
            first = self.prepare(config=PreprocessConfig(ocr="tesseract"))
            self.assertEqual(first.ocr.status, "failed")
            second = self.prepare(config=PreprocessConfig(ocr="tesseract"))
        self.assertEqual(first.id, second.id)
        self.assertEqual(calls, 2)
        self.assertEqual(second.ocr.status, "complete")
        self.assertEqual([span.text for span in second.ocr.spans], ["5.10"])

    def test_malformed_tesseract_output_is_not_complete_ocr(self):
        self.image()

        def run(arguments, **options):
            text = "tesseract 5.5.1\n" if "--version" in arguments else "this is not TSV\n"
            return subprocess.CompletedProcess(arguments, 0, text, "")

        with patch("drawing_preprocessor.ocr.find_tesseract", return_value="fake-tesseract"), \
                patch("drawing_preprocessor.ocr.subprocess.run", side_effect=run):
            prepared = self.prepare(config=PreprocessConfig(ocr="tesseract"))
        self.assertIn(prepared.ocr.status, {"partial", "failed"})
        self.assertEqual(prepared.ocr.spans, [])
        self.assertTrue(prepared.ocr.warnings)

    def test_explicit_tesseract_command_takes_priority_over_path(self):
        with patch.dict("os.environ", {"TESSERACT_CMD": "team-tesseract"}, clear=True), \
                patch("drawing_preprocessor.ocr.shutil.which", return_value="selected-executable") as which:
            self.assertEqual(find_tesseract(), "selected-executable")
        which.assert_called_once_with("team-tesseract")

    def test_invalid_explicit_tesseract_command_does_not_silently_fall_back(self):
        with patch.dict("os.environ", {"TESSERACT_CMD": "missing-command"}, clear=True), \
                patch("drawing_preprocessor.ocr.shutil.which", return_value=None) as which:
            self.assertIsNone(find_tesseract())
        which.assert_called_once_with("missing-command")

    def test_configured_tessdata_directory_takes_priority(self):
        configured = self.root / "selected-models"
        configured.mkdir()
        with patch.dict("os.environ", {"TESSDATA_PREFIX": str(configured)}, clear=True):
            self.assertEqual(data_directory("other/tesseract"), configured)

    def test_language_fingerprint_tracks_selected_model_bytes_and_missing_data(self):
        models = self.root / "tessdata"
        models.mkdir()
        english = models / "eng.traineddata"
        english.write_bytes(b"first model revision")
        with patch("drawing_preprocessor.ocr.find_tesseract", return_value="fake-tesseract"), \
                patch("drawing_preprocessor.ocr.data_directory", return_value=models):
            first = language_fingerprint("eng+fin")
            self.assertEqual(first["eng"], hashlib.sha256(english.read_bytes()).hexdigest())
            self.assertEqual(first["fin"], "not_located")
            english.write_bytes(b"second model revision")
            second = language_fingerprint("eng+fin")
        self.assertNotEqual(first["eng"], second["eng"])
        self.assertEqual(first["fin"], second["fin"])

    def test_changed_traineddata_invalidates_preparation_cache(self):
        models = self.root / "tessdata"
        models.mkdir()
        english = models / "eng.traineddata"
        english.write_bytes(b"first model revision")
        tsv_rows = "5\t1\t1\t1\t1\t1\t20\t20\t20\t10\t93\t5.10\n"
        with patch("drawing_preprocessor.ocr.data_directory", return_value=models):
            first = self.prepare_ocr(tsv_rows)
            english.write_bytes(b"second model revision")
            second = self.prepare_ocr(tsv_rows)
        self.assertEqual(first.source_sha256, second.source_sha256)
        self.assertNotEqual(first.config_sha256, second.config_sha256)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.ocr.status, "complete")
        self.assertEqual(second.ocr.status, "complete")

    def test_inspection_returns_intersecting_ocr_in_source_coordinates(self):
        prepared = self.prepare_ocr(
            "5\t1\t1\t1\t1\t1\t20\t20\t20\t10\t93\t5.10\n"
            "5\t1\t1\t1\t1\t2\t500\t500\t30\t10\t90\tother\n"
        )
        crop = inspect_region(self.manifest_path(prepared), self.full_region(prepared).id,
                              [10, 10, 100, 100])
        self.assertEqual([span["text"] for span in crop["ocr_spans"]], ["5.10"])
        self.assertEqual(crop["ocr_spans"][0]["bbox"], [20, 20, 40, 30])
        self.assertEqual(crop["ocr_spans"][0]["frame_id"], prepared.source_frame_id)

    def test_tool_schema_and_dispatch_keep_paths_out_of_model_arguments(self):
        spec = inspection_tool_spec()
        self.assertEqual(spec["type"], "function")
        self.assertEqual(spec["function"]["name"], "inspect_region")
        arguments_schema = spec["function"]["parameters"]
        self.assertFalse(arguments_schema["additionalProperties"])
        self.assertNotIn("manifest_path", arguments_schema["properties"])
        self.image()
        prepared = self.prepare()
        arguments = {"view_id": self.full_region(prepared).id, "bbox": [0, 0, 30, 40]}
        result = execute_inspection_tool(self.manifest_path(prepared), arguments)
        self.assertEqual(tuple(result["source_bbox"]), (0, 0, 30, 40))
        with self.assertRaises(ValidationError):
            execute_inspection_tool(self.manifest_path(prepared),
                                    {**arguments, "manifest_path": "untrusted-path"})


if __name__ == "__main__":
    unittest.main()

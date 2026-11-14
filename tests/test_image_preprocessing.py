"""Credential-free preprocessing integration and original display-frame checks."""
from __future__ import annotations

from contextlib import asynccontextmanager
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from PIL import Image, ImageDraw, PngImagePlugin

from drawing_preprocessor.core import PreparationError
from image_api.app import create_app
from image_api.config import ApiSettings
from image_api.errors import ApiError
from image_api.images import prepare_image
from image_api.preprocessing import ImagePreprocessor
from nemotron import AsyncNemotronClient, NemotronSettings
from tests.test_image_api import TEST_KEY, TEST_MODEL, completion, image_bytes


def content_image(size=(809, 613), *, color="black", png_note=None):
    image = Image.new("RGB", size, "white")
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((120, 90, 600, 390), outline=color, width=5)
    drawing.rectangle((30, size[1] - 50, size[0] - 30, size[1] - 20), fill=color)
    output = io.BytesIO()
    info = None
    if png_note is not None:
        info = PngImagePlugin.PngInfo()
        info.add_text("note", png_note)
    image.save(output, format="PNG", pnginfo=info)
    return output.getvalue()


class ImagePreprocessorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def directory(self, name):
        directory = self.root / name
        directory.mkdir()
        return directory

    def processor(self, **options):
        processor = ImagePreprocessor(ApiSettings(**options))
        self.addCleanup(processor.close)
        return processor

    def test_original_mode_preserves_canonical_bytes_and_display_identity(self):
        content = content_image()
        settings = ApiSettings()
        reference = prepare_image(content, settings, self.directory("reference"))
        processor = self.processor()
        actual = processor.prepare(content, self.directory("request"))
        self.assertEqual(actual.preprocessing_mode, "original")
        self.assertEqual(actual.path.read_bytes(), reference.path.read_bytes())
        self.assertEqual(actual.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(actual.inference_sha256, reference.inference_sha256)
        self.assertEqual((actual.width, actual.height), (809, 613))
        self.assertEqual((actual.model_width, actual.model_height), (809, 613))
        self.assertFalse(actual.preparation_cache_hit)
        self.assertTrue(actual.prepared_id)

    def test_exif_and_transparency_are_canonicalized_before_preprocessing(self):
        processor = self.processor()
        exif = Image.Exif()
        exif[274] = 6
        jpeg = image_bytes(size=(80, 40), format="JPEG", exif=exif)
        upright = processor.prepare(jpeg, self.directory("exif"))
        self.assertEqual((upright.width, upright.height), (40, 80))
        self.assertEqual((upright.model_width, upright.model_height), (40, 80))
        transparent = io.BytesIO()
        Image.new("RGBA", (31, 17), (255, 0, 0, 0)).save(transparent, format="PNG")
        prepared = processor.prepare(transparent.getvalue(), self.directory("alpha"))
        with Image.open(prepared.path) as image:
            self.assertEqual(image.convert("RGB").getpixel((10, 10)), (255, 255, 255))

    def test_overview_is_of_entire_source_and_keeps_separate_footer(self):
        content = content_image()
        processor = self.processor(preprocess_mode="overview", preprocess_overview_long_edge=257)
        actual = processor.prepare(content, self.directory("request"))
        with Image.open(io.BytesIO(content)) as original:
            expected = original.resize((257, round(613 * 257 / 809)), Image.Resampling.LANCZOS)
        with Image.open(actual.path) as actual_image:
            self.assertEqual(actual_image.size, expected.size)
            self.assertEqual(actual_image.tobytes(), expected.tobytes())
        self.assertEqual((actual.width, actual.height), (809, 613))
        self.assertEqual((actual.model_width, actual.model_height), expected.size)
        self.assertEqual(actual.preprocessing_mode, "overview")

    def test_same_canonical_pixels_reuse_preparation_despite_upload_metadata(self):
        first_content = content_image(png_note="upload one")
        second_content = content_image(png_note="upload two")
        self.assertNotEqual(first_content, second_content)
        processor = self.processor()
        first = processor.prepare(first_content, self.directory("one"))
        second = processor.prepare(second_content, self.directory("two"))
        self.assertFalse(first.preparation_cache_hit)
        self.assertTrue(second.preparation_cache_hit)
        self.assertEqual(first.prepared_id, second.prepared_id)
        self.assertNotEqual(first.sha256, second.sha256)
        self.assertEqual(first.inference_sha256, second.inference_sha256)

    def test_off_mode_skips_drawing_preparation(self):
        processor = self.processor(preprocess_mode="off")
        with patch("image_api.preprocessing.prepare_drawing", side_effect=AssertionError("must not prepare")):
            result = processor.prepare(content_image(), self.directory("request"))
        self.assertEqual(result.preprocessing_mode, "off")
        self.assertIsNone(result.prepared_id)
        self.assertEqual((result.model_width, result.model_height), (809, 613))

    def test_preparation_does_not_run_ocr(self):
        processor = self.processor()
        with patch("drawing_preprocessor.core.recognize", side_effect=AssertionError("must not OCR")), \
                patch("drawing_preprocessor.core.tesseract_version", side_effect=AssertionError("must not probe OCR")):
            result = processor.prepare(content_image(), self.directory("request"))
        self.assertTrue(result.prepared_id)

    def test_bounded_cache_evicts_without_deleting_inflight_request_image(self):
        processor = self.processor(preprocess_mode="overview", preprocess_cache_entries=1)
        first = processor.prepare(content_image(color="black"), self.directory("one"))
        second = processor.prepare(content_image(color="blue"), self.directory("two"))
        self.assertNotEqual(first.prepared_id, second.prepared_id)
        self.assertTrue(first.path.is_file())
        with Image.open(first.path) as retained:
            retained.verify()
        repeated = processor.prepare(content_image(color="black"), self.directory("three"))
        self.assertFalse(repeated.preparation_cache_hit)
        self.assertEqual(first.prepared_id, repeated.prepared_id)

    def test_corrupt_cached_overview_is_regenerated_before_reuse(self):
        content = content_image()
        processor = self.processor(preprocess_mode="overview", preprocess_overview_long_edge=257)
        first = processor.prepare(content, self.directory("one"))
        artifact_root = processor.cache_root / first.prepared_id
        manifest = json.loads((artifact_root / "manifest.json").read_text(encoding="utf-8"))
        full = next(region for region in manifest["regions"] if region["role"] == "full_source")
        overview = artifact_root / full["overview_uri"]
        overview.write_bytes(b"corrupted cached overview")
        second = processor.prepare(content, self.directory("two"))
        self.assertFalse(second.preparation_cache_hit)
        self.assertEqual(second.prepared_id, first.prepared_id)
        self.assertEqual(second.sha256, first.sha256)
        self.assertEqual((second.width, second.height), (first.width, first.height))
        self.assertEqual((second.model_width, second.model_height), (first.model_width, first.model_height))
        with Image.open(overview) as regenerated:
            self.assertEqual(regenerated.size, (second.model_width, second.model_height))
            regenerated.verify()
        with Image.open(second.path) as submitted:
            submitted.verify()
        self.assertEqual(second.inference_sha256, hashlib.sha256(second.path.read_bytes()).hexdigest())

    def test_close_removes_owned_cache_but_keeps_caller_owned_image(self):
        processor = self.processor(preprocess_mode="overview")
        image = processor.prepare(content_image(), self.directory("request"))
        cache_root = processor.cache_root
        self.assertTrue(cache_root.is_dir())
        processor.close()
        self.assertFalse(cache_root.exists())
        self.assertTrue(image.path.is_file())

    def test_preparation_failure_is_explicit_and_does_not_leak_internal_detail(self):
        processor = self.processor()
        with patch("image_api.preprocessing.prepare_drawing", side_effect=PreparationError("private/source/path")):
            with self.assertRaises(ApiError) as caught:
                processor.prepare(content_image(), self.directory("request"))
        self.assertEqual(caught.exception.status_code, 500)
        self.assertNotIn("private/source/path", caught.exception.message)


class ImagePreprocessingApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.requests = []
        self.inference_paths = []

    @asynccontextmanager
    async def api(self, **settings):
        async def transport(request):
            self.requests.append(json.loads(request.content))
            return completion()
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        sdk = AsyncNemotronClient(NemotronSettings(api_key=TEST_KEY, model=TEST_MODEL, max_retries=0),
                                  http_client=http_client)
        original_ask = sdk.ask

        async def tracked_ask(*args, **kwargs):
            self.inference_paths.extend(Path(path) for path in kwargs.get("images", []))
            return await original_ask(*args, **kwargs)
        sdk.ask = tracked_ask
        app = create_app(settings=ApiSettings(**settings), client_factory=lambda: sdk)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
                yield client
        self.assertTrue(http_client.is_closed)
        self.assertTrue(all(not path.exists() for path in self.inference_paths))

    async def post(self, client, content, question="Where are the windows?"):
        return await client.post("/api/v1/candidates", data={"question": question}, files={
            "image": ("drawing.png", content, "image/png"),
        })

    def model_image(self, index=0):
        image_parts = [part for message in self.requests[index]["messages"]
                       if isinstance(message["content"], list) for part in message["content"]
                       if part["type"] == "image_url"]
        self.assertEqual(len(image_parts), 1)
        return base64.b64decode(image_parts[0]["image_url"]["url"].split(",", 1)[1])

    async def test_default_mode_single_provider_call_and_preparation_metadata(self):
        content = content_image()
        async with self.api() as client:
            response = await self.post(client, content)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["image"]["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual((result["image"]["width"], result["image"]["height"]), (809, 613))
        prep = result["provenance"]["preprocessing"]
        self.assertEqual(prep["mode"], "original")
        self.assertEqual((prep["input_width"], prep["input_height"]), (809, 613))
        self.assertTrue(prep["prepared_id"])
        self.assertTrue(prep["pipeline_version"])
        self.assertGreaterEqual(result["metrics"]["preparation_ms"], 0)
        self.assertFalse(result["metrics"]["preparation_cache_hit"])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(hashlib.sha256(self.model_image()).hexdigest(), result["image"]["inference_sha256"])

    async def test_overview_boxes_still_use_original_odd_sized_display_frame(self):
        content = content_image()
        async with self.api(preprocess_mode="overview", preprocess_overview_long_edge=257) as client:
            response = await self.post(client, content)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        prep = result["provenance"]["preprocessing"]
        self.assertEqual(prep["mode"], "overview")
        self.assertEqual((prep["input_width"], prep["input_height"]), (257, round(613 * 257 / 809)))
        self.assertEqual((result["image"]["width"], result["image"]["height"]), (809, 613))
        geometry = result["candidates"][0]["geometry"]
        for actual, expected in zip(geometry["minimum"], (80.9, 122.6)):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(geometry["maximum"], (728.1, 490.4)):
            self.assertAlmostEqual(actual, expected)
        with Image.open(io.BytesIO(self.model_image())) as submitted:
            self.assertEqual(submitted.size, (prep["input_width"], prep["input_height"]))
        system = next(message["content"] for message in self.requests[0]["messages"]
                      if message["role"] == "system")
        self.assertIn(str(prep["input_width"]), system)
        self.assertIn(str(prep["input_height"]), system)
        self.assertEqual(len(self.requests), 1)

    async def test_questions_reuse_preparation_without_caching_provider_answers(self):
        content = content_image()
        async with self.api() as client:
            first = await self.post(client, content, "Where are the windows?")
            second = await self.post(client, content, "Where are the doors?")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["provenance"]["preprocessing"]["prepared_id"],
                         second.json()["provenance"]["preprocessing"]["prepared_id"])
        self.assertFalse(first.json()["metrics"]["preparation_cache_hit"])
        self.assertTrue(second.json()["metrics"]["preparation_cache_hit"])
        self.assertEqual(len(self.requests), 2)

    async def test_off_mode_is_reported_and_still_keeps_original_source_coordinates(self):
        async with self.api(preprocess_mode="off") as client:
            with patch("image_api.preprocessing.prepare_drawing", side_effect=AssertionError("must not prepare")):
                response = await self.post(client, content_image())
        self.assertEqual(response.status_code, 200, response.text)
        prep = response.json()["provenance"]["preprocessing"]
        self.assertEqual(prep["mode"], "off")
        self.assertIsNone(prep["prepared_id"])
        self.assertEqual((prep["input_width"], prep["input_height"]), (809, 613))
        self.assertEqual(len(self.requests), 1)

    async def test_preprocessing_failure_returns_error_before_provider_call(self):
        async with self.api() as client:
            with patch("image_api.preprocessing.prepare_drawing", side_effect=PreparationError("private/source/path")):
                response = await self.post(client, content_image())
        self.assertEqual(response.status_code, 500, response.text)
        self.assertNotIn("private/source/path", response.text)
        self.assertEqual(len(self.requests), 0)


if __name__ == "__main__":
    unittest.main()

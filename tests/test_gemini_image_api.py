"""Synthetic Gemini image API/IFC isolation checks; no live provider requests.

These tests verify request routing, contract adaptation, and lifecycle behavior.
They do not measure drawing recognition or candidate localization accuracy.
"""
from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import ifcopenshell.guid
from PIL import Image

from gemini import AsyncGeminiClient, GeminiSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from nemotron import AsyncNemotronClient, ConfigurationError, NemotronSettings
from tests.test_ifc_api import completion as ifc_completion, proposal as ifc_proposal
from tests.test_ifc_engine import sample_model
from tests.test_image_api import completion as nemotron_completion, image_bytes


KEY = "synthetic-gemini-integration-credential"
VERDA_KEY = "synthetic-independent-ifc-credential"
MODEL = "gemini-4-hydrogen"


def proposals():
    return {
        "status": "ok",
        "candidates": [{
            "category": "window",
            "source_label": "121.A",
            "box_2d": [100, 200, 400, 500],
            "uncertain": False,
            "uncertainty_reason": None,
            "visual_cue": "Parallel lines in the exterior wall.",
        }],
        "limitations": [],
    }


def interaction(payload=None, *, text=None, status="completed", usage=True):
    value = {
        "id": "synthetic-interaction",
        "object": "interaction",
        "model": MODEL,
        "status": status,
        "steps": [{"type": "model_output", "content": [{
            "type": "text",
            "text": text if text is not None else json.dumps(payload if payload is not None else proposals()),
        }]}],
    }
    if usage:
        value["usage"] = {
            "total_input_tokens": 101,
            "total_output_tokens": 41,
            "total_thought_tokens": 13,
            "total_tokens": 155,
        }
    return httpx.Response(200, json=value)


class GeminiImageApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        path = Path(cls.directory.name) / "synthetic.ifc"
        source, _, _, _, ground, _ = sample_model(path)
        window = source.create_entity(
            "IfcWindow", GlobalId=ifcopenshell.guid.new(), Name="121.A",
            OverallWidth=900., OverallHeight=1500.,
        )
        source.create_entity(
            "IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(),
            RelatingStructure=ground, RelatedElements=[window],
        )
        source.write(str(path))
        cls.ifc_bytes = path.read_bytes()
        cls.ifc_sha = hashlib.sha256(cls.ifc_bytes).hexdigest()
        cls.window_step = window.id()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.gemini_requests = []
        self.nemotron_requests = []
        self.paths = []
        self.clients = []

    @asynccontextmanager
    async def api(self, handler=None, *, settings=None, gemini_configured=True,
                  nemotron_configured=True, nemotron_handler=None):
        async def gemini_transport(request):
            self.gemini_requests.append(request)
            value = handler(request) if handler else interaction()
            return await value if hasattr(value, "__await__") else value

        async def nemotron_transport(request):
            self.nemotron_requests.append(request)
            value = nemotron_handler(request) if nemotron_handler else ifc_completion(ifc_proposal())
            return await value if hasattr(value, "__await__") else value

        def gemini_factory():
            if not gemini_configured:
                raise ConfigurationError("synthetic missing Gemini configuration")
            sdk = AsyncGeminiClient(
                GeminiSettings(api_key=KEY), transport=httpx.MockTransport(gemini_transport),
            )
            generate = sdk.generate_candidates

            async def track_image(*args, **kwargs):
                self.paths.append(Path(kwargs["image"]))
                return await generate(*args, **kwargs)

            sdk.generate_candidates = track_image
            sdk.close = AsyncMock(wraps=sdk.close)
            self.clients.append(sdk)
            return sdk

        def nemotron_factory():
            if not nemotron_configured:
                raise ConfigurationError("synthetic missing Verda configuration")
            http_client = httpx.AsyncClient(transport=httpx.MockTransport(nemotron_transport))
            sdk = AsyncNemotronClient(
                NemotronSettings(api_key=VERDA_KEY, model="synthetic-ifc-planner", max_retries=0),
                http_client=http_client,
            )
            sdk.close = AsyncMock(wraps=sdk.close)
            self.clients.append(sdk)
            return sdk

        app = create_app(
            settings or ApiSettings(provider="gemini", preprocess_mode="off"),
            client_factory=nemotron_factory,
            gemini_client_factory=gemini_factory,
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
                yield client, app
        for sdk in self.clients:
            self.assertEqual(sdk.close.await_count, 1, "Each owned provider client must close once")

    async def post(self, client, *, content=None, question="Where are the windows?"):
        return await client.post(
            "/api/v1/candidates", data={"question": question},
            files={"image": ("drawing.png", content if content is not None else image_bytes((1200, 800)), "image/png")},
        )

    async def ifc_question(self, client):
        uploaded = await client.post(
            "/api/ifc/models", data={"source_sha256": self.ifc_sha},
            files={"file": ("synthetic.ifc", self.ifc_bytes, "application/x-step")},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        model = uploaded.json()
        return await client.post("/api/ifc/questions", json={
            "model_id": model["model_id"], "source_sha256": self.ifc_sha,
            "question": "How many windows?", "scope": "view",
            "visible_step_ids": [self.window_step], "view_label": "Ground",
        })

    def assert_safe_error(self, response, status, code=None):
        self.assertEqual(response.status_code, status, response.text)
        body = response.json()
        if code is not None:
            self.assertEqual(body["code"], code)
        self.assertTrue(body["request_id"])
        self.assertIsInstance(body["retryable"], bool)
        for private in (KEY, VERDA_KEY, "private detail", "/tmp/"):
            self.assertNotIn(private, response.text)
        self.assertNotIn("candidates", body)
        return body

    async def test_one_low_thinking_request_maps_y_first_boxes_to_display_pixels(self):
        content = image_bytes((1200, 800))
        question = "Missä ikkunat 121.A sijaitsevat?"
        async with self.api() as (client, _):
            response = await self.post(client, content=content, question=question)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        candidate = body["candidates"][0]
        self.assertEqual(candidate["geometry"], {
            "kind": "box", "minimum": [240, 80], "maximum": [600, 320],
        })
        self.assertEqual(candidate["source_label"], "121.A")
        self.assertEqual(body["image"]["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual((body["image"]["width"], body["image"]["height"]), (1200, 800))
        self.assertEqual(body["scope"], "submitted_image")
        self.assertEqual(body["inventory_completeness"], "unverified")
        self.assertEqual(body["provenance"]["requested_model"], MODEL)
        self.assertEqual(body["provenance"]["returned_model"], MODEL)
        self.assertEqual(body["provenance"]["prompt_version"], "gemini-candidate-v1")
        self.assertEqual(body["metrics"]["prompt_tokens"], 101)
        self.assertEqual(body["metrics"]["completion_tokens"], 54)
        self.assertEqual(len(self.gemini_requests), 1)
        self.assertEqual(self.nemotron_requests, [])
        request = self.gemini_requests[0]
        payload = json.loads(request.content)
        self.assertEqual(payload["model"], MODEL)
        self.assertEqual(payload["generation_config"]["thinking_level"], "low")
        self.assertEqual(payload["generation_config"]["thinking_summaries"], "none")
        self.assertFalse(payload["store"])
        self.assertEqual(payload["response_format"]["mime_type"], "application/json")
        self.assertIn("schema", payload["response_format"])
        native_schema = payload["response_format"]["schema"]
        self.assertNotIn("maxItems", native_schema["properties"]["candidates"])
        self.assertNotIn("maxItems", native_schema["properties"]["limitations"])
        native_candidate = native_schema["$defs"]["_GeminiProposal"]
        self.assertEqual(native_candidate["properties"]["box_2d"]["items"], {"type": "number"})
        self.assertEqual(native_candidate["properties"]["box_2d"]["maxItems"], 4)
        self.assertEqual([item["text"] for item in payload["input"] if item["type"] == "text"], [question])
        images = [item for item in payload["input"] if item["type"] == "image"]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["mime_type"], "image/png")
        pixels = base64.b64decode(images[0]["data"])
        self.assertEqual(body["image"]["inference_sha256"], hashlib.sha256(pixels).hexdigest())
        self.assertTrue(self.paths)
        self.assertTrue(all(not path.exists() for path in self.paths))

    async def test_exif_overview_keeps_original_display_frame_and_inference_hash(self):
        exif = Image.Exif()
        exif[274] = 6
        content = image_bytes((800, 1200), format="JPEG", exif=exif)
        settings = ApiSettings(provider="gemini", preprocess_mode="overview", preprocess_overview_long_edge=600)
        async with self.api(settings=settings) as (client, _):
            response = await self.post(client, content=content)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body["image"]["width"], body["image"]["height"]), (1200, 800))
        self.assertEqual(body["image"]["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(body["candidates"][0]["geometry"]["minimum"], [240, 80])
        self.assertEqual(body["candidates"][0]["geometry"]["maximum"], [600, 320])
        prepared = body["provenance"]["preprocessing"]
        self.assertEqual((prepared["input_width"], prepared["input_height"]), (600, 400))
        self.assertEqual(prepared["mode"], "overview")
        payload = json.loads(self.gemini_requests[0].content)
        pixels = base64.b64decode(next(item["data"] for item in payload["input"] if item["type"] == "image"))
        with Image.open(io.BytesIO(pixels)) as image:
            self.assertEqual(image.size, (600, 400))
        self.assertEqual(body["image"]["inference_sha256"], hashlib.sha256(pixels).hexdigest())
        self.assertEqual(len(self.gemini_requests), 1)

    async def test_same_server_keeps_ifc_queries_on_nemotron(self):
        async with self.api() as (client, _):
            self.assertEqual((await self.post(client)).status_code, 200)
            response = await self.ifc_question(client)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["result"]["claims"][0]["value"]["value"], 1)
        self.assertEqual(body["included_elements"][0]["step_id"], self.window_step)
        self.assertEqual(len(self.gemini_requests), 1)
        self.assertEqual(len(self.nemotron_requests), 1)
        self.assertEqual(json.loads(self.nemotron_requests[0].content)["model"], "synthetic-ifc-planner")
        self.assertEqual(self.nemotron_requests[0].headers["authorization"], "Bearer " + VERDA_KEY)
        self.assertNotIn("image_url", self.nemotron_requests[0].content.decode())
        self.assertNotIn(KEY, response.text)

    async def test_missing_gemini_configuration_does_not_disable_ifc_or_fallback(self):
        async with self.api(gemini_configured=False) as (client, _):
            self.assertEqual((await client.get("/health")).status_code, 503)
            self.assert_safe_error(await self.post(client), 503, "not_configured")
            response = await self.ifc_question(client)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.gemini_requests, [])
        self.assertEqual(len(self.nemotron_requests), 1)

    async def test_missing_verda_configuration_does_not_disable_gemini_images(self):
        async with self.api(nemotron_configured=False) as (client, _):
            self.assertEqual((await client.get("/health")).status_code, 200)
            self.assertEqual((await self.post(client)).status_code, 200)
            ifc_response = await self.ifc_question(client)
        self.assertEqual(ifc_response.status_code, 503, ifc_response.text)
        self.assertEqual(len(self.gemini_requests), 1)
        self.assertEqual(self.nemotron_requests, [])

    async def test_explicit_nemotron_image_mode_does_not_construct_gemini(self):
        settings = ApiSettings(provider="nemotron", preprocess_mode="off")
        async with self.api(settings=settings, nemotron_handler=lambda _: nemotron_completion()) as (client, _):
            response = await self.post(client)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.gemini_requests, [])
        self.assertEqual(len(self.nemotron_requests), 1)
        self.assertEqual(len(self.clients), 1)
        self.assertEqual(response.json()["provenance"]["prompt_version"], "candidate-v2")

    async def test_health_docs_and_cors_make_no_provider_requests(self):
        async with self.api() as (client, _):
            self.assertEqual((await client.get("/health")).json(), {"status": "ok", "configured": True})
            self.assertEqual((await client.get("/docs")).status_code, 200)
            self.assertEqual((await client.get("/openapi.json")).status_code, 200)
            response = await client.options("/api/v1/candidates", headers={
                "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
            })
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.gemini_requests, [])
        self.assertEqual(self.nemotron_requests, [])

    async def test_candidate_outcomes_and_uncertainty_keep_their_meanings(self):
        for status in ("ok", "partial", "unreadable", "unsupported"):
            with self.subTest(status=status):
                payload = {"status": status, "candidates": [], "limitations": [] if status == "ok" else ["Visible detail is limited."]}
                if status == "partial":
                    payload["candidates"] = proposals()["candidates"]
                    payload["candidates"][0].update(uncertain=True, uncertainty_reason="The wall symbol is faint.")
                async with self.api(lambda _, payload=payload: interaction(payload)) as (client, _):
                    response = await self.post(client)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["status"], status)
                self.assertEqual(response.json()["limitations"], payload["limitations"])
                if status == "partial":
                    self.assertTrue(response.json()["candidates"][0]["uncertain"])

    async def test_invalid_boxes_and_batches_fail_without_repair_or_fallback(self):
        invalid = []
        for box in ([400, 200, 100, 500], [100, 500, 400, 200], [-1, 200, 400, 500],
                    [100, 200, 1001, 500], [100, 200, 100, 500], [100, 200, 400],
                    [True, 200, 400, 500]):
            payload = proposals()
            payload["candidates"][0]["box_2d"] = box
            invalid.append(payload)
        payload = proposals()
        payload["candidates"].append(deepcopy(payload["candidates"][0]))
        invalid.append(payload)
        payload = proposals()
        payload["candidates"][0]["uncertain"] = True
        invalid.append(payload)
        payload = proposals()
        payload["status"] = "unsupported"
        payload["limitations"] = ["Unsupported."]
        invalid.append(payload)
        for payload in invalid:
            with self.subTest(payload=payload):
                before = len(self.gemini_requests)
                async with self.api(lambda _, payload=payload: interaction(payload)) as (client, _):
                    self.assert_safe_error(await self.post(client), 502, "invalid_model_output")
                self.assertEqual(len(self.gemini_requests), before + 1)
        self.assertEqual(self.nemotron_requests, [])

    async def test_malformed_and_incomplete_output_is_never_a_successful_empty_result(self):
        responses = [interaction(text="private detail " + KEY), interaction(status="incomplete"),
                     interaction(status="failed"), interaction(status="requires_action")]
        for response in responses:
            with self.subTest(response=response.content):
                async with self.api(lambda _, response=response: response) as (client, _):
                    self.assert_safe_error(await self.post(client), 502)
        self.assertEqual(self.nemotron_requests, [])

    async def test_provider_failures_are_safe_and_never_fallback_or_retry(self):
        for provider_status, expected_status, code, retryable in (
            (401, 503, "provider_configuration", False),
            (402, 503, "provider_configuration", False),
            (403, 503, "provider_configuration", False),
            (429, 503, "provider_unavailable", True),
            (503, 503, "provider_unavailable", True),
            (400, 502, "provider_error", False),
        ):
            with self.subTest(status=provider_status):
                before = len(self.gemini_requests)
                response = httpx.Response(provider_status, json={"error": {"message": "private detail " + KEY}})
                async with self.api(lambda _, response=response: response) as (client, _):
                    body = self.assert_safe_error(await self.post(client), expected_status, code)
                    self.assertEqual(body["retryable"], retryable)
                self.assertEqual(len(self.gemini_requests), before + 1)
        self.assertEqual(self.nemotron_requests, [])

    async def test_missing_usage_stays_unknown(self):
        async with self.api(lambda _: interaction(usage=False)) as (client, _):
            response = await self.post(client)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["metrics"]["prompt_tokens"])
        self.assertIsNone(response.json()["metrics"]["completion_tokens"])

    async def test_simpler_native_schema_keeps_local_inventory_and_text_limits(self):
        batches = []
        payload = proposals()
        payload["candidates"] = [deepcopy(payload["candidates"][0]) for _ in range(101)]
        for index, candidate in enumerate(payload["candidates"]):
            candidate["box_2d"] = [index, 100, index + 1, 200]
        batches.append(payload)
        payload = proposals()
        payload["candidates"][0]["visual_cue"] = "x" * 1001
        batches.append(payload)
        payload = proposals()
        payload["limitations"] = ["Some detail is unclear."] * 101
        batches.append(payload)
        for payload in batches:
            async with self.api(lambda _, payload=payload: interaction(payload)) as (client, _):
                self.assert_safe_error(await self.post(client), 502, "invalid_model_output")

    async def test_serialized_request_limit_fails_before_provider_inference(self):
        with patch("gemini.client.MAX_REQUEST_BYTES", 128):
            async with self.api() as (client, _):
                self.assert_safe_error(await self.post(client, content=image_bytes()), 413)
        self.assertEqual(self.gemini_requests, [])
        self.assertEqual(self.nemotron_requests, [])

    async def test_total_deadline_cancels_gemini_and_releases_temporary_images(self):
        cancelled = asyncio.Event()

        async def handler(_):
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        settings = ApiSettings(provider="gemini", preprocess_mode="off", deadline_seconds=0.25)
        async with self.api(handler, settings=settings) as (client, app):
            self.assert_safe_error(await self.post(client, content=image_bytes()), 504, "deadline_exceeded")
            self.assertTrue(cancelled.is_set())
            self.assertEqual(app.state.in_flight, 0)
        self.assertEqual(len(self.gemini_requests), 1)
        self.assertEqual(self.nemotron_requests, [])
        self.assertTrue(self.paths)
        self.assertTrue(all(not path.exists() for path in self.paths))


class ImageProviderSettingsTests(unittest.TestCase):
    def test_nemotron_is_default_and_process_selection_overrides_file(self):
        self.assertEqual(ApiSettings().provider, "nemotron")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("IMAGE_API_PROVIDER=nemotron\n", encoding="utf-8")
            settings = ApiSettings.from_env(path, environ={"IMAGE_API_PROVIDER": "gemini"})
        self.assertEqual(settings.provider, "gemini")

    def test_unknown_image_provider_is_a_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("IMAGE_API_PROVIDER=unknown-provider\n", encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                ApiSettings.from_env(path, environ={})


if __name__ == "__main__":
    unittest.main()

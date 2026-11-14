"""Independent image/IFC provider routing and ownership with mocked transports."""
from __future__ import annotations

from contextlib import asynccontextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import ifcopenshell.guid

from gemini import AsyncGeminiClient, ConfigurationError, GeminiSettings
from ifc_api.config import IfcSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from nemotron import AsyncNemotronClient, NemotronSettings
from tests.test_gemini_image_api import interaction
from tests.test_ifc_api import completion, proposal
from tests.test_ifc_engine import sample_model
from tests.test_image_api import completion as image_completion, image_bytes


KEY = "synthetic-independent-planner-key"


class IfcProviderAppTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        path = Path(cls.directory.name) / "source.ifc"
        source, _, _, _, ground, _ = sample_model(path)
        window = source.create_entity("IfcWindow", GlobalId=ifcopenshell.guid.new(), Name="121.A")
        source.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(),
                             RelatingStructure=ground, RelatedElements=[window])
        source.write(str(path))
        cls.content = path.read_bytes()
        cls.sha = hashlib.sha256(cls.content).hexdigest()
        cls.step = window.id()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.requests = {"nemotron": [], "gemini_image": [], "gemini_ifc": []}
        self.clients = []

    @asynccontextmanager
    async def api(self, *, image_provider="nemotron", ifc_provider="gemini",
                  nemotron_configured=True, gemini_ifc_configured=True,
                  invalid_ifc_settings=False, ifc_failure_status=None):
        def nemotron_factory():
            if not nemotron_configured:
                raise ConfigurationError("Synthetic absent Verda credential")

            def handler(request):
                self.requests["nemotron"].append(json.loads(request.content))
                body = self.requests["nemotron"][-1]
                return image_completion() if "image_url" in json.dumps(body) else completion(proposal())

            sdk = AsyncNemotronClient(NemotronSettings(api_key=KEY, max_retries=0),
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
            sdk.close = AsyncMock(wraps=sdk.close)
            self.clients.append(sdk)
            return sdk

        def gemini_factory(kind):
            if kind == "gemini_ifc" and not gemini_ifc_configured:
                raise ConfigurationError("Synthetic absent IFC Gemini credential")

            def handler(request):
                self.requests[kind].append(json.loads(request.content))
                if kind == "gemini_ifc" and ifc_failure_status is not None:
                    return httpx.Response(ifc_failure_status,
                        json={"error": {"status": "INVALID_ARGUMENT", "message": KEY}})
                return interaction(proposal()) if kind == "gemini_ifc" else interaction()

            sdk = AsyncGeminiClient(GeminiSettings(api_key=KEY), transport=httpx.MockTransport(handler))
            sdk.close = AsyncMock(wraps=sdk.close)
            self.clients.append(sdk)
            return sdk

        config = patch("image_api.app.IfcSettings.from_env", side_effect=ConfigurationError(KEY)) if invalid_ifc_settings else nullcontext()
        with config:
            app = create_app(ApiSettings(provider=image_provider, preprocess_mode="off"),
                client_factory=nemotron_factory,
                gemini_client_factory=lambda: gemini_factory("gemini_image"),
                ifc_gemini_client_factory=lambda: gemini_factory("gemini_ifc"),
                ifc_settings=None if invalid_ifc_settings else IfcSettings(provider=ifc_provider, gemini_thinking_level="high"))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
                yield client, app
        self.assertTrue(self.clients)
        for sdk in self.clients:
            self.assertEqual(sdk.close.await_count, 1, "Each owned client closes once")

    async def question(self, client):
        uploaded = await client.post("/api/ifc/models", data={"source_sha256": self.sha},
            files={"file": ("source.ifc", self.content, "application/x-step")})
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        return await client.post("/api/ifc/questions", json={
            "model_id": uploaded.json()["model_id"], "source_sha256": self.sha,
            "question": "How many windows?", "scope": "model",
        })

    async def image(self, client):
        return await client.post("/api/v1/candidates", data={"question": "Find windows"},
            files={"image": ("drawing.png", image_bytes((1200, 800)), "image/png")})

    async def test_gemini_ifc_operates_without_verda_and_reports_native_computed_count(self):
        async with self.api(nemotron_configured=False) as (client, _):
            self.assertEqual((await client.get("/health")).status_code, 503)
            response = await self.question(client)
            self.assertEqual((await self.image(client)).status_code, 503)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["result"]["claims"][0]["value"]["value"], 1)
        self.assertEqual(response.json()["included_elements"][0]["step_id"], self.step)
        self.assertEqual(self.requests["nemotron"], [])
        self.assertEqual(self.requests["gemini_image"], [])
        self.assertEqual(len(self.requests["gemini_ifc"]), 1)
        self.assertEqual([part["type"] for part in self.requests["gemini_ifc"][0]["input"]], ["text"])
        self.assertNotIn(KEY, response.text)

    async def test_gemini_image_and_ifc_have_distinct_reasoning_budgets_and_clients(self):
        async with self.api(image_provider="gemini") as (client, _):
            self.assertEqual((await self.image(client)).status_code, 200)
            response = await self.question(client)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.requests["nemotron"], [])
        self.assertEqual(len(self.requests["gemini_image"]), 1)
        self.assertEqual(len(self.requests["gemini_ifc"]), 1)
        self.assertEqual(self.requests["gemini_image"][0]["generation_config"]["thinking_level"], "low")
        self.assertEqual(self.requests["gemini_ifc"][0]["generation_config"]["thinking_level"], "high")
        self.assertEqual(len(self.clients), 3)

    async def test_missing_gemini_ifc_configuration_keeps_nemotron_images_without_ifc_fallback(self):
        async with self.api(gemini_ifc_configured=False) as (client, _):
            self.assertEqual((await client.get("/health")).status_code, 200)
            self.assertEqual((await self.image(client)).status_code, 200)
            response = await self.question(client)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["code"], "not_configured")
        self.assertEqual(len(self.requests["nemotron"]), 1)
        self.assertTrue("image_url" in json.dumps(self.requests["nemotron"][0]))
        self.assertEqual(self.requests["gemini_ifc"], [])

    async def test_explicit_nemotron_ifc_does_not_construct_gemini_ifc_client(self):
        async with self.api(image_provider="nemotron", ifc_provider="nemotron") as (client, _):
            response = await self.question(client)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.clients), 1)
        self.assertEqual(len(self.requests["nemotron"]), 1)
        self.assertEqual(self.requests["gemini_ifc"], [])
        self.assertEqual(self.requests["gemini_image"], [])

    async def test_invalid_ifc_settings_preserve_images_and_never_fall_back_to_nemotron_ifc(self):
        async with self.api(invalid_ifc_settings=True) as (client, app):
            self.assertEqual((await client.get("/health")).status_code, 200)
            self.assertEqual((await self.image(client)).status_code, 200)
            self.assertIsNone(app.state.ifc_service.planner)
            response = await self.question(client)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["code"], "not_configured")
        self.assertIn("Invalid IFC planner settings", response.json()["message"])
        self.assertNotIn(KEY, response.text)
        self.assertEqual(len(self.requests["nemotron"]), 1)
        self.assertTrue("image_url" in json.dumps(self.requests["nemotron"][0]))
        self.assertEqual(self.requests["gemini_ifc"], [])

    async def test_provider_diagnostics_remain_private_at_the_http_boundary(self):
        async with self.api(ifc_failure_status=400) as (client, _):
            response = await self.question(client)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["code"], "provider_configuration")
        self.assertNotIn("provider_status_code", response.json())
        self.assertNotIn("provider_code", response.json())
        self.assertNotIn("INVALID_ARGUMENT", response.text)
        self.assertNotIn(KEY, response.text)


if __name__ == "__main__":
    unittest.main()

"""IFC provider selection/text transport checks; no live inference."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest

import httpx
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from gemini import AsyncGeminiClient, ConfigurationError, GeminiSettings
from ifc_api.config import IfcSettings
from ifc_api.providers import GeminiPlanner, NemotronPlanner, gemini_plan_schema, gemini_schema
from image_api.errors import ApiError
from nemotron import AsyncNemotronClient, NemotronSettings
from tests.test_gemini import interaction


KEY = "synthetic-ifc-provider-key"
SCHEMA = {"type": "object", "properties": {"status": {"type": "string", "const": "ready"}},
          "required": ["status"], "additionalProperties": False}


class IfcPlannerSettingsTests(unittest.TestCase):
    def test_independent_file_settings_and_process_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("IMAGE_API_PROVIDER=gemini\nGEMINI_THINKING_LEVEL=low\n"
                            "IFC_API_PROVIDER=nemotron\nIFC_GEMINI_THINKING_LEVEL=high\n"
                            "IFC_API_MAX_MODEL_REQUESTS=2\n", encoding="utf-8")
            before = dict(os.environ)
            settings = IfcSettings.from_env(path, environ={"IFC_API_PROVIDER": "gemini"})
            self.assertEqual(settings.provider, "gemini")
            self.assertEqual(settings.gemini_thinking_level, "high")
            self.assertEqual(settings.max_model_requests, 2)
            self.assertEqual(settings.max_inspections, 6)
            self.assertEqual(dict(os.environ), before)
            self.assertEqual(IfcSettings.from_env(path, environ={}).provider, "nemotron")

    def test_image_provider_does_not_select_ifc(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("IMAGE_API_PROVIDER=gemini\nGEMINI_THINKING_LEVEL=low\n", encoding="utf-8")
            settings = IfcSettings.from_env(path, environ={})
            self.assertEqual(settings.provider, "nemotron")
            self.assertEqual(settings.gemini_thinking_level, "high")

    def test_bounded_invalid_configuration_has_safe_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("", encoding="utf-8")
            for values in (
                {"IFC_API_PROVIDER": KEY}, {"IFC_GEMINI_THINKING_LEVEL": "minimal"},
                {"IFC_API_MAX_MODEL_REQUESTS": "4"}, {"IFC_API_MAX_INSPECTIONS": "7"},
                {"IFC_API_MAX_MODEL_REQUESTS": "0"}, {"IFC_API_DEADLINE_SECONDS": "nan"},
                {"IFC_GEMINI_MAX_OUTPUT_TOKENS": "65537"}, {"IFC_API_MAX_TOKENS": "0"},
            ):
                with self.subTest(values=values), self.assertRaises(ConfigurationError) as raised:
                    IfcSettings.from_env(path, environ=values)
                self.assertNotIn(KEY, str(raised.exception))

    def test_image_settings_still_accept_only_low_thinking(self):
        with self.assertRaises(ValidationError):
            GeminiSettings(api_key=KEY, thinking_level="high")
        for level in ("low", "medium", "high", "xhigh"):
            self.assertEqual(IfcSettings(gemini_thinking_level=level).gemini_thinking_level, level)


class IfcProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_text_only_request_has_independent_reasoning_and_usage(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=interaction('{"status":"ready"}'))

        settings = IfcSettings(provider="gemini", gemini_thinking_level="high", gemini_max_output_tokens=32000)
        async with AsyncGeminiClient(GeminiSettings(api_key=KEY), transport=httpx.MockTransport(handler)) as client:
            planner = GeminiPlanner(client, settings)
            reply = await planner.generate("Count exterior doors", system="Use native source proof", schema=SCHEMA)
            self.assertEqual(client.settings.thinking_level, "low")
            self.assertEqual(planner.provenance, {"provider": "gemini", "requested_model": "gemini-4-hydrogen",
                                                 "thinking_level": "high", "max_output_tokens": 32000})
        self.assertEqual(len(requests), 1)
        payload = json.loads(requests[0].content)
        self.assertEqual(payload["input"], [{"type": "text", "text": "Count exterior doors"}])
        self.assertEqual(payload["generation_config"], {
            "thinking_level": "high", "max_output_tokens": 32000, "thinking_summaries": "none"})
        self.assertFalse(payload["store"])
        self.assertNotIn("temperature", payload["generation_config"])
        self.assertNotIn("tools", payload)
        self.assertEqual(payload["response_format"]["schema"]["properties"]["status"]["enum"], ["ready"])
        self.assertIn(json.dumps(SCHEMA, ensure_ascii=False), payload["system_instruction"])
        self.assertEqual(reply.text, '{"status":"ready"}')
        self.assertEqual(reply.usage.prompt_tokens, 13)
        self.assertEqual(reply.usage.completion_tokens, 26)
        self.assertEqual(reply.usage.thought_tokens, 19)
        self.assertNotIn(KEY, repr(reply))

    async def test_gemini_provider_failures_are_safe_and_have_no_automatic_fallback(self):
        for status, code in ((400, "provider_configuration"), (403, "provider_configuration"),
                             (429, "provider_unavailable"), (503, "provider_unavailable"),
                             (422, "provider_error")):
            requests = []

            def handler(request):
                requests.append(request)
                return httpx.Response(status, json={"error": {"message": KEY, "status": "INVALID_ARGUMENT"}})

            async with AsyncGeminiClient(GeminiSettings(api_key=KEY), transport=httpx.MockTransport(handler)) as client:
                with self.subTest(status=status), self.assertRaises(ApiError) as raised:
                    await GeminiPlanner(client).generate("Question", system="Instructions", schema=SCHEMA)
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(raised.exception.provider_status_code, status)
            self.assertEqual(raised.exception.provider_code, "INVALID_ARGUMENT")
            self.assertEqual(len(requests), 1)
            self.assertNotIn(KEY, str(raised.exception))

    async def test_unrecognized_upstream_error_strings_do_not_enter_private_diagnostics(self):
        async with AsyncGeminiClient(GeminiSettings(api_key=KEY), transport=httpx.MockTransport(
                lambda _: httpx.Response(400, json={"error": {"code": KEY, "status": KEY, "message": KEY}}))) as client:
            with self.assertRaises(ApiError) as raised:
                await GeminiPlanner(client).generate("Question", system="Instructions", schema=SCHEMA)
        self.assertEqual(raised.exception.provider_status_code, 400)
        self.assertIsNone(raised.exception.provider_code)
        self.assertNotIn(KEY, str(raised.exception))

    async def test_cancelled_gemini_request_does_not_retry(self):
        started = asyncio.Event()
        requests = []

        async def handler(request):
            requests.append(request)
            started.set()
            await asyncio.Event().wait()

        async with AsyncGeminiClient(GeminiSettings(api_key=KEY), transport=httpx.MockTransport(handler)) as client:
            task = asyncio.create_task(GeminiPlanner(client).generate("Question", system="Instructions", schema=SCHEMA))
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(len(requests), 1)

    async def test_native_tools_or_truncated_gemini_reply_are_rejected(self):
        for body in (interaction(status="incomplete"),
                     interaction(steps=[{"type": "function_call", "name": "run_python"}])):
            async with AsyncGeminiClient(GeminiSettings(api_key=KEY),
                    transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))) as client:
                with self.assertRaises(ApiError) as raised:
                    await GeminiPlanner(client).generate("Question", system="Instructions", schema=SCHEMA)
            self.assertEqual(raised.exception.code, "invalid_model_output")

    async def test_nemotron_preserves_existing_request_and_normalizes_reply(self):
        from tests.test_ifc_api import completion
        requests = []

        def handler(request):
            requests.append(request)
            return completion({"status": "ready"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = AsyncNemotronClient(NemotronSettings(api_key=KEY, max_retries=0), http_client=http_client)
            planner = NemotronPlanner(client, IfcSettings(max_tokens=7000))
            reply = await planner.generate("Question", system="Instructions", schema=SCHEMA)
        body = json.loads(requests[0].content)
        self.assertEqual(body["max_tokens"], 7000)
        self.assertEqual(body["temperature"], 0)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIn(json.dumps(SCHEMA), body["messages"][0]["content"])
        self.assertEqual(reply.model, "synthetic-planner")
        self.assertEqual(reply.usage.prompt_tokens, 123)
        self.assertEqual(reply.usage.completion_tokens, 45)
        self.assertEqual(planner.provenance["thinking_level"], "disabled")


class GeminiPlannerSchemaTests(unittest.TestCase):
    def test_native_schema_accepts_connected_room_count_composition(self):
        from ifc_api.service import PlanProposal
        from tests.test_ifc_api import proposal

        wire = proposal("space")
        wire["steps"][1:1] = [
            {"id": "connections", "operation": {"kind": "spatial_query", "input_step_id": "objects",
                "relation": "door_connections", "method": "native"}},
            {"id": "rooms", "operation": {"kind": "related_entities", "input_step_id": "connections",
                "column": "related"}},
        ]
        wire["steps"][-1]["operation"]["input_step_id"] = "rooms"
        validator = Draft202012Validator(gemini_plan_schema(PlanProposal.model_json_schema()))
        validator.validate(wire)
        PlanProposal.model_validate(wire)

        wire["steps"][2]["operation"].pop("input_step_id")
        self.assertFalse(validator.is_valid(wire))

    def test_native_envelope_is_shallow_while_operation_validation_stays_strict(self):
        from ifc_api.service import PlanProposal
        from tests.test_ifc_api import proposal
        source = PlanProposal.model_json_schema()
        native = gemini_plan_schema(source)
        validator = Draft202012Validator(native)
        Draft202012Validator.check_schema(native)
        self.assertLess(len(json.dumps(native)), 6500)
        self.assertEqual(set(native["$defs"]), {"CountPolicy", "FieldRef"})
        wire = proposal()
        validator.validate(wire)
        PlanProposal.model_validate(wire)
        # Each operation's required arguments are native constraints. Recursive
        # predicate semantics still pass through the unchanged local validator.
        malformed = deepcopy(wire)
        malformed["steps"][0]["operation"]["arbitrary_code"] = "do not execute"
        self.assertFalse(validator.is_valid(malformed))
        for step, field in ((0, "concept_ids"), (0, "count_policy"), (1, "method"), (1, "input_step_id")):
            malformed = deepcopy(wire)
            malformed["steps"][step]["operation"].pop(field)
            self.assertFalse(validator.is_valid(malformed))
        malformed = deepcopy(wire)
        malformed["steps"][0]["operation"]["where"] = {"kind": "compare", "arbitrary_code": "do not execute"}
        validator.validate(malformed)
        with self.assertRaises(ValidationError):
            PlanProposal.model_validate(malformed)
        malformed["steps"][0]["operation"]["kind"] = "execute_python"
        self.assertFalse(validator.is_valid(malformed))
        exterior = proposal("door")
        exterior["steps"].insert(1, {"id": "exterior", "operation": {
            "kind": "spatial_query", "input_step_id": "objects", "relation": "exterior_doors", "exterior_basis": "combined"}})
        exterior["steps"][-1]["operation"]["input_step_id"] = "exterior"
        validator.validate(exterior)
        PlanProposal.model_validate(exterior)
        exterior["steps"][1]["operation"].pop("input_step_id")
        self.assertFalse(validator.is_valid(exterior))
        inspect = {"status": "inspect", "interpretation": "Inspect source values",
            "explicitly_requests_entire_model": False, "steps": [], "output_step_id": None,
            "outputs": {}, "requests": [{"action": "facets", "property_keys": ["source-key"]}]}
        validator.validate(inspect)
        PlanProposal.model_validate(inspect)
        inspect["requests"][0]["action"] = "run_code"
        self.assertFalse(validator.is_valid(inspect))

    def test_recursive_ifc_schema_retains_structure_and_local_validation(self):
        from ifc_api.service import PlanProposal
        from tests.test_ifc_api import proposal
        original = PlanProposal.model_json_schema()
        snapshot = deepcopy(original)
        normalized = gemini_schema(original)
        Draft202012Validator.check_schema(normalized)
        wire = proposal()
        Draft202012Validator(normalized).validate(wire)
        PlanProposal.model_validate(wire)
        self.assertEqual(original, snapshot)
        self.assertNotIn('"discriminator"', json.dumps(normalized))
        self.assertNotIn('"oneOf"', json.dumps(normalized))
        self.assertNotIn('"maxItems"', json.dumps(normalized))
        self.assertIn('"$ref"', json.dumps(normalized))
        self.assertEqual(normalized["properties"]["outputs"]["additionalProperties"], {"type": "string"})
        wire["steps"][0]["operation"]["count_policy"]["leaf_limit"] = 42
        with self.assertRaises(ValidationError):
            PlanProposal.model_validate(wire)


if __name__ == "__main__":
    unittest.main()

"""Offline checks of Gemini configuration and the native HTTP boundary."""
from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from gemini import (
    AsyncGeminiClient, ConfigurationError, GeminiError, GeminiRequestTooLarge,
    GeminiSettings,
)
from gemini.client import API_REVISION, ENDPOINT, MAX_REQUEST_BYTES

TEST_KEY = "test-gemini-credential-not-valid"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7V0AAAAASUVORK5CYII=")
SCHEMA = {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}


def interaction(text='{"status":"ok"}', **updates):
    value = {
        "id": "synthetic-interaction", "status": "completed", "model": "gemini-4-hydrogen",
        "steps": [
            {"type": "thought", "signature": "opaque", "summary": [{"type": "text", "text": "private thought"}]},
            {"type": "model_output", "content": [{"type": "text", "text": text}]},
        ],
        "usage": {"total_input_tokens": 13, "total_output_tokens": 7, "total_thought_tokens": 19},
    }
    value.update(updates)
    return value


class GeminiSettingsTests(unittest.TestCase):
    def test_defaults_and_secret_representation(self):
        settings = GeminiSettings(api_key=TEST_KEY)
        self.assertEqual(settings.model, "gemini-4-hydrogen")
        self.assertEqual(settings.thinking_level, "low")
        self.assertEqual(settings.max_output_tokens, 65536)
        self.assertEqual(settings.timeout_seconds, 120)
        self.assertNotIn(TEST_KEY, repr(settings))
        self.assertNotIn(TEST_KEY, settings.model_dump_json())

    def test_file_loading_process_precedence_and_no_environment_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(f"\ufeffGEMINI_API_KEY={TEST_KEY}\nGEMINI_TIMEOUT_SECONDS=40\n", encoding="utf-8")
            before = dict(os.environ)
            settings = GeminiSettings.from_env(path, environ={"GEMINI_TIMEOUT_SECONDS": "60"})
            self.assertEqual(settings.api_key.get_secret_value(), TEST_KEY)
            self.assertEqual(settings.timeout_seconds, 60)
            self.assertEqual(dict(os.environ), before)

    def test_key_dollar_sequences_are_literal_and_unrelated_credentials_do_not_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("GEMINI_API_KEY=literal-${UNSET}-key\n", encoding="utf-8")
            settings = GeminiSettings.from_env(path, environ={"GOOGLE_API_KEY": "other", "VERDA_INFERENCE_KEY": "other"})
            self.assertEqual(settings.api_key.get_secret_value(), "literal-${UNSET}-key")
            settings = GeminiSettings.from_env(path, environ={"GEMINI_API_KEY": TEST_KEY})
            self.assertEqual(settings.api_key.get_secret_value(), TEST_KEY)

    def test_default_env_uses_existing_root_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(f"GEMINI_API_KEY={TEST_KEY}\n", encoding="utf-8")
            with patch("gemini.config.default_env_file", return_value=path):
                self.assertEqual(GeminiSettings.from_env(environ={}).api_key.get_secret_value(), TEST_KEY)

    def test_missing_and_invalid_configuration_is_safe(self):
        cases = [
            {}, {"GEMINI_API_KEY": ""}, {"GEMINI_API_KEY": "changeme"},
            {"GEMINI_API_KEY": "bad key"}, {"GEMINI_API_KEY": "invalid-\x00-key"},
            {"GEMINI_API_KEY": "invalid-ä-key"},
            {"GEMINI_API_KEY": TEST_KEY, "GEMINI_MODEL": "different-model"},
            {"GEMINI_API_KEY": TEST_KEY, "GEMINI_THINKING_LEVEL": "high"},
            {"GEMINI_API_KEY": TEST_KEY, "GEMINI_MAX_OUTPUT_TOKENS": "65537"},
            {"GEMINI_API_KEY": TEST_KEY, "GEMINI_MAX_OUTPUT_TOKENS": "0"},
            {"GEMINI_API_KEY": TEST_KEY, "GEMINI_TIMEOUT_SECONDS": "nan"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("", encoding="utf-8")
            for values in cases:
                with self.subTest(settings=list(values)):
                    with self.assertRaises(ConfigurationError) as raised:
                        GeminiSettings.from_env(path, environ=values)
                    self.assertNotIn(TEST_KEY, str(raised.exception))

    def test_missing_file_and_bad_encoding_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            with self.assertRaises(ConfigurationError):
                GeminiSettings.from_env(path, environ={"GEMINI_API_KEY": TEST_KEY})
            path.write_bytes(b"\xff\xfe")
            with self.assertRaises(ConfigurationError):
                GeminiSettings.from_env(path, environ={})

    def test_direct_validation_hides_input_values(self):
        with self.assertRaises(ValidationError) as raised:
            GeminiSettings(api_key=f"{TEST_KEY} private")
        self.assertNotIn(TEST_KEY, str(raised.exception))

    def test_allowlisted_profiles_preserve_settings_without_mutation(self):
        settings = GeminiSettings(api_key=TEST_KEY, timeout_seconds=50, max_output_tokens=1024)
        strong = settings.profile("strong")
        self.assertEqual((strong.model, strong.thinking_level), ("gemini-4-carbon", "medium"))
        self.assertEqual((strong.timeout_seconds, strong.max_output_tokens), (50, 1024))
        self.assertEqual(strong.api_key, settings.api_key)
        self.assertEqual(settings.profile("strong", thinking_level="low").thinking_level, "low")
        self.assertEqual(settings.model, "gemini-4-hydrogen")
        self.assertEqual(strong.profile("normal"), settings)
        for model, thinking in (("gemini-4-hydrogen", "medium"), ("gemini-4-carbon", "high")):
            with self.assertRaises(ValidationError):
                GeminiSettings(api_key=TEST_KEY, model=model, thinking_level=thinking)
        with self.assertRaises(ValueError):
            settings.profile("arbitrary")

    def test_carbon_profile_environment_allows_medium_thinking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("", encoding="utf-8")
            settings = GeminiSettings.from_env(path, environ={
                "GEMINI_API_KEY": TEST_KEY, "GEMINI_MODEL": "gemini-4-carbon",
                "GEMINI_THINKING_LEVEL": "medium",
            })
            self.assertEqual(settings.model, "gemini-4-carbon")


class GeminiClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.image = Path(self.directory.name) / "prepared.png"
        self.image.write_bytes(PNG)
        self.settings = GeminiSettings(api_key=TEST_KEY)

    async def make_request(self, handler, *, settings=None, question="Find doors", system="Instructions", schema=SCHEMA,
                           resolution=None):
        async with AsyncGeminiClient(settings or self.settings, transport=httpx.MockTransport(handler)) as client:
            return await client.generate_candidates(question, system=system, image=self.image, schema=schema, resolution=resolution)

    async def test_exact_native_request_and_combined_usage(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=interaction())

        reply = await self.make_request(handler, question="Find 121.A ovet", system="Only image evidence")
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(str(request.url), ENDPOINT)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.headers["x-goog-api-key"], TEST_KEY)
        self.assertEqual(request.headers["Api-Revision"], API_REVISION)
        self.assertNotIn(TEST_KEY, str(request.url))
        body = json.loads(request.content)
        self.assertEqual(body, {
            "model": "gemini-4-hydrogen", "system_instruction": "Only image evidence",
            "input": [{"type": "text", "text": "Find 121.A ovet"},
                      {"type": "image", "mime_type": "image/png", "data": base64.b64encode(PNG).decode("ascii")}],
            "generation_config": {"thinking_level": "low", "thinking_summaries": "none", "max_output_tokens": 65536},
            "response_format": {"type": "text", "mime_type": "application/json", "schema": SCHEMA},
            "store": False,
        })
        self.assertEqual(reply.text, '{"status":"ok"}')
        self.assertEqual(reply.model, "gemini-4-hydrogen")
        self.assertEqual(reply.usage.prompt_tokens, 13)
        self.assertEqual(reply.usage.output_tokens, 7)
        self.assertEqual(reply.usage.thought_tokens, 19)
        self.assertEqual(reply.usage.completion_tokens, 26)
        self.assertNotIn("private thought", repr(reply))

    async def test_explicit_resolution_is_serialized_on_image_only(self):
        for resolution in ("low", "medium", "high", "ultra_high"):
            with self.subTest(resolution=resolution):
                requests = []
                def handler(request):
                    requests.append(json.loads(request.content))
                    return httpx.Response(200, json=interaction())
                await self.make_request(handler, resolution=resolution)
                self.assertEqual(len(requests), 1)
                body = requests[0]
                self.assertEqual(body["input"][1]["resolution"], resolution)
                self.assertNotIn("resolution", body["input"][0])
                self.assertNotIn("resolution", body["generation_config"])
                self.assertEqual(body["input"][1]["data"], base64.b64encode(PNG).decode("ascii"))

    async def test_invalid_resolution_never_sends_a_request(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=interaction())
        for resolution in ("", "HIGH", "original", True, 1, [], {}):
            with self.subTest(resolution=resolution), self.assertRaises(GeminiError):
                await self.make_request(handler, resolution=resolution)
        self.assertEqual(requests, [])

    async def test_partial_or_missing_usage_is_nullable(self):
        for usage in (None, {}, {"total_input_tokens": 8}, {"total_output_tokens": 2}, {"total_thought_tokens": 0}):
            with self.subTest(usage=usage):
                reply = await self.make_request(lambda request: httpx.Response(200, json=interaction(usage=usage)))
                if usage is None:
                    self.assertIsNone(reply.usage)
                else:
                    self.assertIsNone(reply.usage.completion_tokens)
        reply = await self.make_request(lambda request: httpx.Response(200, json=interaction(usage={"total_output_tokens": 0, "total_thought_tokens": 0})))
        self.assertEqual(reply.usage.completion_tokens, 0)

    async def test_carbon_uses_medium_thinking_with_same_candidate_contract(self):
        calls = []

        def handler(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json=interaction(model="gemini-4-carbon"))

        reply = await self.make_request(handler, settings=self.settings.profile("strong"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model"], "gemini-4-carbon")
        self.assertEqual(calls[0]["generation_config"]["thinking_level"], "medium")
        self.assertEqual(calls[0]["response_format"]["schema"], SCHEMA)
        self.assertEqual(reply.model, "gemini-4-carbon")

    async def test_incomplete_response_retains_only_validated_usage_and_model(self):
        raw = {"status": "incomplete", "model": "gemini-4-carbon",
               "continuation_token": TEST_KEY,
               "usage": {"total_input_tokens": 2188, "total_output_tokens": 3,
                         "total_thought_tokens": 4093}}
        with self.assertRaises(GeminiError) as raised:
            await self.make_request(lambda _: httpx.Response(200, json=raw))
        error = raised.exception
        self.assertEqual(error.code, "invalid_model_output")
        self.assertEqual(error.returned_model, "gemini-4-carbon")
        self.assertEqual(error.usage.prompt_tokens, 2188)
        self.assertEqual(error.usage.completion_tokens, 4096)
        self.assertNotIn(TEST_KEY, str(error))
        self.assertFalse(hasattr(error, "continuation_token"))
        with self.assertRaises(GeminiError) as unknown_model:
            await self.make_request(lambda _: httpx.Response(200, json={**raw, "model": TEST_KEY}))
        self.assertIsNone(unknown_model.exception.returned_model)
        for usage in (None, {"total_input_tokens": -1}, {"total_output_tokens": True}):
            with self.subTest(usage=usage), self.assertRaises(GeminiError) as invalid:
                await self.make_request(lambda _: httpx.Response(200, json={**raw, "usage": usage}))
            self.assertIsNone(invalid.exception.usage)

    async def test_only_model_text_is_joined(self):
        steps = [
            {"type": "thought", "summary": [{"type": "text", "text": "not JSON"}]},
            {"type": "model_output", "content": [{"type": "text", "text": '{"status":'}, {"type": "text", "text": '"ok"}'}]},
        ]
        reply = await self.make_request(lambda request: httpx.Response(200, json=interaction(steps=steps)))
        self.assertEqual(json.loads(reply.text), {"status": "ok"})

    async def test_invalid_incomplete_and_refusal_responses_fail_safely(self):
        invalid = [
            [], {}, interaction(status="incomplete"), interaction(status="failed"),
            interaction(status="requires_action"), interaction(status="cancelled"),
            interaction(model=None), interaction(model=""), interaction(model="bad model"),
            interaction(steps=None), interaction(steps=[]), interaction(steps=[None]),
            interaction(steps=[{"type": "thought", "summary": [{"type": "text", "text": '{"status":"ok"}'}]}]),
            interaction(steps=[{"type": "function_call", "name": "x"}]),
            interaction(steps=[{"type": "model_output", "content": [{"type": "refusal", "text": "blocked"}]}]),
            interaction(steps=[{"type": "model_output", "content": [{"type": "text", "text": 3}]}]),
            interaction(steps=[{"type": "model_output", "content": []}]), interaction("   "),
            interaction(usage=[]), interaction(usage={"total_input_tokens": True}),
            interaction(usage={"total_output_tokens": -1}), interaction(usage={"total_thought_tokens": 1.5}),
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(GeminiError) as raised:
                    await self.make_request(lambda request: httpx.Response(200, json=value))
                self.assertEqual(raised.exception.code, "invalid_model_output")
                self.assertFalse(raised.exception.retryable)
                self.assertNotIn(TEST_KEY, str(raised.exception))

    async def test_invalid_json_html_and_response_size_limit(self):
        for content in (b"not JSON", b"<html>failure</html>", b"\xff"):
            with self.subTest(content=content):
                with self.assertRaises(GeminiError) as raised:
                    await self.make_request(lambda request: httpx.Response(200, content=content))
                self.assertEqual(raised.exception.code, "invalid_model_output")
        with patch("gemini.client.MAX_RESPONSE_BYTES", 32):
            with self.assertRaises(GeminiError) as raised:
                await self.make_request(lambda request: httpx.Response(200, json=interaction()))
            self.assertEqual(raised.exception.code, "invalid_model_output")

    async def test_status_errors_do_not_retry_or_expose_private_bodies(self):
        for status in (301, 307, 400, 401, 402, 403, 404, 408, 413, 429, 500, 503):
            requests = []

            def handler(request):
                requests.append(request)
                return httpx.Response(status, headers={"location": "https://other.example/upload"},
                                      json={"error": {"message": f"private image and {TEST_KEY}"}})

            with self.subTest(status=status):
                with self.assertRaises(GeminiError) as raised:
                    await self.make_request(handler)
                self.assertEqual(raised.exception.status_code, status)
                self.assertEqual(raised.exception.retryable, status in {408, 409, 429} or status >= 500)
                self.assertEqual(len(requests), 1)
                self.assertNotIn(TEST_KEY, str(raised.exception))
                self.assertNotIn("private image", str(raised.exception))

    async def test_transport_failures_are_safe_and_not_retried(self):
        for exception in (httpx.ReadTimeout, httpx.ConnectError):
            requests = []

            def handler(request):
                requests.append(request)
                raise exception(f"private {TEST_KEY}", request=request)

            with self.subTest(exception=exception):
                with self.assertRaises(GeminiError) as raised:
                    await self.make_request(handler)
                self.assertTrue(raised.exception.retryable)
                self.assertNotIn(TEST_KEY, str(raised.exception))
                self.assertEqual(len(requests), 1)

    async def test_only_allowlisted_provider_machine_codes_are_retained(self):
        for payload, expected in (
            ({"code": "invalid_request", "message": TEST_KEY}, "invalid_request"),
            ({"code": "failed_precondition", "message": TEST_KEY}, "failed_precondition"),
            ({"code": 400, "status": "INVALID_ARGUMENT", "message": TEST_KEY}, "INVALID_ARGUMENT"),
            ({"status": "FAILED_PRECONDITION", "message": TEST_KEY}, "FAILED_PRECONDITION"),
            ({"status": "RESOURCE_EXHAUSTED", "message": TEST_KEY}, "RESOURCE_EXHAUSTED"),
            ({"code": TEST_KEY, "status": "UNAVAILABLE"}, "UNAVAILABLE"),
            ({"code": TEST_KEY, "message": TEST_KEY}, None),
            ({"code": f"invalid_request {TEST_KEY}"}, None),
            ({"code": {"secret": TEST_KEY}, "status": [TEST_KEY]}, None),
            ({"message": "INVALID_ARGUMENT"}, None),
            ({"status": "invalid_argument"}, None),
        ):
            requests = []

            def handler(request):
                requests.append(request)
                return httpx.Response(400, json={"error": payload})

            with self.subTest(expected=expected):
                with self.assertRaises(GeminiError) as raised:
                    await self.make_request(handler)
                error = raised.exception
                self.assertEqual(error.provider_code, expected)
                self.assertEqual(error.status_code, 400)
                self.assertFalse(error.retryable)
                self.assertNotIn(TEST_KEY, str(error))
                self.assertNotIn(TEST_KEY, repr(error.__dict__))
                self.assertEqual(len(requests), 1)
        self.assertIsNone(GeminiError("Safe message", provider_code=TEST_KEY).provider_code)

    async def test_error_diagnostics_are_bounded_and_malformed_bodies_preserve_status(self):
        invalid = [b"<html>failure</html>", b"\xff", b"[]", b"null", b'{"error":[]}', b'{}']
        for content in invalid:
            with self.subTest(content=content):
                with self.assertRaises(GeminiError) as raised:
                    await self.make_request(lambda request: httpx.Response(400, content=content))
                self.assertIsNone(raised.exception.provider_code)
                self.assertEqual(raised.exception.status_code, 400)
                self.assertEqual(raised.exception.code, "provider_error")
        with patch("gemini.client.MAX_ERROR_RESPONSE_BYTES", 32):
            with self.assertRaises(GeminiError) as raised:
                await self.make_request(lambda request: httpx.Response(400, json={
                    "error": {"code": "invalid_request", "message": "x" * 100},
                }))
            self.assertEqual(raised.exception.status_code, 400)
            self.assertIsNone(raised.exception.provider_code)

    async def test_broken_error_stream_keeps_known_status_and_closes(self):
        closed = []

        class ErrorStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'{"error":'
                raise httpx.ReadTimeout(f"private {TEST_KEY}")

            async def aclose(self):
                closed.append(True)

        with self.assertRaises(GeminiError) as raised:
            await self.make_request(lambda request: httpx.Response(400, stream=ErrorStream()))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertFalse(raised.exception.retryable)
        self.assertIsNone(raised.exception.provider_code)
        self.assertNotIn(TEST_KEY, str(raised.exception))
        self.assertEqual(closed, [True])

    async def test_missing_non_png_and_invalid_inputs_prevent_requests(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=interaction())

        for question, system, schema in ((" ", "x", SCHEMA), ("x", " ", SCHEMA), ("x", "x", {})):
            with self.assertRaises(GeminiError):
                await self.make_request(handler, question=question, system=system, schema=schema)
        self.image.write_bytes(b"not a PNG")
        with self.assertRaises(GeminiError):
            await self.make_request(handler)
        self.image.unlink()
        with self.assertRaises(GeminiError):
            await self.make_request(handler)
        self.assertEqual(calls, [])

    async def test_serialized_utf8_request_size_is_checked_including_prompt_and_schema(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=interaction())

        await self.make_request(handler, question="ovet ä")
        exact_size = len(requests[0].content)
        with patch("gemini.client.MAX_REQUEST_BYTES", exact_size):
            await self.make_request(handler, question="ovet ä")
        with patch("gemini.client.MAX_REQUEST_BYTES", exact_size - 1):
            with self.assertRaises(GeminiRequestTooLarge):
                await self.make_request(handler, question="ovet ä")
        self.assertEqual(len(requests), 2)

    async def test_base64_expansion_is_bounded_before_network(self):
        # A PNG byte payload can pass a 20 MiB upload cap yet exceed Google's
        # 20 MB serialized inline request cap after base64 encoding.
        self.image.write_bytes(PNG + b"0" * 15_000_000)
        requests = []
        with self.assertRaises(GeminiRequestTooLarge):
            await self.make_request(lambda request: requests.append(request))
        self.assertEqual(requests, [])
        self.assertLess(self.image.stat().st_size, MAX_REQUEST_BYTES)

    async def test_cancellation_propagates_and_owned_transport_closes(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        closed = []

        class Transport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

            async def aclose(self):
                closed.append(True)

        async with AsyncGeminiClient(self.settings, transport=Transport()) as client:
            task = asyncio.create_task(client.generate_candidates("Find doors", system="Candidates", image=self.image, schema=SCHEMA))
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(cancelled.is_set())
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()

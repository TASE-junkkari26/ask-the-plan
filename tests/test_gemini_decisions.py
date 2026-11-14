"""Offline checks for the Decisions native HTTP and classification boundary."""
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

from gemini import AsyncDecisionsClient, ConfigurationError, DecisionsSettings, GeminiError, GeminiRequestTooLarge
from gemini.decisions import ENDPOINT
from tests.test_gemini import PNG, TEST_KEY

QUESTIONS = {
    "normal_fit": {"type": "choice", "instructions": "Does the normal profile fit?",
                   "criteria": {"supported": "Within demonstrated capabilities.", "uncertain": "Insufficient basis."}},
    "needs_detail": {"type": "noul", "instructions": "Is higher detail needed?",
                     "criteria": {"true_description": "Too small.", "false_description": "Already legible."}},
    "readability": {"type": "score", "instructions": "How readable is this image?",
                    "criteria": ["Clear", "Difficult", "Unreadable"]},
}


def result():
    return {"answers": {
        "normal_fit": {"type": "choice", "choice": "supported",
                       "probabilities": {"supported": 0.95, "uncertain": 0.05}, "confidence": 0.95},
        "needs_detail": {"type": "noul", "noul": 0.03, "confidence": 0.97},
        "readability": {"type": "score", "score": 0.3, "confidence": 0.8,
                        "legend": {"0": "Clear", "1": "Difficult", "2": "Unreadable"},
                        "probabilities": {"0": 0.8, "1": 0.1, "2": 0.1}},
    }, "usage": {"total_input_tokens": 312, "total_output_tokens": 0, "total_tokens": 312}}


class DecisionsSettingsTests(unittest.TestCase):
    def test_secrets_defaults_and_independent_settings(self):
        settings = DecisionsSettings(api_key=TEST_KEY)
        self.assertEqual(settings.model, "gemini-decision-1")
        self.assertEqual(settings.timeout_seconds, 3)
        self.assertNotIn(TEST_KEY, repr(settings))
        self.assertNotIn(TEST_KEY, settings.model_dump_json())
        with self.assertRaises(ValidationError):
            DecisionsSettings(api_key=TEST_KEY, model="arbitrary")

    def test_file_loading_process_precedence_literal_key_and_environment_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("\ufeffGEMINI_API_KEY=literal-${UNSET}-key\nGEMINI_DECISIONS_TIMEOUT_SECONDS=4\nGEMINI_MODEL=irrelevant\n", encoding="utf-8")
            before = dict(os.environ)
            settings = DecisionsSettings.from_env(path, environ={"GEMINI_DECISIONS_TIMEOUT_SECONDS": "2"})
            self.assertEqual(settings.api_key.get_secret_value(), "literal-${UNSET}-key")
            self.assertEqual(settings.timeout_seconds, 2)
            self.assertEqual(dict(os.environ), before)

    def test_invalid_config_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            with self.assertRaises(ConfigurationError):
                DecisionsSettings.from_env(path, environ={"GEMINI_API_KEY": TEST_KEY})
            path.write_text("", encoding="utf-8")
            for values in ({}, {"GEMINI_API_KEY": TEST_KEY, "GEMINI_DECISIONS_TIMEOUT_SECONDS": "nan"},
                           {"GEMINI_API_KEY": TEST_KEY, "GEMINI_DECISIONS_TIMEOUT_SECONDS": "0"},
                           {"GEMINI_API_KEY": TEST_KEY, "GEMINI_DECISIONS_TIMEOUT_SECONDS": "31"},
                           {"GEMINI_API_KEY": "changeme"}):
                with self.assertRaises(ConfigurationError) as raised:
                    DecisionsSettings.from_env(path, environ=values)
                self.assertNotIn(TEST_KEY, str(raised.exception))
            path.write_bytes(b"\xff")
            with self.assertRaises(ConfigurationError):
                DecisionsSettings.from_env(path, environ={})


class DecisionsClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.image = Path(self.directory.name) / "prepared.png"
        self.image.write_bytes(PNG)
        self.settings = DecisionsSettings(api_key=TEST_KEY)

    async def request(self, handler, *, questions=None, question="Find 121.A ovet", context="Selected view only"):
        async with AsyncDecisionsClient(self.settings, transport=httpx.MockTransport(handler)) as client:
            return await client.decide(question, image=self.image,
                                       questions=QUESTIONS if questions is None else questions, context=context)

    async def test_exact_request_and_all_answer_types(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=result())

        reply = await self.request(handler)
        self.assertEqual(len(calls), 1)
        request = calls[0]
        self.assertEqual(str(request.url), ENDPOINT)
        self.assertEqual(request.headers["x-goog-api-key"], TEST_KEY)
        self.assertNotIn("Api-Revision", request.headers)
        self.assertNotIn(TEST_KEY, str(request.url))
        body = json.loads(request.content)
        self.assertEqual(body, {
            "model": "gemini-decision-1",
            "input": [{"type": "text", "text": "Selected view only\nQuestion (source data): Find 121.A ovet"},
                      {"type": "image", "mime_type": "image/png", "data": base64.b64encode(PNG).decode("ascii")}],
            "questions": QUESTIONS,
        })
        self.assertEqual(reply.decisions, result()["answers"])
        self.assertEqual(reply.model, "gemini-decision-1")
        self.assertEqual(reply.usage.prompt_tokens, 312)
        self.assertEqual(reply.usage.completion_tokens, 0)
        self.assertNotIn("supported", repr(reply))
        # Confident no is retained as P(yes)=.03, not converted into a .97 yes.
        self.assertEqual(reply.decisions["needs_detail"]["noul"], 0.03)

    async def test_nullable_usage_does_not_invent_zero(self):
        for usage in (None, {}, {"total_input_tokens": 8}, {"total_output_tokens": 0}):
            payload = result()
            payload["usage"] = usage
            reply = await self.request(lambda request: httpx.Response(200, json=payload))
            if usage is None:
                self.assertIsNone(reply.usage)
            else:
                self.assertEqual(reply.usage.prompt_tokens, usage.get("total_input_tokens"))
                self.assertEqual(reply.usage.completion_tokens, usage.get("total_output_tokens"))

    async def test_rejects_missing_extra_mistyped_or_inconsistent_answers(self):
        payloads = [[], {}, {"answers": []}]
        for key, answer in (
            ("normal_fit", None),
            ("normal_fit", {"type": "noul", "noul": .95, "confidence": .95}),
            ("normal_fit", {"type": "choice", "choice": "arbitrary", "confidence": .95,
                            "probabilities": {"supported": .95, "uncertain": .05}}),
            ("normal_fit", {"type": "choice", "choice": "uncertain", "confidence": .95,
                            "probabilities": {"supported": .95, "uncertain": .05}}),
            ("normal_fit", {"type": "choice", "choice": "supported", "confidence": .95,
                            "probabilities": {"supported": .95}}),
            ("normal_fit", {"type": "choice", "choice": "supported", "confidence": .95,
                            "probabilities": {"supported": .95, "uncertain": .95}}),
            ("needs_detail", {"type": "noul", "noul": .03, "confidence": .03}),
            ("needs_detail", {"type": "noul", "noul": True, "confidence": .97}),
            ("needs_detail", {"type": "noul", "noul": -1, "confidence": .97}),
            ("needs_detail", {"type": "noul", "noul": float("nan"), "confidence": .97}),
            ("needs_detail", {"type": "noul", "noul": float("inf"), "confidence": .97}),
            ("needs_detail", {"type": "noul", "noul": 10 ** 400, "confidence": .97}),
            ("readability", {"type": "score", "score": 5, "confidence": .8,
                             "legend": {"0": "Clear", "1": "Difficult", "2": "Unreadable"},
                             "probabilities": {"0": .8, "1": .1, "2": .1}}),
        ):
            payload = result()
            payload["answers"][key] = answer
            payloads.append(payload)
        payload = result()
        del payload["answers"]["readability"]
        payloads.append(payload)
        payload = result()
        payload["answers"]["extra"] = payload["answers"]["normal_fit"]
        payloads.append(payload)
        for usage in ([], {"total_input_tokens": True}, {"total_input_tokens": -1}, {"total_output_tokens": 1}):
            payload = result()
            payload["usage"] = usage
            payloads.append(payload)
        for payload in payloads:
            with self.subTest(payload=payload):
                # Use raw json.dumps for NaN/Infinity to verify rejection of nonfinite JSON extensions.
                with self.assertRaises(GeminiError) as raised:
                    await self.request(lambda request: httpx.Response(200, content=json.dumps(payload)))
                self.assertEqual(raised.exception.code, "invalid_model_output")

    async def test_invalid_json_duplicate_keys_size_and_unsupported_actions(self):
        for content in (b"<html>bad</html>", b"\xff", b'{"answers":{},"answers":{}}',
                        b'{"tool_calls":[{"name":"danger"}]}'):
            with self.assertRaises(GeminiError) as raised:
                await self.request(lambda request: httpx.Response(200, content=content))
            self.assertEqual(raised.exception.code, "invalid_model_output")
        with patch("gemini.decisions.MAX_RESPONSE_BYTES", 32):
            with self.assertRaises(GeminiError):
                await self.request(lambda request: httpx.Response(200, json=result()))

    async def test_request_validation_happens_before_network(self):
        calls = []
        cases = [{}, {"bad key": QUESTIONS["normal_fit"]}, {"x": {"type": "unknown", "instructions": "q"}},
                 {"x": {"type": "choice", "instructions": "q", "criteria": {"only": "one"}}},
                 {"x": {"type": "choice", "instructions": "q", "criteria": {" leading": "", "other": ""}}},
                 {"x": {"type": "score", "instructions": "q", "criteria": ["", "two"]}},
                 {"x": {"type": "noul", "instructions": "q", "criteria": {"true_description": "yes"}}},
                 {"x": {"type": "noul", "instructions": " "}}]
        for questions in cases:
            with self.assertRaises(GeminiError):
                await self.request(lambda request: calls.append(request), questions=questions)
        with self.assertRaises(GeminiError):
            await self.request(lambda request: calls.append(request), question=" ")
        self.image.write_bytes(b"not png")
        with self.assertRaises(GeminiError):
            await self.request(lambda request: calls.append(request))
        self.image.unlink()
        with self.assertRaises(GeminiError):
            await self.request(lambda request: calls.append(request))
        self.assertEqual(calls, [])

    async def test_serialized_limit_includes_base64_and_criteria(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=result())

        await self.request(handler)
        size = len(calls[0].content)
        with patch("gemini.decisions.MAX_REQUEST_BYTES", size):
            await self.request(handler)
        with patch("gemini.decisions.MAX_REQUEST_BYTES", size - 1):
            with self.assertRaises(GeminiRequestTooLarge):
                await self.request(handler)
        self.assertEqual(len(calls), 2)

    async def test_status_transport_errors_are_safe_no_redirects_or_retries(self):
        for status in (302, 400, 401, 403, 404, 429, 500):
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(status, headers={"location": "https://other.example"},
                                      json={"error": {"code": "INVALID_ARGUMENT", "message": TEST_KEY}})

            with self.assertRaises(GeminiError) as raised:
                await self.request(handler)
            self.assertEqual(raised.exception.status_code, status)
            self.assertEqual(len(calls), 1)
            self.assertNotIn(TEST_KEY, str(raised.exception))
        for kind in (httpx.ReadTimeout, httpx.ConnectError):
            calls = []

            def handler(request):
                calls.append(request)
                raise kind(TEST_KEY)

            with self.assertRaises(GeminiError) as raised:
                await self.request(handler)
            self.assertEqual(len(calls), 1)
            self.assertNotIn(TEST_KEY, str(raised.exception))
            self.assertTrue(raised.exception.retryable)

    async def test_cancellation_and_client_close_propagate(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        closed = []

        class Transport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

            async def aclose(self):
                closed.append(True)

        async with AsyncDecisionsClient(self.settings, transport=Transport()) as client:
            task = asyncio.create_task(client.decide("Find doors", image=self.image, questions=QUESTIONS))
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(cancelled.is_set())
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()

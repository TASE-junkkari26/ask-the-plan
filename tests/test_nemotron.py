"""Credential-free HTTP integration tests for the Verda adapter."""
from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from pydantic import BaseModel, ConfigDict

from nemotron import (
    AsyncNemotronClient, ConfigurationError, NemotronClient,
    NemotronError, NemotronSettings, completion_text,
)
from nemotron.cli import main
from nemotron.config import DEFAULT_BASE_URL, DEFAULT_MODEL, default_env_file

# An artificial test credential, never a real provider key.
TEST_KEY = "test-verda-credential-not-valid"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7V0AAAAASUVORK5CYII=")


def response(text="OK", *, finish_reason="stop", status=200):
    if status != 200:
        return httpx.Response(status, json={"error": {"message": f"private: {TEST_KEY}"}})
    return httpx.Response(200, json={
        "id": "chatcmpl-test", "object": "chat.completion", "created": 1,
        "model": DEFAULT_MODEL,
        "choices": [{"index": 0, "finish_reason": finish_reason,
                     "message": {"role": "assistant", "content": text, "reasoning_content": "Internal reasoning is not CLI output."}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
    })


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    count: int


class SettingsTests(unittest.TestCase):
    def test_default_env_is_checkout_root_independent_of_working_directory(self):
        expected = Path(__file__).resolve().parents[1] / ".env"
        with patch("nemotron.config.Path.cwd", return_value=Path(tempfile.gettempdir())):
            self.assertEqual(default_env_file(), expected)

    def test_file_key_and_shell_override_without_mutating_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(f'VERDA_INFERENCE_KEY="{TEST_KEY}"\nVERDA_MODEL=file-model\n', encoding="utf-8")
            before = dict(os.environ)
            settings = NemotronSettings.from_env(path, environ={"VERDA_MODEL": "shell-model"})
            self.assertEqual(settings.api_key.get_secret_value(), TEST_KEY)
            self.assertEqual(settings.model, "shell-model")
            self.assertEqual(dict(os.environ), before)
            self.assertNotIn(TEST_KEY, repr(settings))
            self.assertNotIn(TEST_KEY, settings.model_dump_json())

    def test_shell_key_wins_and_dollar_sequences_are_literal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("VERDA_INFERENCE_KEY=literal-${UNSET}-value\n", encoding="utf-8")
            settings = NemotronSettings.from_env(path, environ={})
            self.assertEqual(settings.api_key.get_secret_value(), "literal-${UNSET}-value")
            settings = NemotronSettings.from_env(path, environ={"VERDA_INFERENCE_KEY": TEST_KEY})
            self.assertEqual(settings.api_key.get_secret_value(), TEST_KEY)

    def test_missing_key_fails_with_actionable_message(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("VERDA_INFERENCE_KEY=\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "VERDA_INFERENCE_KEY"):
                NemotronSettings.from_env(path, environ={})

    def test_explicit_missing_env_file_does_not_silently_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ConfigurationError, "--env-file"):
                NemotronSettings.from_env(Path(directory) / "absent", environ={"VERDA_INFERENCE_KEY": TEST_KEY})

    def test_invalid_settings_do_not_echo_values(self):
        cases = {
            "VERDA_INFERENCE_KEY": "your-api-key",
            "VERDA_BASE_URL": f"https://{TEST_KEY}@example.com/v1",
            "VERDA_TIMEOUT_SECONDS": "nan",
            "VERDA_MAX_RETRIES": "6",
            "VERDA_MAX_TOKENS": "0",
            "VERDA_TEMPERATURE": "inf",
            "VERDA_ENABLE_THINKING": "perhaps",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.touch()
            for field, value in cases.items():
                with self.subTest(field=field):
                    with self.assertRaises(ConfigurationError) as raised:
                        NemotronSettings.from_env(path, environ={"VERDA_INFERENCE_KEY": TEST_KEY, field: value})
                    self.assertIn(field, str(raised.exception))
                    self.assertNotIn(TEST_KEY, str(raised.exception))

    def test_thinking_can_be_omitted_and_base_url_normalizes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.touch()
            settings = NemotronSettings.from_env(path, environ={
                "VERDA_INFERENCE_KEY": TEST_KEY,
                "VERDA_ENABLE_THINKING": "auto",
                "VERDA_BASE_URL": DEFAULT_BASE_URL + "/",
            })
            self.assertIsNone(settings.enable_thinking)
            self.assertEqual(settings.base_url, DEFAULT_BASE_URL)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.requests = []

    def client(self, handler=None, **settings):
        def transport(request):
            self.requests.append(request)
            return handler(request) if handler else response()
        return NemotronClient(
            NemotronSettings(api_key=TEST_KEY, max_retries=0, **settings),
            http_client=httpx.Client(transport=httpx.MockTransport(transport)),
        )

    def test_text_uses_supplied_endpoint_bearer_auth_and_token_field(self):
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://unused.invalid/v1"}):
            with self.client(timeout_seconds=45) as client:
                result = client.ask("Read door 121.A", system="Keep original identifiers.")
        request = self.requests[0]
        self.assertEqual(str(request.url), DEFAULT_BASE_URL + "/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer " + TEST_KEY)
        body = json.loads(request.content)
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertEqual(body["messages"][1]["content"], "Read door 121.A")
        self.assertEqual(body["max_tokens"], 2048)
        self.assertNotIn("max_completion_tokens", body)
        self.assertEqual(body["chat_template_kwargs"], {"enable_thinking": False})
        self.assertNotIn("extra_body", body)
        self.assertEqual(request.extensions["timeout"]["read"], 45)
        self.assertEqual(completion_text(result), "OK")
        self.assertEqual(result.usage.total_tokens, 12)

    def test_image_is_embedded_with_actual_media_type(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "different-extension.jpg"
            path.write_bytes(PNG)
            with self.client() as client:
                client.ask("Find door symbols", images=[path])
        content = json.loads(self.requests[0].content)["messages"][0]["content"]
        self.assertEqual(content[0], {"type": "text", "text": "Find door symbols"})
        url = content[1]["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(url.split(",", 1)[1]), PNG)
        self.assertNotIn(str(path), str(content))

    def test_unsupported_missing_and_large_images_fail_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drawing.pdf"
            path.write_bytes(b"%PDF-1.4")
            with self.client() as client:
                for item in (path, Path(directory) / "missing.png"):
                    with self.assertRaises(NemotronError):
                        client.ask("Describe", images=[item])
                with patch("nemotron.client.MAX_IMAGE_BYTES", 4):
                    with self.assertRaisesRegex(NemotronError, "client limit"):
                        client.ask("Describe", images=[path])
        self.assertEqual(self.requests, [])

    def test_validated_json_includes_schema_and_uses_json_mode(self):
        with self.client(lambda _: response('{"label":"door","count":2}')) as client:
            result = client.ask_json("Describe the symbols", Observation, system="Preserve source IDs.")
        self.assertEqual(result.count, 2)
        body = json.loads(self.requests[0].content)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIn('"count"', body["messages"][0]["content"])
        self.assertIn("Preserve source IDs.", body["messages"][0]["content"])

    def test_invalid_or_truncated_json_is_never_accepted(self):
        for text, finish in [('{"label":"door"}', "stop"), ('not JSON', "stop"), ('{"label":"door","count":2}', "length")]:
            with self.subTest(text=text, finish=finish):
                with self.client(lambda _, text=text, finish=finish: response(text, finish_reason=finish)) as client:
                    with self.assertRaises(NemotronError):
                        client.ask_json("Describe", Observation)

    def test_raw_chat_preserves_tool_calls_without_executing_them(self):
        def handler(_):
            result = response(None, finish_reason="tool_calls")
            data = json.loads(result.content)
            data["choices"][0]["message"]["tool_calls"] = [{
                "id": "call-1", "type": "function", "function": {"name": "count_doors", "arguments": "{}"},
            }]
            return httpx.Response(200, json=data)
        tools = [{"type": "function", "function": {"name": "count_doors", "parameters": {"type": "object"}}}]
        with self.client(handler, enable_thinking=None) as client:
            result = client.chat([{"role": "user", "content": "Count doors"}], tools=tools, tool_choice="auto")
        self.assertEqual(result.choices[0].message.tool_calls[0].function.name, "count_doors")
        body = json.loads(self.requests[0].content)
        self.assertEqual(body["tools"], tools)
        self.assertNotIn("chat_template_kwargs", body)
        with self.assertRaises(NemotronError):
            completion_text(result)

    def test_api_errors_are_actionable_and_redact_provider_bodies(self):
        for code in (400, 401, 403, 404, 413, 429, 500):
            with self.subTest(code=code):
                with self.client(lambda _, code=code: response(status=code)) as client:
                    with self.assertRaises(NemotronError) as raised:
                        client.ask("Check")
                self.assertEqual(raised.exception.status_code, code)
                self.assertNotIn(TEST_KEY, str(raised.exception))
                self.assertNotIn("private", str(raised.exception))
                self.assertIn(str(code), str(raised.exception))

    def test_timeout_is_sanitized(self):
        def handler(request):
            raise httpx.ReadTimeout(TEST_KEY, request=request)
        with self.client(handler) as client:
            with self.assertRaisesRegex(NemotronError, "timed out") as raised:
                client.ask("Check")
        self.assertTrue(raised.exception.retryable)
        self.assertNotIn(TEST_KEY, str(raised.exception))

    def test_retryable_error_retries_but_auth_error_does_not(self):
        requests = []
        def transient(request):
            requests.append(request)
            return response(status=500) if len(requests) == 1 else response()
        settings = NemotronSettings(api_key=TEST_KEY, max_retries=1)
        with NemotronClient(settings, http_client=httpx.Client(transport=httpx.MockTransport(transient))) as client:
            self.assertEqual(completion_text(client.ask("Check")), "OK")
        self.assertEqual(len(requests), 2)
        requests.clear()
        def denied(request):
            requests.append(request)
            return response(status=401)
        with NemotronClient(settings, http_client=httpx.Client(transport=httpx.MockTransport(denied))) as client:
            with self.assertRaises(NemotronError):
                client.ask("Check")
        self.assertEqual(len(requests), 1)

    def test_invalid_request_options_fail_before_network(self):
        with self.client() as client:
            for options in ({"max_tokens": 0}, {"temperature": float("nan")}):
                with self.assertRaises(NemotronError):
                    client.ask("Check", **options)
            with self.assertRaises(NemotronError):
                client.ask(" ")
        self.assertEqual(self.requests, [])

    def test_empty_answer_is_not_confused_with_reasoning(self):
        with self.client(lambda _: response(None)) as client:
            with self.assertRaisesRegex(NemotronError, "no answer text"):
                completion_text(client.ask("Check"))

    def test_non_json_or_malformed_provider_responses_fail_cleanly(self):
        replies = [
            httpx.Response(200, text="<html>Proxy error</html>", headers={"content-type": "text/html"}),
            httpx.Response(200, text="{", headers={"content-type": "application/json"}),
            httpx.Response(200, json={"choices": []}),
            httpx.Response(200, json={"choices": [None]}),
        ]
        for reply in replies:
            with self.subTest(reply=reply.content):
                with self.client(lambda _, reply=reply: reply) as client:
                    with self.assertRaises(NemotronError):
                        completion_text(client.ask("Check"))

    def test_connection_errors_redact_transport_details(self):
        def handler(request):
            raise httpx.ConnectError(TEST_KEY, request=request)
        with self.client(handler) as client:
            with self.assertRaisesRegex(NemotronError, "Could not connect") as raised:
                client.ask("Check")
        self.assertNotIn(TEST_KEY, str(raised.exception))


class AsyncClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_image_json_request_uses_same_protocol(self):
        requests = []
        def handler(request):
            requests.append(request)
            return response('{"label":"door","count":1}')
        settings = NemotronSettings(api_key=TEST_KEY, max_retries=0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drawing.png"
            path.write_bytes(PNG)
            async with AsyncNemotronClient(settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
                result = await client.ask_json("Describe", Observation, images=[path])
        self.assertEqual(result.count, 1)
        body = json.loads(requests[0].content)
        self.assertTrue(body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png"))
        self.assertEqual(body["response_format"]["type"], "json_object")

    async def test_async_auth_error_is_sanitized(self):
        settings = NemotronSettings(api_key=TEST_KEY, max_retries=0)
        async with AsyncNemotronClient(settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response(status=401)))) as client:
            with self.assertRaises(NemotronError) as raised:
                await client.ask("Check")
        self.assertEqual(raised.exception.status_code, 401)
        self.assertNotIn(TEST_KEY, str(raised.exception))


class CliTests(unittest.TestCase):
    def run_cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(args)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_missing_key_returns_setup_message_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("VERDA_INFERENCE_KEY=\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch("nemotron.cli.NemotronClient") as client:
                code, stdout, stderr = self.run_cli(["--env-file", str(path), "check"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("VERDA_INFERENCE_KEY", stderr)
        client.assert_not_called()

    def test_check_reports_answer_and_usage_without_reasoning_or_key(self):
        settings = NemotronSettings(api_key=TEST_KEY)
        sdk = NemotronClient(settings, http_client=httpx.Client(transport=httpx.MockTransport(lambda _: response())))
        with patch("nemotron.cli.NemotronSettings.from_env", return_value=settings), patch("nemotron.cli.NemotronClient", return_value=sdk):
            code, stdout, stderr = self.run_cli(["check"])
        result = json.loads(stdout)
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(result["status"], "connected")
        self.assertEqual(result["usage"]["total_tokens"], 12)
        self.assertNotIn("Internal reasoning", stdout)
        self.assertNotIn(TEST_KEY, stdout)


if __name__ == "__main__":
    unittest.main()

"""Synthetic ASGI lifecycle checks; no provider network calls or source assets."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
import threading
from time import perf_counter
import unittest
from unittest.mock import patch

import httpx

from image_api.app import create_app
from image_api.config import ApiSettings
from image_api.images import prepare_image
from nemotron import AsyncNemotronClient, NemotronSettings
from tests.test_image_api import completion, image_bytes, proposals


TEST_KEY = "synthetic-lifecycle-credential"


class ImageApiLifecycleTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def api(self, handler=None, *, settings=None):
        requests, paths = [], []

        async def transport(request):
            requests.append(request)
            return await handler(request) if handler is not None else completion()

        provider_http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        sdk = AsyncNemotronClient(
            NemotronSettings(api_key=TEST_KEY, max_retries=0), http_client=provider_http,
        )
        ask = sdk.ask

        async def record_paths(*args, **kwargs):
            paths.extend(Path(path) for path in kwargs.get("images", []))
            return await ask(*args, **kwargs)

        sdk.ask = record_paths
        app = create_app(settings=settings or ApiSettings(), client_factory=lambda: sdk)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
                yield client, app, requests, paths
        self.assertTrue(provider_http.is_closed)

    async def post(self, client, *, image=None, question="Windows?", headers=None):
        return await client.post(
            "/api/v1/candidates", data={"question": question},
            files={"image": ("plan.png", image if image is not None else image_bytes(), "image/png")},
            headers=headers,
        )

    async def wait_until(self, predicate, *, timeout=3):
        async def poll():
            while not predicate():
                await asyncio.sleep(0.01)
        await asyncio.wait_for(poll(), timeout)

    async def test_concurrent_requests_keep_their_own_images_questions_and_ids(self):
        entered = 0
        both_entered = asyncio.Event()

        async def handle(request):
            nonlocal entered
            body = json.loads(request.content)
            question = next(part["text"] for part in body["messages"][-1]["content"] if part["type"] == "text")
            entered += 1
            if entered == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), 3)
            payload = proposals()
            payload["candidates"][0]["source_label"] = question
            return completion(payload)

        images = [image_bytes((100, 50)), image_bytes((40, 80))]
        questions = ["Windows on first view?", "Windows on second view?"]
        async with self.api(handle) as (client, app, requests, paths):
            responses = await asyncio.gather(*[
                self.post(client, image=image, question=question)
                for image, question in zip(images, questions)
            ])
            self.assertEqual(app.state.in_flight, 0)
        bodies = []
        for response, image, question, dimensions in zip(responses, images, questions, [(100, 50), (40, 80)]):
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            bodies.append(body)
            self.assertEqual(body["image"]["sha256"], hashlib.sha256(image).hexdigest())
            self.assertEqual((body["image"]["width"], body["image"]["height"]), dimensions)
            self.assertEqual(body["candidates"][0]["source_label"], question)
            self.assertEqual(body["candidates"][0]["geometry"]["minimum"], [dimensions[0] * 0.1, dimensions[1] * 0.2])
        self.assertNotEqual(bodies[0]["request_id"], bodies[1]["request_id"])
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(set(paths)), 2)
        self.assertTrue(all(not path.exists() for path in paths))

    async def test_busy_request_does_not_call_provider_and_slot_recovers(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def handle(_):
            entered.set()
            await release.wait()
            return completion()

        async with self.api(handle, settings=ApiSettings(max_concurrent=1)) as (client, app, requests, paths):
            first = asyncio.create_task(self.post(client))
            try:
                await asyncio.wait_for(entered.wait(), 3)
                busy = await self.post(client)
                self.assertEqual(busy.status_code, 429, busy.text)
                self.assertEqual(busy.json()["code"], "busy")
                self.assertTrue(busy.json()["retryable"])
                self.assertEqual(len(requests), 1)
                release.set()
                self.assertEqual((await first).status_code, 200)
                self.assertEqual(app.state.in_flight, 0)
                self.assertEqual((await self.post(client)).status_code, 200)
            finally:
                release.set()
                await asyncio.gather(first, return_exceptions=True)
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(not path.exists() for path in paths))

    async def test_disconnect_cancels_inference_before_removing_temporary_image(self):
        entered, cancelled, disconnect = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def handle(_):
            entered.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        async with self.api(handle) as (_, app, requests, paths):
            request = httpx.Request(
                "POST", "http://test/api/v1/candidates", data={"question": "Windows?"},
                files={"image": ("plan.png", image_bytes(), "image/png")},
            )
            body = request.read()
            delivered = False
            messages = []

            async def receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await disconnect.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                messages.append(message)

            scope = {
                "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1", "scheme": "http", "method": "POST",
                "path": "/api/v1/candidates", "raw_path": b"/api/v1/candidates",
                "root_path": "", "query_string": b"",
                "headers": [(name.lower(), value) for name, value in request.headers.raw],
                "server": ("test", 80), "client": ("127.0.0.1", 1234),
            }
            task = asyncio.create_task(app(scope, receive, send))
            try:
                await self.wait_until(lambda: entered.is_set() or task.done())
                if not entered.is_set():
                    await task
                    self.fail(f"Inference did not start: {messages}")
                self.assertTrue(paths[0].exists())
                disconnect.set()
                await asyncio.wait_for(task, 3)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self.assertTrue(cancelled.is_set())
            self.assertEqual(app.state.in_flight, 0)
        self.assertEqual(len(requests), 1)
        self.assertTrue(all(not path.exists() for path in paths))
        self.assertEqual(next(message["status"] for message in messages if message["type"] == "http.response.start"), 499)

    async def test_timeout_returns_promptly_and_delays_cleanup_until_worker_finishes(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        directories = []

        def slow_prepare(content, settings, directory):
            directories.append(directory)
            started.set()
            if not release.wait(3):
                raise RuntimeError("Test failed to release the image worker.")
            try:
                self.assertTrue(directory.exists(), "Cleanup must wait for the worker.")
                return prepare_image(content, settings, directory)
            finally:
                finished.set()

        async with self.api(settings=ApiSettings(deadline_seconds=0.1)) as (client, app, requests, _):
            with patch("image_api.preprocessing.prepare_image", side_effect=slow_prepare):
                try:
                    before = perf_counter()
                    response = await self.post(client)
                    elapsed = perf_counter() - before
                    self.assertEqual(response.status_code, 504, response.text)
                    self.assertLess(elapsed, 0.8)
                    self.assertTrue(started.is_set())
                    self.assertFalse(finished.is_set())
                    self.assertTrue(directories[0].exists())
                    release.set()
                    await self.wait_until(lambda: finished.is_set() and not directories[0].exists())
                finally:
                    release.set()
                    await self.wait_until(finished.is_set)
        self.assertEqual(requests, [])

    async def test_unexpected_failure_has_safe_envelope_cors_and_request_id(self):
        async with self.api() as (client, app, requests, paths):
            async def crash(image, question, request_id):
                paths.append(image.path)
                raise RuntimeError(f"private {TEST_KEY} /tmp/private-image {question}")

            with patch.object(app.state.service, "extract", side_effect=crash):
                response = await self.post(client, question="PRIVATE_QUESTION", headers={"Origin": "http://localhost:5173"})
            self.assertEqual(response.status_code, 500, response.text)
            body = response.json()
            self.assertEqual(body["code"], "internal_error")
            self.assertEqual(body["request_id"], response.headers["x-request-id"])
            self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
            self.assertEqual(response.headers["cache-control"], "no-store")
            for detail in (TEST_KEY, "private", "/tmp/", "PRIVATE_QUESTION"):
                self.assertNotIn(detail, response.text)
            self.assertEqual(app.state.in_flight, 0)
        self.assertEqual(requests, [])
        self.assertTrue(paths)
        self.assertTrue(all(not path.exists() for path in paths))


if __name__ == "__main__":
    unittest.main()

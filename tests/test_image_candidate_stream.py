"""Synthetic stream/lifecycle checks; no external providers or model accuracy claim."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx

from gemini import AsyncGeminiClient, GeminiSettings
from gemini.decisions import AsyncDecisionsClient
from gemini.decisions_config import DecisionsSettings
from image_api.config import ApiSettings
# Importing the module creates its default app. Keep that discovery credential-free.
with patch('image_api.config.default_env_file', return_value=Path('/nonexistent-synthetic-stream-env')):
    from image_api.app import create_app
from image_api.routing import QUESTIONS
from nemotron import ConfigurationError
from tests.test_gemini_image_api import interaction
from tests.test_image_api import image_bytes

KEY = 'synthetic-stream-credential'
CHOICES = dict(normal_fit='supported', document_kind='floor_plan', task_kind='instance_discovery',
               count_grain='assembly', target_kind='windows', scope='selected_view')


def decision_answers(fit='supported'):
    choices = {**CHOICES, 'normal_fit': fit}
    return {key: {'type': 'choice', 'choice': choices[key], 'confidence': 0.99,
                  'probabilities': {name: 0.99 if name == choices[key] else 0.01/(len(q['criteria'])-1)
                                    for name in q['criteria']}}
            for key, q in QUESTIONS.items()}


class Wire:
    """Observe ASGI body sends while the response is still in flight."""
    def __init__(self, app, *, question='Find windows', headers=None, content=None, asgi_spec='2.0', send_failure=False):
        request = httpx.Request('POST', 'http://test/api/v1/candidates',
                                data={'question': question},
                                files={'image': ('drawing.png', content if content is not None else image_bytes(), 'image/png')},
                                headers=headers or {'Accept': 'application/x-ndjson'})
        body = request.read()
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()
        self.incoming.put_nowait({'type': 'http.request', 'body': body, 'more_body': False})
        scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': asgi_spec},
                 'http_version': '1.1', 'method': 'POST', 'scheme': 'http',
                 'path': '/api/v1/candidates', 'raw_path': b'/api/v1/candidates', 'query_string': b'',
                 'headers': [(name.lower(), value) for name, value in request.headers.raw], 'client': ('127.0.0.1', 1234), 'server': ('test', 80)}
        async def send(message):
            self.outgoing.put_nowait(message)
            if send_failure and message['type'] == 'http.response.body' and b'\"handoff\"' in message.get('body', b''):
                raise OSError('Synthetic disconnected transport')
        self.task = asyncio.create_task(app(scope, self.incoming.get, send))

    async def message(self):
        return await asyncio.wait_for(self.outgoing.get(), 3)

    async def start(self):
        message = await self.message()
        assert message['type'] == 'http.response.start', message
        return message

    async def frame(self):
        message = await self.message()
        assert message['type'] == 'http.response.body', message
        assert message.get('body'), message
        return json.loads(message['body'])

    async def finish(self):
        await asyncio.wait_for(self.task, 3)

    async def disconnect(self):
        self.incoming.put_nowait({'type': 'http.disconnect'})
        await self.finish()

    async def close(self):
        if not self.task.done():
            self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)


class ImageCandidateStreamTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def api(self, *, mode='auto', fit='supported', strong=True, handler=None, **settings):
        self.calls, self.paths, self.clients = [], [], []
        async def decide(request):
            self.calls.append(('decision', json.loads(request.content)))
            return httpx.Response(200, json={'answers': decision_answers(fit)})
        async def analyze(request):
            body = json.loads(request.content)
            self.calls.append(('analysis', body))
            if handler:
                return await handler(request)
            value = interaction().json()
            value['model'] = body['model']
            return httpx.Response(200, json=value)
        def client(profile):
            sdk = AsyncGeminiClient(GeminiSettings(api_key=KEY).profile(profile), transport=httpx.MockTransport(analyze))
            generate = sdk.generate_candidates
            async def record(*args, **kwargs):
                self.paths.append(Path(kwargs['image']))
                return await generate(*args, **kwargs)
            sdk.generate_candidates = record
            self.clients.append(sdk)
            return sdk
        def unavailable():
            raise ConfigurationError('Synthetic unavailable profile')
        decider = AsyncDecisionsClient(DecisionsSettings(api_key=KEY), transport=httpx.MockTransport(decide))
        app = create_app(ApiSettings(provider='gemini', routing_mode=mode, preprocess_mode='off', **settings),
                         client_factory=unavailable, gemini_client_factory=lambda: client('normal'),
                         strong_client_factory=(lambda: client('strong')) if strong else unavailable,
                         decisions_client_factory=lambda: decider)
        try:
            async with app.router.lifespan_context(app):
                yield app
        finally:
            await decider.close()  # off mode does not construct/own the injected decider.
        self.assertTrue(all(c._http.is_closed for c in self.clients))
        self.assertTrue(all(not p.exists() for p in self.paths))

    async def test_handoff_is_sent_before_blocked_analyzer_completes(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def blocked(request):
            entered.set()
            await release.wait()
            value = interaction().json()
            value['model'] = json.loads(request.content)['model']
            return httpx.Response(200, json=value)
        async with self.api(handler=blocked) as app:
            wire = Wire(app)
            try:
                start = await wire.start()
                progress = await wire.frame()
                await asyncio.wait_for(entered.wait(), 3)
                self.assertFalse(release.is_set())
                self.assertFalse(wire.task.done())
                self.assertEqual(app.state.in_flight, 1)
                self.assertEqual(progress['type'], 'handoff')
                value = progress['progress']
                self.assertEqual(value['requested_model'], 'gemini-4-hydrogen')
                self.assertEqual(value['request_id'], dict(start['headers'])[b'x-request-id'].decode())
                self.assertEqual(value['image']['sha256'], hashlib.sha256(image_bytes()).hexdigest())
                self.assertEqual(value['question_sha256'], hashlib.sha256(b'Find windows').hexdigest())
                release.set()
                terminal = await wire.frame()
                self.assertEqual(terminal['type'], 'result')
                self.assertEqual(terminal['result']['request_id'], value['request_id'])
                await wire.finish()
                self.assertEqual(app.state.in_flight, 0)
                self.assertEqual([kind for kind, _ in self.calls], ['decision', 'analysis'])
            finally:
                release.set()
                await wire.close()

    async def test_handoff_reports_actual_strong_shadow_and_off_models(self):
        for mode, fit, expected in [('auto', 'needs_strong', 'gemini-4-carbon'),
                                    ('shadow', 'needs_strong', 'gemini-4-hydrogen'),
                                    ('off', 'supported', 'gemini-4-hydrogen')]:
            with self.subTest(mode=mode):
                async with self.api(mode=mode, fit=fit) as app:
                    wire = Wire(app)
                    try:
                        await wire.start()
                        handoff = await wire.frame()
                        terminal = await wire.frame()
                        await wire.finish()
                        self.assertEqual(handoff['progress']['requested_model'], expected)
                        self.assertEqual(terminal['result']['provenance']['requested_model'], expected)
                        self.assertEqual(len([1 for k, _ in self.calls if k == 'analysis']), 1)
                        self.assertEqual(app.state.in_flight, 0)
                    finally:
                        await wire.close()

    async def test_cached_route_still_announces_analyzer_without_another_decision(self):
        async with self.api() as app:
            for number in range(2):
                wire = Wire(app)
                try:
                    await wire.start()
                    self.assertEqual((await wire.frame())['type'], 'handoff')
                    terminal = await wire.frame()
                    await wire.finish()
                    if number:
                        self.assertEqual(terminal['result']['decision_trace']['nodes'][0]['state'], 'reused')
                finally:
                    await wire.close()
            self.assertEqual([kind for kind, _ in self.calls], ['decision', 'analysis', 'analysis'])

    async def test_unavailable_strong_has_terminal_error_without_false_handoff(self):
        async with self.api(fit='needs_strong', strong=False) as app:
            wire = Wire(app)
            try:
                await wire.start()
                terminal = await wire.frame()
                await wire.finish()
                self.assertEqual(terminal['type'], 'error')
                self.assertEqual(terminal['error']['code'], 'strong_unavailable')
                self.assertEqual(terminal['error']['decision_trace']['selected_profile'], 'strong')
                self.assertEqual([kind for kind, _ in self.calls], ['decision'])
                self.assertEqual(app.state.in_flight, 0)
            finally:
                await wire.close()

    async def test_provider_failure_after_handoff_retains_sanitized_trace(self):
        async def denied(_):
            return httpx.Response(403, json={'error': {'message': KEY}})
        async with self.api(handler=denied) as app:
            wire = Wire(app)
            try:
                await wire.start()
                handoff = await wire.frame()
                terminal = await wire.frame()
                await wire.finish()
                self.assertEqual(handoff['type'], 'handoff')
                self.assertEqual(terminal['type'], 'error')
                self.assertEqual(terminal['error']['code'], 'provider_configuration')
                self.assertEqual(terminal['error']['decision_trace']['calls'][-1]['outcome'], 'failed')
                self.assertNotIn(KEY, json.dumps(terminal))
                self.assertEqual(len([1 for k, _ in self.calls if k == 'analysis']), 1)
            finally:
                await wire.close()

    async def test_disconnect_cancels_analyzer_and_releases_admission_and_files(self):
        cancelled = asyncio.Event()
        async def stalled(_):
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
        async with self.api(handler=stalled, max_concurrent=1) as app:
            wire = Wire(app)
            try:
                await wire.start()
                self.assertEqual((await wire.frame())['type'], 'handoff')
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as http:
                    busy = await http.post('/api/v1/candidates', data={'question': 'Find windows'},
                                           files={'image': ('image.png', image_bytes(), 'image/png')})
                self.assertEqual(busy.status_code, 429)
                await wire.disconnect()
                await asyncio.wait_for(cancelled.wait(), 3)
                self.assertEqual(app.state.in_flight, 0)
                self.assertTrue(self.paths)
                self.assertTrue(all(not p.exists() for p in self.paths))
            finally:
                await wire.close()

    async def assert_receive_disconnect_cleanup(self, asgi_spec):
        entered, cleanup_done = asyncio.Event(), asyncio.Event()
        observed = {}
        async def stalled(_):
            entered.set()
            try:
                await asyncio.Future()
            finally:
                observed['file_before_cleanup'] = self.paths[0].exists()
                observed['slot_before_cleanup'] = app.state.in_flight
                await asyncio.sleep(0.01)
                observed['file_after_cleanup'] = self.paths[0].exists()
                cleanup_done.set()
        async with self.api(handler=stalled, max_concurrent=1) as app:
            wire = Wire(app, asgi_spec=asgi_spec)
            try:
                await wire.start()
                self.assertEqual((await wire.frame())['type'], 'handoff')
                await asyncio.wait_for(entered.wait(), 3)
                await wire.disconnect()
                self.assertTrue(cleanup_done.is_set())
                self.assertEqual(observed, {'file_before_cleanup': True, 'slot_before_cleanup': 1,
                                            'file_after_cleanup': True})
                self.assertEqual(app.state.in_flight, 0)
                self.assertTrue(all(not p.exists() for p in self.paths))
                self.assertEqual(len([1 for kind, _ in self.calls if kind == 'analysis']), 1)
            finally:
                await wire.close()

    async def test_asgi23_disconnect_awaits_async_provider_cleanup_before_releasing_files(self):
        await self.assert_receive_disconnect_cleanup('2.3')

    async def test_asgi24_receive_disconnect_cancels_blocked_analyzer_and_preserves_cleanup(self):
        # No send failure is simulated: ASGI2.4 must watch receive while the
        # provider is blocked, rather than waiting until another send occurs.
        await self.assert_receive_disconnect_cleanup('2.4')

    async def test_asgi24_send_failure_closes_suspended_iterator_before_releasing_slot(self):
        from starlette.requests import ClientDisconnect
        cancelled = asyncio.Event()
        async def stalled(_):
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
        async with self.api(handler=stalled, max_concurrent=1) as app:
            wire = Wire(app, asgi_spec='2.4', send_failure=True)
            try:
                await wire.start()
                self.assertEqual((await wire.frame())['type'], 'handoff')
                with self.assertRaises(ClientDisconnect):
                    await wire.finish()
                await asyncio.wait_for(cancelled.wait(), 3)
                self.assertEqual(app.state.in_flight, 0)
                self.assertTrue(self.paths)
                self.assertTrue(all(not p.exists() for p in self.paths))
                self.assertEqual(len([1 for kind, _ in self.calls if kind == 'analysis']), 1)
            finally:
                await wire.close()

    async def test_stream_deadline_cancels_provider_and_sends_error(self):
        cancelled = asyncio.Event()
        async def stalled(_):
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
        # The routed service reserves five seconds; this leaves a short live call.
        async with self.api(handler=stalled, deadline_seconds=5.15) as app:
            wire = Wire(app)
            try:
                await wire.start()
                self.assertEqual((await wire.frame())['type'], 'handoff')
                error = await wire.frame()
                await wire.finish()
                self.assertEqual(error['type'], 'error')
                self.assertEqual(error['error']['code'], 'deadline_exceeded')
                self.assertTrue(cancelled.is_set())
                self.assertEqual(app.state.in_flight, 0)
                self.assertEqual(error['error']['decision_trace']['calls'][-1]['outcome'], 'cancelled')
            finally:
                await wire.close()

    async def test_invalid_upload_keeps_http_json_error_and_default_json_is_unchanged(self):
        async with self.api() as app:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as http:
                invalid = await http.post('/api/v1/candidates', headers={'Accept': 'application/x-ndjson'}, json={})
                self.assertEqual(invalid.status_code, 415)
                self.assertEqual(invalid.headers['content-type'], 'application/json')
                self.assertEqual(app.state.in_flight, 0)
                corrupt = await http.post('/api/v1/candidates', headers={'Accept': 'application/x-ndjson'},
                                          data={'question': 'Find windows'},
                                          files={'image': ('image.png', image_bytes()[:35], 'image/png')})
                self.assertEqual(corrupt.status_code, 422, corrupt.text)
                self.assertEqual(corrupt.headers['content-type'], 'application/json')
                self.assertEqual(app.state.in_flight, 0)
                self.assertEqual(self.calls, [])
                result = await http.post('/api/v1/candidates', data={'question': 'Find windows'},
                                         files={'image': ('image.png', image_bytes(), 'image/png')})
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.headers['content-type'], 'application/json')
                self.assertEqual(result.json()['status'], 'ok')
                self.assertEqual(app.state.in_flight, 0)

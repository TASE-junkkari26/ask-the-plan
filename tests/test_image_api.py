"""Credential-free HTTP-to-model integration tests for image candidate extraction.

Images and completions are synthetic; these checks establish API behavior, not
blueprint identification accuracy. The real provider is never contacted.
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
import random
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

from image_api.app import create_app
from image_api.config import ApiSettings
from nemotron import AsyncNemotronClient, ConfigurationError, NemotronSettings


TEST_KEY = 'synthetic-image-api-test-credential'
TEST_MODEL = 'synthetic-vision-model'


def image_bytes(size=(80, 40), *, format='PNG', **options):
    output = io.BytesIO()
    with Image.new('RGB', size, 'white') as image:
        image.save(output, format=format, **options)
    return output.getvalue()


def proposals():
    return {
        'status': 'ok',
        'candidates': [{
            'category': 'window',
            'source_label': '121.A',
            'bbox_1000': [100, 200, 900, 800],
            'uncertain': False,
            'uncertainty_reason': None,
            'visual_cue': 'Parallel lines inside an exterior wall.',
        }],
        'limitations': [],
    }


def completion(payload=None, *, text=None, finish_reason='stop', status=200):
    if status != 200:
        return httpx.Response(status, json={'error': {'message': f'private {TEST_KEY}'}})
    content = text if text is not None else json.dumps(payload if payload is not None else proposals())
    return httpx.Response(200, json={
        'id': 'chatcmpl-synthetic',
        'object': 'chat.completion',
        'created': 1,
        'model': TEST_MODEL,
        'choices': [{
            'index': 0,
            'finish_reason': finish_reason,
            'message': {'role': 'assistant', 'content': content},
        }],
        'usage': {'prompt_tokens': 17, 'completion_tokens': 31, 'total_tokens': 48},
    })


class ImageApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.requests = []
        self.image = image_bytes()

    @asynccontextmanager
    async def api(self, handler=None, *, settings=None, paths=None):
        async def transport(request):
            self.requests.append(request)
            result = handler(request) if handler is not None else completion()
            return await result if hasattr(result, '__await__') else result
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        sdk = AsyncNemotronClient(
            NemotronSettings(api_key=TEST_KEY, model=TEST_MODEL, max_retries=0),
            http_client=http_client,
        )
        if paths is not None:
            original_ask = sdk.ask

            async def tracked_ask(*args, **kwargs):
                paths.extend((Path(path) for path in kwargs.get('images', [])))
                return await original_ask(*args, **kwargs)
            sdk.ask = tracked_ask
        app = create_app(settings=settings or ApiSettings(), client_factory=lambda: sdk)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
                yield client
        self.assertTrue(http_client.is_closed)

    async def post(self, client, *, image=None, question='How many windows are visible?'):
        return await client.post('/api/v1/candidates', data={'question': question}, files={
            'image': ('floorplan.png', self.image if image is None else image, 'image/png'),
        })

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        body = response.json()
        self.assertEqual(body['schema_version'], '0.1.0')
        self.assertTrue(body['request_id'])
        self.assertTrue(body['code'])
        self.assertTrue(body['message'])
        self.assertIsInstance(body['retryable'], bool)
        self.assertNotIn(TEST_KEY, response.text)
        self.assertNotIn('private', response.text)
        self.assertNotIn('/tmp/', response.text)
        self.assertNotIn('candidates', body)
        return body

    async def test_request_reaches_model_once_and_returns_image_bound_pixel_boxes(self):
        paths = []
        question = 'Missä ikkunat ovat? Säilytä 121.A.'
        async with self.api(paths=paths) as client:
            response = await self.post(client, question=question)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['scope'], 'submitted_image')
        self.assertEqual(body['inventory_completeness'], 'unverified')
        self.assertEqual(body['image']['sha256'], hashlib.sha256(self.image).hexdigest())
        self.assertEqual((body['image']['width'], body['image']['height']), (80, 40))
        self.assertEqual(body['image']['coordinate_system'], 'display_pixels_top_left')
        candidate = body['candidates'][0]
        self.assertEqual(candidate['geometry'], {'kind': 'box', 'minimum': [8, 8], 'maximum': [72, 32]})
        self.assertEqual(candidate['source_label'], '121.A')
        self.assertTrue(candidate['id'])
        self.assertEqual(body['provenance']['returned_model'], TEST_MODEL)
        self.assertEqual(body['metrics']['prompt_tokens'], 17)
        self.assertEqual(body['metrics']['completion_tokens'], 31)
        self.assertNotIn('count', body)
        self.assertNotIn('answer', body)
        self.assertEqual(len(self.requests), 1)
        request = json.loads(self.requests[0].content)
        self.assertEqual(request['response_format'], {'type': 'json_object'})
        text = '\n'.join(
            part['text'] for message in request['messages']
            if isinstance(message['content'], list)
            for part in message['content'] if part['type'] == 'text'
        )
        self.assertIn(question, text)
        image_parts = [
            part for message in request['messages'] if isinstance(message['content'], list)
            for part in message['content'] if part['type'] == 'image_url'
        ]
        self.assertEqual(len(image_parts), 1)
        encoded = image_parts[0]['image_url']['url'].split(',', 1)[1]
        self.assertEqual(body['image']['inference_sha256'], hashlib.sha256(base64.b64decode(encoded)).hexdigest())
        self.assertTrue(paths)
        self.assertTrue(all((not path.exists() for path in paths)))

    async def test_missing_blank_repeated_and_extra_fields_fail_before_inference(self):
        cases = [
            {'files': [('question', (None, 'Windows?'))]},
            {'files': {'image': ('plan.png', self.image, 'image/png')}},
            {'data': {'question': '   '}, 'files': {'image': ('plan.png', self.image, 'image/png')}},
            {'files': [
                ('question', (None, 'Windows?')), ('question', (None, 'Doors?')),
                ('image', ('plan.png', self.image, 'image/png')),
            ]},
            {'data': {'question': 'Windows?'}, 'files': [
                ('image', ('one.png', self.image, 'image/png')),
                ('image', ('two.png', self.image, 'image/png')),
            ]},
            {'data': {'question': 'Windows?', 'unrecognized': 'extra'},
             'files': {'image': ('plan.png', self.image, 'image/png')}},
        ]
        async with self.api() as client:
            for kwargs in cases:
                with self.subTest(kwargs=list(kwargs)):
                    self.assert_error(await client.post('/api/v1/candidates', **kwargs), 422)
        self.assertEqual(self.requests, [])

    async def test_json_request_is_rejected_as_wrong_content_type(self):
        async with self.api() as client:
            response = await client.post('/api/v1/candidates', json={'question': 'Windows?', 'image': 'fake'})
            self.assert_error(response, 415)
        self.assertEqual(self.requests, [])

    async def test_actual_image_type_controls_acceptance_and_corruption_is_distinct(self):
        async with self.api() as client:
            good = await client.post('/api/v1/candidates', data={'question': 'Windows?'}, files={
                'image': ('wrong-extension.jpg', self.image, 'image/jpeg'),
            })
            self.assertEqual(good.status_code, 200, good.text)
            self.assert_error(await self.post(client, image=b'%PDF-1.4 fake'), 415)
            self.assert_error(await self.post(client, image=self.image[:35]), 422)
        self.assertEqual(len(self.requests), 1)

    async def test_upload_and_pixel_limits_prevent_inference(self):
        for settings in (ApiSettings(max_image_bytes=20), ApiSettings(max_pixels=10)):
            with self.subTest(settings=settings):
                async with self.api(settings=settings) as client:
                    self.assert_error(await self.post(client), 413)
        self.assertEqual(self.requests, [])

    async def test_oversized_chunked_body_is_rejected_without_content_length(self):
        settings = ApiSettings(max_body_bytes=1024)

        async def chunks():
            yield b'x' * 600
            yield b'y' * 600

        async with self.api(settings=settings) as client:
            response = await client.post('/api/v1/candidates', content=chunks(), headers={
                'Content-Type': 'multipart/form-data; boundary=test',
            })
            self.assert_error(response, 413)
        self.assertEqual(self.requests, [])

    async def test_question_limit_prevents_inference(self):
        async with self.api(settings=ApiSettings(max_question_chars=5)) as client:
            self.assert_error(await self.post(client, question='Too long'), 422)
        self.assertEqual(self.requests, [])

    async def test_prepared_png_limit_is_checked_before_inference(self):
        random_bytes = random.Random(1234).randbytes(100 * 100 * 3)
        source = Image.frombytes('RGB', (100, 100), random_bytes)
        output = io.BytesIO()
        source.save(output, format='JPEG', quality=50)
        upload = output.getvalue()
        # JPEG fits the upload cap, but its lossless inference PNG does not.
        async with self.api(settings=ApiSettings(max_image_bytes=len(upload) + 1)) as client:
            self.assert_error(await self.post(client, image=upload), 413)
        self.assertEqual(self.requests, [])

    async def test_animation_is_not_silently_reduced_to_one_frame(self):
        output = io.BytesIO()
        first, second = (Image.new('RGB', (10, 10), 'white'), Image.new('RGB', (10, 10), 'black'))
        first.save(output, format='PNG', save_all=True, append_images=[second], duration=100, loop=0)
        async with self.api() as client:
            self.assert_error(await self.post(client, image=output.getvalue()), 422)
        self.assertEqual(self.requests, [])

    async def test_exif_orientation_and_inference_dimensions_agree(self):
        exif = Image.Exif()
        exif[274] = 6
        upload = image_bytes((80, 40), format='JPEG', exif=exif)
        async with self.api() as client:
            response = await self.post(client, image=upload)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body['image']['width'], body['image']['height']), (40, 80))
        self.assertEqual(body['candidates'][0]['geometry']['maximum'], [36, 64])
        content = json.loads(self.requests[0].content)['messages'][-1]['content']
        url = next((part['image_url']['url'] for part in content if part['type'] == 'image_url'))
        with Image.open(io.BytesIO(base64.b64decode(url.split(',', 1)[1]))) as sent:
            self.assertEqual(sent.size, (40, 80))
            self.assertNotIn(274, sent.getexif())

    async def test_empty_partial_unreadable_and_unsupported_are_preserved(self):
        cases = (
            ('ok', [], []),
            ('partial', proposals()['candidates'], ['A corner is obscured.']),
            ('unreadable', [], ['The submitted image is unreadable.']),
            ('unsupported', [], ['Unseen floors cannot be assessed from this image.']),
        )
        for status, candidates, limitations in cases:
            payload = {'status': status, 'candidates': candidates, 'limitations': limitations}
            with self.subTest(status=status):
                async with self.api(lambda _, payload=payload: completion(payload)) as client:
                    response = await self.post(client)
                    self.assertEqual(response.status_code, 200, response.text)
                    body = response.json()
                    self.assertEqual(body['status'], status)
                    self.assertEqual(body['limitations'], limitations)
                    self.assertEqual(len(body['candidates']), len(candidates))
                    self.assertEqual(body['inventory_completeness'], 'unverified')
                    self.assertNotIn('count', body)

    async def test_uncertain_candidate_keeps_its_reason(self):
        payload = proposals()
        payload['candidates'][0].update(uncertain=True, uncertainty_reason='Could be a glazed door.')
        async with self.api(lambda _: completion(payload)) as client:
            response = await self.post(client)
        self.assertEqual(response.status_code, 200, response.text)
        candidate = response.json()['candidates'][0]
        self.assertTrue(candidate['uncertain'])
        self.assertEqual(candidate['uncertainty_reason'], 'Could be a glazed door.')

    async def test_invalid_geometry_and_inconsistent_batches_fail_without_repairs(self):
        batches = []
        boxes = (
            [-1, 0, 100, 100], [0, 0, 1001, 100], [10, 20, 10, 30],
            [0, 0, float('nan'), 20], [False, 0, 10, 20], ['0', 0, 10, 20],
        )
        for box in boxes:
            payload = proposals()
            payload['candidates'][0]['bbox_1000'] = box
            batches.append(payload)
        duplicate = proposals()
        duplicate['candidates'].append(deepcopy(duplicate['candidates'][0]))
        batches.append(duplicate)
        partial_without_explanation = proposals()
        partial_without_explanation['status'] = 'partial'
        batches.append(partial_without_explanation)
        unsupported_with_candidates = proposals()
        unsupported_with_candidates.update(status='unsupported', limitations=['Unsupported.'])
        batches.append(unsupported_with_candidates)
        for payload in batches:
            with self.subTest(payload=payload):
                async with self.api(lambda _, payload=payload: completion(payload)) as client:
                    self.assert_error(await self.post(client), 502)
        self.assertEqual(len(self.requests), len(batches))

    async def test_malformed_and_truncated_completions_never_become_empty_results(self):
        for text, finish in (('not JSON', 'stop'), ('{}', 'stop'), (json.dumps(proposals()), 'length')):
            with self.subTest(finish=finish, text=text[:20]):
                async with self.api(lambda _, text=text, finish=finish: completion(text=text, finish_reason=finish)) as client:
                    self.assert_error(await self.post(client), 502)
        self.assertEqual(len(self.requests), 3)

    async def test_provider_failures_are_redacted_and_never_retried(self):
        for status, expected in ((400, 502), (401, 503), (429, 503), (503, 503)):
            with self.subTest(provider=status):
                async with self.api(lambda _, status=status: completion(status=status)) as client:
                    self.assert_error(await self.post(client), expected)
        self.assertEqual(len(self.requests), 4)

    async def test_total_deadline_cleans_up_temporary_images(self):
        paths = []

        async def delayed(_):
            await asyncio.sleep(1)
            return completion()

        # Isolate cancellation during inference; the lifecycle suite separately
        # holds preparation past its deadline and verifies deferred file cleanup.
        async with self.api(delayed, settings=ApiSettings(deadline_seconds=0.2, preprocess_mode="off"), paths=paths) as client:
            self.assert_error(await self.post(client), 504)
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(paths)
        self.assertTrue(all((not path.exists() for path in paths)))

    async def test_health_docs_and_cors_do_not_spend_inference_requests(self):
        async with self.api() as client:
            health = await client.get('/health')
            self.assertEqual(health.status_code, 200)
            self.assertNotIn(TEST_KEY, health.text)
            self.assertEqual((await client.get('/docs')).status_code, 200)
            schema = (await client.get('/openapi.json')).json()
            upload = schema['paths']['/api/v1/candidates']['post']['requestBody']['content']
            self.assertIn('multipart/form-data', upload)
            cors = await client.options('/api/v1/candidates', headers={
                'Origin': 'http://localhost:5173',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
            })
            self.assertEqual(cors.status_code, 200)
            self.assertEqual(cors.headers['access-control-allow-origin'], 'http://localhost:5173')
            rejected = await client.options('/api/v1/candidates', headers={
                'Origin': 'https://untrusted.invalid', 'Access-Control-Request-Method': 'POST',
            })
            self.assertNotIn('access-control-allow-origin', rejected.headers)
        self.assertEqual(self.requests, [])

    async def test_missing_backend_key_is_service_error_not_zero_candidates(self):
        with patch('image_api.app.NemotronSettings.from_env',
                   side_effect=ConfigurationError('Missing backend key.')):
            app = create_app(settings=ApiSettings())
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
                    self.assertEqual((await client.get('/health')).status_code, 503)
                    self.assert_error(await self.post(client), 503)


if __name__ == '__main__':
    unittest.main()

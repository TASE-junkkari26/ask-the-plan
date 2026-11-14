"""Mocked routing policy/lifecycle checks; no drawing-accuracy claim or network."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx
from gemini import AsyncGeminiClient, GeminiSettings
from gemini.decisions import AsyncDecisionsClient
from gemini.decisions_config import DecisionsSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from image_api.routing import QUESTIONS, POLICY_VERSION, route_decision
from nemotron import ConfigurationError
from tests.test_gemini_image_api import interaction
from tests.test_image_api import image_bytes

KEY = 'synthetic-routing-credential'
DEFAULT_CHOICES = dict(normal_fit='supported', document_kind='floor_plan',
                       task_kind='instance_discovery', count_grain='assembly',
                       target_kind='windows', scope='selected_view')


def answers(**choices):
    selected = {**DEFAULT_CHOICES, **choices}
    return {key: {'type': 'choice', 'choice': selected[key],
                  'probabilities': {option: (0.99 if option == selected[key] else 0.01 / (len(q['criteria']) - 1))
                                    for option in q['criteria']}, 'confidence': 0.99}
            for key, q in QUESTIONS.items()}


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def api(self, *, decision_handler=None, analysis_handler=None, strong=True, **settings):
        self.requests = []
        self.closed_clients = []
        async def decide(request):
            self.requests.append(('decision', json.loads(request.content)))
            return await decision_handler(request) if decision_handler else httpx.Response(200, json={
                'answers': answers(), 'usage': {'total_input_tokens': 10, 'total_output_tokens': 0}})
        async def analyze(request):
            body = json.loads(request.content)
            self.requests.append(('analysis', body))
            if analysis_handler:
                return await analysis_handler(request)
            value = interaction().json()
            value['model'] = body['model']
            return httpx.Response(200, json=value)
        def client(profile):
            instance = AsyncGeminiClient(GeminiSettings(api_key=KEY).profile(profile, thinking_level=settings.get('routing_strong_thinking_level', 'medium')), transport=httpx.MockTransport(analyze))
            self.closed_clients.append(instance)
            return instance
        def unavailable():
            raise ConfigurationError('synthetic unavailable profile')
        decision_client = AsyncDecisionsClient(DecisionsSettings(api_key=KEY), transport=httpx.MockTransport(decide))
        app = create_app(ApiSettings(provider='gemini', routing_mode='auto', preprocess_mode='off', **settings),
                         client_factory=unavailable, gemini_client_factory=lambda: client('normal'),
                         strong_client_factory=(lambda: client('strong')) if strong else unavailable,
                         decisions_client_factory=lambda: decision_client)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as http:
                yield http
        self.assertTrue(all(c._http.is_closed for c in self.closed_clients))
        self.assertTrue(decision_client._http.is_closed)

    async def post(self, http, question='Find windows'):
        return await http.post('/api/v1/candidates', data={'question': question},
                               files={'image': ('drawing.png', image_bytes(), 'image/png')})

    async def test_supported_route_one_analyzer_source_and_question_bound(self):
        async with self.api() as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        trace = body['decision_trace']
        self.assertEqual(trace['selected_profile'], 'normal')
        self.assertEqual(trace['image'], body['image'])
        self.assertEqual(trace['question_sha256'], hashlib.sha256(b'Find windows').hexdigest())
        self.assertEqual(trace['request_id'], body['request_id'])
        self.assertEqual([c['purpose'] for c in trace['calls']], ['routing', 'analysis'])
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[-1][1]['model'], 'gemini-4-hydrogen')
        self.assertEqual(self.requests[-1][1]['generation_config']['thinking_level'], 'low')

    async def test_hard_goes_direct_to_carbon_without_hydrogen(self):
        async def hard(_):
            return httpx.Response(200, json={'answers': answers(normal_fit='needs_strong')})
        async with self.api(decision_handler=hard) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['decision_trace']['selected_profile'], 'strong')
        calls = [b for kind, b in self.requests if kind == 'analysis']
        self.assertEqual([b['model'] for b in calls], ['gemini-4-carbon'])
        self.assertEqual(calls[0]['generation_config']['thinking_level'], 'medium')
        self.assertEqual(calls[0]['input'][0]['text'], 'Find windows')

    async def test_router_timeout_selects_hydrogen_and_preserves_failed_call_unknown_usage(self):
        cancelled = asyncio.Event()
        async def timeout(_):
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
        async with self.api(decision_handler=timeout, routing_timeout_seconds=0.02) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 200, result.text)
        trace = result.json()['decision_trace']
        self.assertTrue(cancelled.is_set())
        self.assertEqual(trace['nodes'][0]['reason_code'], 'router_timeout')
        self.assertEqual(trace['calls'][0]['outcome'], 'failed')
        self.assertIsNone(trace['calls'][0]['prompt_tokens'])
        self.assertEqual(trace['selected_profile'], 'normal')
        self.assertEqual(trace['nodes'][1]['reason_code'], 'routing_fallback_normal')
        self.assertEqual(self.requests[-1][1]['model'], 'gemini-4-hydrogen')

    async def test_carbon_low_can_be_configured_for_strong_route(self):
        async def hard(_):
            return httpx.Response(200, json={'answers': answers(normal_fit='needs_strong')})
        async with self.api(decision_handler=hard, routing_strong_thinking_level='low') as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 200, result.text)
        calls = [body for kind, body in self.requests if kind == 'analysis']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['model'], 'gemini-4-carbon')
        self.assertEqual(calls[0]['generation_config']['thinking_level'], 'low')

    async def test_routing_errors_use_hydrogen_without_carbon_or_retry(self):
        for status, body in ((503, {'error': {'message': KEY}}), (200, {'answers': {}})):
            async def failed(_, status=status, body=body):
                return httpx.Response(status, json=body)
            async with self.api(decision_handler=failed) as http:
                result = await self.post(http)
            self.assertEqual(result.status_code, 200, result.text)
            trace = result.json()['decision_trace']
            self.assertEqual(trace['selected_profile'], 'normal')
            self.assertEqual(trace['nodes'][1]['reason_code'], 'routing_fallback_normal')
            self.assertEqual(trace['assessments'], {})
            self.assertEqual([kind for kind, _ in self.requests], ['decision', 'analysis'])
            self.assertEqual(self.requests[-1][1]['model'], 'gemini-4-hydrogen')
            self.assertNotIn(KEY, result.text)

    async def test_transport_timeout_phases_remain_failures_not_difficulty_assessments(self):
        for error_type, phase in ((httpx.ConnectTimeout, 'connect'), (httpx.WriteTimeout, 'write'),
                                  (httpx.ReadTimeout, 'read'), (httpx.PoolTimeout, 'pool')):
            with self.subTest(phase=phase):
                async def timeout(_):
                    raise error_type('private provider details')
                async with self.api(decision_handler=timeout) as http:
                    result = await self.post(http)
                self.assertEqual(result.status_code, 200, result.text)
                trace = result.json()['decision_trace']
                self.assertEqual(trace['nodes'][0]['reason_code'], f'router_{phase}_timeout')
                self.assertEqual(trace['assessments'], {})
                self.assertEqual(trace['selected_profile'], 'normal')
                self.assertEqual([kind for kind, _ in self.requests], ['decision', 'analysis'])
                self.assertNotIn('private provider details', result.text)

    async def test_incomplete_analysis_retains_reported_cost_inputs(self):
        async def hard(_):
            return httpx.Response(200, json={'answers': answers(normal_fit='needs_strong')})
        async def incomplete(_):
            return httpx.Response(200, json={
                'status': 'incomplete', 'model': 'gemini-4-carbon', 'continuation_token': KEY,
                'usage': {'total_input_tokens': 2188, 'total_output_tokens': 3, 'total_thought_tokens': 4093}})
        async with self.api(decision_handler=hard, analysis_handler=incomplete) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 502, result.text)
        self.assertEqual(result.json()['code'], 'invalid_model_output')
        call = result.json()['decision_trace']['calls'][-1]
        self.assertEqual((call['prompt_tokens'], call['completion_tokens']), (2188, 4096))
        self.assertEqual(call['returned_model'], 'gemini-4-carbon')
        self.assertEqual(call['requested_model'], 'gemini-4-carbon')
        self.assertEqual(call['outcome'], 'failed')
        self.assertNotIn('continuation_token', result.text)
        self.assertNotIn(KEY, result.text)
        async def malformed_completed(_):
            value = interaction(text='not candidate JSON').json()
            value['model'] = KEY  # Untrusted metadata must not cross an error boundary.
            return httpx.Response(200, json=value)
        async with self.api(decision_handler=hard, analysis_handler=malformed_completed) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 502, result.text)
        call = result.json()['decision_trace']['calls'][-1]
        self.assertIsNone(call['returned_model'])
        self.assertEqual((call['prompt_tokens'], call['completion_tokens']), (101, 54))
        self.assertNotIn(KEY, result.text)

    async def test_cache_question_identity_and_no_rebill(self):
        async with self.api() as http:
            first = await self.post(http)
            same = await self.post(http)
            other = await self.post(http, 'Find doors')
        self.assertEqual(first.status_code, 200, first.text)
        trace = same.json()['decision_trace']
        self.assertEqual(trace['nodes'][0]['state'], 'reused')
        self.assertEqual([c['purpose'] for c in trace['calls']], ['analysis'])
        self.assertEqual(len([1 for k, _ in self.requests if k == 'decision']), 2)
        self.assertNotEqual(trace['question_sha256'], other.json()['decision_trace']['question_sha256'])

    async def test_strong_unavailable_error_keeps_decision_without_weak_fallback(self):
        async def uncertain(_):
            return httpx.Response(200, json={'answers': answers(normal_fit='needs_strong')})
        async with self.api(decision_handler=uncertain, strong=False) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 503, result.text)
        trace = result.json()['decision_trace']
        self.assertEqual(trace['nodes'][-1]['reason_code'], 'strong_unavailable')
        self.assertEqual(trace['selected_profile'], 'strong')
        self.assertEqual(len(self.requests), 1)

    async def test_provider_error_and_deadline_keep_terminal_trace(self):
        async def denied(_):
            return httpx.Response(403, json={'error': {'message': KEY}})
        async with self.api(analysis_handler=denied) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 503, result.text)
        self.assertEqual(result.json()['decision_trace']['calls'][-1]['outcome'], 'failed')
        self.assertNotIn(KEY, result.text)
        async def stalled(_):
            await asyncio.Future()
        async with self.api(analysis_handler=stalled, deadline_seconds=5.05) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 504, result.text)
        self.assertEqual(result.json()['decision_trace']['calls'][-1]['outcome'], 'cancelled')

    def test_ordinary_families_do_not_trigger_an_independent_registry_veto(self):
        for options in ({'task_kind': 'literal_lookup', 'count_grain': 'not_counting_or_unclear'},
                        {'count_grain': 'room_or_unit', 'target_kind': 'other_or_unclear'},
                        {'document_kind': 'mixed_panels'}, {'document_kind': 'schedule'},
                        {'document_kind': 'section_or_elevation'}, {'task_kind': 'quantity_value'},
                        {'task_kind': 'arithmetic'}, {'count_grain': 'unit_or_leaf'},
                        {'scope': 'wider_or_named'}):
            with self.subTest(options=options):
                self.assertEqual(route_decision(answers(**options), 0.6)[0], 'normal')

    def test_carbon_requires_explicit_difficulty_at_strong_threshold(self):
        self.assertEqual(ApiSettings().routing_strong_threshold, 0.8)
        for strong, expected in ((0.799, 'normal'), (0.8, 'strong'), (0.9, 'strong')):
            value = answers(normal_fit='needs_strong')
            value['normal_fit']['probabilities'] = dict(supported=1-strong, needs_strong=strong, uncertain=0)
            self.assertEqual(route_decision(value, 0.8)[0], expected)
        self.assertEqual(route_decision(answers(normal_fit='uncertain'), 0.8)[0], 'normal')
        value = answers(normal_fit='needs_strong')
        value['normal_fit']['probabilities'] = dict(supported=0.15, needs_strong=0.75, uncertain=0.1)
        self.assertEqual(route_decision(value, 0.8)[0], 'normal')
        self.assertEqual(route_decision(value, 0.7)[0], 'strong')

    def test_moderate_overall_fit_with_low_diagnostic_certainty_stays_normal(self):
        # Synthetic regression inspired by development scores, not model accuracy.
        value = answers()
        value['normal_fit']['probabilities'] = dict(supported=0.659, needs_strong=0.266, uncertain=0.075)
        value['normal_fit']['confidence'] = 0.659
        for key in ('document_kind', 'task_kind', 'count_grain', 'target_kind', 'scope'):
            options = value[key]['probabilities']
            chosen = value[key]['choice']
            value[key]['probabilities'] = {name: 0.55 if name == chosen else 0.45/(len(options)-1) for name in options}
            value[key]['confidence'] = 0.55
        self.assertEqual(route_decision(value, 0.6)[:2], ('normal', 'normal_supported'))

    async def test_scope_and_unsupported_limits_are_preserved_on_both_routes(self):
        for fit, expected_model in (('supported', 'gemini-4-hydrogen'), ('needs_strong', 'gemini-4-carbon')):
            async def scoped(_, fit=fit):
                return httpx.Response(200, json={'answers': answers(normal_fit=fit, scope='wider_or_named')})
            async def unsupported(request):
                model = json.loads(request.content)['model']
                value = interaction(payload={'status': 'unsupported', 'candidates': [],
                                              'limitations': ['The other floor is absent from this selected image.']}).json()
                value['model'] = model
                return httpx.Response(200, json=value)
            async with self.api(decision_handler=scoped, analysis_handler=unsupported) as http:
                result = await self.post(http, 'Find windows on the other floor')
            self.assertEqual(result.status_code, 200, result.text)
            body = result.json()
            self.assertEqual((body['scope'], body['status'], body['candidates']), ('submitted_image', 'unsupported', []))
            calls = [body for kind, body in self.requests if kind == 'analysis']
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]['model'], expected_model)
            self.assertEqual(calls[0]['input'][0]['text'], 'Find windows on the other floor')
            self.assertEqual(body['image']['sha256'], hashlib.sha256(image_bytes()).hexdigest())

    async def test_policy_threshold_and_version_changes_invalidate_decision_cache(self):
        async def typical(_):
            value = answers(normal_fit='needs_strong')
            value['normal_fit'].update(probabilities=dict(supported=0.2, needs_strong=0.7, uncertain=0.1), confidence=0.7)
            return httpx.Response(200, json={'answers': value})
        async with self.api(decision_handler=typical) as http:
            first = await self.post(http)
            cached = await self.post(http)
            service = http._transport.app.state.service
            service.settings = service.settings.model_copy(update={'routing_strong_threshold': 0.6})
            stricter = await self.post(http)
            with patch('image_api.routing.POLICY_VERSION', POLICY_VERSION + '-test'):
                versioned = await self.post(http)
        self.assertEqual(first.json()['decision_trace']['selected_profile'], 'normal')
        self.assertEqual(cached.json()['decision_trace']['nodes'][0]['state'], 'reused')
        self.assertEqual(stricter.json()['decision_trace']['selected_profile'], 'strong')
        self.assertEqual(versioned.json()['decision_trace']['policy_version'], POLICY_VERSION + '-test')
        self.assertEqual(len([1 for kind, _ in self.requests if kind == 'decision']), 3)

    async def test_exhausted_deadline_schedules_no_paid_calls(self):
        async with self.api(deadline_seconds=0.1) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 504, result.text)
        trace = result.json()['decision_trace']
        self.assertEqual(trace['selected_profile'], 'pending')
        self.assertEqual(trace['nodes'][-1]['reason_code'], 'budget_exhausted')
        self.assertEqual(self.requests, [])

    async def test_unexpected_analysis_exception_is_sanitized_with_trace(self):
        async def broken(_):
            raise RuntimeError(KEY)
        async with self.api(analysis_handler=broken) as http:
            result = await self.post(http)
        self.assertEqual(result.status_code, 500, result.text)
        self.assertEqual(result.json()['decision_trace']['calls'][-1]['outcome'], 'failed')
        self.assertNotIn(KEY, result.text)

    async def test_secondary_probability_is_diagnostic_and_does_not_select_strong(self):
        async def low_task(_):
            value = answers()
            options = QUESTIONS['task_kind']['criteria']
            value['task_kind']['probabilities'] = {key: 0.55 if key == 'instance_discovery' else 0.45 / (len(options) - 1) for key in options}
            value['task_kind']['confidence'] = 0.55
            return httpx.Response(200, json={'answers': value})
        async with self.api(decision_handler=low_task) as http:
            result = await self.post(http)
        trace = result.json()['decision_trace']
        self.assertEqual(trace['assessment_probabilities']['task_kind'], 0.55)
        self.assertEqual(trace['selected_profile'], 'normal')
        self.assertEqual([body['model'] for kind, body in self.requests if kind == 'analysis'], ['gemini-4-hydrogen'])
        self.assertEqual(trace['nodes'][0]['threshold'], 0.8)
        self.assertIsNone(trace['calls'][0]['returned_model'])

    async def test_shadow_records_recommendation_but_executes_baseline_once(self):
        # Reuse injection with settings built explicitly for shadow.
        async def hard(_):
            return httpx.Response(200, json={'answers': answers(normal_fit='needs_strong')})
        async with self.api(decision_handler=hard) as http:
            # Test the host service through the exact same HTTP path in shadow mode.
            app = http._transport.app
            app.state.service.settings = app.state.service.settings.model_copy(update={'routing_mode': 'shadow'})
            result = await self.post(http)
        trace = result.json()['decision_trace']
        self.assertEqual((trace['selected_profile'], trace['recommended_profile']), ('manual', 'strong'))
        self.assertEqual([b['model'] for k, b in self.requests if k == 'analysis'], ['gemini-4-hydrogen'])

    def test_invalid_routing_configuration_fails_early(self):
        from pydantic import ValidationError
        for options in ({'provider': 'nemotron'}, {'preprocess_mode': 'overview'}, {'max_concurrent': 3}):
            with self.assertRaises(ValidationError):
                ApiSettings(**{**dict(provider='gemini', routing_mode='auto'), **options})

"""Synthetic source-to-answer HTTP checks; no model accuracy claims or paid calls."""
from __future__ import annotations

import hashlib
import json
import unittest

from contracts import models as m
from contracts.validation import validate_answer
from tests import test_image_api as image_tests
from tests import test_ifc_api as ifc_tests


class DrawingAnswerApiTests(unittest.IsolatedAsyncioTestCase):
    setUp = image_tests.ImageApiTests.setUp
    api = image_tests.ImageApiTests.api

    async def register(self, client):
        digest = hashlib.sha256(self.image).hexdigest()
        snapshot = dict(source_sha256=digest, source_revision=digest, display_sha256=digest,
                        display_width=80, display_height=40, page_index=0, rotation=0)
        response = await client.post('/api/v1/sources', data={'snapshot': json.dumps(snapshot)}, files={
            'file': ('original.png', self.image, 'image/png'), 'image': ('display.png', self.image, 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        return {**response.json(), 'snapshot': snapshot}

    async def ask(self, client, session, question='How many windows?', **kwargs):
        request = dict(source_id=session['source_id'], source_sha256=session['source_sha256'],
                       snapshot=session['snapshot'], question=question)
        return await client.post('/api/v1/answers', json=request, **kwargs)

    async def test_registered_original_display_and_qualified_answer_are_bound(self):
        async with self.api() as client:
            session = await self.register(client)
            response = await self.ask(client, session)
            self.assertEqual(response.status_code, 200, response.text)
            answer = m.AnswerResponse.model_validate(response.json())
            validate_answer(answer)
            self.assertEqual(answer.parts[0].status, 'partial')
            self.assertEqual(answer.parts[0].result.claims[0].value.value, 1)
            self.assertEqual(answer.parts[0].result.claims[0].quality, 'estimated')
            self.assertIn('total is not confirmed', answer.narrative[0].text)
            self.assertEqual(answer.metrics.external_attempts, 1)
            self.assertEqual(answer.metrics.model_input_tokens, 17)
            self.assertEqual(len(self.requests), 1)
            asset = await client.get('/api/v1/sources/' + session['source_id'])
            self.assertEqual(asset.content, self.image)
            self.assertNotIn('/tmp/', response.text)

    async def test_empty_scan_is_not_zero(self):
        data = image_tests.proposals()
        data['candidates'] = []
        async with self.api(lambda _: image_tests.completion(data)) as client:
            session = await self.register(client)
            response = await self.ask(client, session)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()['parts'][0]['result']
        self.assertEqual(result['status'], 'incomplete_coverage')
        self.assertEqual(result['claims'], [])

    async def test_missing_linked_model_uses_no_visual_call(self):
        async with self.api() as client:
            session = await self.register(client)
            response = await self.ask(client, session, 'How many windows are in the entire IFC model?')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['parts'][0]['status'], 'missing_source')
        self.assertEqual(response.json()['metrics']['external_attempts'], 0)
        self.assertEqual(self.requests, [])

    async def test_measurement_question_does_not_become_box_count(self):
        async with self.api() as client:
            session = await self.register(client)
            response = await self.ask(client, session, 'What is the net area of room 7.16?')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['parts'][0]['status'], 'unsupported_operation')
        self.assertEqual(response.json()['parts'][0]['result']['claims'], [])
        self.assertTrue(response.json()['candidate_response']['candidates'])

    async def test_swedish_count_remains_a_qualified_count_in_swedish(self):
        async with self.api() as client:
            session = await self.register(client)
            response = await self.ask(client, session, 'Hur många fönster finns det?')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['interpretation']['language'], 'sv')
        self.assertEqual(response.json()['parts'][0]['status'], 'partial')
        self.assertIn('totalen är inte bekräftad', response.json()['narrative'][0]['text'])

    async def test_failed_visual_attempts_are_counted_across_compound_parts(self):
        async with self.api(lambda _: image_tests.completion(status=503)) as client:
            session = await self.register(client)
            response = await self.ask(client, session, 'How many windows? How many doors?')
        self.assertEqual(response.status_code, 200, response.text)
        metrics = response.json()['metrics']
        self.assertEqual(metrics['external_attempts'], 2)
        self.assertEqual([call['outcome'] for call in metrics['calls']], ['failed', 'failed'])
        self.assertIsNone(metrics['model_input_tokens'])

    async def test_compound_drawing_handoff_binds_original_question(self):
        question = 'How many windows? How many doors?'
        async with self.api() as client:
            session = await self.register(client)
            response = await self.ask(client, session, question, headers={'accept': 'application/x-ndjson'})
        frames = [m.AnswerStreamEvent.model_validate_json(line) for line in response.text.splitlines()]
        self.assertEqual([frame.type for frame in frames], ['handoff', 'result'])
        self.assertEqual(frames[0].progress.question_sha256, hashlib.sha256(question.encode()).hexdigest())
        self.assertEqual(len(frames[1].result.parts), 2)

    async def test_changed_snapshot_and_deleted_session_are_rejected(self):
        async with self.api() as client:
            session = await self.register(client)
            session['snapshot']['page_index'] = 2
            response = await self.ask(client, session)
            self.assertEqual(response.status_code, 409, response.text)
            await client.delete('/api/v1/sources/' + session['source_id'])
            response = await self.ask(client, session)
            self.assertEqual(response.status_code, 410, response.text)
        self.assertEqual(self.requests, [])

    async def test_answer_stream_retains_real_analyzer_handoff(self):
        async with self.api() as client:
            session = await self.register(client)
            response = await self.ask(client, session, headers={'accept': 'application/x-ndjson'})
        self.assertEqual(response.status_code, 200, response.text)
        events = [m.AnswerStreamEvent.model_validate_json(line) for line in response.text.splitlines()]
        self.assertEqual([event.type for event in events], ['handoff', 'result'])
        self.assertEqual(events[0].progress.requested_model, events[1].result.candidate_response.provenance.requested_model)
        self.assertEqual(events[1].result.request_id, response.headers['x-request-id'])
        validate_answer(events[1].result)


class IfcAnswerApiTests(unittest.IsolatedAsyncioTestCase):
    setUpClass = classmethod(ifc_tests.IfcApiTests.setUpClass.__func__)
    tearDownClass = classmethod(ifc_tests.IfcApiTests.tearDownClass.__func__)
    setUp = ifc_tests.IfcApiTests.setUp
    api = ifc_tests.IfcApiTests.api
    upload = ifc_tests.IfcApiTests.upload

    async def test_ifc_uses_registered_model_and_validates_exact_count(self):
        async with self.api() as (client, app):
            uploaded = await self.upload(client)
            model_id = uploaded['model_id']
            response = await client.post('/api/v1/answers', json=dict(model_id=model_id,
                source_sha256=self.sha, question='How many windows in the model?'))
            self.assertEqual(response.status_code, 200, response.text)
            answer = m.AnswerResponse.model_validate(response.json())
            validate_answer(answer)
        self.assertEqual(answer.source.scope_label, 'Entire model')
        self.assertEqual(answer.parts[0].status, 'answered')
        self.assertEqual(answer.parts[0].result.claims[0].value.value, 3)
        self.assertEqual(answer.metrics.external_attempts, 1)
        self.assertEqual(answer.ifc_response.scope, 'model')

    async def test_independent_compound_failure_keeps_count_and_missing_price(self):
        self.reply = ifc_tests.proposal()
        self.reply.pop('output_step_id')
        self.reply['outputs'] = {'windows': 'answer'}
        self.reply['unavailable_parts'] = [{'key': 'price', 'status': 'missing_information',
                                           'message': 'No price factor is recorded in the source.'}]
        self.reply['requested_parts'] = [{'key': 'windows', 'question': 'Count windows.'},
                                        {'key': 'price', 'question': 'Give their purchase cost.'}]
        async with self.api() as (client, app):
            uploaded = await self.upload(client)
            response = await client.post('/api/v1/answers', json=dict(model_id=uploaded['model_id'],
                source_sha256=self.sha, question='What are the window count and purchase cost?'))
        self.assertEqual(response.status_code, 200, response.text)
        answer = m.AnswerResponse.model_validate(response.json())
        validate_answer(answer)
        self.assertEqual({part.key: part.status for part in answer.parts}, {'windows': 'answered', 'price': 'missing_information'})
        self.assertEqual({sentence.part_key for sentence in answer.narrative}, {'windows', 'price'})
        self.assertEqual(answer.metrics.external_attempts, 1)

    async def test_unsupported_output_does_not_abort_independent_count(self):
        self.reply = ifc_tests.proposal()
        self.reply.pop('output_step_id')
        self.reply['outputs'] = {'windows': 'answer', 'walking_distance': 'route'}
        self.reply['requested_parts'] = [{'key': 'windows', 'question': 'Count windows.'},
                                        {'key': 'walking_distance', 'question': 'Measure a walking route.'}]
        self.reply['steps'].append({'id': 'route', 'operation': {'kind': 'measure', 'input_step_id': 'objects',
            'metric': 'distance', 'output_unit_id': 'unit:m', 'basis': 'walking route'}})
        async with self.api() as (client, app):
            uploaded = await self.upload(client)
            response = await client.post('/api/v1/answers', json=dict(model_id=uploaded['model_id'],
                source_sha256=self.sha, question='What are the window count and walking route distance?'))
        self.assertEqual(response.status_code, 200, response.text)
        parts = {part['key']: part for part in response.json()['parts']}
        self.assertEqual(parts['windows']['status'], 'answered')
        self.assertNotEqual(parts['walking_distance']['status'], 'answered')

    async def test_planner_cannot_drop_host_resolved_compound_part(self):
        self.reply = ifc_tests.proposal()
        self.reply.pop('output_step_id')
        self.reply['outputs'] = {'part-1': 'answer'}
        async with self.api() as (client, app):
            uploaded = await self.upload(client)
            response = await client.post('/api/v1/answers', json=dict(model_id=uploaded['model_id'],
                source_sha256=self.sha, question='How many windows? What is their fire rating?'))
        self.assertEqual(response.status_code, 200, response.text)
        parts = {part['key']: part for part in response.json()['parts']}
        self.assertEqual(parts['part-1']['status'], 'answered')
        self.assertEqual(parts['part-2']['status'], 'needs_clarification')

    async def test_invalid_dependency_order_is_part_failure(self):
        self.reply = ifc_tests.proposal()
        self.reply['steps'].reverse()
        async with self.api() as (client, app):
            uploaded = await self.upload(client)
            response = await client.post('/api/v1/answers', json=dict(model_id=uploaded['model_id'],
                source_sha256=self.sha, question='How many windows?'))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['parts'][0]['status'], 'needs_clarification')

    async def test_unchecked_planner_numbers_do_not_become_missing_information_prose(self):
        self.reply = {'status': 'missing_information', 'interpretation': 'There are 999 windows; price missing.',
            'explicitly_requests_entire_model': False, 'steps': []}
        async with self.api() as (client, app):
            uploaded = await self.upload(client)
            response = await client.post('/api/v1/answers', json=dict(model_id=uploaded['model_id'],
                source_sha256=self.sha, question='How many windows and what is their price?'))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('999', ' '.join(sentence['text'] for sentence in response.json()['narrative']))

    async def test_direct_plans_need_no_model_and_failed_dependency_is_visible(self):
        async with self.api() as (client, app):
            uploaded = await self.upload(client)
            model_id = uploaded['model_id']
            model = app.state.ifc_service._model(model_id, self.sha)
            plan = model.engine.plan('window')
            response = await client.post('/api/v1/answers', json=dict(model_id=model_id, source_sha256=self.sha,
                question='Count windows.', parts=[{'key': 'count', 'question': 'Count windows.'},
                    {'key': 'cost', 'question': 'Calculate cost.', 'depends_on': ['missing']},
                ], plans={'count': plan.model_dump(mode='json')}))
            self.assertEqual(response.status_code, 422)
            response = await client.post('/api/v1/answers', json=dict(model_id=model_id, source_sha256=self.sha,
                question='Count windows.', parts=[{'key': 'count', 'question': 'Count windows.'}],
                plans={'count': plan.model_dump(mode='json')}))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['metrics']['external_attempts'], 0)
        self.assertEqual(self.provider_requests, [])


if __name__ == '__main__':
    unittest.main()

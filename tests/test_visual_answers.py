"""Source-bound visual matches stay useful without becoming measurements."""
from copy import deepcopy
import unittest

from contracts import models as m
from contracts.validation import validate_answer
from answer_api.service import visual_identification
from answer_api.realize import with_narrative
from tests import test_image_api as images
from tests.test_answer_api import DrawingAnswerApiTests as _DrawingFixture


def room_proposals():
    data = images.proposals()
    data['candidates'][0].update(category='room', source_label='Zimmer 4.02',
        visual_cue='Room in the upper-left apartment with a curved exterior wall.')
    return data


class VisualAnswerTests(unittest.IsolatedAsyncioTestCase):
    setUp = images.ImageApiTests.setUp
    api = images.ImageApiTests.api
    register = _DrawingFixture.register
    ask = _DrawingFixture.ask

    async def test_partial_largest_room_query_returns_literal_match_not_measured_rank(self):
        async with self.api(lambda _: images.completion(room_proposals())) as client:
            session = await self.register(client)
            response = await self.ask(client, session, 'largest roo')
        self.assertEqual(response.status_code, 200, response.text)
        answer = m.AnswerResponse.model_validate(response.json())
        validate_answer(answer)
        part = answer.parts[0]
        claim = part.result.claims[0]
        self.assertEqual(part.status, 'partial')
        self.assertEqual(claim.value.kind, 'references')
        self.assertEqual(claim.quality, 'estimated')
        self.assertEqual(answer.narrative[0].text, 'Likely Zimmer 4.02. Size comparison is unverified.')
        self.assertEqual(len(claim.value.entity_ids), 1)
        self.assertTrue(answer.narrative[0].anchor_ids)
        self.assertEqual(claim.evidence[0].evidence_kind, 'candidate')
        self.assertEqual(answer.evidence_contexts[0].bundle.anchors[0].quote.text, 'Zimmer 4.02')
        self.assertEqual(answer.metrics.external_attempts, 1)
        self.assertFalse(any(node.operation in {'measure','rank'} for node in part.result.calculations))
        for quality in ('exact','lower_bound'):
            changed = deepcopy(answer)
            changed.parts[0].result.claims[0].quality = quality
            changed.parts[0].result.calculations[0].quality = quality
            with self.assertRaises(ValueError):
                validate_answer(with_narrative(changed))

    async def test_multiple_matches_remain_alternatives_without_box_area_ranking(self):
        data = room_proposals()
        data['candidates'].append({**data['candidates'][0], 'source_label':'Zimmer 4.11',
            'bbox_1000':[10,10,90,90]})
        async with self.api(lambda _: images.completion(data)) as client:
            session = await self.register(client)
            response = await self.ask(client, session, 'Which room is largest?')
        answer = m.AnswerResponse.model_validate(response.json())
        validate_answer(answer)
        self.assertEqual(len(answer.parts[0].result.claims[0].value.entity_ids), 2)
        self.assertEqual(answer.narrative[0].text,
            'Possible matches: Zimmer 4.02, Zimmer 4.11. Size comparison is unverified.')

    async def test_locate_keeps_original_identifier_and_visual_qualification(self):
        data = room_proposals()
        data['candidates'][0]['source_label'] = '121.A Keittiö'
        async with self.api(lambda _: images.completion(data)) as client:
            session = await self.register(client)
            response = await self.ask(client, session, 'Find room 121.A')
        answer = m.AnswerResponse.model_validate(response.json())
        validate_answer(answer)
        self.assertEqual(answer.narrative[0].text, 'Likely 121.A Keittiö. Visual match, not verified.')

    async def test_visual_match_does_not_supply_area_or_measurement(self):
        async with self.api(lambda _: images.completion(room_proposals())) as client:
            session = await self.register(client)
            response = await self.ask(client, session, 'What is the area of the largest room in m²?')
        answer = m.AnswerResponse.model_validate(response.json())
        validate_answer(answer)
        self.assertEqual(answer.parts[0].status, 'unsupported_operation')
        self.assertEqual(answer.parts[0].result.claims, [])
        self.assertTrue(answer.candidate_response.candidates)
        self.assertIn('implementation gap', answer.parts[0].result.issues[0].message.text)
        self.assertNotIn('implementation gap', answer.narrative[0].text)
        self.assertLess(len(answer.narrative[0].text), 110)

    async def test_no_match_and_provider_unsupported_do_not_create_identity_claims(self):
        for data in ({**room_proposals(), 'candidates':[]},
                     {**room_proposals(), 'candidates':[], 'status':'unsupported', 'limitations':['Original source lacks the required view.']}):
            async with self.api(lambda _,data=data: images.completion(data)) as client:
                session = await self.register(client)
                response = await self.ask(client,session,'largest room')
            answer = m.AnswerResponse.model_validate(response.json())
            validate_answer(answer)
            self.assertFalse(answer.parts[0].result.claims)
            self.assertIn(answer.parts[0].status, {'incomplete_coverage','unsupported_operation'})

    def test_matching_hint_excludes_numeric_properties_relations_and_counts(self):
        for question in ('How many rooms?', 'Find the width of the door', 'largest room area',
                         'Which room is adjacent to 121.A?', 'Show external door fire rating',
                         'What is the volume of the biggest room?', 'Find room occupancy',
                         'Show the room connected to 121.A', 'Find the door opening direction',
                         'What temperature is the largest room?'):
            self.assertIsNone(visual_identification(question), question)
        for question in ('largest roo','Which room is largest?','suurin huone'):
            self.assertEqual(visual_identification(question), 'rank')


del _DrawingFixture

if __name__ == '__main__':
    unittest.main()

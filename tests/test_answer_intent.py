"""Independent requests must stay separate from their counting constraints."""
import unittest

from answer_api.intent import requested_parts
from contracts import models as m
from tests import test_answer_api as answer_tests


def parts(question, **kwargs):
    return requested_parts(m.AnswerRequest(source_id='source:test', source_sha256='a' * 64,
                                         question=question, **kwargs))


class DrawingIntentTests(unittest.TestCase):
    def test_supplied_door_counting_rules_stay_with_the_question(self):
        questions = (
            'How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count.',
            'Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ovi; pelkkiä oviaukkoja ilman ovilehteä ei lasketa.',
        )
        for question in questions:
            with self.subTest(question=question):
                actual = parts(question)
                self.assertEqual(len(actual), 1)
                self.assertEqual(actual[0].key, 'answer')
                self.assertEqual(actual[0].question, question)

    def test_counting_qualifications_are_not_independent_outputs(self):
        questions = (
            'How many doors? Exclude open doorways.',
            'How many sinks? Only count fitted sinks; A double-bowl sink counts as one.',
            'How many doors? Count doorways fitted with a door; Open doorways without a door leaf do not count.',
            'Kuinka monta ovea? Laske vain asennetut ovet; Älä laske avoimia aukkoja.',
        )
        for question in questions:
            with self.subTest(question=question):
                self.assertEqual([part.question for part in parts(question)], [question])

    def test_independent_inventory_questions_still_split(self):
        for question, expected in (
            ('How many windows? How many doors?', ['How many windows?', 'How many doors?']),
            ('Kuinka monta ikkunaa? Kuinka monta ovea?', ['Kuinka monta ikkunaa?', 'Kuinka monta ovea?']),
            ('How many windows and how many doors?', ['How many windows', 'how many doors?']),
            ('How many windows? Count doors.', ['How many windows?', 'Count doors.']),
        ):
            with self.subTest(question=question):
                self.assertEqual([part.question for part in parts(question)], expected)

    def test_rule_stays_with_its_own_part_in_a_compound_request(self):
        question = 'How many doors? Exclude open doorways; How many windows? Only count exterior windows.'
        actual = parts(question)
        self.assertEqual([part.question for part in actual], [
            'How many doors? Exclude open doorways;', 'How many windows? Only count exterior windows.'])

    def test_quoted_source_identifiers_are_literal(self):
        for quote in ('"A? B"', '«A? B»', '“A? B”', "'A? B'", '"A and show B"'):
            question = f'How many rooms named {quote}?'
            with self.subTest(quote=quote):
                actual = parts(question)
                self.assertEqual(len(actual), 1)
                self.assertEqual(actual[0].question, question)
                self.assertEqual(actual[0].literal_identifiers, ['A and show B' if 'show' in quote else 'A? B'])

    def test_explicit_parts_remain_authoritative(self):
        explicit = [m.AnswerRequestedPart(key='doors',question='Count doors',exclusions=['open doorways'])]
        self.assertEqual(parts('How many doors? How many windows?', parts=explicit), explicit)


class CountingRuleApiTests(unittest.IsolatedAsyncioTestCase):
    setUp = answer_tests.DrawingAnswerApiTests.setUp
    api = answer_tests.DrawingAnswerApiTests.api
    register = answer_tests.DrawingAnswerApiTests.register
    ask = answer_tests.DrawingAnswerApiTests.ask

    async def test_supplied_rule_uses_one_scan_and_retains_overlay(self):
        questions = (
            'How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count.',
            'Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ovi; pelkkiä oviaukkoja ilman ovilehteä ei lasketa.',
        )
        async with self.api() as client:
            for question in questions:
                session = await self.register(client)
                response = await self.ask(client, session, question)
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(len(body['parts']), 1)
                self.assertEqual(body['interpretation']['requested_parts'][0]['question'], question)
                self.assertEqual(body['metrics']['external_attempts'], 1)
                self.assertIsNotNone(body['candidate_response'])
        self.assertEqual(len(self.requests), 2)


if __name__ == '__main__':
    unittest.main()

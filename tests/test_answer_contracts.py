"""Answer presentation must preserve executed scope, values and uncertainty."""
from copy import deepcopy
import hashlib
import unittest

from pydantic import ValidationError

from answer_api.adapters import candidate_part
from answer_api.realize import realize_answer, with_narrative
from contracts import models as m
from contracts.validation import validate_answer
from tests.fixtures import bundle_data, plan_data, result_data
from tests.test_image_candidate_contracts import candidate_response_data


def drawing_answer(empty=False):
    data = candidate_response_data()
    if empty:
        data["candidates"] = []
    candidate = m.ImageCandidateResponse.model_validate(data)
    source = m.AnswerSourceBinding(source_id="source:test", kind="image", scope_label="selected drawing",
        source_sha256="f" * 64, source_revision="f" * 64, display_sha256="a" * 64,
        display_width=1600, display_height=1200)
    part, context = candidate_part(candidate, source, candidate.request_id)
    question = "How many windows?"
    return with_narrative(m.AnswerResponse(request_id=candidate.request_id, question=question,
        question_sha256=hashlib.sha256(question.encode()).hexdigest(), source=source,
        interpretation=m.AnswerIntent(scope_label=source.scope_label,
            requested_parts=[m.AnswerRequestedPart(key="answer", question=question)]),
        parts=[part], evidence_contexts=[context], candidate_response=candidate,
        metrics=m.AnswerMetrics(elapsed_ms=12.5, external_attempts=1)))


def quantity_answer():
    result = m.QueryResult.model_validate(result_data())
    source = m.AnswerSourceBinding(source_id="source:cad", kind="dxf", scope_label="room 7.16",
        source_sha256="a" * 64, source_revision="A")
    question = "What is the net area of 7.16?"
    return with_narrative(m.AnswerResponse(request_id=result.request_id, question=question,
        question_sha256=hashlib.sha256(question.encode()).hexdigest(), source=source,
        interpretation=m.AnswerIntent(scope_label=source.scope_label,
            requested_parts=[m.AnswerRequestedPart(key="area", question=question)]),
        parts=[m.AnswerPart(key="area", status="answered", result=result,
            plan=m.QueryPlan.model_validate(plan_data()), evidence_context_id="context:cad")],
        evidence_contexts=[m.AnswerEvidenceContext(id="context:cad", bundle=m.KnowledgeBundle.model_validate(bundle_data()))],
        metrics=m.AnswerMetrics(elapsed_ms=1, model_input_tokens=0, model_output_tokens=0)))


class AnswerContractsTests(unittest.TestCase):
    def test_candidates_remain_partial_with_clickable_original_label(self):
        answer = drawing_answer()
        validate_answer(answer)
        self.assertEqual(answer.parts[0].status, "partial")
        self.assertEqual(answer.parts[0].result.claims[0].quality, "estimated")
        self.assertIn("total is not confirmed", answer.narrative[0].text)
        anchor = answer.evidence_contexts[0].bundle.anchors[0]
        self.assertEqual(anchor.selector.value, "candidate-001")
        self.assertEqual(anchor.quote.text, "121.A")
        self.assertIn(anchor.id, answer.narrative[0].anchor_ids)

    def test_empty_scan_never_answers_zero(self):
        answer = drawing_answer(empty=True)
        validate_answer(answer)
        self.assertEqual(answer.parts[0].status, "incomplete_coverage")
        self.assertFalse(answer.parts[0].result.claims)
        self.assertIn("does not establish", answer.narrative[0].text)

    def test_quantity_keeps_value_unit_basis_and_scope(self):
        answer = quantity_answer()
        validate_answer(answer)
        text = answer.narrative[0].text
        for expected in ("19", "m2", "net", "7.16"):
            self.assertIn(expected, text)

    def test_text_edits_numbers_qualifiers_and_citations_are_rejected(self):
        original = drawing_answer()
        for mutation in (
            lambda answer: setattr(answer.narrative[0], "text", "There are exactly 5 windows."),
            lambda answer: setattr(answer.narrative[0], "qualification", "exact"),
            lambda answer: setattr(answer.narrative[0], "anchor_ids", ["invented-anchor"]),
            lambda answer: setattr(answer.narrative[0], "claim_ids", ["invented-claim"]),
        ):
            changed = deepcopy(original)
            mutation(changed)
            with self.assertRaises(ValueError):
                validate_answer(changed)

    def test_candidate_cannot_become_lower_bound(self):
        answer = drawing_answer()
        answer.parts[0].result.claims[0].quality = "lower_bound"
        answer.parts[0].result.calculations[0].quality = "lower_bound"
        answer = with_narrative(answer)
        with self.assertRaisesRegex(ValueError, "candidates"):
            validate_answer(answer)

    def test_stale_source_revision_or_question_is_rejected(self):
        answer = quantity_answer()
        answer.source.source_revision = "another revision"
        with self.assertRaisesRegex(ValueError, "revision"):
            validate_answer(answer)
        answer = drawing_answer()
        answer.question = "Different question"
        with self.assertRaises(ValueError):
            validate_answer(answer)

    def test_compound_evidence_binds_display_without_legacy_overlay(self):
        for field, value in (('display_sha256', 'b' * 64), ('page_index', 25), ('rotation', 90)):
            answer = drawing_answer()
            answer.candidate_response = None
            setattr(answer.source, field, value)
            with self.assertRaisesRegex(ValueError, 'snapshot|display'):
                validate_answer(with_narrative(answer))

    def test_missing_requested_part_is_rejected(self):
        data = drawing_answer().model_dump(mode="python")
        data["interpretation"]["requested_parts"].append({"key": "missing", "question": "And its area?"})
        with self.assertRaises(ValidationError):
            m.AnswerResponse.model_validate(data)

    def test_partial_compound_keeps_independent_success_and_missing_part(self):
        answer = quantity_answer()
        answer.interpretation.requested_parts.append(m.AnswerRequestedPart(key="price", question="And the cost?"))
        answer.parts.append(m.AnswerPart(key="price", status="missing_information",
            message=m.LocalizedText(text="The source contains no price factor.")))
        answer = with_narrative(answer)
        validate_answer(answer)
        self.assertEqual({sentence.part_key for sentence in answer.narrative}, {"area", "price"})
        self.assertEqual(answer.parts[0].status, "answered")

    def test_failed_dependency_cannot_supply_exact_output(self):
        answer = quantity_answer()
        answer.interpretation.requested_parts.insert(0, m.AnswerRequestedPart(key="input", question="Price factor?"))
        answer.interpretation.requested_parts[1].depends_on = ["input"]
        answer.parts[0].depends_on = ["input"]
        answer.parts.insert(0, m.AnswerPart(key="input", status="missing_information",
            message=m.LocalizedText(text="Price factor is missing.")))
        answer = with_narrative(answer)
        with self.assertRaisesRegex(ValueError, "dependent output"):
            validate_answer(answer)

    def test_language_templates_do_not_translate_original_labels(self):
        answer = quantity_answer()
        for language, scope in (("fi", "Rajaus"), ("de", "Umfang"), ("fr", "Périmètre"), ("it", "Ambito")):
            answer.interpretation.language = language
            text = realize_answer(answer)[0].text
            self.assertIn(scope, text)
            self.assertIn("7.16", text)

    def test_budget_and_stream_payload_constraints(self):
        with self.assertRaises(ValidationError):
            m.AnswerMetrics(elapsed_ms=1, external_attempts=16)
        with self.assertRaises(ValidationError):
            m.AnswerStreamEvent(type="result", error=m.ImageCandidateError(
                request_id="request", code="failure", message="Unavailable", retryable=False))


if __name__ == "__main__":
    unittest.main()

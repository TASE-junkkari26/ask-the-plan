"""Offline manifest/scoring checks; these fixtures establish no model accuracy."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from experiments.answers.audit_sources import MAX_NATIVE_BYTES, inspect_source
from experiments.answers.evaluate import compare_numbers, evaluate, score_files
from experiments.answers.manifest import build_manifest, safe_source


def classified(path, question='How many windows?', family='Count / Windows', line=1):
    return SimpleNamespace(path=path, question=question, family=family, line=line,
        source=Path(path).parts[1], answer_type='count', template=question)


def fixture(number=7, quality='exact', status='answered', operation='count', unit='count'):
    question = 'How many windows?' if operation == 'count' else 'What is the net area?'
    case = {'case_id': 'qa:case', 'jsonl_line': 1, 'path': 'data/cubicasa5k/plan.png',
        'source_sha256': 'a' * 64, 'question': question, 'question_sha256': hashlib.sha256(question.encode()).hexdigest(),
        'stored_answer_type': 'text', 'family': operation.title() + ' / Test', 'operation': operation,
        'language_hint': 'en', 'project_hint': 'project:fixture', 'leakage_group': 'group:fixture'}
    value = {'kind': 'count', 'value': number} if unit == 'count' else {
        'kind': 'quantity', 'magnitude': str(number), 'unit_id': 'unit:test', 'basis': 'net', 'quality': quality}
    policy = {'grain': 'occurrence', 'hierarchy': 'all_matches', 'rule_key': 'fixture'}
    scope = {'project_id': 'p', 'document_ids': ['d'], 'universe': 'modeled_objects'}
    claim = {'id': 'claim', 'output_key': 'answer', 'value': value, 'quality': quality, 'scope': scope,
        'count_policy': policy, 'coverage_ids': ['coverage'], 'concept_ids': [],
        'evidence': [{'value_path': '', 'calculation_id': 'calculation', 'anchor_ids': ['anchor'], 'evidence_kind': 'verified'}]}
    answer = {'request_id': 'request', 'question_sha256': case['question_sha256'],
        'source': {'source_sha256': 'a' * 64}, 'interpretation': {'requested_parts': [{'key': 'answer'}]},
        'parts': [{'key': 'answer', 'status': status, 'evidence_context_id': 'context',
            'plan': {'id': 'plan', 'request_id': 'request', 'outputs': {'answer': 'step'}},
            'result': {'request_id': 'request', 'plan_id': 'plan', 'claims': [claim], 'calculations': [
                {'id': 'calculation', 'plan_step_id': 'step', 'operation': 'count', 'output': value}]}}],
        'evidence_contexts': [{'id': 'context', 'bundle': {'assets': [{'id': 'asset', 'sha256': 'a' * 64}],
            'anchors': [{'id': 'anchor'}], 'facts': [], 'units': [{'id': 'unit:test', 'symbol': unit}],
            'coverage': [{'id': 'coverage', 'scope': scope, 'count_policy': policy, 'concept_ids': [], 'completeness': 'complete'}]}}],
        'narrative': [{'part_key': 'answer', 'claim_ids': ['claim']}],
        'metrics': {'external_attempts': 0, 'model_input_tokens': 0, 'model_output_tokens': None, 'elapsed_ms': 10,
                    'cost_amount': '0', 'cost_currency': 'USD'}}
    manifest = {'cases': [case], 'assets': [{'path': case['path'], 'sha256': 'a' * 64}], 'links': []}
    reference = {'path': case['path'], 'question': question, 'type': 'text', 'answer': 'There are 7 windows.', 'unit': None}
    return manifest, {'qa:case': {'case_id': 'qa:case', 'answer': answer}}, {1: reference}


class AnswerManifestTests(unittest.TestCase):
    def test_reference_free_cases_group_translations_formats_and_duplicate_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory)
            first = 'data/ifc_models/model_plan-01-ground.pdf'
            native = 'data/ifc_models/model.ifc'
            duplicate = 'data/ifc_bench/renamed_arc.ifc'
            for relative, content in ((first, b'PDF'), (native, b'IFC'), (duplicate, b'IFC')):
                path = dataset / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            rows = [classified(first), classified(first, 'Wie viele Fenster?', line=2), classified(duplicate, line=3)]
            manifest = build_manifest(dataset, rows)
            self.assertFalse(manifest['reference_answers_used'])
            self.assertEqual(len({case['leakage_group'] for case in manifest['cases']}), 1)
            self.assertEqual(len({case['proposed_split'] for case in manifest['cases']}), 1)
            self.assertIn(native, {asset['path'] for asset in manifest['assets']})
            self.assertTrue(any(link['kind'] == 'byte_duplicate' for link in manifest['links']))
            self.assertTrue(all('answer' not in case and 'reference_value' not in case for case in manifest['cases']))

    def test_swiss_floors_in_same_site_share_a_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ['data/swiss_dwellings/site9_bldg1_floor1.pdf', 'data/swiss_dwellings/site9_bldg2_floor2.pdf']
            for index, relative in enumerate(paths):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(index))
            manifest = build_manifest(root, [classified(path, line=index + 1) for index, path in enumerate(paths)])
            self.assertEqual(len({case['leakage_group'] for case in manifest['cases']}), 1)

    def test_outside_source_paths_and_unproven_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ('../outside.ifc', '/tmp/outside.ifc', 'C:/outside.ifc'):
                with self.assertRaises(ValueError):
                    safe_source(root, path)
            with self.assertRaises(ValueError):
                build_manifest(root, [], explicit_links=[{'source': 'a', 'target': 'b'}])

    def test_size_limited_audit_does_not_establish_missing_information(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'data/ifc_bench/large.ifc'
            path.parent.mkdir(parents=True)
            with path.open('wb') as stream:
                stream.truncate(MAX_NATIVE_BYTES + 1)
            result = inspect_source(root, {'path': 'data/ifc_bench/large.ifc', 'sha256': '0' * 64,
                'format': 'ifc', 'available': True})
            self.assertEqual(result['status'], 'not_inspected_size_limit')
            self.assertFalse(result['information_absence_established'])


class SavedAnswerEvaluationTests(unittest.TestCase):
    def test_numeric_claim_inside_reference_text_is_scored_exactly_for_counts(self):
        manifest, saved, references = fixture()
        report = evaluate(manifest, saved, references)
        self.assertTrue(report['cases'][0]['raw_reference_agreement'])
        self.assertTrue(report['cases'][0]['strict_pass'])
        saved['qa:case']['answer']['parts'][0]['result']['claims'][0]['value']['value'] = 8
        saved['qa:case']['answer']['parts'][0]['result']['calculations'][0]['output']['value'] = 8
        self.assertFalse(evaluate(manifest, saved, references)['cases'][0]['strict_pass'])

    def test_quantities_convert_units_before_two_percent_tolerance(self):
        def number(value, unit):
            return {'number': Decimal(value), 'unit': unit, 'typed': True}
        self.assertTrue(compare_numbers([number('1', 'm2')], [number('10100', 'cm2')], operation='area')[0])
        self.assertFalse(compare_numbers([number('1', 'm2')], [number('1.021', 'm2')], operation='area')[0])
        self.assertFalse(compare_numbers([number('1', 'm2')], [number('1', 'm')], operation='area')[0])
        self.assertFalse(compare_numbers([number('7', 'count')], [number('7.01', 'count')], operation='count')[0])
        self.assertFalse(compare_numbers([number('0', 'm2')], [number('0.001', 'm2')], operation='area')[0])

    def test_numeric_text_with_attached_units_cannot_bypass_scoring(self):
        manifest, saved, references = fixture(number='102', operation='area', unit='cm2')
        references[1]['answer'] = 'The area is 0.01m².'
        report = evaluate(manifest, saved, references)
        self.assertTrue(report['cases'][0]['raw_reference_agreement'])
        saved['qa:case']['answer']['parts'][0]['result']['claims'][0]['value']['magnitude'] = '103'
        saved['qa:case']['answer']['parts'][0]['result']['calculations'][0]['output']['magnitude'] = '103'
        self.assertFalse(evaluate(manifest, saved, references)['cases'][0]['raw_reference_agreement'])

    def test_qualified_match_is_not_scored_as_an_exact_answer(self):
        manifest, saved, references = fixture(quality='estimated', status='partial')
        report = evaluate(manifest, saved, references)
        self.assertTrue(report['cases'][0]['raw_reference_agreement'])
        self.assertFalse(report['cases'][0]['strict_pass'])
        self.assertEqual(report['row_weighted']['statuses'], {'partial': 1})

    def test_matching_area_number_with_wrong_net_gross_basis_fails(self):
        manifest, saved, references = fixture(number='1', operation='area', unit='m2')
        references[1]['answer'] = 'The net area is 1 m².'
        saved['qa:case']['answer']['parts'][0]['result']['claims'][0]['value']['basis'] = 'gross'
        saved['qa:case']['answer']['parts'][0]['result']['calculations'][0]['output']['basis'] = 'gross'
        result = evaluate(manifest, saved, references)['cases'][0]
        self.assertTrue(result['raw_reference_agreement'])
        self.assertFalse(result['strict_pass'])
        self.assertIn('quantity_basis_unresolved_or_mismatched', result['evidence_errors'])

    def test_correct_number_with_bad_evidence_fails_structural_check(self):
        manifest, saved, references = fixture()
        saved['qa:case']['answer']['parts'][0]['result']['claims'][0]['evidence'][0]['anchor_ids'] = ['invented']
        result = evaluate(manifest, saved, references)['cases'][0]
        self.assertTrue(result['raw_reference_agreement'])
        self.assertFalse(result['strict_pass'])
        self.assertIn('unresolved_claim_evidence', result['evidence_errors'])

    def test_not_run_cases_remain_in_family_project_and_row_denominators(self):
        manifest, saved, references = fixture()
        missing = {**manifest['cases'][0], 'case_id': 'qa:missing', 'jsonl_line': 2,
                   'family': 'Count / Rare family', 'leakage_group': 'group:other'}
        manifest['cases'].append(missing)
        report = evaluate(manifest, saved, references)
        self.assertEqual(report['row_weighted']['total'], 2)
        self.assertEqual(report['row_weighted']['attempted'], 1)
        self.assertEqual(report['row_weighted']['statuses']['not_run'], 1)
        self.assertEqual(report['family_weighted_strict_pass_rate_all_cases'], .5)
        self.assertEqual(report['project_weighted_strict_pass_rate_all_cases'], .5)
        self.assertEqual(report['cost_latency']['output_usage_unknown_cases'], 1)
        self.assertEqual(report['cost_latency']['model_input_tokens_known'], 0)

    def test_reference_disputes_preserve_raw_result_and_require_source_evidence(self):
        manifest, saved, references = fixture(number=8)
        dispute = {'reason': 'Source review found a reference discrepancy.', 'source_sha256': 'a' * 64,
                   'evidence_locator': 'page0:window7'}
        result = evaluate(manifest, saved, references, {'qa:case': dispute})['cases'][0]
        self.assertEqual(result['status'], 'disputed')
        self.assertFalse(result['raw_reference_agreement'])
        self.assertEqual(references[1]['answer'], 'There are 7 windows.')
        with self.assertRaises(ValueError):
            evaluate(manifest, saved, references, {'qa:case': {'reason': 'unsupported disagreement'}})

    def test_scorer_requires_saved_outputs_before_opening_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = root / 'outputs.jsonl'
            outputs.write_text('')
            with self.assertRaisesRegex(ValueError, 'Save nonempty'):
                score_files(root / 'missing-manifest.json', outputs, root / 'absent-qa.jsonl')

    def test_frozen_reference_binding_and_duplicate_output_checks(self):
        manifest, saved, references = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_payload = json.dumps(references[1]) + '\n'
            manifest['questions_sha256'] = hashlib.sha256(reference_payload.encode()).hexdigest()
            manifest_path, outputs_path, refs_path = (root / name for name in ('manifest.json', 'outputs.jsonl', 'questions.jsonl'))
            manifest_path.write_text(json.dumps(manifest))
            outputs_path.write_text(json.dumps(saved['qa:case']) + '\n')
            refs_path.write_text(reference_payload)
            report = score_files(manifest_path, outputs_path, refs_path)
            self.assertTrue(report['inputs']['references_opened_after_saved_outputs'])
            refs_path.write_text(reference_payload + '\n')
            with self.assertRaisesRegex(ValueError, 'bytes differ'):
                score_files(manifest_path, outputs_path, refs_path)
            outputs_path.write_text((json.dumps(saved['qa:case']) + '\n') * 2)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                score_files(manifest_path, outputs_path, refs_path)


if __name__ == '__main__':
    unittest.main()

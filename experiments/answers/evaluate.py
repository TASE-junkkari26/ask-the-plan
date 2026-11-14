"""Score frozen saved answers, then open reference QA in a separate offline step.

Usage: python -m experiments.answers.evaluate --manifest build/answers/manifest.json
       --outputs build/answers/outputs.jsonl --references DATASET/questions.jsonl
       --report build/answers/evaluation.json

Each output line is {"case_id": "qa:...", "answer": <saved AnswerResponse>} or
{"case_id": "qa:...", "error": {"code": "..."}}. Runtime services never receive
the manifest, case IDs, reference answers or this scorer.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean

UNITS = {
    '1': ('number', Decimal(1)), '%': ('number', Decimal('.01')),
    'count': ('count', Decimal(1)), 'pcs': ('count', Decimal(1)),
    'm': ('length', Decimal(1)), 'mm': ('length', Decimal('.001')), 'cm': ('length', Decimal('.01')),
    'ft': ('length', Decimal('.3048')), 'in': ('length', Decimal('.0254')),
    'm2': ('area', Decimal(1)), 'mm2': ('area', Decimal('.000001')), 'cm2': ('area', Decimal('.0001')),
    'ft2': ('area', Decimal('.09290304')),
    'm3': ('volume', Decimal(1)), 'mm3': ('volume', Decimal('.000000001')), 'ft3': ('volume', Decimal('.028316846592')),
    'kg': ('mass', Decimal(1)), 'g': ('mass', Decimal('.001')),
    'eur': ('currency:EUR', Decimal(1)), 'usd': ('currency:USD', Decimal(1)),
}
NUMBER = r'(?<![\w.#])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?(?:[eE][-+]?\d+)?(?![\d.])'
NUMERIC = re.compile('(' + NUMBER + r')\s*(mm[²³23]|cm[²2]|m[²³23]|ft[²³23]|mm|cm|kg|pcs|count|EUR|USD|ft|in|m|g|%|€|\$)?', re.I)


def normalize_unit(value):
    if value is None:
        return None
    unit = str(value).strip().lower().replace('²', '2').replace('³', '3').replace('^', '').replace(' ', '').replace('€', 'eur').replace('$', 'usd')
    return None if unit in {'', '-', 'none', 'null'} else unit


def decimal_number(value):
    text = str(value)
    if ',' in text:
        text = text.replace(',', '') if re.fullmatch(r'[-+]?\d{1,3}(,\d{3})+(\.\d+)?', text) else text.replace(',', '.')
    number = Decimal(text)
    if not number.is_finite():
        raise ValueError('Nonfinite numeric reference or result')
    return number


def _numeric_reference(value, unit, operation):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float, Decimal)):
        return [{'number': decimal_number(value), 'unit': normalize_unit(unit), 'typed': True}]
    if isinstance(value, str):
        return [{'number': decimal_number(match.group(1)),
                 'unit': normalize_unit(match.group(2) or unit), 'typed': False}
                for match in NUMERIC.finditer(value)]
    if isinstance(value, list):
        return [item for child in value for item in _numeric_reference(child, unit, operation)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _numeric_reference(child, unit, operation)]
    return []


def _numeric_values(value, units):
    kind = value.get('kind')
    if kind == 'count':
        return [{'number': decimal_number(value['value']), 'unit': 'count', 'typed': True}]
    if kind == 'quantity':
        unit = units.get(value.get('unit_id'), {})
        return [{'number': decimal_number(value['magnitude']), 'unit': normalize_unit(unit.get('symbol')),
                 'si_multiplier': unit.get('si_multiplier'), 'dimension': unit.get('dimension'),
                 'basis': value.get('basis'), 'typed': True}]
    if kind == 'text':
        return _numeric_reference(value.get('value', {}).get('text', ''), None, None)
    identifiers = {'label', 'name', 'id', 'entity_id', 'step_id', 'ifc_guid', 'room_id', 'room_number'}
    children = (value.get('items', []) if kind == 'list' else [child for key, child in value.get('fields', {}).items() if key not in identifiers] if kind == 'record'
                else [child for row in value.get('rows', []) for key, child in row.items() if key not in identifiers] if kind == 'table' else [])
    return [number for child in children for number in _numeric_values(child, units)]


def _canonical(item, *, operation):
    unit = item.get('unit')
    if unit in UNITS:
        dimension, multiplier = UNITS[unit]
        if operation == 'count' and dimension == 'number':
            dimension = 'count'
        return item['number'] * multiplier, dimension
    if unit is None and operation == 'count':
        return item['number'], 'count'
    if item.get('dimension') is not None and item.get('si_multiplier') is not None:
        dimensions = {(1, 0, 0, 0, 0, 0, 0): 'length', (2, 0, 0, 0, 0, 0, 0): 'area',
                      (3, 0, 0, 0, 0, 0, 0): 'volume', (0, 1, 0, 0, 0, 0, 0): 'mass',
                      (0, 0, 0, 0, 0, 0, 0): 'number'}
        dimension = dimensions.get(tuple(item['dimension']))
        if dimension:
            return item['number'] * Decimal(item['si_multiplier']), dimension
    return None


def compare_numbers(expected, actual, *, operation, tolerance=Decimal('.02')):
    """Unordered numeric matching, with dimensions before tolerance.

    Multiple free-text numbers need source review for field association even if
    their multiset agrees; this function only reports raw numeric agreement.
    """
    if len(expected) != len(actual) or not expected:
        return False, 'numeric_claim_count_mismatch'
    left = [_canonical(item, operation=operation) for item in expected]
    right = [_canonical(item, operation=operation) for item in actual]
    if any(item is None for item in [*left, *right]):
        return None, 'unit_or_dimension_unresolved'
    unmatched = list(right)
    for value, dimension in left:
        def same(candidate):
            number, actual_dimension = candidate
            if dimension != actual_dimension:
                return False
            if operation == 'count' or dimension == 'count':
                return number == value
            return number == value if value == 0 else abs(number - value) / abs(value) <= tolerance
        index = next((index for index, candidate in enumerate(unmatched) if same(candidate)), None)
        if index is None:
            return False, 'numeric_value_or_dimension_mismatch'
        unmatched.pop(index)
    return True, 'exact_count_or_numeric_tolerance_match'


def _typed_leaves(value):
    yield value
    if value.get('kind') == 'list':
        children = value.get('items', [])
    elif value.get('kind') == 'record':
        children = value.get('fields', {}).values()
    elif value.get('kind') == 'table':
        children = [child for row in value.get('rows', []) for child in row.values()]
    else:
        children = []
    for child in children:
        yield from _typed_leaves(child)


def evidence_structure(answer, case, manifest):
    """Check saved provenance links, not real-world correctness/localization."""
    errors = []
    if answer.get('question_sha256') != case['question_sha256']:
        errors.append('question_binding_mismatch')
    allowed_paths = {case['path']}
    changed = True
    while changed:
        changed = False
        for link in manifest.get('links', []):
            if link['kind'] not in {'same_drawing_declared_by_dataset', 'floor_render_declared_by_dataset', 'byte_duplicate', 'explicit_evaluation_link'}:
                continue
            if link['source'] in allowed_paths and link['target'] not in allowed_paths:
                allowed_paths.add(link['target'])
                changed = True
    allowed_hashes = {asset['sha256'] for asset in manifest.get('assets', []) if asset['path'] in allowed_paths and asset.get('sha256')}
    if answer.get('source', {}).get('source_sha256') not in allowed_hashes:
        errors.append('source_binding_unverified_or_mismatched')
    contexts = {context['id']: context.get('bundle', {}) for context in answer.get('evidence_contexts', [])}
    requested = {part['key'] for part in answer.get('interpretation', {}).get('requested_parts', [])}
    parts = answer.get('parts', [])
    if requested != {part.get('key') for part in parts} or len({part.get('key') for part in parts}) != len(parts):
        errors.append('requested_part_accounting_mismatch')
    claims_by_part = {}
    for part in parts:
        result, plan = part.get('result') or {}, part.get('plan') or {}
        if part.get('status') in {'answered', 'partial'} and not result.get('claims'):
            errors.append('successful_part_without_claims')
        bundle = contexts.get(part.get('evidence_context_id'), {})
        if result.get('claims'):
            if answer.get('source', {}).get('source_sha256') not in {asset.get('sha256') for asset in bundle.get('assets', [])}:
                errors.append('evidence_context_original_hash_mismatch')
            if result.get('request_id') != answer.get('request_id') or plan.get('request_id') != answer.get('request_id') or result.get('plan_id') != plan.get('id'):
                errors.append('result_request_plan_identity_mismatch')
        anchors = {anchor['id'] for anchor in bundle.get('anchors', [])}
        facts = {fact['id'] for fact in bundle.get('facts', [])}
        coverage = {item['id']: item for item in bundle.get('coverage', [])}
        nodes = {node['id']: node for node in result.get('calculations', [])}
        sets = {item['id']: item for item in result.get('entity_sets', [])}
        claims_by_part[part.get('key')] = {claim['id'] for claim in result.get('claims', [])}
        for item in sets.values():
            members = item.get('entity_ids')
            if members is not None and (len(set(members)) != len(members) or len(members) != item.get('count')):
                errors.append('included_set_cardinality_mismatch')
        for claim in result.get('claims', []):
            roots = [binding for binding in claim.get('evidence', []) if binding.get('value_path', '') == '']
            if not roots:
                errors.append('missing_root_claim_evidence')
            for binding in claim.get('evidence', []):
                if not set(binding.get('anchor_ids', [])) <= anchors or not set(binding.get('fact_ids', [])) <= facts:
                    errors.append('unresolved_claim_evidence')
            for binding in roots:
                node = nodes.get(binding.get('calculation_id'))
                if not node or node.get('output') != claim.get('value') or node.get('plan_step_id') != plan.get('outputs', {}).get(claim.get('output_key')):
                    errors.append('claim_calculation_binding_mismatch')
                if binding.get('evidence_kind') == 'candidate' and claim.get('quality') in {'exact', 'lower_bound'}:
                    errors.append('candidate_promoted_to_exact_or_lower_bound')
            if any(value.get('kind') in {'count', 'quantity'} for value in _typed_leaves(claim.get('value', {}))) and claim.get('quality') == 'exact':
                matching = [coverage[key] for key in claim.get('coverage_ids', []) if key in coverage
                            and coverage[key].get('scope') == claim.get('scope')
                            and set(claim.get('concept_ids', [])) <= set(coverage[key].get('concept_ids', []))
                            and set(claim.get('property_keys', [])) <= set(coverage[key].get('property_keys', []))
                            and (not claim.get('count_policy') or claim['count_policy'] == coverage[key].get('count_policy'))]
                if not any(item.get('completeness') == 'complete' for item in matching):
                    errors.append('exact_numeric_claim_without_complete_matching_coverage')
                if case['operation'] == 'count' and not claim.get('count_policy'):
                    errors.append('numeric_count_without_counting_grain')
    for sentence in answer.get('narrative', []):
        if not set(sentence.get('claim_ids', [])) <= claims_by_part.get(sentence.get('part_key'), set()):
            errors.append('narrative_claim_reference_mismatch')
    return not errors, sorted(set(errors))


def _status(parts):
    statuses = [part.get('status') for part in parts]
    if statuses and all(status == 'answered' for status in statuses):
        return 'answered'
    if any(status in {'answered', 'partial'} for status in statuses):
        return 'partial'
    for value, report in [('missing_source', 'missing_source'), ('unsupported_operation', 'unsupported'),
                          ('missing_information', 'missing_information'), ('needs_clarification', 'needs_clarification')]:
        if value in statuses:
            return report
    return 'failed'


def score_case(case, saved, reference, manifest, dispute=None):
    if saved is None:
        return {'case_id': case['case_id'], 'status': 'not_run', 'strict_pass': False, 'raw_reference_agreement': None}
    answer = saved.get('answer')
    if not isinstance(answer, dict):
        return {'case_id': case['case_id'], 'status': 'failed', 'strict_pass': False,
                'raw_reference_agreement': None, 'reason': saved.get('error', {}).get('code', 'missing_answer')}
    status = _status(answer.get('parts', []))
    evidence_ok, errors = evidence_structure(answer, case, manifest)
    actual, qualities, texts = [], [], []
    contexts = {item['id']: item.get('bundle', {}) for item in answer.get('evidence_contexts', [])}
    for part in answer.get('parts', []):
        units = {unit['id']: unit for unit in contexts.get(part.get('evidence_context_id'), {}).get('units', [])}
        for claim in (part.get('result') or {}).get('claims', []):
            actual.extend(_numeric_values(claim['value'], units))
            qualities.append(claim.get('quality'))
            texts.extend(value.get('value', {}).get('text', '') for value in _typed_leaves(claim['value']) if value.get('kind') == 'text')
    expected = _numeric_reference(reference.get('answer'), reference.get('unit'), case['operation'])
    semantic_review = False
    if expected:
        raw_match, reason = compare_numbers(expected, actual, operation=case['operation'])
        semantic_review = len(expected) > 1 or any(not item['typed'] for item in actual)
        if semantic_review:
            reason += '; numeric associations or text-valued claims require source review'
    else:
        normalize = lambda text: ' '.join(str(text).casefold().split())
        raw_match = any(normalize(text) == normalize(reference.get('answer')) for text in texts)
        reason = 'descriptive_factual_clauses_require_source_review'
        semantic_review = True
    requested_basis = ' '.join((case.get('family', ''), case.get('question', ''))).casefold()
    net = bool(re.search(r'\bnet(?:to|ta|te)?\b', requested_basis))
    gross = bool(re.search(r'\b(?:gross|brutto|brut|bruta|brute)\b', requested_basis))
    if net != gross and actual and case['operation'] in {'area', 'length', 'volume'}:
        expected_basis = 'net' if net else 'gross'
        for item in actual:
            if 'basis' in item and expected_basis not in item['basis'].casefold():
                errors.append('quantity_basis_unresolved_or_mismatched')
                evidence_ok = False
    result = {'case_id': case['case_id'], 'status': status, 'raw_reference_agreement': raw_match,
        'strict_pass': bool(raw_match and evidence_ok and status == 'answered' and all(item == 'exact' for item in qualities) and not semantic_review),
        'numeric_reference_claims': len(expected), 'numeric_output_claims': len(actual),
        'evidence_structural_pass': evidence_ok, 'evidence_errors': errors,
        'source_review_required': semantic_review, 'source_localization_reviewed': False, 'reason': reason,
        'latency_phase': saved.get('phase', 'unspecified'), 'metrics': answer.get('metrics', {})}
    if dispute is not None:
        if not dispute.get('reason') or not dispute.get('source_sha256') or not dispute.get('evidence_locator'):
            raise ValueError('Reference disputes require source hash, locator and a reason')
        if dispute['source_sha256'] not in {asset.get('sha256') for asset in manifest['assets']}:
            raise ValueError('Reference dispute belongs to an unregistered source')
        result['original_status'] = status
        result['status'] = 'disputed'
        result['dispute'] = dispute
        result['strict_pass'] = False  # Preserve raw reference agreement; never rewrite reference QA.
    return result


def _summary(rows):
    attempted = [row for row in rows if row['status'] != 'not_run']
    scored = [row for row in rows if row.get('raw_reference_agreement') is not None]
    correct = sum(row['strict_pass'] for row in rows)
    return {'total': len(rows), 'attempted': len(attempted), 'scored_against_reference': len(scored),
            'statuses': dict(sorted(Counter(row['status'] for row in rows).items())),
            'strict_numeric_and_structural_passes': correct,
            'strict_pass_rate_all_cases': correct / len(rows) if rows else None,
            'strict_pass_rate_attempted': correct / len(attempted) if attempted else None,
            'raw_reference_agreements': sum(row.get('raw_reference_agreement') is True for row in scored),
            'raw_reference_agreement_rate_scored': sum(row.get('raw_reference_agreement') is True for row in scored) / len(scored) if scored else None,
            'source_review_required': sum(row.get('source_review_required', False) for row in rows),
            'evidence_structure_failures': sum(row.get('evidence_structural_pass') is False for row in rows)}


def evaluate(manifest: dict, saved: dict, references: dict, disputes=None) -> dict:
    cases = manifest['cases']
    known_ids = {case['case_id'] for case in cases}
    if not saved.keys() <= known_ids:
        raise ValueError('Saved outputs include cases absent from the frozen manifest')
    results = []
    for case in cases:
        reference = references.get(case['jsonl_line'], {})
        if case['case_id'] in saved and not reference:
            raise ValueError('A saved output has no corresponding reference row')
        if reference and (reference.get('path', '').replace('\\', '/') != case['path'] or reference.get('question') != case['question']):
            raise ValueError('Reference QA row does not match the frozen path and question')
        result = score_case(case, saved.get(case['case_id']), reference, manifest, (disputes or {}).get(case['case_id']))
        results.append({**result, 'family': case['family'], 'project_hint': case['project_hint'],
                        'leakage_group': case['leakage_group'], 'language_hint': case['language_hint']})
    by_family, by_project = defaultdict(list), defaultdict(list)
    for result in results:
        by_family[result['family']].append(result)
        by_project[result['leakage_group']].append(result)
    families = {key: _summary(rows) for key, rows in sorted(by_family.items())}
    projects = {key: _summary(rows) for key, rows in sorted(by_project.items())}
    metrics = [row.get('metrics', {}) for row in results if row['status'] != 'not_run']
    latencies = sorted(item['elapsed_ms'] for item in metrics if isinstance(item.get('elapsed_ms'), (int, float)))
    costs_by_currency = defaultdict(lambda: Decimal(0))
    for item in metrics:
        if item.get('cost_amount') is not None and item.get('cost_currency'):
            costs_by_currency[item['cost_currency']] += Decimal(item['cost_amount'])
    return {'version': 'saved-answer-evaluation-v1', 'completion_claim': False,
        'scoring': {'count_tolerance': 'exact', 'numeric_relative_tolerance': '0.02',
                    'zero_reference_requires_zero': True, 'text_numeric_claims_scored_as_numbers': True,
                    'multinumeric_text_and_descriptions_require_source_review': True,
                    'evidence_check': 'structural links only; no independent localization or omission review'},
        'row_weighted': _summary(results), 'by_family': families, 'by_project_leakage_group': projects,
        'family_weighted_strict_pass_rate_all_cases': mean(value['strict_pass_rate_all_cases'] for value in families.values()) if families else None,
        'project_weighted_strict_pass_rate_all_cases': mean(value['strict_pass_rate_all_cases'] for value in projects.values()) if projects else None,
        'coverage': {'families_total': len(families), 'families_attempted': sum(value['attempted'] > 0 for value in families.values()),
                     'project_groups_total': len(projects), 'project_groups_attempted': sum(value['attempted'] > 0 for value in projects.values())},
        'cost_latency': {'external_attempts_known': sum(item.get('external_attempts', 0) for item in metrics),
            'external_attempts_unknown_cases': sum(item.get('external_attempts') is None for item in metrics),
            'model_input_tokens_known': sum(item['model_input_tokens'] for item in metrics if item.get('model_input_tokens') is not None),
            'model_output_tokens_known': sum(item['model_output_tokens'] for item in metrics if item.get('model_output_tokens') is not None),
            'input_usage_unknown_cases': sum(item.get('model_input_tokens') is None for item in metrics),
            'output_usage_unknown_cases': sum(item.get('model_output_tokens') is None for item in metrics),
            'cost_amount_known_by_currency': {currency: str(amount) for currency, amount in sorted(costs_by_currency.items())},
            'cost_unknown_cases': sum(item.get('cost_amount') is None for item in metrics),
            'cost_currencies': sorted({item['cost_currency'] for item in metrics if item.get('cost_currency')}),
            'latency_phases': dict(Counter(row.get('latency_phase', 'unspecified') for row in results if row['status'] != 'not_run')),
            'latency_cases': len(latencies), 'median_ms': latencies[len(latencies) // 2] if latencies else None,
            'p95_ms': latencies[max(0, math.ceil(.95 * len(latencies)) - 1)] if latencies else None},
        'cases': results}


def score_files(manifest_path: Path, outputs_path: Path, references_path: Path, *, disputes_path: Path | None = None):
    # Freeze outputs first; callers cannot run this scoring phase without a
    # saved artifact. No reference data is used to prepare runtime requests.
    payload = outputs_path.read_bytes()
    if not payload.strip():
        raise ValueError('Save nonempty model/executor outputs before opening reference QA')
    saved = {}
    for line in payload.decode('utf-8-sig').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row['case_id'] in saved:
            raise ValueError('Duplicate saved output case_id')
        saved[row['case_id']] = row
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    needed = {case['jsonl_line'] for case in manifest['cases'] if case['case_id'] in saved}
    references = {}
    digest = hashlib.sha256()
    with references_path.open('rb') as stream:
        for line, raw in enumerate(stream, 1):
            digest.update(raw)
            if line in needed:
                references[line] = json.loads(raw)
    if manifest.get('questions_sha256') and digest.hexdigest() != manifest['questions_sha256']:
        raise ValueError('Reference QA bytes differ from the frozen manifest dataset')
    disputes = json.loads(disputes_path.read_text(encoding='utf-8')) if disputes_path else {}
    report = evaluate(manifest, saved, references, disputes)
    report['inputs'] = {'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                        'saved_outputs_sha256': hashlib.sha256(payload).hexdigest(),
                        'reference_qa_sha256': digest.hexdigest(), 'references_opened_after_saved_outputs': True}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--outputs', required=True, type=Path)
    parser.add_argument('--references', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--disputes', type=Path)
    args = parser.parse_args()
    report = score_files(args.manifest, args.outputs, args.references, disputes_path=args.disputes)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['row_weighted'], ensure_ascii=False))


if __name__ == '__main__':
    main()

"""Build the offline family work ledger from the saved classification, never QA answers.

This file and its output are evaluation/development tools. The runtime answer
packages do not import the taxonomy, this ledger, or distributed reference QA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCES = ('cubicasa5k', 'swiss_dwellings', 'ifc_models', 'ifc_bench', 'opening_design')


def build(root: Path = ROOT, *, manifest: dict | None = None, audits: dict | None = None) -> dict:
    report = (root / 'docs/QUESTION_CLASSIFICATION.md').read_text(encoding='utf-8')
    family_table = report.split('## Every semantic family, with counts by source', 1)[1].split('## Swiss room-label', 1)[0]
    catalog = report.split('## Exhaustive wording and template catalog', 1)[1]
    examples: dict[str, list[dict]] = {}
    source = None
    names = dict(zip(('CubiCasa5K', 'Swiss Dwellings', 'IFC models', 'IFC-Bench', 'Opening Design'), SOURCES))
    for line in catalog.splitlines():
        if line.startswith('### '):
            source = names.get(line[4:])
        if source and line.startswith('| ') and ' / ' in line:
            cells = [value.strip().replace('&#124;', '|') for value in line.strip('|').split('|')]
            if len(cells) == 5 and cells[2].replace(',', '').isdigit():
                examples.setdefault(cells[0], []).append({'source': source, 'question': cells[1], 'first_jsonl_line': int(cells[4])})
    prerequisites = {
        'Count': ['resolved scope and counting grain', 'complete native inventory or evaluated visual coverage protocol', 'included/excluded/unresolved membership'],
        'Area': ['literal room/unit identity and membership', 'stored/printed quantity basis or calibrated shell/holes', 'units and exclusions'],
        'Volume': ['stored quantity or calibrated closed geometry', 'material/assembly membership', 'units and net/gross basis'],
        'Length': ['stored length or calibrated source geometry', 'requested members and path definition', 'units'],
        'Derived': ['anchored scalar inputs and factors', 'dimensionally valid decimal arithmetic', 'zero/missing propagation'],
        'Compound': ['all requested parts recorded', 'independent executable subplans', 'shared budget and dependency graph'],
        'Connectivity': ['native ports and connections', 'graph coverage and direction', 'service membership proof'],
        'Compliance': ['explicit applicable criterion', 'anchored dimensions', 'rule executor'],
        'Spatial': ['native topology or supported geometry', 'north/portal/path prerequisites for requested metric'],
        'Sustainability': ['recorded project materials/content', 'anchored factors where requested'],
    }
    families = []
    for line in family_table.splitlines():
        if not line.startswith('| ') or ' / ' not in line:
            continue
        cells = [item.strip() for item in line.strip('|').split('|')]
        if len(cells) != 7:
            raise ValueError('Unexpected family report columns')
        family, *counts = cells
        operation, target = family.split(' / ', 1)
        by_source = dict(zip(SOURCES, (int(item.replace(',', '')) for item in counts[1:])))
        families.append({
            'family': family, 'operation': operation.lower(), 'target': target,
            'rows': int(counts[0].replace(',', '')), 'rows_by_source': by_source,
            'examples': examples.get(family, [])[:4],
            'source_prerequisites': prerequisites.get(operation, ['complete native properties/relations', 'literal identifiers', 'source anchors for every factual clause']),
            'candidate_routes': [*(['ifc_api/ + ifc_engine/'] if by_source['ifc_models'] or by_source['ifc_bench'] else []),
                                 *(['document_engine/ native PDF tools'] if by_source['opening_design'] or by_source['swiss_dwellings'] else []),
                                 *(['image_api/ qualified observations'] if by_source['cubicasa5k'] or by_source['swiss_dwellings'] or by_source['opening_design'] else [])],
            'evidence': 'source anchors, typed values, included/excluded sets and calculation inputs',
            'implementation_status': 'unverified_family_coverage',
            'source_audit_status': 'assets_unavailable',
            'evaluated_outcome': None,
        })
    if len(families) != 234 or sum(row['rows'] for row in families) != 127044:
        raise ValueError('Saved classification no longer matches the declared 234-family scope')
    if manifest is not None:
        cases = defaultdict(list)
        assets = {asset['path']: asset for asset in manifest['assets']}
        inspected = {item['path']: item for item in (audits or {}).get('sources', [])}
        for case in manifest['cases']:
            cases[case['family']].append(case)
        for family in families:
            members = cases[family['family']]
            if len(members) != family['rows']:
                raise ValueError('Actual questions disagree with saved family frequencies: ' + family['family'])
            actual_sources = Counter(case['source'] for case in members)
            if any(actual_sources[source] != count for source, count in family['rows_by_source'].items()):
                raise ValueError('Actual family source frequencies disagree with the classification')
            paths = sorted({case['path'] for case in members})
            languages = sorted({case['language_hint'] for case in members})
            selected_examples = []
            seen = set()
            for case in members:
                key = case['source'], case['language_hint']
                if key not in seen:
                    seen.add(key)
                    selected_examples.append({key: case[key] for key in ('case_id', 'source', 'path', 'question', 'jsonl_line', 'language_hint', 'project_hint', 'leakage_group')})
            selected_audits = [inspected[path] for path in paths if path in inspected]
            # Linked native models are prerequisites for rendered IFC-floor
            # questions; grouping links are not a runtime authorization route.
            links = [link for link in manifest['links'] if link['source'] in paths
                     and link['kind'] in {'floor_render_declared_by_dataset', 'explicit_evaluation_link'}]
            native_paths = sorted({link['target'] for link in links})
            selected_audits.extend(inspected[path] for path in native_paths if path in inspected and path not in paths)
            audit_counts = dict(Counter(item['status'] for item in selected_audits))
            family.update({'examples': selected_examples, 'question_languages': languages,
                'language_hint_method': manifest['language_method'], 'source_paths': paths,
                'linked_native_prerequisite_paths': native_paths,
                'referenced_source_count': len(paths), 'available_source_count': sum(assets[path]['available'] for path in paths),
                'project_count': len({case['project_hint'] for case in members}),
                'leakage_group_count': len({case['leakage_group'] for case in members}),
                'source_formats': sorted({assets[path]['format'] for path in paths}),
                'source_audit_status': 'structural_audit_partial' if selected_audits else 'available_not_inspected',
                'structural_audit_counts': audit_counts,
                'structural_audit_paths': sorted({item['path'] for item in selected_audits}),
                'genuine_source_limitation_established': False,
                'source_audit_limits': 'Structural metadata does not verify question-specific source sufficiency or establish an absent prerequisite.',
                'implementation_status': 'unverified_family_coverage', 'evaluated_outcome': None})
            gaps = []
            primitives = []
            if family['rows_by_source']['ifc_models'] or family['rows_by_source']['ifc_bench']:
                primitives = ['select', 'project', 'traverse', 'aggregate.count/sum/mean/min/max', 'rank']
                if family['operation'] == 'derived':
                    primitives += ['arithmetic.add/subtract/multiply/divide (scalars only)']
                    gaps += ['Source-backed factor/currency dimensions and every family-specific arithmetic route remain unverified.']
                if family['operation'] == 'spatial':
                    primitives += ['bounded native containment/adjacency/door connectivity']
                    gaps += ['Generic metric distance, orientation and routes have no executor.']
                if family['operation'] == 'connectivity':
                    gaps += ['Native MEP-port graph and service-to-room executor required.']
                if family['operation'] == 'compliance':
                    gaps += ['Applicable rule criteria and rule executor required.']
                if family['operation'] == 'sustainability':
                    gaps += ['Family-specific recorded content/factor extraction and derived calculations require validation.']
            if family['rows_by_source']['cubicasa5k'] or family['rows_by_source']['swiss_dwellings']:
                gaps += ['No visual family has an enabled, source-reviewed held-out omission protocol for automatic exact totals.']
            if family['rows_by_source']['swiss_dwellings'] and family['operation'] == 'area':
                gaps += ['Room/unit membership, exclusions, printed-value association and calibrated fallback require source-family validation.']
            if family['rows_by_source']['opening_design']:
                primitives += ['PDF.js native text', 'typed table facts and decimal schedule arithmetic']
                gaps += ['All 64 supplied schedule/fixture questions have not been exercised against frozen outputs.']
            if family['operation'] == 'compound':
                primitives += ['independent subplan composition and dependency blocking']
            family['capability_assessment'] = {'implemented_primitives_not_family_completion': primitives,
                                               'required_work_or_validation_gaps': gaps,
                                               'all_family_examples_executed': False}
    return {'version': 'answer-family-ledger-v2', 'classification_sha256': hashlib.sha256(report.encode()).hexdigest(),
            'reference_answers_used': False, 'full_dataset_available': (root / 'dataset/junction-dataset/questions.jsonl').is_file(),
            'preview_dataset_available': (root / 'dataset/junction-dataset-preview/questions.jsonl').is_file(),
            'actual_manifest_counts': manifest['counts'] if manifest else None,
            'split_status': manifest['split_status'] if manifest else 'not_generated',
            'source_audit_kind': 'bounded_native_metadata' if audits else 'not_run',
            'completion_claim': False, 'families': families}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments/answers/family_ledger.json')
    parser.add_argument('--dataset', type=Path, default=ROOT / 'dataset/junction-dataset')
    parser.add_argument('--manifest-out', type=Path, default=ROOT / 'build/answers/manifest.json')
    parser.add_argument('--audit-out', type=Path, default=ROOT / 'experiments/answers/source_audit.json')
    parser.add_argument('--audit', action='store_true', help='Inspect bounded native IFC metadata and a project-diverse PDF sample')
    parser.add_argument('--skip-hashes', action='store_true', help='Exploration only; duplicate-byte leakage grouping stays unverified')
    parser.add_argument('--links', type=Path, help='Optional offline explicit asset links with source/target/provenance')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest, audits = None, None
    if (args.dataset / 'questions.jsonl').is_file():
        from scripts.classify_questions import classify
        from experiments.answers.manifest import build_manifest
        taxonomy = json.loads((ROOT / 'scripts/question_classification_taxonomy.json').read_text(encoding='utf-8'))
        rows, _, _ = classify(args.dataset, taxonomy)
        links = json.loads(args.links.read_text(encoding='utf-8')) if args.links else []
        manifest = build_manifest(args.dataset.resolve(), rows, hash_assets=not args.skip_hashes, explicit_links=links)
        manifest['questions_sha256'] = hashlib.sha256((args.dataset / 'questions.jsonl').read_bytes()).hexdigest()
        if args.audit:
            from experiments.answers.audit_sources import audit_sources
            audits = audit_sources(args.dataset.resolve(), manifest)
            args.audit_out.parent.mkdir(parents=True, exist_ok=True)
            args.audit_out.write_text(json.dumps(audits, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        elif args.audit_out.is_file():
            audits = json.loads(args.audit_out.read_text(encoding='utf-8'))
            hashes = {item['path']: item['sha256'] for item in manifest['assets']}
            if any(item['source_sha256'] != hashes.get(item['path']) for item in audits['sources']):
                raise ValueError('Saved source audit belongs to changed source bytes; rerun --audit')
        if not args.check:
            args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
            args.manifest_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    content = json.dumps(build(manifest=manifest, audits=audits), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding='utf-8') != content:
            parser.exit(1, 'Answer family ledger is stale. Run python scripts/build_answer_ledger.py.\n')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding='utf-8')
    print('234 families and 127044 question rows reconciled; no reference answers used.')


if __name__ == '__main__':
    main()

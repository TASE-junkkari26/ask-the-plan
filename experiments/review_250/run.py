"""Freeze, execute and separately score a seeded 250-question development sample."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
from time import perf_counter

import httpx
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
ALLOCATION = {'cubicasa_png': 75, 'swiss_pdf': 75, 'ifc_floor_pdf': 25,
              'opening_pdf': 25, 'ifc_quantitative': 25, 'ifc_bench': 25}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if path.suffix == '.gz':
        data = gzip.compress(data)
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read_json(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def category(row):
    if row.source == 'cubicasa5k':
        return 'cubicasa_png'
    if row.source == 'swiss_dwellings':
        return 'swiss_pdf'
    if row.source == 'opening_design':
        return 'opening_pdf'
    if Path(row.path).suffix.lower() == '.pdf':
        return 'ifc_floor_pdf' if row.scope == 'floor/view' else None
    return 'ifc_bench' if row.source == 'ifc_bench' else 'ifc_quantitative'


def code_state():
    files = {}
    for directory in ('answer_api', 'document_engine', 'ifc_api', 'ifc_engine', 'contracts',
                      'image_api', 'nemotron', 'gemini', 'drawing_preprocessor', 'experiments/review_250'):
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file() and path.suffix in {'.py', '.mjs', '.txt', '.json'} and '__pycache__' not in path.parts:
                files[path.relative_to(ROOT).as_posix()] = file_hash(path)
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    return {'git_revision': revision, 'files': files, 'sha256': digest(json.dumps(files, sort_keys=True).encode())}


def plan(args):
    from scripts.classify_questions import classify
    taxonomy = read_json(ROOT / 'scripts/question_classification_taxonomy.json')
    rows, questions_hash, _ = classify(args.dataset, taxonomy)
    rng = random.Random(args.seed)
    selected, populations = [], {}
    for bucket, requested in ALLOCATION.items():
        eligible = [row for row in rows if category(row) == bucket]
        if len(eligible) < requested:
            raise ValueError(f'Insufficient eligible questions for {bucket}.')
        populations[bucket] = len(eligible)
        groups = defaultdict(list)
        for row in eligible:
            groups[row.family].append(row)
        families = sorted(groups)
        rng.shuffle(families)
        for group in groups.values():
            rng.shuffle(group)
        taken, used_sources = 0, set()
        while taken < requested:
            for family in families:
                options = groups[family]
                if not options:
                    continue
                index = next((index for index in range(len(options) - 1, -1, -1)
                              if options[index].path not in used_sources), len(options) - 1)
                row = options.pop(index)
                used_sources.add(row.path)
                selected.append({'id': f'Q{len(selected) + 1:03d}', 'case_id': f'line:{row.line}',
                    'line': row.line, 'path': row.path, 'question': row.question,
                    'question_sha256': digest(row.question.encode()), 'operation': row.answer_type,
                    'family': row.family, 'category': bucket, 'scope': row.scope})
                taken += 1
                if taken == requested:
                    break
    assets = []
    for path in sorted({case['path'] for case in selected}):
        source = args.dataset / path
        assets.append({'id': f'A{len(assets) + 1:03d}', 'path': path,
                       'sha256': file_hash(source), 'bytes': source.stat().st_size})
    args.run_dir.mkdir(parents=True, exist_ok=False)
    write_json(args.run_dir / 'cases.json', {'seed': args.seed, 'allocation': ALLOCATION,
        'eligible_rows': populations, 'dataset_questions_sha256': questions_hash,
        'created_at': datetime.now(timezone.utc).isoformat(), 'cases': selected, 'assets': assets,
        'sampling': 'Fixed category allocation; shuffled family cycle; random rows within family, preferring new sources. IFC PDF questions require explicit floor/view scope. Answer fields are excluded.'})
    print(json.dumps({'cases': len(selected), 'assets': len(assets), 'allocation': ALLOCATION,
                      'families': len({case['family'] for case in selected})}), flush=True)


def prepare(args, manifest):
    for asset in manifest['assets']:
        source = args.dataset / asset['path']
        if file_hash(source) != asset['sha256']:
            raise ValueError('A sampled source changed after selection.')
        if source.suffix.lower() == '.ifc':
            continue
        target = args.run_dir / 'inputs' / asset['id']
        if source.suffix.lower() != '.pdf':
            with Image.open(source) as opened:
                rgba = ImageOps.exif_transpose(opened).convert('RGBA')
                display = Image.new('RGBA', rgba.size, 'white')
                display.alpha_composite(rgba)
                target.mkdir(parents=True, exist_ok=True)
                display.convert('RGB').save(target / 'display.png')
        if not (target / 'display.png').is_file():
            raise ValueError('Render selected PDFs before running.')


def safe_failure(response):
    try:
        value = response.json()
    except ValueError:
        value = {}
    code = value.get('code', 'http_error') if isinstance(value, dict) else 'http_error'
    return {'code': code, 'http_status': response.status_code}


async def run(args):
    from image_api.app import create_app
    from image_api.config import ApiSettings
    from ifc_api.config import IfcSettings
    from gemini.config import GeminiSettings
    from nemotron.config import NemotronSettings

    manifest = read_json(args.run_dir / 'cases.json')
    if file_hash(args.dataset / 'questions.jsonl') != manifest['dataset_questions_sha256']:
        raise ValueError('The question file changed after sample selection.')
    prepare(args, manifest)
    displays = {}
    for asset in manifest['assets']:
        folder = args.run_dir / 'inputs' / asset['id']
        if (folder / 'display.png').exists():
            with Image.open(folder / 'display.png') as display:
                width, height = display.size
            displays[asset['id']] = {'sha256': file_hash(folder / 'display.png'), 'width': width, 'height': height,
                                    'pdf_render': read_json(folder / 'render.json') if (folder / 'render.json').exists() else None}
    settings = ApiSettings.from_env().model_copy(update={'max_concurrent': args.workers})
    ifc_settings = IfcSettings.from_env()
    identity = {'code': code_state(), 'image_settings': settings.model_dump(mode='json'),
        'ifc_settings': ifc_settings.model_dump(mode='json'),
        'gemini': GeminiSettings.from_env().model_dump(mode='json', exclude={'api_key'}),
        'nemotron': NemotronSettings.from_env().model_copy(update={'max_retries': 0}).model_dump(mode='json', exclude={'api_key'}),
        'python': platform.python_version(), 'workers': args.workers,
        'display_snapshots': displays,
        'transport': 'in-process production ASGI routes with live configured external providers'}
    identity_path = args.run_dir / 'runtime.json'
    phase = 1
    phase_path = args.run_dir / 'concurrency-phases.json'
    phases = read_json(phase_path) if phase_path.exists() else []
    if identity_path.exists() and read_json(identity_path) != identity:
        previous = read_json(identity_path)
        def invariant(value):
            value = json.loads(json.dumps(value))
            value.pop('workers', None)
            value.pop('ifc_workers', None)
            value['image_settings'].pop('max_concurrent', None)
            value['code'].pop('sha256', None)
            value['code']['files'].pop('experiments/review_250/run.py', None)
            return value
        if not args.change_concurrency or invariant(previous) != invariant(identity):
            raise ValueError('Runtime code or configuration changed. Use a fresh run directory.')
        interrupted = [case['id'] for case in manifest['cases']
                       if (args.run_dir / 'started' / f"{case['id']}.json").exists()
                       and not (args.run_dir / 'predictions' / f"{case['id']}.json.gz").exists()]
        phases.append({'phase': len(phases) + 1, 'runtime': previous,
            'ended_at': datetime.now(timezone.utc).isoformat(),
            'completed_before_handoff': sum((args.run_dir / 'predictions' / f"{case['id']}.json.gz").exists() for case in manifest['cases']),
            'interrupted_cases_prior_usage_unknown': interrupted,
            'reason': 'User explicitly requested increased parallelism on remaining questions.'})
        write_json(phase_path, phases)
    phase = len(phases) + 1
    write_json(identity_path, identity)
    app = create_app(settings=settings, ifc_settings=ifc_settings)
    assets = {asset['path']: asset for asset in manifest['assets']}
    by_source = defaultdict(list)
    for case in manifest['cases']:
        by_source[case['path']].append(case)
    drawing_queue = asyncio.Queue()
    ifc_queue = asyncio.Queue()
    for path, cases in by_source.items():
        if Path(path).suffix.lower() == '.ifc':
            ifc_queue.put_nowait((path, cases))
        else:
            drawing_queue.put_nowait((path, cases))
    completed = sum((args.run_dir / 'predictions' / f"{case['id']}.json.gz").is_file() for case in manifest['cases'])
    started = perf_counter()

    def save(case, value):
        nonlocal completed
        write_json(args.run_dir / 'predictions' / f"{case['id']}.json.gz", {'case_id': case['case_id'], 'concurrency_phase': phase, **value})
        completed += 1
        statuses = [part['status'] for part in value.get('answer', {}).get('parts', [])]
        print(json.dumps({'completed': completed, 'total': len(manifest['cases']), 'case': case['id'],
                          'category': case['category'], 'statuses': statuses,
                          'error': value.get('error'), 'seconds': round(perf_counter() - started, 1)}), flush=True)

    async def group(client, path, cases):
        pending = []
        for case in cases:
            if (args.run_dir / 'predictions' / f"{case['id']}.json.gz").is_file():
                continue
            if (args.run_dir / 'started' / f"{case['id']}.json").exists():
                if args.retry_interrupted:
                    write_json(args.run_dir / 'interrupted' / f"{case['id']}-phase-{phase - 1}.json",
                               read_json(args.run_dir / 'started' / f"{case['id']}.json"))
                    pending.append(case)
                else:
                    save(case, {'error': {'code': 'interrupted_attempt_usage_unknown'}})
            else:
                pending.append(case)
        if not pending:
            return
        asset = assets[path]
        source = args.dataset / path
        is_ifc = source.suffix.lower() == '.ifc'
        registered = None
        import_started = perf_counter()
        try:
            if is_ifc:
                with source.open('rb') as stream:
                    response = await client.post('/api/ifc/models', files={'file': (source.name, stream, 'application/octet-stream')},
                                                 data={'source_sha256': asset['sha256']})
            else:
                folder = args.run_dir / 'inputs' / asset['id']
                image = (folder / 'display.png').read_bytes()
                with Image.open(BytesIO(image)) as display:
                    width, height = display.size
                snapshot = {'source_sha256': asset['sha256'], 'source_revision': asset['sha256'],
                            'display_sha256': digest(image), 'display_width': width, 'display_height': height,
                            'page_index': 0, 'rotation': 0}
                if source.suffix.lower() == '.pdf':
                    render = read_json(folder / 'render.json')
                    snapshot.update(rotation=render['rotation'], viewport_transform=render['viewport_transform'],
                                    source_bounds=render['source_bounds'])
                with source.open('rb') as stream:
                    response = await client.post('/api/v1/sources', files={
                        'file': (source.name, stream), 'image': ('display.png', image, 'image/png')},
                        data={'snapshot': json.dumps(snapshot)})
            import_ms = (perf_counter() - import_started) * 1000
            if response.status_code != 200:
                for case in pending:
                    save(case, {'phase': 'cold_import', 'error': safe_failure(response), 'import_ms': import_ms})
                return
            registered = response.json()
            for case in pending:
                write_json(args.run_dir / 'started' / f"{case['id']}.json", {'case_id': case['case_id'],
                    'started_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': asset['sha256'], 'concurrency_phase': phase})
                request = {'source_sha256': asset['sha256'], 'question': case['question'], 'detail': not is_ifc}
                if is_ifc:
                    request['model_id'] = registered['model_id']
                else:
                    request.update(source_id=registered['source_id'], snapshot=registered['snapshot'])
                question_started = perf_counter()
                try:
                    response = await client.post('/api/v1/answers', json=request)
                    elapsed = (perf_counter() - question_started) * 1000
                    saved = {'phase': 'warm_question', 'elapsed_ms': elapsed, 'import_ms': import_ms,
                             'source_sha256': asset['sha256']}
                    saved.update(answer=response.json()) if response.status_code == 200 else saved.update(error=safe_failure(response))
                    save(case, saved)
                except Exception:
                    save(case, {'phase': 'warm_question', 'error': {'code': 'transport_or_internal_error_usage_unknown'},
                                'elapsed_ms': (perf_counter() - question_started) * 1000})
        except Exception:
            for case in pending:
                if not (args.run_dir / 'predictions' / f"{case['id']}.json.gz").exists():
                    save(case, {'phase': 'cold_import', 'error': {'code': 'source_import_internal_error'},
                                'import_ms': (perf_counter() - import_started) * 1000})
        finally:
            if registered is not None:
                endpoint = '/api/ifc/models/' + registered['model_id'] if is_ifc else '/api/v1/sources/' + registered['source_id']
                try:
                    await client.delete(endpoint)
                except Exception:
                    write_json(args.run_dir / 'cleanup' / f"{asset['id']}.json", {'code': 'session_cleanup_failed'})

    async def drawing_worker(client):
        while not drawing_queue.empty():
            path, cases = drawing_queue.get_nowait()
            await group(client, path, cases)

    async def ifc_worker(client):
        while not ifc_queue.empty():
            path, cases = ifc_queue.get_nowait()
            await group(client, path, cases)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url='http://evaluation', timeout=600) as client:
            await asyncio.gather(ifc_worker(client), *(drawing_worker(client) for _ in range(args.workers - 1)))
    write_json(args.run_dir / 'completion.json', {'completed': completed, 'elapsed_seconds': perf_counter() - started,
        'code_unchanged_during_run': code_state()['sha256'] == identity['code']['sha256'],
        'finished_at': datetime.now(timezone.utc).isoformat(), 'concurrency_phase': phase,
        'interrupted_cases_prior_usage_unknown': len(list((args.run_dir / 'interrupted').glob('*.json')))})


def score(args):
    manifest = read_json(args.run_dir / 'cases.json')
    outputs = {}
    for case in manifest['cases']:
        path = args.run_dir / 'predictions' / f"{case['id']}.json.gz"
        if not path.is_file():
            raise ValueError('Every selected case needs a frozen outcome before references can be read.')
        outputs[case['line']] = read_json(path)
    if file_hash(args.dataset / 'questions.jsonl') != manifest['dataset_questions_sha256']:
        raise ValueError('The question/reference file changed.')
    from experiments.answers.evaluate import score_case
    references = {}
    for index, line in enumerate((args.dataset / 'questions.jsonl').open(encoding='utf-8'), 1):
        if index in outputs:
            references[index] = json.loads(line)
    rows = []
    for case in manifest['cases']:
        saved = outputs[case['line']]
        reference = references[case['line']]
        if reference['path'] != case['path'] or reference['question'] != case['question']:
            raise ValueError('A reference does not match its frozen case inputs.')
        result = score_case(case, saved, reference, manifest)
        rows.append({**case, **result, 'error': saved.get('error'), 'elapsed_ms': saved.get('elapsed_ms'),
                     'import_ms': saved.get('import_ms'), 'part_statuses': dict(Counter(part['status'] for part in saved.get('answer', {}).get('parts', [])))})
    def summary(items):
        latencies = [row['elapsed_ms'] / 1000 for row in items if row.get('elapsed_ms') is not None]
        numeric = [row for row in items if row['operation'] != 'text']
        return {'selected': len(items), 'outcomes': dict(Counter(row['status'] for row in items)),
            'numeric_questions': len(numeric), 'numeric_reference_agreements': sum(row.get('raw_reference_agreement') is True for row in numeric),
            'strict_numeric_structural_passes': sum(row.get('strict_pass') is True for row in numeric),
            'text_questions_ungraded': sum(row['operation'] == 'text' for row in items),
            'structural_failures': sum(row.get('evidence_structural_pass') is False for row in items),
            'errors': dict(Counter((row.get('error') or {}).get('code') for row in items if row.get('error'))),
            'external_attempts_reported': sum(row.get('metrics', {}).get('external_attempts', 0) for row in items),
            'provider_usage_unknown_cases': sum(bool(row.get('error')) or any(call.get('prompt_tokens') is None or call.get('completion_tokens') is None
                for call in row.get('metrics', {}).get('calls', [])) for row in items),
            'median_warm_question_seconds': statistics.median(latencies) if latencies else None}
    report = {'overall': summary(rows), 'by_category': {category: summary([row for row in rows if row['category'] == category]) for category in ALLOCATION},
              'by_operation': {operation: summary([row for row in rows if row['operation'] == operation]) for operation in sorted({row['operation'] for row in rows})},
              'cases_sha256': file_hash(args.run_dir / 'cases.json'), 'rows': rows}
    write_json(args.run_dir / 'evaluation.json', report)
    print(json.dumps({key: value for key, value in report.items() if key != 'rows'}, ensure_ascii=True, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'run', 'score'])
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'dataset/junction-dataset')
    parser.add_argument('--seed', type=int, default=20261115)
    parser.add_argument('--workers', type=int, default=4, choices=range(2, 13))
    parser.add_argument('--change-concurrency', action='store_true')
    parser.add_argument('--retry-interrupted', action='store_true')
    args = parser.parse_args()
    if args.command == 'run':
        asyncio.run(run(args))
    else:
        globals()[args.command](args)


if __name__ == '__main__':
    main()

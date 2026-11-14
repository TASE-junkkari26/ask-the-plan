"""Reference-free evaluation cases and conservative source leakage groups."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_source(dataset: Path, relative: str) -> Path:
    relative_path = PurePosixPath(relative.replace('\\', '/'))
    if relative_path.is_absolute() or '..' in relative_path.parts or not relative_path.parts or ':' in relative_path.parts[0]:
        raise ValueError('Dataset source paths must be relative and remain inside the dataset')
    path = dataset.joinpath(*relative_path.parts).resolve()
    if not path.is_relative_to(dataset.resolve()):
        raise ValueError('Dataset source resolves outside the supplied dataset')
    return path


def language_hint(question: str, template: str = '') -> str:
    if re.match(r'^(en|fi|de|fr|it):', template):
        return template.split(':', 1)[0]
    prefixes = {
        'fi': ('Kuinka', 'Mikä', 'Montako', 'Monta', 'Laske'),
        'de': ('Wie ', 'Was ', 'Welche', 'Wo ', 'Gibt ', 'Nenne '),
        'fr': ('Combien', 'Quelle', 'Quel ', 'Quels', 'Où '),
        'it': ('Quanti', 'Quante', 'Qual ', 'Quale', 'Dove '),
        'da': ('Hvor ', 'Hvad ', 'Hvilke', 'Hvilken'),
        'nl': ('Hoeveel', 'Wat ', 'Welke', 'Waar '),
        'et': ('Mitu ', 'Kui ', 'Milline', 'Mis '),
        'pl': ('Ile ', 'Jaka ', 'Jaki ', 'Jakie ', 'Które', 'Gdzie '),
        'ro': ('Care ', 'Câte ', 'Câți ', 'Unde '),
        'es': ('¿', 'Cuánt', 'Cuál '),
        'sv': ('Hur ', 'Vilka', 'Vilken', 'Vad '),
        'en': ('How ', 'What ', 'Which ', 'Where ', 'Is ', 'Are ', 'List ', 'Describe ', 'Identify ', 'Provide ', 'Does ', 'Can ', 'Calculate ', 'Give '),
    }
    return next((language for language, candidates in prefixes.items() if question.startswith(candidates)), 'und')


def project_hint(relative: str) -> str:
    """Conservative grouping metadata, not a runtime source-identity assertion."""
    path = PurePosixPath(relative)
    source = path.parts[1]
    if source == 'swiss_dwellings':
        site = re.match(r'(site\d+)_bldg\d+_floor\d+', path.stem)
        return source + ':' + (site.group(1) if site else path.stem)
    if source == 'opening_design' and len(path.parts) > 3:
        return source + ':' + path.parts[2]
    if source in {'ifc_models', 'ifc_bench'}:
        stem = re.sub(r'_plan-\d+.*$', '', path.stem, flags=re.I)
        stem = re.sub(r'_(?:arc|str|mep|heating|plumbing|ventilation|electrical)$', '', stem, flags=re.I)
        stem = re.sub(r'_\d+$', '', stem)
        return source + ':' + stem
    return source + ':' + path.stem


class _Groups:
    def __init__(self, keys):
        self.parents = {key: key for key in keys}

    def find(self, key):
        while self.parents[key] != key:
            self.parents[key] = self.parents[self.parents[key]]
            key = self.parents[key]
        return key

    def union(self, left, right):
        a, b = self.find(left), self.find(right)
        self.parents[max(a, b)] = min(a, b)


def build_manifest(dataset: Path, classified, *, hash_assets=True, explicit_links=()) -> dict:
    """Build cases from classifier records that contain no reference answers.

    Same basename formats and rendered IFC floors use the dataset README's
    explicit declarations. Other filename grouping is conservative split
    grouping only; it does not authorize a source switch in the app.
    """
    rows = list(classified)
    referenced = {row.path.replace('\\', '/') for row in rows}
    paths = set(referenced)
    links = []
    by_parent = defaultdict(list)
    for relative in sorted(referenced):
        path = safe_source(dataset, relative)
        if path.is_file():
            by_parent[path.parent].append((relative, path))
    for parent, selected in by_parent.items():
        siblings = list(parent.iterdir())
        siblings_by_stem = defaultdict(list)
        for sibling in siblings:
            siblings_by_stem[sibling.stem].append(sibling)
        model_stems = {path.stem: path for path in siblings if path.suffix.lower() == '.ifc'}
        for relative, path in selected:
            for sibling in siblings_by_stem[path.stem]:
                if sibling.is_file() and sibling.suffix.lower() in {'.pdf', '.png', '.svg', '.dxf', '.dwg', '.ifc'}:
                    companion = sibling.relative_to(dataset.resolve()).as_posix()
                    paths.add(companion)
                    if companion != relative:
                        links.append({'source': relative, 'target': companion, 'kind': 'same_drawing_declared_by_dataset', 'provenance': 'README.md: same name, different extension'})
            if '/ifc_models/' in '/' + relative:
                candidates = [stem for stem in model_stems if path.stem.startswith(stem + '_plan-')]
                if candidates:
                    stem = max(candidates, key=len)
                    companion = model_stems[stem].relative_to(dataset.resolve()).as_posix()
                    paths.add(companion)
                    links.append({'source': relative, 'target': companion, 'kind': 'floor_render_declared_by_dataset', 'provenance': 'README.md: IFC-model floor plans rendered from named model'})
    for link in explicit_links:
        if not {'source', 'target', 'provenance'} <= link.keys() or not link['provenance']:
            raise ValueError('Explicit evaluation source links require both paths and provenance')
        for relative in (link['source'], link['target']):
            if not safe_source(dataset, relative).is_file():
                raise ValueError('Explicit evaluation links must identify available dataset sources')
            paths.add(relative)
        links.append({**link, 'kind': 'explicit_evaluation_link'})
    assets = {}
    groups = _Groups(paths)
    projects, digests = {}, {}
    for relative in sorted(paths):
        path = safe_source(dataset, relative)
        present = path.is_file()
        digest = sha256_file(path) if present and hash_assets else None
        project = project_hint(relative)
        assets[relative] = {'path': relative, 'available': present, 'bytes': path.stat().st_size if present else None,
                            'sha256': digest, 'project_hint': project, 'format': path.suffix.lower().lstrip('.')}
        if project in projects:
            groups.union(relative, projects[project])
        projects[project] = relative
        if digest is not None:
            if digest in digests:
                groups.union(relative, digests[digest])
                links.append({'source': relative, 'target': digests[digest], 'kind': 'byte_duplicate', 'provenance': 'sha256:' + digest})
            digests[digest] = relative
    for link in links:
        groups.union(link['source'], link['target'])
    membership = defaultdict(list)
    for path in paths:
        membership[groups.find(path)].append(path)
    group_ids = {root: 'source-group:' + hashlib.sha256('\n'.join(sorted(members)).encode()).hexdigest()[:24]
                 for root, members in membership.items()}
    for relative, asset in assets.items():
        group = group_ids[groups.find(relative)]
        asset['leakage_group'] = group
        bucket = int(hashlib.sha256(group.encode()).hexdigest()[:8], 16) % 10
        asset['proposed_split'] = 'development' if bucket < 6 else 'validation' if bucket < 8 else 'held_out'
    cases = []
    for row in rows:
        path = row.path.replace('\\', '/')
        asset = assets[path]
        key = '\0'.join((path, row.question, row.answer_type))
        cases.append({'case_id': 'qa:' + hashlib.sha256(key.encode()).hexdigest()[:24],
            'jsonl_line': row.line, 'path': path, 'source': row.source,
            'source_sha256': asset['sha256'], 'question': row.question,
            'question_sha256': hashlib.sha256(row.question.encode()).hexdigest(),
            'stored_answer_type': row.answer_type, 'family': row.family,
            'operation': row.family.split(' / ', 1)[0].lower(),
            'question_scope_label': getattr(row, 'scope', '') or 'not_classified',
            'language_hint': language_hint(row.question, row.template),
            'project_hint': asset['project_hint'], 'leakage_group': asset['leakage_group'],
            'proposed_split': asset['proposed_split']})
    if len({case['case_id'] for case in cases}) != len(cases):
        raise ValueError('Duplicate path/question/type cases require explicit duplicate handling')
    return {'version': 'answer-evaluation-manifest-v1', 'reference_answers_used': False,
            'hashes_complete_for_registered_assets': hash_assets and all(asset['sha256'] for asset in assets.values()),
            'split_status': 'proposed_only; historical development sources are not fresh holdouts',
            'language_method': 'question_prefix_heuristic_v1; und means unclassified',
            'source_links_scope': 'offline grouping only; never runtime source authorization',
            'cases': cases, 'assets': list(assets.values()),
            'links': sorted({json.dumps(link, sort_keys=True): link for link in links}.values(), key=lambda item: (item['source'], item['target'], item['kind'])),
            'counts': {'cases': len(cases), 'families': len({row.family for row in rows}),
                       'referenced_assets': len(referenced), 'registered_assets': len(assets),
                       'available_registered_assets': sum(asset['available'] for asset in assets.values()),
                       'leakage_groups': len(membership), 'languages': dict(sorted(Counter(case['language_hint'] for case in cases).items()))}}

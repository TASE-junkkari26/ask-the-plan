"""Classify supplied QA questions for an analysis report; never an answer service.

Standard library only. Reference answers are neither used for classification nor
copied into its outputs. Unknown sources, labels, or unmatched templates fail
explicitly instead of falling through to an unreviewed 'other' category.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('cubicasa5k', 'swiss_dwellings', 'ifc_models', 'ifc_bench', 'opening_design')
SOURCE_NAMES = {
    'cubicasa5k': 'CubiCasa5K', 'swiss_dwellings': 'Swiss Dwellings',
    'ifc_models': 'IFC models', 'ifc_bench': 'IFC-Bench', 'opening_design': 'Opening Design',
}

# Literal labels stay in the output. Only their separate semantic grouping is
# shared across languages. 'Zimmer', 'Pièce', and 'Stanza' do not imply bedroom.
ROOM_GROUPS = {
    'Kitchens': ('Küche', 'Cuisine', 'Cucina'),
    'Bedrooms': ('Schlafzimmer', 'Chambre à coucher', 'Camera da letto'),
    'Bathrooms and washrooms': ('Bad', 'Bain', 'Bagno'),
    'Balconies': ('Balkon', 'Balcon', 'Balcone'),
    'Loggias': ('Loggia',),
    'Corridors': ('Korridor', 'Couloir', 'Corridoio'),
    'Stairwell rooms': ('Treppenhaus', "Cage d'escalier", 'Vano scala'),
    'Generic labelled rooms (not necessarily bedrooms)': ('Zimmer', 'Pièce', 'Stanza', 'Raum', 'Local'),
    'Living and dining rooms together': ('Wohnen/Essen', 'Séjour/repas', 'Soggiorno/pranzo'),
    'Living rooms': ('Wohnen', 'Séjour', 'Soggiorno'),
    'Storage rooms': ('Reduit', 'Réduit', 'Ripostiglio'),
    'Kitchen and dining rooms together': ('Küche/Essen',),
    'Cellar rooms': ('Kellerabteil', 'Vano cantina', 'Compartiment cave'),
    'Office rooms and office areas': ('Büro', 'Bürofläche'),
    'Dining rooms': ('Essen', 'Repas'),
    'Winter gardens': ("Jardin d'hiver", 'Wintergarten'),
    'Entrance halls': ('Hall',),
    'Laundry rooms': ('Buanderie',),
    'Terraces': ('Terrazza', 'Terrasse'),
    'Arcades': ('Arkade',),
    'Seating areas': ('Sitzplatz',),
}
ROOM_LABELS = {label: group for group, labels in ROOM_GROUPS.items() for label in labels}

SWISS_LABEL_COUNT = (
    ('en', r"How many rooms labelled '(?P<label>.*)' are there on this floor\?"),
    ('de', r'Wie viele Räume mit der Bezeichnung «(?P<label>.*)» gibt es in diesem Geschoss\?'),
    ('fr', r'Combien de pièces portant la désignation «(?P<label>.*)» y a-t-il à cet étage \?'),
    ('it', r'Quanti locali con la denominazione «(?P<label>.*)» ci sono in questo piano\?'),
)
SWISS_LABEL_AREA = (
    ('en', r"What is the total net area in m² of all rooms labelled '(?P<label>.*)' on this floor\?"),
    ('de', r'Wie gross ist die gesamte Nettofläche in m² aller Räume mit der Bezeichnung «(?P<label>.*)» in diesem Geschoss\?'),
    ('fr', r'Quelle est la surface nette totale en m² de toutes les pièces désignées «(?P<label>.*)» à cet étage \?'),
    ('it', r'Qual è la superficie netta totale in m² di tutti i locali denominati «(?P<label>.*)» in questo piano\?'),
)
SWISS_ROOM_AREA = (
    ('en', r"What is the net floor area of room (?P<room>.+) \('(?P<label>.*)'\) in m²\?"),
    ('de', r'Wie gross ist die Nettofläche von Raum (?P<room>.+) \(«(?P<label>.*)»\) in m²\?'),
    ('fr', r'Quelle est la surface nette de la pièce (?P<room>.+) \(«(?P<label>.*)»\) en m² \?'),
    ('it', r'Qual è la superficie netta del locale (?P<room>.+) \(«(?P<label>.*)»\) in m²\?'),
)
SWISS_COUNTS = {
    'Apartments and residential units': (
        'How many apartments (residential units)', 'Wie viele Wohnungen',
        "Combien d'appartements", 'Quanti appartamenti',
    ),
    'Doors': ('How many doors (interior doors', 'Wie viele Türen', 'Combien de portes', 'Quante porte'),
    'Windows': ('How many windows', 'Wie viele Fenster', 'Combien de fenêtres', 'Quante finestre'),
    'Toilet bowls and WC fixtures': ('How many toilets (WC)', 'Wie viele WCs', 'Combien de WC', 'Quanti WC'),
    'Sinks and washbasins': ('How many washbasins', 'Wie viele Lavabos', 'Combien de lavabos', 'Quanti lavabi'),
    'Bathtubs': ('How many bathtubs', 'Wie viele Badewannen', 'Combien de baignoires', 'Quante vasche'),
    'Showers': ('How many showers', 'Wie viele Duschen', 'Combien de douches', 'Quante docce'),
}
SWISS_APARTMENT_AREA = (
    'What is the net floor area of apartment ', 'Wie gross ist die Nettowohnfläche von Wohnung ',
    "Quelle est la surface nette de l'appartement ", "Qual è la superficie netta dell'appartamento ",
)
SWISS_FLOOR_AREA = (
    'What is the total net floor area in m² of all numbered indoor rooms',
    'Wie gross ist die gesamte Nettogeschossfläche', 'Quelle est la surface nette totale en m² de toutes les pièces intérieures',
    'Qual è la superficie netta totale in m² di tutti i locali interni',
)

# Prefixes end before source-specific room/model/storey literals. Selection of a
# class is explicit in each observed language; never search inside a model name.
IFC_COUNT_PREFIXES = {
    'Doors': ('How many doors ', 'Wie viele Türen ', 'Hvor mange døre ', 'Hoeveel deuren ',
              '¿Cuál es el número de puertas ', 'Mitu ust ', 'Ile drzwi ', 'Qual è il numero di porte '),
    'Windows': ('How many windows ', 'Wie viele Fenster ', 'Hvor mange vinduer ', 'Hoeveel ramen ',
                '¿Cuál es el número de ventanas ', 'Mitu akent ', 'Ile okien ', 'Qual è il numero di finestre ',
                'Care este numărul de ferestre '),
    'Rooms and spaces': ('How many rooms (spaces) ', 'Wie viele Räume ', 'Hvor mange rum ', 'Hoeveel ruimtes ',
                         '¿Cuál es el número de locales ', 'Mitu ruumi ', 'Ile pomieszczeń '),
    'Walls': ('How many walls ', 'Wie viele Wände ', 'Hvor mange vægge ', 'Hoeveel wanden ',
              '¿Cuál es el número de muros ', 'Mitu seina ', 'Ile ścian ', 'Qual è il numero di muri ',
              'Care este numărul de pereți '),
    'Stairs': ('How many stairs ', 'Wie viele Treppen ', 'Hvor mange trapper ', 'Hoeveel trappen ',
               '¿Cuál es el número de escaleras ', 'Mitu treppi ', 'Ile schodów ', 'Ile schody ',
               'Care este numărul de scări '),
    'Columns': ('How many columns ', 'Wie viele Stützen ', 'Hvor mange søjler ', 'Hoeveel kolommen ',
                 '¿Cuál es el número de pilares ', 'Mitu posti ', 'Ile słupów ', 'Care este numărul de stâlpi '),
    'Beams': ('How many beams ', 'Wie viele Träger ', 'Hvor mange bjælker ', 'Hoeveel balken ',
               '¿Cuál es el número de vigas ', 'Mitu tala ', 'Ile belek ', 'Care este numărul de grinzi '),
    'Sanitary fixtures (combined)': ('How many sanitary fixtures ', 'Wie viele Sanitärobjekte ', 'Hoeveel sanitaire toestellen '),
    'Light fixtures': ('How many light fixtures ', 'Wie viele Leuchten ', 'Care este numărul de corpuri de iluminat '),
}
IFC_QUANTITY_PREFIXES = {
    ('area', 'Area / One room or space'): (
        'What is the net floor area of the room ', 'Kui suur on ruumi ',
        'Wat is de netto vloeroppervlakte van de ruimte ', '¿Cuál es la superficie útil del local ',
        'Hvad er nettoarealet af rummet ', 'Wie groß ist die Netto-Grundfläche des Raums ',
        'Jaka jest powierzchnia netto pomieszczenia ',
    ),
    ('area', 'Area / Net floor area of all spaces on one level'): (
        'What is the total net floor area of all rooms (spaces) ', 'Kui suur on kõigi ruumide ',
        'Wat is de totale netto vloeroppervlakte van alle ruimtes ',
        '¿Cuál es la superficie útil total de todos los locales ', 'Hvad er det samlede nettoareal af alle rum ',
        'Wie groß ist die gesamte Netto-Grundfläche aller Räume ',
        'Jaka jest łączna powierzchnia netto wszystkich pomieszczeń ',
    ),
    ('area', 'Area / Net side area of walls'): (
        'What is the total net side area of all walls ', 'Wie groß ist die gesamte Netto-Seitenfläche aller Wände ',
        'Hvad er det samlede nettosideareal af alle vægge ', 'Wat is de totale netto zijoppervlakte van alle wanden ',
    ),
    ('length', 'Length / All walls on one level'): (
        'What is the total length of all walls ', 'Wie lang sind alle Wände ',
        'Hvad er den samlede længde af alle vægge ', 'Wat is de totale lengte van alle wanden ',
    ),
    ('volume', 'Volume / Net wall volume'): (
        'What is the total net volume of all walls ', 'Wie groß ist das gesamte Netto-Volumen aller Wände ',
        'Hvad er det samlede nettovolumen af alle vægge ', 'Wat is het totale netto volume van alle wanden ',
    ),
    ('volume', 'Volume / Net slab volume'): (
        'What is the total net volume of all slabs ', 'Wie groß ist das gesamte Netto-Volumen aller Decken und Bodenplatten ',
        'Hvad er det samlede nettovolumen af alle dæk og plader ', 'Wat is het totale netto volume van alle vloeren ',
    ),
}


@dataclass(frozen=True)
class Classified:
    line: int
    source: str
    path: str
    question: str
    answer_type: str
    family: str
    template: str
    label: str = ''
    label_operation: str = ''
    scope: str = ''


def swiss(question: str, answer_type: str) -> tuple[str, str, str, str]:
    for operation, patterns in (('count', SWISS_LABEL_COUNT), ('sum_area', SWISS_LABEL_AREA), ('one_area', SWISS_ROOM_AREA)):
        for language, pattern in patterns:
            match = re.fullmatch(pattern, question)
            if not match:
                continue
            label = match['label'].strip()
            group = ROOM_LABELS[label]  # New literal labels require explicit review.
            if operation == 'count':
                assert answer_type == 'count'
                family = f'Count / {group}'
            elif operation == 'sum_area':
                assert answer_type == 'area'
                family = f'Area / Sum of labelled rooms: {group.lower()}'
            else:
                assert answer_type == 'area'
                family = 'Area / One room or space'
            return family, f'{language}:{operation}:{group}', label, operation
    for target, prefixes in SWISS_COUNTS.items():
        for prefix in prefixes:
            if question.startswith(prefix):
                assert answer_type == 'count'
                return f'Count / {target}', prefix, '', ''
    for prefix in SWISS_APARTMENT_AREA:
        if question.startswith(prefix):
            assert answer_type == 'area'
            return 'Area / Net apartment floor area excluding outdoor spaces', prefix, '', ''
    for prefix in SWISS_FLOOR_AREA:
        if question.startswith(prefix):
            assert answer_type == 'area'
            return 'Area / Net indoor floor area excluding outdoor spaces, shafts and voids', prefix, '', ''
    raise ValueError(f'Unreviewed Swiss question: {question}')


def ifc_quantitative(question: str, answer_type: str) -> tuple[str, str, str]:
    if answer_type == 'count':
        matches = [(target, prefix) for target, prefixes in IFC_COUNT_PREFIXES.items()
                   for prefix in prefixes if question.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f'Expected one IFC count rule, got {matches}: {question}')
        target, prefix = matches[0]
        floor_markers = ('floor plan', 'Grundriss', 'plantegningen', 'plattegrond', 'plano de la planta',
                         'plaanil', 'planul nivelului', 'rzucie', 'pianta del piano')
        # Check only the lead-in, not quoted model or floor names.
        lead = re.split(r"['„]", question, maxsplit=1)[0]
        scope = 'floor/view' if any(marker in lead for marker in floor_markers) else 'whole model'
        return f'Count / {target}', f'{prefix}<{scope}>', scope
    matches = [(family, prefix) for (kind, family), prefixes in IFC_QUANTITY_PREFIXES.items()
               for prefix in prefixes if kind == answer_type and question.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f'Expected one IFC quantity rule, got {matches}: {question}')
    family, prefix = matches[0]
    return family, prefix, 'floor/view'


def classify(dataset: Path, taxonomy: dict) -> tuple[list[Classified], str, int]:
    payload = (dataset / 'questions.jsonl').read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    result = []
    blank_lines = 0
    for line, raw in enumerate(payload.decode('utf-8-sig').splitlines(), 1):
        if not raw.strip():
            blank_lines += 1
            continue
        row = json.loads(raw)
        path, question, answer_type = row['path'], row['question'], row['type']
        source = path.replace('\\', '/').split('/')[1]
        if source not in SOURCES:
            raise ValueError(f'Unreviewed question source on line {line}: {source}')
        label = label_operation = scope = ''
        if source == 'swiss_dwellings':
            family, template, label, label_operation = swiss(question, answer_type)
        elif source == 'ifc_models':
            family, template, scope = ifc_quantitative(question, answer_type)
        else:
            try:
                family = taxonomy[source][question]
            except KeyError as exc:
                raise ValueError(f'Unreviewed {source} question on line {line}: {question}') from exc
            template = question
        assert ' / ' in family
        result.append(Classified(line, source, path, question, answer_type, family, template, label, label_operation, scope))
    assert result
    assert len({r.line for r in result}) == len(result)
    return result, digest, blank_lines


def cell(value: object) -> str:
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('\n', ' ')


def table(headers: list[str], rows: list[list[object]]) -> list[str]:
    return ['| ' + ' | '.join(map(cell, headers)) + ' |',
            '| ' + ' | '.join('---' for _ in headers) + ' |',
            *['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows], '']


def report(rows: list[Classified], digest: str, blanks: int, dataset: Path, report_date: str) -> str:
    total = len(rows)
    families = Counter(r.family for r in rows)
    sources = Counter(r.source for r in rows)
    kinds = Counter(r.answer_type for r in rows)
    operations = Counter(r.family.split(' / ')[0] for r in rows)
    texts = len({r.question for r in rows})
    by_family_source = Counter((r.family, r.source) for r in rows)
    assert sum(families.values()) == sum(sources.values()) == sum(kinds.values()) == total
    assert sum(operations.values()) == total
    by_source = {source: [r for r in rows if r.source == source] for source in SOURCES}
    # Counts must reconcile independently at every granularity.
    for source in SOURCES:
        assert sum(n for (family, s), n in by_family_source.items() if s == source) == sources[source]

    lines = [
        '# Exact question classification of the full Junction dataset', '',
        f'Generated {report_date} from the supplied full dataset, excluding the preview.', '',
        'Regenerate this report with [the classifier](../scripts/classify_questions.py); edit its taxonomy/generator rather than this generated file.', '',
        f'**{total:,} question rows; {texts:,} distinct verbatim question texts; {len(families):,} semantic question families; every row classified exactly once.**', '',
        'These are counts of **questions**, not counts of physical windows, doors, or other objects. No reference answers were summed.', '',
        '## Counting and classification rules', '',
        '- Each nonblank JSONL record counts once, including translations and repeated wording on different drawings. These are row frequencies, not independent buildings or training examples.',
        '- Semantically equivalent questions in different languages share a family. Literal room IDs, storey names, and model names remain unchanged in examples; parameter variations do not create new families.',
        '- Families combine the requested operation and target. They are an explicit analysis taxonomy, not organizer-supplied semantic labels. The dataset\'s own `type` field describes the stored answer format and is reported separately. All IFC-Bench rows are stored as `text`, even when they ask for counts, areas, or other numeric results.',
        '- The family table is mutually exclusive. Multipart inventories stay in one descriptive family; questions asking multiple independent counts or a count plus area have explicit compound families. Do not add inventory/compound rows to a simple count without changing the definition.',
        '- "Count windows" includes direct total/filtered/window-schedule assembly counts. Type/size inventories, window dimensions, window area, and multiplying assembly widths into individual units are separate families. Door leaves, mixed door-schedule entries, and gates are also separate from direct door counts.',
        '- Room labels are normalized separately using the explicit Swiss label mapping below. Generic `Zimmer`/`Pièce`/`Stanza` are not assumed to be bedrooms. Stairwell rooms, stairs, and stair steps remain distinct.',
        '- Source counting conventions still apply: CubiCasa includes only doorways fitted with a door, combines showers with bathtubs, and counts a double-bowl sink as one. Its kitchen and bathroom definitions differ from a literal Swiss label filter. The five ambiguous IFC-Bench "toilets" wordings remain explicitly unspecified rather than being guessed as fixtures or rooms.',
        '- The classification describes **what the question requests**, not whether its answer is available, correct, estimated, or implemented. No model or source-geometry accuracy is implied.', '',
        '## Direct count questions: exact totals', '',
        'These families ask directly for object counts, including filtered counts and per-floor count breakdowns. Named-type inventories and compound questions appear separately in the exhaustive family table.', '',
    ]
    count_families = sorted((f for f in families if f.startswith('Count / ')), key=lambda f: (-families[f], f))
    lines += table(['Question asks how many…', 'Question rows', 'Share of all rows'],
                   [[f.split(' / ', 1)[1], f'{families[f]:,}', f'{families[f] / total:.4%}'] for f in count_families]
                   + [['**Direct-count subtotal**', f'{sum(families[f] for f in count_families):,}', '']])
    lines += ['## Requested-operation totals', '',
              'These semantic operation buckets are separate from the original answer-format labels.', '']
    lines += table(['Requested operation', 'Question rows', 'Share'],
                   [[op, f'{n:,}', f'{n / total:.4%}'] for op, n in operations.most_common()]
                   + [['**Total**', f'{total:,}', '100%']])
    lines += ['## Original dataset answer-format totals', '']
    lines += table(['Stored `type`', 'Question rows', 'Share'],
                   [[kind, f'{kinds[kind]:,}', f'{kinds[kind] / total:.4%}'] for kind in ('count', 'area', 'text', 'volume', 'length', 'other')]
                   + [['**Total**', f'{total:,}', '100%']])
    lines += ['### Requested operation versus stored answer format', '',
              'This cross-tab makes numeric tasks stored as `text` visible without altering the supplied type labels.', '']
    cross_tab = Counter((r.family.split(' / ')[0], r.answer_type) for r in rows)
    answer_formats = ('count', 'area', 'text', 'volume', 'length', 'other')
    lines += table(['Requested operation', *answer_formats, 'Total'],
                   [[operation, *[f'{cross_tab[operation, kind]:,}' for kind in answer_formats], f'{n:,}']
                    for operation, n in operations.most_common()]
                   + [['**Total**', *[f'{kinds[kind]:,}' for kind in answer_formats], f'{total:,}']])
    lines += ['## Source coverage', '']
    source_rows = [[SOURCE_NAMES[s], f'{sources[s]:,}', f'{len({r.question for r in by_source[s]}):,}',
                    f'{len({r.path for r in by_source[s]}):,}', f'{len({r.family for r in by_source[s]}):,}'] for s in SOURCES]
    for source in sorted(p.name for p in (dataset / 'data').iterdir() if p.is_dir() and p.name not in SOURCES):
        source_rows.append([source, '0', '0', '0', '0'])
    lines += table(['Source', 'Question rows', 'Distinct question texts', 'Referenced paths', 'Families in source'], source_rows)
    lines += ['## Every semantic family, with counts by source', '',
              'Each row below is a disjoint family. Column totals and the grand total are checked by the generator. Zero means no supplied questions in that family/source, not zero objects in a drawing.', '']
    family_order = sorted(families, key=lambda f: (f.split(' / ')[0], -families[f], f))
    lines += table(['Question family', 'Total', 'CubiCasa', 'Swiss', 'IFC models', 'IFC-Bench', 'Opening Design'],
                   [[family, f'{families[family]:,}', *[f'{by_family_source[family, s]:,}' for s in SOURCES]] for family in family_order]
                   + [['**Total**', f'{total:,}', *[f'{sources[s]:,}' for s in SOURCES]]])

    lines += ['## Swiss room-label questions without losing the original labels', '',
              'Counts below cover Swiss Dwellings only. Count-label and sum-by-label columns are subsets of the corresponding family totals; individual-room area queries belong to "Area / One room or space". English and local-language rows both count. Only surrounding guillemet spacing is trimmed.', '']
    label_counts = Counter((r.label, r.label_operation) for r in rows if r.label)
    label_rows = [[label, ROOM_LABELS[label], *[f'{label_counts[label, op]:,}' for op in ('count', 'one_area', 'sum_area')]]
                  for label in sorted({r.label for r in rows if r.label}, key=lambda x: (ROOM_LABELS[x], x))]
    lines += table(['Literal label', 'Semantic room group', 'Count questions', 'One-room area questions', 'Sum-area questions'], label_rows
                   + [['**Total**', '', *[f'{sum(n for (label, kind), n in label_counts.items() if kind == op):,}' for op in ('count', 'one_area', 'sum_area')]]])

    lines += ['## Quantitative IFC count scope', '',
              'Only the structured `ifc_models` source is included here. Explicit whole-model questions and floor/view questions remain separate even when their referenced file is a single floor PDF. IFC-Bench and schedule counts are covered in the family/catalog tables.', '']
    scoped = Counter((r.family, r.scope) for r in rows if r.source == 'ifc_models' and r.answer_type == 'count')
    lines += table(['Count target', 'Floor/view rows', 'Whole-model rows', 'Total'],
                   [[family.split(' / ', 1)[1], scoped[family, 'floor/view'], scoped[family, 'whole model'],
                     scoped[family, 'floor/view'] + scoped[family, 'whole model']]
                    for family in sorted({family for family, scope in scoped})])

    lines += ['## Exhaustive wording and template catalog', '',
              'Every supplied row is represented below. For CubiCasa, IFC-Bench, and Opening Design, each entry is one exact question text. Swiss and quantitative IFC entries group only reviewed parameterized templates; each shows a verbatim example, its row count, number of distinct wordings/parameter values, and the first one-based source line. Swiss labels are expanded separately above. The classifier can additionally export every original row and its assigned family.', '',
              'An example is not a promise that every row has the same room ID or scope. Follow its family and, for quantitative IFC counts, the separately preserved floor/model scope. No answers are included.', '']
    catalog_total = 0
    for source in SOURCES:
        groups = defaultdict(list)
        for r in by_source[source]:
            groups[r.family, r.template].append(r)
        assert sum(map(len, groups.values())) == sources[source]
        catalog_total += sum(map(len, groups.values()))
        lines += [f'### {SOURCE_NAMES[source]}', '', '<details>',
                  f'<summary>{sources[source]:,} rows in {len(groups):,} exact texts or parameterized templates</summary>', '']
        entries = []
        for (family, template), items in sorted(groups.items()):
            first = items[0]
            entries.append([family, first.question, f'{len(items):,}', len({r.question for r in items}), first.line])
        lines += table(['Family', 'Verbatim question or example', 'Rows', 'Distinct question texts', 'First JSONL line'], entries)
        lines += ['</details>', '']
    assert catalog_total == total

    lines += ['## Provenance and reproduction', '',
              '- Input: the full `dataset/junction-dataset/questions.jsonl`, not the preview and not previously aggregated audits.',
              f'- SHA-256 of the exact input bytes: `{digest}`.',
              f'- Parsed records: **{total:,}**. Blank lines skipped: **{blanks:,}**. Unclassified rows: **0**.',
              '- Classification uses reviewed multilingual templates plus an explicit text-to-family taxonomy for all 701 distinct IFC-Bench questions, 24 CubiCasa questions, and 64 Opening Design questions. These semantic assignments were reviewed during this analysis; running the generator uses no LLM/API calls, sampling, or reference-answer inference.',
              '- The generator rejects unknown questions/labels/sources and checks coverage and reconciled totals. A changed corpus may require taxonomy review before regeneration.', '',
              'Run from the repository root:', '', '```sh',
              'python scripts/classify_questions.py --report-date ' + report_date,
              'python scripts/classify_questions.py --report-date ' + report_date + ' --check',
              '# Optional: export every source row with its family (analysis data, no answers).',
              'python scripts/classify_questions.py --report-date ' + report_date + ' --check --rows-out question-classification.jsonl',
              'python scripts/check_docs.py', '```', '',
              'Use the configured Python interpreter on either OS. The optional row export writes the named JSONL even with `--check`; the tracked Markdown report stays unchanged. No reference answers are exported.', '',
              'Sources: [classifier](../scripts/classify_questions.py), [reviewed taxonomy](../scripts/question_classification_taxonomy.json), '
              '[dataset question file](../dataset/junction-dataset/questions.jsonl), [dataset README](../dataset/junction-dataset/README.md), '
              '[full dataset findings](../dataset/FULL_DATASET_FINDINGS.md), and [project scope](PROJECT_SCOPE.md).', '']
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'dataset/junction-dataset')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/QUESTION_CLASSIFICATION.md')
    parser.add_argument('--taxonomy', type=Path, default=Path(__file__).with_name('question_classification_taxonomy.json'))
    parser.add_argument('--report-date', default=date.today().isoformat())
    parser.add_argument('--rows-out', type=Path, help='Optional analysis JSONL with every row, its text and family; no answers')
    parser.add_argument('--check', action='store_true', help='Check the report is current without modifying it')
    args = parser.parse_args()
    taxonomy = json.loads(args.taxonomy.read_text(encoding='utf-8'))
    rows, digest, blanks = classify(args.dataset, taxonomy)
    content = report(rows, digest, blanks, args.dataset, args.report_date)
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding='utf-8') != content:
            print(f'Out of date: {args.output}')
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding='utf-8')
    if args.rows_out:
        with args.rows_out.open('w', encoding='utf-8') as stream:
            for r in rows:
                stream.write(json.dumps(vars(r), ensure_ascii=False) + '\n')
    print(f'{len(rows):,} rows; {len({r.question for r in rows}):,} distinct texts; {len({r.family for r in rows}):,} families; no unclassified rows.')
    print(f'{"Checked" if args.check else "Wrote"} {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

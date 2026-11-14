"""Bounded offline native-metadata audits, with no geometry or model inference.

Inspection is structural evidence only. Class/port presence does not establish
usable connectivity; text presence does not establish correct table semantics.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAX_NATIVE_BYTES = 64 * 1024 * 1024


def ifc_metadata(path: Path) -> dict:
    import ifcopenshell
    model = ifcopenshell.open(str(path))
    classes = Counter(entity.is_a() for entity in model)
    def values(name):
        try:
            return model.by_type(name)
        except RuntimeError:
            return []
    property_names = sorted({item.Name for item in values('IfcPropertySingleValue') if item.Name})
    quantity_names = sorted({item.Name for item in values('IfcPhysicalSimpleQuantity') if item.Name})
    psets = sorted({item.Name for item in values('IfcPropertySet') if item.Name})
    qsets = sorted({item.Name for item in values('IfcElementQuantity') if item.Name})
    units = []
    for item in values('IfcUnitAssignment'):
        for unit in item.Units:
            units.append({'ifc_class': unit.is_a(), 'unit_type': getattr(unit, 'UnitType', None),
                          'name': getattr(unit, 'Name', None), 'prefix': getattr(unit, 'Prefix', None),
                          'currency': getattr(unit, 'Currency', None)})
    return {'method': 'IfcOpenShell native metadata; no geometry', 'ifcopenshell_version': ifcopenshell.version,
        'schema': model.schema, 'native_entity_count': sum(classes.values()), 'classes': dict(sorted(classes.items())),
        'single_value_property_names': property_names[:512], 'single_value_property_name_count': len(property_names),
        'quantity_names': quantity_names[:512], 'quantity_name_count': len(quantity_names),
        'property_sets': psets[:512], 'property_set_count': len(psets),
        'quantity_sets': qsets[:512], 'quantity_set_count': len(qsets),
        'catalog_names_capped': any(len(items) > 512 for items in (property_names, quantity_names, psets, qsets)),
        'unit_assignments': units[:128], 'unit_assignment_entries': len(units),
        'distribution_ports': len(values('IfcDistributionPort')),
        'port_connections': len(values('IfcRelConnectsPorts')),
        'port_to_element_connections': len(values('IfcRelConnectsPortToElement')),
        'has_recorded_true_north': any(getattr(context, 'TrueNorth', None) is not None for context in values('IfcGeometricRepresentationContext')),
        'limits': ['Native record presence only; query applicability, semantic completeness, port traversal, north applicability and evidence localization remain unverified.']}


def inspect_source(dataset: Path, asset: dict, *, timeout=20) -> dict:
    from .manifest import safe_source
    path = safe_source(dataset, asset['path'])
    base = {'path': asset['path'], 'source_sha256': asset['sha256'], 'format': asset['format'],
            'scope': 'original asset metadata', 'agent_reviewed': False}
    if not asset['available']:
        return {**base, 'status': 'asset_unavailable', 'information_absence_established': False}
    if path.stat().st_size > MAX_NATIVE_BYTES:
        return {**base, 'status': 'not_inspected_size_limit', 'max_bytes': MAX_NATIVE_BYTES,
                'information_absence_established': False}
    if asset['format'] == 'ifc':
        command = [sys.executable, str(Path(__file__).resolve()), '--ifc-worker', str(path)]
        payload = None
    elif asset['format'] == 'pdf':
        node = shutil.which('node')
        if not node:
            return {**base, 'status': 'not_inspected_parser_unavailable', 'information_absence_established': False}
        command = [node, '--max-old-space-size=384', str(ROOT / 'frontend/scripts/pdf-document-worker.mjs')]
        payload = json.dumps({'source_path': str(path), 'snapshot': {'page_index': 0, 'rotation': 0,
                            'display_width': 1, 'display_height': 1}}).encode()
    else:
        return {**base, 'status': 'not_inspected_format', 'information_absence_established': False}
    try:
        process = subprocess.run(command, input=payload, capture_output=True, timeout=timeout, check=False)
        if len(process.stdout) > 8 * 1024 * 1024:
            return {**base, 'status': 'not_inspected_output_limit', 'information_absence_established': False}
        record = json.loads(process.stdout)
        if process.returncode or 'error' in record:
            return {**base, 'status': 'inspection_failed', 'error_code': record.get('error', {}).get('code', 'parser_error'),
                    'information_absence_established': False}
        if asset['format'] == 'pdf':
            spans = record['spans']
            record = {'method': 'PDF.js native text; first page only', 'pdfjs_version': record['pdfjs_version'],
                'page_count': record['page_count'], 'inspected_page_indices': [0], 'first_page_text_spans': len(spans),
                'first_page_text_characters': sum(len(span['text']) for span in spans),
                'first_page_text_enumeration_complete': record['text_enumeration_complete'],
                'first_page_rotation': record['page_rotation'], 'first_page_source_bounds': record['source_bounds'],
                'first_page_numeric_text_spans': sum(any(character.isdigit() for character in span['text']) for span in spans),
                'limits': ['Only native text on page 0 was inspected; no table reconstruction, printed quantity semantics, visual inventory or source-to-display mapping was validated.']}
        return {**base, 'status': 'structurally_inspected', 'information_absence_established': False, 'observations': record}
    except subprocess.TimeoutExpired:
        return {**base, 'status': 'inspection_timeout', 'timeout_seconds': timeout, 'information_absence_established': False}
    except (OSError, ValueError, KeyError):
        return {**base, 'status': 'inspection_failed', 'error_code': 'parser_unavailable_or_invalid_output', 'information_absence_established': False}


def audit_sources(dataset: Path, manifest: dict, *, pdf_limit=16, ifc_limit=80, workers=3, timeout=20) -> dict:
    assets = manifest['assets']
    # Inspect rare IFC families and all Opening Design sources first, then a
    # bounded project-diverse sample; the ledger keeps every omitted source open.
    ifcs = sorted((asset for asset in assets if asset['format'] == 'ifc'),
                  key=lambda asset: ('/ifc_bench/' not in '/' + asset['path'], asset['path']))[:ifc_limit]
    pdfs = sorted((asset for asset in assets if asset['format'] == 'pdf'),
                  key=lambda asset: ('/opening_design/' not in '/' + asset['path'], asset['path']))
    selected, projects = [], set()
    for asset in pdfs:
        if len(selected) >= pdf_limit:
            break
        if asset['project_hint'] not in projects or '/opening_design/' in '/' + asset['path']:
            selected.append(asset)
            projects.add(asset['project_hint'])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda asset: inspect_source(dataset, asset, timeout=timeout), [*ifcs, *selected]))
    return {'version': 'answer-source-prerequisite-audit-v1', 'reference_answers_used': False,
            'manual_or_agent_source_review': False, 'completion_claim': False,
            'limits': {'max_source_bytes': MAX_NATIVE_BYTES, 'per_file_timeout_seconds': timeout,
                       'ifc_file_limit': ifc_limit, 'pdf_file_limit': pdf_limit, 'pdf_pages_per_file': 1},
            'counts': dict(Counter(record['status'] for record in results)), 'sources': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ifc-worker', type=Path)
    args = parser.parse_args()
    if args.ifc_worker:
        try:
            print(json.dumps(ifc_metadata(args.ifc_worker), ensure_ascii=False))
        except Exception:
            print(json.dumps({'error': {'code': 'native_ifc_parse_failed'}}))
            raise SystemExit(1)


if __name__ == '__main__':
    main()

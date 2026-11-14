import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveEvidenceElements } from './evidence.ts';
import type { EvidenceElement } from './evidence.ts';

const element = (entity_id: string, step_id: number | null, guid: string | null): EvidenceElement => ({
  entity_id, step_id, guid, ifc_class: 'IfcWindow', name: entity_id,
});

test('only source STEP/GUID pairs in drawable geometry are marked', () => {
  const result = resolveEvidenceElements([
    element('window:first', 10, 'guid-A'),
    element('window:metadata', 20, 'guid-B'),
    element('window:mismatched', 30, 'different-guid'),
    element('window:no-locator', null, 'guid-C'),
  ], new Set([10, 30]), new Map([[10, 'guid-A'], [30, 'guid-C']]));
  assert.deepEqual(result.stepIds, [10]);
  assert.deepEqual(result.unavailable, ['window:metadata', 'window:no-locator']);
  assert.deepEqual(result.identityMismatches, ['window:mismatched']);
});

test('evidence with GUID missing in preview is withheld; no GUID uses revision-scoped STEP locator', () => {
  const result = resolveEvidenceElements([
    element('missing-guid', 10, 'guid-A'),
    element('step-only', 20, null),
    element('step-only-duplicate-depiction', 20, null),
  ], new Set([10, 20]), new Map());
  assert.deepEqual(result.stepIds, [20]);
  assert.deepEqual(result.identityMismatches, ['missing-guid']);
  assert.equal(result.unavailable.length, 0);
});

test('empty evidence yields an empty highlight without inventing a count', () => {
  assert.deepEqual(resolveEvidenceElements([], new Set([10]), new Map()), {
    stepIds: [], unavailable: [], identityMismatches: [],
  });
});

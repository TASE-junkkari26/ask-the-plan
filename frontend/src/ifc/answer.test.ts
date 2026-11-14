import test from 'node:test';
import assert from 'node:assert/strict';
import { sourceReferenceLabel } from './answer.ts';
import type { EvidenceElement } from './evidence.ts';

test('spatial answer references preserve literal source names and distinguish duplicate room names', () => {
  const elements = new Map<string, EvidenceElement>([
    ['room:one', { entity_id: 'room:one', name: '121.A', ifc_class: 'IfcSpace', step_id: 16 }],
    ['room:two', { entity_id: 'room:two', name: '121.A', ifc_class: 'IfcSpace', step_id: 99 }],
  ]);
  assert.equal(sourceReferenceLabel('room:one', elements), '121.A · #16');
  assert.equal(sourceReferenceLabel('room:two', elements), '121.A · #99');
});

test('metadata-only and unresolved references retain inspectable identities without inventing locators', () => {
  const elements = new Map<string, EvidenceElement>([
    ['zone:a', { entity_id: 'zone:a', name: 'Lämmitys', ifc_class: 'IfcZone', step_id: null }],
    ['element:42', { entity_id: 'element:42', name: '#42', ifc_class: 'IfcElement', step_id: 42 }],
    ['unnamed', { entity_id: 'unnamed', name: '', ifc_class: 'IfcSpace', step_id: 51 }],
  ]);
  assert.equal(sourceReferenceLabel('zone:a', elements), 'Lämmitys');
  assert.equal(sourceReferenceLabel('element:42', elements), '#42');
  assert.equal(sourceReferenceLabel('unnamed', elements), 'IfcSpace · #51');
  assert.equal(sourceReferenceLabel('unresolved:source', elements), 'unresolved:source');
});

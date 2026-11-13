import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DRAWINGS, BEDROOM, doorMarks } from './data.ts';
import { askDemo, resolveDemo } from './engine.ts';
import { polygonArea } from '../lib/viewport.ts';

test('counts stay inside the selected drawing rather than accumulating floors', () => {
  const totals = DRAWINGS.map(
    (d) => resolveDemo(d, 'How many doors are shown?', 'en').value,
  );
  assert.deepEqual(totals, ['8', '6', '8', '1']);
  assert.equal(
    resolveDemo(DRAWINGS[0], 'How many doors are in the entire building?', 'en')
      .result.status,
    'missing_information',
  );
});

test('English and Finnish questions resolve to the same objects', () => {
  const en = resolveDemo(DRAWINGS[0], 'How many windows are shown?', 'en');
  const fi = resolveDemo(
    DRAWINGS[0],
    'Kuinka monta ikkunaa kuvassa näkyy?',
    'fi',
  );
  assert.equal(en.value, '7');
  assert.equal(fi.value, en.value);
  assert.deepEqual(
    fi.marks.map((m) => m.entityId),
    en.marks.map((m) => m.entityId),
  );
});

test('source appearances share identity but source-local mark IDs remain distinct', () => {
  const plan = doorMarks(DRAWINGS[0])[2];
  const schedule = doorMarks(DRAWINGS[2])[2];
  assert.equal(plan.entityId, schedule.entityId);
  assert.notEqual(plan.id, schedule.id);
  assert.notEqual(doorMarks(DRAWINGS[1])[2].entityId, plan.entityId);
});

test('the net area and calculation trace agree with the polygon and interior hole', () => {
  assert.ok(BEDROOM.polygon && BEDROOM.holes);
  const shell = polygonArea(BEDROOM.polygon);
  const hole = BEDROOM.holes.reduce((sum, ring) => sum + polygonArea(ring), 0);
  const physicalArea = (shell - hole) * 0.015 ** 2;
  const response = resolveDemo(
    DRAWINGS[0],
    'What is the net area of Bedroom 01?',
    'en',
  );
  assert.equal(physicalArea.toFixed(2), response.value);
  assert.equal(response.result.calculations?.length, 3);
  assert.equal(response.result.calculations?.at(-1)?.input_node_ids?.length, 2);
  assert.ok(
    BEDROOM.holes.every((ring) =>
      ring.every(([x, y]) => x > 160 && x < 480 && y > 155 && y < 340),
    ),
  );
});

test('a different room does not receive Bedroom 01’s prepared area', () => {
  const result = resolveDemo(
    DRAWINGS[0],
    'What is the area of Bedroom 02?',
    'en',
  );
  assert.equal(result.result.status, 'unsupported_operation');
  assert.equal(result.marks.length, 0);
});

test('schedule lookup preserves exact door identity and source unit', () => {
  const response = resolveDemo(
    DRAWINGS[2],
    'What is the width of door D03?',
    'en',
  );
  assert.equal(response.intent, 'schedule');
  assert.equal(response.value, '900');
  assert.equal(response.unit, 'mm');
  assert.equal(response.marks[0].entityId, 'demo:door:D03');
  assert.deepEqual(response.marks[0].bounds, [570, 299, 120, 42]);
});

test('absent fire ratings and unknown fixtures never produce invented zero counts', () => {
  const absent = resolveDemo(DRAWINGS[2], 'What is the fire rating?', 'en');
  assert.equal(absent.result.status, 'missing_information');
  assert.equal(absent.result.claims?.length ?? 0, 0);
  assert.equal(absent.value, '');
  const unsupported = resolveDemo(
    DRAWINGS[2],
    'What is the width of D42?',
    'en',
  );
  assert.equal(unsupported.result.status, 'unsupported_operation');
  assert.equal(unsupported.marks.length, 0);
});

test('the declared count and evidence membership remain consistent', () => {
  for (const drawing of DRAWINGS) {
    const response = resolveDemo(drawing, 'How many doors are shown?', 'en');
    const claim = response.result.claims?.[0];
    assert.equal(claim?.value.kind, 'count');
    if (claim?.value.kind === 'count')
      assert.equal(
        claim.value.value,
        response.result.entity_sets?.[0].entity_ids?.length,
      );
    assert.equal(
      new Set(response.marks.map((m) => m.entityId)).size,
      response.marks.length,
    );
  }
});

test('cancelling an in-flight query prevents a stale response after a source switch', async () => {
  const controller = new AbortController();
  const pending = askDemo(
    DRAWINGS[0],
    'How many doors?',
    'en',
    controller.signal,
  );
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
});

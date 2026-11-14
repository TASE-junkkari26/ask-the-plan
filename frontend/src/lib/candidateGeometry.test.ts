import { test } from 'node:test';
import assert from 'node:assert/strict';
import { candidateBounds } from './candidateGeometry.ts';
import type { ImageCandidate } from '../contracts/ImageCandidateResponse';

function box(x1: number, y1: number, x2: number, y2: number): ImageCandidate {
  return {
    id: 'candidate-001', category: 'window', source_label: '121.A',
    geometry: { kind: 'box', minimum: [x1, y1], maximum: [x2, y2] },
    uncertain: false, uncertainty_reason: null, visual_cue: 'Synthetic window.',
  };
}

test('landscape boxes share image fit scale and vertical letterboxing', () => {
  const image = { width: 2000, height: 1000 };
  assert.deepEqual(candidateBounds(box(0, 0, 2000, 1000), image), [25, 127.5, 1050, 525]);
  assert.deepEqual(candidateBounds(box(200, 100, 400, 300), image), [130, 180, 105, 105]);
});

test('portrait boxes share horizontal letterboxing with the imported image', () => {
  const image = { width: 500, height: 1000 };
  assert.deepEqual(candidateBounds(box(0, 0, 500, 1000), image), [367.5, 25, 365, 730]);
  assert.deepEqual(candidateBounds(box(100, 200, 300, 400), image), [440.5, 171, 146, 146]);
});

test('right and bottom image edges map to fitted bounds without dropping offsets', () => {
  const [x, y, width, height] = candidateBounds(box(900, 400, 1000, 500), { width: 1000, height: 500 });
  assert.equal(x + width, 1075);
  assert.equal(y + height, 652.5);
  assert.throws(() => candidateBounds(box(0, 0, 1, 1), { width: 0, height: 100 }), /positive/);
});

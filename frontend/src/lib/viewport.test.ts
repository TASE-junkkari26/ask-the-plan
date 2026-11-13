import { test } from 'node:test';
import assert from 'node:assert/strict';
import { areaPath, clampZoom, focusPan } from './viewport.ts';

test('focusing a source point remains correct after quarter-turn rotation', () => {
  const bounds: [number, number, number, number] = [200, 200, 100, 100];
  const normal = focusPan(bounds, 1100, 2, 0);
  const rotated = focusPan(bounds, 1100, 2, 90);
  assert.equal(normal.x, 600);
  assert.equal(normal.y, 280);
  assert.ok(Math.abs(rotated.x + 280) < 1e-9);
  assert.ok(Math.abs(rotated.y - 600) < 1e-9);
});

test('zoom is bounded and area paths preserve separate closed hole rings', () => {
  assert.equal(clampZoom(0.1), 0.5);
  assert.equal(clampZoom(8), 3);
  const path = areaPath(
    [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
    ],
    [
      [
        [2, 2],
        [3, 2],
        [3, 3],
        [2, 3],
      ],
    ],
  );
  assert.equal((path.match(/M/g) ?? []).length, 2);
  assert.equal((path.match(/Z/g) ?? []).length, 2);
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { MeshLambertMaterial, ShaderMaterial } from 'three';
import {
  clippingRange,
  renderPixelRatio,
  styleIfcSurface,
} from './rendering.ts';

const building = {
  min: { x: -10, y: 0, z: -10 },
  max: { x: 10, y: 20, z: 10 },
};
test('clipping keeps small details visible and distant large models inside the frustum', () => {
  const inside = clippingRange({ x: 0, y: 10, z: 0.5 }, building);
  assert.ok(inside.near < 0.01 && inside.far > 20);
  const outside = clippingRange({ x: 0, y: 10, z: 100 }, building);
  assert.ok(outside.near > 30 && outside.far > 110);
  const campus = clippingRange(
    { x: 5000, y: 5000, z: 5000 },
    {
      min: { x: -1000, y: -1000, z: -1000 },
      max: { x: 1000, y: 1000, z: 1000 },
    },
  );
  assert.ok(campus.far > 10_000 && campus.near > 1000);
  assert.ok(campus.far / campus.near < 5);
});
test('empty/non-geometric bounds cannot create NaN clipping planes', () => {
  assert.deepEqual(
    clippingRange(
      { x: 0, y: 0, z: 0 },
      {
        min: { x: Infinity, y: Infinity, z: Infinity },
        max: { x: -Infinity, y: -Infinity, z: -Infinity },
      },
    ),
    { near: 0.01, far: 1000, radius: 1 },
  );
});
test('large and HiDPI viewports keep a bounded drawing-buffer pixel cost', () => {
  assert.equal(renderPixelRatio(800, 600, 2), 1.5);
  const ratio = renderPixelRatio(3840, 2160, 2);
  assert.ok(3840 * 2160 * ratio ** 2 <= 3_000_001);
  assert.equal(renderPixelRatio(0, 0, 1), 1);
});
test('coplanar surface bias is stable, separates materials, and preserves selection bias', () => {
  const red = new MeshLambertMaterial({ color: '#aa0000' });
  const blue = new MeshLambertMaterial({
    color: '#0000aa',
    transparent: true,
    opacity: 0.5,
  });
  const same = red.clone();
  styleIfcSurface(red);
  styleIfcSurface(blue);
  styleIfcSurface(same);
  assert.equal(red.polygonOffset, true);
  assert.notEqual(red.polygonOffsetFactor, blue.polygonOffsetFactor);
  assert.equal(red.polygonOffsetFactor, same.polygonOffsetFactor);
  assert.equal(red.depthWrite, true);
  assert.equal(blue.depthWrite, false);
  const selected = new MeshLambertMaterial({
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
    transparent: true,
  });
  styleIfcSurface(selected);
  assert.equal(selected.polygonOffsetFactor, -1);
  assert.equal(selected.depthWrite, false);
  const lod = Object.assign(new ShaderMaterial(), { isLodMaterial: true });
  styleIfcSurface(lod);
  assert.equal(lod.polygonOffset, false);
});

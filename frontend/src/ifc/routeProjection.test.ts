import assert from 'node:assert/strict';
import test from 'node:test';
import type { RouteEvaluation } from '../contracts/IfcQuestionResponse';
import { projectRoute } from './routeProjection.ts';

const route: RouteEvaluation = { subject_id: 'room:1', method: 'native_walking_route.v1',
  frame: 'ifc_world', unit: 'm', status: 'partial', tolerance_m: .001,
  path_points_m: [[10000, 20000, 3], [10003, 20004, 3], [10003, 20004, 6]] };

test('plan projection preserves a stair rise in its physical path length and source coordinates', () => {
  const original = JSON.stringify(route);
  const display = projectRoute(route)!;
  assert.equal(display.length, 8); // Five metres horizontally, three metres vertically.
  assert.equal(display.points.at(-1)![2], 6);
  const xy = display.polyline.split(' ');
  assert.equal(xy[1], xy[2]); // Plan projection does not invent horizontal stair travel.
  assert.equal(JSON.stringify(route), original);
});

test('unknown, wrong-frame and malformed routes cannot produce a drawn path or zero distance', () => {
  for (const invalid of [{ ...route, status: 'unavailable' }, { ...route, frame: 'display' },
    { ...route, unit: 'mm' }, { ...route, path_points_m: [[0, 0, 0]] },
    { ...route, path_points_m: [[0, 0, 0], [1, '2', 0]] },
    { ...route, path_points_m: [[0, 0, 0], [1, NaN, 0]] }]) {
    assert.equal(projectRoute(invalid as RouteEvaluation), null);
  }
});

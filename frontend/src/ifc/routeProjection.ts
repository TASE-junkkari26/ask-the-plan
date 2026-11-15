import type { RouteEvaluation } from '../contracts/IfcQuestionResponse';

export type RoutePoint = [number, number, number];

/** Display source-world metres without assuming the rebased viewer transform. */
export function projectRoute(route: RouteEvaluation) {
  const raw = route.path_points_m;
  if (route.frame !== 'ifc_world' || (route.unit ?? 'm') !== 'm' || route.status === 'unavailable'
    || !Array.isArray(raw) || raw.length < 2 || raw.length > 2048) return null;
  if (!raw.every((point) => Array.isArray(point) && point.length === 3
    && point.every((coordinate) => typeof coordinate === 'number' && Number.isFinite(coordinate)))) return null;
  const points = raw as RoutePoint[];
  const xs = points.map((point) => point[0]), ys = points.map((point) => point[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = maxX - minX, height = maxY - minY;
  const scale = Math.min(268 / (width || 1), 148 / (height || 1));
  const offsetX = (300 - width * scale) / 2, offsetY = (180 - height * scale) / 2;
  const projected = points.map(([x, y]) => [offsetX + (x - minX) * scale, 180 - offsetY - (y - minY) * scale]);
  const length = points.slice(1).reduce((sum, point, index) => sum + Math.hypot(
    point[0] - points[index][0], point[1] - points[index][1], point[2] - points[index][2]), 0);
  if (!Number.isFinite(length) || projected.some((point) => point.some((coordinate) => !Number.isFinite(coordinate)))) return null;
  return { points, length, polyline: projected.map((point) => point.join(',')).join(' '),
    start: projected[0], end: projected.at(-1)! };
}

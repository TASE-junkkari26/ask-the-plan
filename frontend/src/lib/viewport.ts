export function clampZoom(value: number): number {
  return Math.min(3, Math.max(0.5, value));
}
export function polygonArea(points: number[][]): number {
  return Math.abs(
    points.reduce((sum, p, i) => {
      const next = points[(i + 1) % points.length];
      return sum + p[0] * next[1] - next[0] * p[1];
    }, 0) / 2,
  );
}
export function ringPath(points: number[][]): string {
  return `${points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ')} Z`;
}
export function areaPath(
  polygon: number[][],
  holes: number[][][] = [],
): string {
  return [polygon, ...holes].map(ringPath).join(' ');
}

export function focusPan(
  bounds: [number, number, number, number],
  paperWidth: number,
  zoom: number,
  rotation: number,
) {
  const [x, y, width, height] = bounds;
  const dx = 550 - (x + width / 2),
    dy = 390 - (y + height / 2);
  const radians = (rotation * Math.PI) / 180;
  const scale = (paperWidth / 1100) * zoom;
  return {
    x: (dx * Math.cos(radians) - dy * Math.sin(radians)) * scale,
    y: (dx * Math.sin(radians) + dy * Math.cos(radians)) * scale,
  };
}

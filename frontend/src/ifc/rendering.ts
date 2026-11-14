import type { Material, MeshLambertMaterial } from 'three';

interface Point {
  x: number;
  y: number;
  z: number;
}
interface Bounds {
  min: Point;
  max: Point;
}

/** Keep depth precision near the inspected building instead of a fixed 1–1000 m range. */
export function clippingRange(eye: Point, bounds: Bounds) {
  const values = [
    eye.x,
    eye.y,
    eye.z,
    bounds.min.x,
    bounds.min.y,
    bounds.min.z,
    bounds.max.x,
    bounds.max.y,
    bounds.max.z,
  ];
  const dx = bounds.max.x - bounds.min.x;
  const dy = bounds.max.y - bounds.min.y;
  const dz = bounds.max.z - bounds.min.z;
  if (!values.every(Number.isFinite) || Math.min(dx, dy, dz) < 0)
    return { near: 0.01, far: 1000, radius: 1 };
  const radius = Math.max(0.001, Math.hypot(dx, dy, dz) / 2);
  const distance = Math.hypot(
    eye.x - (bounds.min.x + dx / 2),
    eye.y - (bounds.min.y + dy / 2),
    eye.z - (bounds.min.z + dz / 2),
  );
  const closeNear = Math.min(0.05, Math.max(0.002, radius * 0.0001));
  const near = Math.max(closeNear, (distance - radius) * 0.5);
  return { near, far: Math.max(near * 2, distance + radius * 1.25, 1), radius };
}

/** Limit GPU fill cost on Retina/4K screens without changing React's CSS resolution. */
export function renderPixelRatio(
  width: number,
  height: number,
  deviceRatio: number,
) {
  const ratio =
    Number.isFinite(deviceRatio) && deviceRatio > 0 ? deviceRatio : 1;
  return Math.min(
    ratio,
    1.5,
    Math.sqrt(3_000_000 / Math.max(1, width * height)),
  );
}

/** Stable, material-specific offsets separate coplanar IFC finishes. LOD lines are not surfaces. */
export function styleIfcSurface(material: Material) {
  if ('isLodMaterial' in material && material.isLodMaterial) return;
  if (!('isMeshLambertMaterial' in material)) return;
  const surface = material as MeshLambertMaterial;
  if (surface.transparent) surface.depthWrite = false;
  // Explicit selection offsets take priority over base-material separation.
  if (surface.polygonOffset) return;
  const key = `${surface.color.getHex()}:${surface.opacity}:${surface.side}:${surface.userData.customId ?? ''}:${surface.userData.localId ?? ''}`;
  let hash = 2166136261;
  for (let i = 0; i < key.length; i++)
    hash = Math.imul(hash ^ key.charCodeAt(i), 16777619);
  surface.polygonOffset = true;
  surface.polygonOffsetUnits = 1;
  surface.polygonOffsetFactor = 0.5 + (hash >>> 0) / 0x1_0000_0000;
}

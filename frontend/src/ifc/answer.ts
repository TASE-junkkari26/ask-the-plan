import type { EvidenceElement } from './evidence';

/** Preserve source names and distinguish identical names with their native locator. */
export function sourceReferenceLabel(entityId: string, elements: ReadonlyMap<string, EvidenceElement>): string {
  const element = elements.get(entityId);
  if (!element) return entityId;
  const label = element.name || element.ifc_class;
  const locator = element.step_id == null ? '' : `#${element.step_id}`;
  return locator && label !== locator ? `${label} · ${locator}` : label;
}

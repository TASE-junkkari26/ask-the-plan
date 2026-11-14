/** Source identifiers are revision-scoped. A drawable STEP ID must also match its GUID. */
export interface EvidenceElement {
  entity_id: string;
  step_id?: number | null;
  guid?: string | null;
  ifc_class: string;
  name: string;
}

export interface HighlightReport {
  stepIds: number[];
  unavailable: string[];
  identityMismatches: string[];
  hiddenStepIds?: number[];
}

export function resolveEvidenceElements(
  elements: EvidenceElement[],
  geometryIds: ReadonlySet<number>,
  sourceGuids: ReadonlyMap<number, string | null>,
): HighlightReport {
  const stepIds = new Set<number>();
  const unavailable: string[] = [];
  const identityMismatches: string[] = [];
  for (const element of elements) {
    if (element.step_id == null || !geometryIds.has(element.step_id)) {
      unavailable.push(element.entity_id);
      continue;
    }
    if (element.guid != null && sourceGuids.get(element.step_id) !== element.guid) {
      identityMismatches.push(element.entity_id);
      continue;
    }
    stepIds.add(element.step_id);
  }
  return { stepIds: [...stepIds], unavailable, identityMismatches };
}

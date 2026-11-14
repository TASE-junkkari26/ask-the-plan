import type { AnswerResponse, AnswerSentence, Fact } from '../contracts/AnswerResponse';

export interface AnswerEvidenceLocation {
  anchorId: string;
  label: string;
  selectorKind: string;
  selectorValue: string;
  quote?: string;
  box?: [number, number, number, number];
  sourceUrl?: string;
  pageIndex?: number;
}

/** Native source coordinates never become display pixels without the exact frame. */
function evidenceResolver(response: AnswerResponse, partKey: string): (anchorIds: readonly string[]) => AnswerEvidenceLocation[] {
  const part = response.parts.find((item) => item.key === partKey);
  const context = response.evidence_contexts?.find((item) => item.id === part?.evidence_context_id);
  const bundle = context?.bundle;
  if (!bundle) return () => [];
  const snapshot = context.source_snapshot ?? response.source;
  const sameDisplay = (['source_sha256', 'source_revision', 'display_sha256', 'page_index', 'layout_name',
    'rotation', 'display_width', 'display_height', 'viewport_transform', 'source_bounds'] as const)
    .every((key) => JSON.stringify(snapshot[key] ?? (key === 'rotation' ? 0 : null))
      === JSON.stringify(response.source[key] ?? (key === 'rotation' ? 0 : null)));
  const anchors = new Map((bundle.anchors ?? []).map((item) => [item.id, item]));
  const assets = new Map(bundle.assets.map((item) => [item.id, item]));
  const geometries = new Map((bundle.geometries ?? []).map((item) => [item.id, item]));
  const frames = new Map((bundle.frames ?? []).map((item) => [item.id, item]));
  const candidates = new Map((response.candidate_response?.candidates ?? []).map((item) => [item.id, item]));
  return (anchorIds) => [...new Set(anchorIds)].flatMap((id) => {
    const anchor = anchors.get(id);
    if (!anchor) return [];
    const selector = anchor.selector;
    const location: AnswerEvidenceLocation = {
      anchorId: id, selectorKind: selector.kind, selectorValue: selector.value,
      label: `${selector.kind === 'step_id' ? '#' : ''}${selector.value}${selector.property_path?.length ? ` · ${selector.property_path.join('.')}` : ''}`,
      quote: anchor.quote?.text,
      pageIndex: snapshot.page_index ?? undefined,
    };
    const sourceAsset = assets.get(anchor.asset_id);
    if (sourceAsset && /^\/api\/v1\/sources\/[^/?#]+(?:\/display)?$/.test(sourceAsset.uri))
      location.sourceUrl = sourceAsset.uri + (sourceAsset.format === 'pdf' && snapshot.page_index != null ? `#page=${snapshot.page_index + 1}` : '');
    const candidate = sameDisplay && selector.kind === 'image_region'
      && response.candidate_response?.image.sha256 === snapshot.display_sha256
      ? candidates.get(selector.value) : null;
    if (candidate) location.box = [...candidate.geometry.minimum, ...candidate.geometry.maximum] as [number, number, number, number];
    const geometry = anchor.geometry_id ? geometries.get(anchor.geometry_id) : undefined;
    const frame = geometry ? frames.get(geometry.frame_id) : undefined;
    const asset = frame ? assets.get(frame.asset_id) : undefined;
    if (sameDisplay && geometry?.shape.kind === 'box' && frame?.dimension === 2 && frame.space === 'presentation'
        && asset?.sha256 === response.source.display_sha256)
      location.box = [...geometry.shape.minimum, ...geometry.shape.maximum] as [number, number, number, number];
    return [location];
  });
}

export function anchorEvidence(response: AnswerResponse, partKey: string, anchorIds: readonly string[]): AnswerEvidenceLocation[] {
  return evidenceResolver(response, partKey)(anchorIds);
}

export function sentenceEvidence(response: AnswerResponse, sentence: AnswerSentence): AnswerEvidenceLocation[] {
  return anchorEvidence(response, sentence.part_key, sentence.anchor_ids ?? []);
}

export interface AnswerMember {
  id: string;
  label: string;
  method?: string;
  facts: Fact[];
  evidence: AnswerEvidenceLocation[];
}

export interface AnswerMemberGroup {
  id: string;
  role: 'included' | 'excluded' | 'unresolved' | 'intermediate';
  count: number;
  members: AnswerMember[];
  grain?: string;
  explanation?: string;
  rules: string[];
  membersUri?: string | null;
  membersSha256?: string | null;
}

/** Preserve executor set roles; membership lists are evidence, not a new answer. */
export function partMemberGroups(response: AnswerResponse, partKey: string): AnswerMemberGroup[] {
  const part = response.parts.find((item) => item.key === partKey);
  const bundle = response.evidence_contexts?.find((context) => context.id === part?.evidence_context_id)?.bundle;
  const result = part?.result;
  if (!bundle || !result) return [];
  const entities = new Map((bundle.entities ?? []).map((entity) => [entity.id, entity]));
  const sourceFacts = new Map<string, Fact[]>();
  for (const fact of bundle.facts ?? []) {
    const prior = sourceFacts.get(fact.subject_id);
    if (prior) prior.push(fact);
    else sourceFacts.set(fact.subject_id, [fact]);
  }
  const representationAnchors = new Map<string, string[]>();
  for (const representation of bundle.representations ?? []) {
    const prior = representationAnchors.get(representation.entity_id) ?? [];
    prior.push(...(representation.anchor_ids ?? []));
    representationAnchors.set(representation.entity_id, prior);
  }
  const resolve = evidenceResolver(response, partKey);
  const members = (ids: readonly string[]) => ids.map((id) => {
    const entity = entities.get(id);
    const facts = sourceFacts.get(id) ?? [];
    const anchorIds = [...(entity?.provenance.anchor_ids ?? []), ...facts.flatMap((item) => item.provenance.anchor_ids ?? []),
      ...(representationAnchors.get(id) ?? [])];
    return { id, label: entity?.labels?.map((item) => item.text).join(' · ') || id,
      method: entity?.provenance.method, facts, evidence: resolve(anchorIds) };
  });
  const terminalIds = new Set((result.claims ?? []).flatMap((claim) => claim.evidence.map((binding) => binding.calculation_id)));
  const groups: AnswerMemberGroup[] = [];
  for (const set of result.entity_sets ?? []) {
    const calculations = (result.calculations ?? []).filter((node) => node.included_set_id === set.id || node.excluded_set_id === set.id);
    const terminal = calculations.filter((node) => terminalIds.has(node.id));
    const roles = new Set<AnswerMemberGroup['role']>();
    for (const node of terminal) {
      if (node.included_set_id === set.id) roles.add('included');
      if (node.excluded_set_id === set.id) roles.add('excluded');
    }
    if (!roles.size) roles.add('intermediate');
    for (const role of roles) groups.push({ id: `${set.id}:${role}`, role, count: set.count,
      members: members(set.entity_ids ?? []), grain: set.count_policy.grain,
      rules: [...new Set(calculations.flatMap((node) => node.rule_key ? [node.rule_key] : []))],
      explanation: role === 'intermediate' ? 'Supporting calculation set; not the final included or excluded selection.' : undefined,
      membersUri: set.members_uri, membersSha256: set.members_sha256 });
  }
  const coverageIds = new Set((result.claims ?? []).flatMap((claim) => claim.coverage_ids));
  for (const coverage of bundle.coverage ?? []) {
    if (!coverageIds.has(coverage.id) || !coverage.unresolved_entity_ids?.length) continue;
    groups.push({ id: coverage.id + ':unresolved', role: 'unresolved', count: coverage.unresolved_entity_ids.length,
      members: members(coverage.unresolved_entity_ids), grain: coverage.count_policy?.grain,
      explanation: coverage.explanation, rules: [] });
  }
  const issueIds = [...new Set((result.issues ?? []).filter((issue) => ['incomplete_coverage', 'conflicting_evidence', 'missing_information'].includes(issue.code))
    .flatMap((issue) => issue.entity_ids ?? []))].filter((id) => !groups.some((group) => group.role === 'unresolved' && group.members.some((member) => member.id === id)));
  if (issueIds.length) groups.push({ id: partKey + ':issues:unresolved', role: 'unresolved', count: issueIds.length,
    members: members(issueIds), explanation: 'These source members have unresolved evidence or inputs.', rules: [] });
  return groups;
}

export function answerStatusLabel(status: string, language: string): string {
  const fi: Record<string, string> = {
    answered: 'Vastattu', partial: 'Osittainen vastaus', missing_source: 'Lähde puuttuu',
    missing_information: 'Tieto puuttuu', incomplete_coverage: 'Kattavuus epävarma',
    unsupported_operation: 'Toimintoa ei ole toteutettu', needs_clarification: 'Tarvitaan tarkennus',
    conflicting_evidence: 'Ristiriitaiset lähdetiedot', insufficient_calibration: 'Mittakaava puuttuu',
    execution_error: 'Suoritus epäonnistui', blocked: 'Riippuva tulos puuttuu',
  };
  const en: Record<string, string> = {
    answered: 'Answered', partial: 'Partial answer', missing_source: 'Missing source',
    missing_information: 'Missing information', incomplete_coverage: 'Coverage unresolved',
    unsupported_operation: 'Implementation gap', needs_clarification: 'Clarification needed',
    conflicting_evidence: 'Conflicting evidence', insufficient_calibration: 'Calibration missing',
    execution_error: 'Execution failed', blocked: 'Dependent input unavailable',
  };
  return (language === 'fi' ? fi : en)[status] ?? status.replaceAll('_', ' ');
}

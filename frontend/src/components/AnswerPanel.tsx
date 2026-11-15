import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Check, CircleAlert, Download, Focus } from 'lucide-react';
import type { AnswerResponse } from '../contracts/AnswerResponse';
import type { Output } from '../contracts/QueryResult';
import { answerOutcomeLabel, answerStatusLabel, partAnswerPresentation, partMemberGroups, sentenceEvidence } from '../lib/answerEvidence';
import type { AnswerEvidenceLocation, AnswerMemberGroup } from '../lib/answerEvidence';
import { answerCost } from '../lib/answerMetrics';
import { formatEstimatedUsd, formatResponseTime } from '../lib/responseMetrics';
import './AnswerPanel.css';

function LazyDetails({ className, summary, children }: {
  className?: string;
  summary: ReactNode;
  children: () => ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  return <details className={className} onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary>{summary}</summary>{expanded && children()}
  </details>;
}

function PartCalculations({ response, partKey, fi }: { response: AnswerResponse; partKey: string; fi: boolean }) {
  const [limit, setLimit] = useState(25);
  const [factLimits, setFactLimits] = useState<Record<string, number>>({});
  const part = response.parts.find((item) => item.key === partKey)!;
  const bundle = response.evidence_contexts?.find((context) => context.id === part.evidence_context_id)?.bundle;
  const units = useMemo(() => new Map((bundle?.units ?? []).map((unit) => [unit.id, unit.symbol])), [bundle]);
  const facts = useMemo(() => new Map((bundle?.facts ?? []).map((fact) => [fact.id, fact])), [bundle]);
  const calculations = part.result?.calculations ?? [];
  return <div>
    {response.parts.length > 1 && <h3>{response.interpretation.requested_parts.find((item) => item.key === partKey)?.question}</h3>}
    {part.result?.claims?.map((claim) => <div className="source-answer-claim" key={claim.id}><strong>{claim.name}</strong><div><AnswerValue value={claim.value} units={units} /></div>{claim.count_policy && <small>{claim.count_policy.grain.replaceAll('_', ' ')} · {claim.count_policy.hierarchy.replaceAll('_', ' ')}</small>}</div>)}
    {calculations.slice(0, limit).map((calculation) => {
      const factLimit = factLimits[calculation.id] ?? 100;
      const factIds = calculation.fact_ids ?? [];
      return <div className="source-answer-calculation" key={calculation.id}>
        <strong>{calculation.operation.replaceAll('_', ' ')}</strong><div><AnswerValue value={calculation.output} units={units} /></div>
        {calculation.rule_key && <code>{calculation.rule_key}</code>}
        {!!factIds.length && <LazyDetails summary={<>{fi ? 'Lähdetiedot' : 'Source inputs'} ({factIds.length})</>}>{() => <>
          {factIds.slice(0, factLimit).map((id) => { const fact = facts.get(id); return <div key={id}><code>{fact?.original_property_path?.join('.') || fact?.property_key || id}</code>{fact?.value && <AnswerValue value={fact.value} units={units} />}</div>; })}
          {factIds.length > factLimit && <button className="text-button" onClick={() => setFactLimits((current) => ({ ...current, [calculation.id]: factLimit + 100 }))}>{fi ? 'Näytä seuraavat 100' : 'Show next 100'} ({factLimit} / {factIds.length})</button>}
        </>}</LazyDetails>}
      </div>;
    })}
    {calculations.length > limit && <button className="text-button" onClick={() => setLimit((count) => count + 25)}>{fi ? 'Näytä seuraavat 25' : 'Show next 25'} ({limit} / {calculations.length})</button>}
  </div>;
}

function AnswerValue({ value, units }: { value: Output; units: ReadonlyMap<string, string> }) {
  const [limit, setLimit] = useState(50);
  switch (value.kind) {
    case 'count': return <>{value.value}</>;
    case 'quantity': return <>{value.quality === 'lower_bound' ? 'At least ' : value.quality === 'upper_bound' ? 'At most ' : value.quality === 'estimated' ? 'Approximately ' : ''}{value.magnitude} {value.unit_id ? (units.get(value.unit_id) === '1' ? '' : units.get(value.unit_id) ?? value.unit_id) : ''} <small>({value.basis})</small></>;
    case 'text': return <>{value.value.text}</>;
    case 'boolean': return <>{value.value ? 'Yes' : 'No'}</>;
    case 'unavailable': return <>{value.explanation}</>;
    case 'references': return <><span>{value.entity_ids.slice(0, limit).join(', ')}</span>{value.entity_ids.length > limit && <button className="text-button" onClick={() => setLimit((count) => count + 50)}>Show next 50 ({limit} / {value.entity_ids.length})</button>}</>;
    case 'record': return <dl>{Object.entries(value.fields).map(([key, item]) => <div key={key}><dt>{key}</dt><dd><AnswerValue value={item} units={units} /></dd></div>)}</dl>;
    case 'list': return <><ol>{value.items.slice(0, limit).map((item, index) => <li key={index}><AnswerValue value={item} units={units} /></li>)}</ol>{value.items.length > limit && <button className="text-button" onClick={() => setLimit((count) => count + 50)}>Show next 50 ({limit} / {value.items.length})</button>}</>;
    case 'table': return <div className="answer-bound-table"><table><thead><tr>{value.columns.map((column) => <th key={column.key}>{column.label.text}</th>)}</tr></thead><tbody>{value.rows.slice(0, limit).map((row, index) => <tr key={index}>{value.columns.map((column) => <td key={column.key}><AnswerValue value={row[column.key]} units={units} /></td>)}</tr>)}</tbody></table>{value.rows.length > limit && <button className="text-button" onClick={() => setLimit((count) => count + 50)}>Show next 50 ({limit} / {value.rows.length})</button>}</div>;
  }
}

function MemberGroup({ group, fi, onLocate, units, propertyLabels }: {
  group: AnswerMemberGroup;
  fi: boolean;
  onLocate?: (location: AnswerEvidenceLocation) => void;
  units: ReadonlyMap<string, string>;
  propertyLabels: ReadonlyMap<string, string>;
}) {
  const [limit, setLimit] = useState(50);
  const roles = fi
    ? { included: 'Sisällytetyt lähdejäsenet', excluded: 'Poissuljetut lähdejäsenet', unresolved: 'Ratkaisemattomat lähdejäsenet', intermediate: 'Laskennan välivaiheen jäsenet' }
    : { included: 'Included source members', excluded: 'Excluded source members', unresolved: 'Unresolved source members', intermediate: 'Intermediate calculation members' };
  const filters = group.rules.flatMap((rule) => {
    const start = rule.indexOf(':{');
    if (start < 0) return [];
    try {
      const value = JSON.parse(rule.slice(start + 1));
      if (!Array.isArray(value.filters)) return [];
      return value.filters.flatMap((filter: unknown) => {
        if (!filter || typeof filter !== 'object' || !('column' in filter) || !('literal' in filter)
            || typeof filter.column !== 'string' || typeof filter.literal !== 'string') return [];
        const exclude = 'exclude' in filter && filter.exclude === true;
        return [`${exclude ? (fi ? 'Sulje pois' : 'Exclude matches') : (fi ? 'Sisällytä' : 'Keep matches')}: ${filter.column} → ${filter.literal}`];
      });
    } catch { return []; }
  });
  return <details className={`source-answer-locators source-answer-members source-answer-members-${group.role}`}>
    <summary><strong>{roles[group.role]}</strong> <span>{group.count}</span>{group.grain && <small> · {group.grain.replaceAll('_', ' ')}</small>}</summary>
    {group.explanation && <p>{group.explanation}</p>}
    {filters.length > 0 && <ul>{[...new Set(filters)].map((filter) => <li key={filter}>{filter}</li>)}</ul>}
    <ol>{group.members.slice(0, limit).map((member) => {
      const focus = member.evidence.find((location) => location.box || location.selectorKind === 'step_id');
      return <li key={member.id}>
        <strong>{member.label}</strong>
        {member.method === 'detected' && <p>{fi ? 'Vahvistamaton havaintoehdokas' : 'Unverified detection candidate'}</p>}
        {onLocate && focus && <button type="button" onClick={() => onLocate(focus)}><Focus size={12} /> {fi ? 'Näytä lähde' : 'Show source'}</button>}
        {!member.evidence.length && <p>{fi ? 'Lähdeviite puuttuu tältä jäseneltä.' : 'Source locator unavailable for this member.'}</p>}
        {member.facts.length > 0 && <details><summary>{fi ? 'Alkuperäiset lähdetiedot ja tila' : 'Source facts & status'} ({member.facts.length})</summary>
          <dl>{member.facts.map((fact) => <div key={fact.id}><dt>{propertyLabels.get(fact.property_key) ?? fact.original_property_path?.join('.') ?? fact.property_key}</dt>
            <dd>{fact.status === 'present' && fact.value ? <AnswerValue value={fact.value} units={units} /> : <span>{fact.status.replaceAll('_', ' ')}</span>}</dd></div>)}</dl>
        </details>}
        {member.evidence.length > 0 && <details><summary>{fi ? 'Lähdeviitteet' : 'Source references'} ({member.evidence.length})</summary>
          <ul>{member.evidence.map((location) => <li key={location.anchorId}>
            {onLocate && (location.box || location.selectorKind === 'step_id')
              ? <button type="button" onClick={() => onLocate(location)}>{location.label}</button>
              : <code>{location.label}</code>}
            {location.sourceUrl && !location.box && <a href={location.sourceUrl} target="_blank" rel="noopener noreferrer"> {fi ? 'Avaa alkuperäinen lähde' : 'Open original source'}{location.pageIndex == null ? '' : ` · ${location.pageIndex + 1}`}</a>}
            {location.quote && <p>{location.quote}</p>}
          </li>)}</ul>
        </details>}
      </li>;
    })}</ol>
    {group.members.length > limit && <button className="text-button" onClick={() => setLimit((count) => count + 50)}>{fi ? 'Näytä seuraavat 50' : 'Show next 50'} ({limit} / {group.count})</button>}
    {group.membersUri && <p>{fi ? 'Jäsenluettelo on erillinen lähdeaineisto.' : 'Member list is stored as a separate evidence resource.'} <code>{group.membersUri}</code>{group.membersSha256 && <code> SHA-256 {group.membersSha256}</code>}</p>}
    {group.rules.length > 0 && <details><summary>{fi ? 'Valinta- ja poissulkusäännöt' : 'Selection and exclusion rules'}</summary>{group.rules.map((rule) => <pre key={rule} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}><code>{rule}</code></pre>)}</details>}
  </details>;
}

export function exportAnswer(response: AnswerResponse, filename = 'answer-evidence.json', sourcePreview?: unknown) {
  const artifact = sourcePreview ? { ...response, source_preview: sourcePreview } : response;
  const url = URL.createObjectURL(new Blob([JSON.stringify(artifact, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** The backend owns every sentence and value; this panel only reveals bindings. */
export function AnswerPanel({ response, language = 'en', onLocate, imageUrl, sourcePreview }: {
  response: AnswerResponse;
  language?: string;
  onLocate?: (location: AnswerEvidenceLocation) => void;
  imageUrl?: string;
  sourcePreview?: unknown;
}) {
  const [selectedSentence, setSelectedSentence] = useState<string | null>(null);
  const [evidenceLimit, setEvidenceLimit] = useState(50);
  const fi = language === 'fi';
  const selected = response.narrative?.find((sentence) => sentence.id === selectedSentence);
  const locations = selected ? sentenceEvidence(response, selected) : [];
  const complete = response.parts.every((part) => part.status === 'answered');
  const cost = answerCost(response.metrics);
  const hasMemberEvidence = useMemo(() => response.parts.some((part) => {
    const result = part.result;
    const bundle = response.evidence_contexts?.find((context) => context.id === part.evidence_context_id)?.bundle;
    if (!result || !bundle) return false;
    if (result.entity_sets?.length || result.issues?.some((issue) =>
      ['incomplete_coverage', 'conflicting_evidence', 'missing_information'].includes(issue.code) && issue.entity_ids?.length)) return true;
    const coverageIds = new Set((result.claims ?? []).flatMap((claim) => claim.coverage_ids ?? []));
    return bundle.coverage?.some((coverage) => coverageIds.has(coverage.id) && coverage.unresolved_entity_ids?.length);
  }), [response]);
  return <section className="source-answer" aria-label={fi ? 'Vastaus ja lähteet' : 'Answer and source evidence'} aria-live="polite">
    <div className={`source-answer-outcome${complete ? '' : ' source-answer-outcome-partial'}`}>
      {complete ? <Check size={14} /> : <CircleAlert size={14} />}
      {answerOutcomeLabel(response, language)}
    </div>
    {response.interpretation.requested_parts.map((requested) => {
      const part = response.parts.find((item) => item.key === requested.key)!;
      const presentation = partAnswerPresentation(response, part.key, language);
      const visible = presentation.claims.length
        ? presentation.claims.map((sentence) => ({ sentence, text: sentence.text }))
        : presentation.message ? [{ sentence: presentation.messageSentence, text: presentation.message }] : [];
      return <div className="source-answer-part" key={part.key}>
        {response.parts.length > 1 && <h3>{requested.question}</h3>}
        {response.parts.length > 1 && part.status !== 'answered' && <p className="source-answer-part-status">{answerStatusLabel(part.status, language)}</p>}
        {visible.map(({ sentence, text }, index) => {
          const evidence = sentence ? sentenceEvidence(response, sentence) : [];
          return <div className="source-answer-sentence" key={sentence?.id ?? index}>
            <p>{text}</p>
            {sentence && evidence.length > 0 && <button type="button" className="source-answer-evidence-link" aria-pressed={selectedSentence === sentence.id}
              onClick={() => { setSelectedSentence((current) => current === sentence.id ? null : sentence.id); setEvidenceLimit(50); onLocate?.(evidence[0]); }}>
              <Focus size={12} />{fi ? 'Näytä piirustuksessa' : 'Show on drawing'}{evidence.length > 1 && <span>{evidence.length}</span>}
            </button>}
          </div>;
        })}
      </div>;
    })}
    {selected && locations.length > 0 && <section className="source-answer-locators" aria-label={fi ? 'Valitut lähdeviitteet' : 'Selected source references'}>
      <h3>{fi ? 'Lähdeviitteet' : 'Source references'}</h3>
      <ol>{locations.slice(0, evidenceLimit).map((location) => <li key={location.anchorId}>
        <button type="button" disabled={!onLocate || (!location.box && location.selectorKind !== 'step_id' && location.selectorKind !== 'image_region')}
          onClick={() => onLocate?.(location)}>{location.label}</button>
        {location.sourceUrl && !location.box && <a href={location.sourceUrl} target="_blank" rel="noopener noreferrer"> {fi ? 'Avaa alkuperäinen lähde' : 'Open original source'}{location.pageIndex == null ? '' : ` · ${location.pageIndex + 1}`}</a>}
        {location.quote && <p>{location.quote}</p>}
        {imageUrl && location.box && <svg viewBox={`${Math.max(0, location.box[0] - 15)} ${Math.max(0, location.box[1] - 15)} ${location.box[2] - location.box[0] + 30} ${location.box[3] - location.box[1] + 30}`} role="img" aria-label={location.quote ?? location.label}>
          <image href={imageUrl} width={response.source.display_width ?? 0} height={response.source.display_height ?? 0} />
          <rect x={location.box[0]} y={location.box[1]} width={location.box[2] - location.box[0]} height={location.box[3] - location.box[1]} fill="#147568" fillOpacity="0.12" stroke="#147568" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        </svg>}
      </li>)}</ol>
      {locations.length > evidenceLimit && <button className="text-button" onClick={() => setEvidenceLimit((limit) => limit + 50)}>{fi ? 'Näytä seuraavat 50' : 'Show next 50'} ({evidenceLimit} / {locations.length})</button>}
    </section>}
    <LazyDetails className="source-answer-details" summary={fi ? 'Lisätiedot' : 'Details'}>{() => <>
    <p className="source-answer-question">{response.question}</p>
    <p className="source-answer-scope"><strong>{fi ? 'Rajaus' : 'Scope'}</strong> {response.source.scope_label}</p>
    {response.interpretation.ambiguities?.map((item, index) => <p className="source-answer-part-status" key={index}>{item}</p>)}
    {response.parts.map((part) => {
      const notes = partAnswerPresentation(response, part.key, language).notes;
      return notes.length > 0 && <details className="source-answer-structured" key={part.key}>
        <summary>{fi ? 'Rajoitukset ja huomautukset' : 'Limitations & notes'}{response.parts.length > 1 && ` · ${response.interpretation.requested_parts.find((requested) => requested.key === part.key)?.question}`}</summary>
        <p className="source-answer-part-status">{answerStatusLabel(part.status, language)}</p>
        {notes.map((note, index) => <p className="source-answer-note" key={index}>{note}</p>)}
      </details>;
    })}
    {hasMemberEvidence && <LazyDetails className="source-answer-structured" summary={fi ? 'Laskennan lähdejäsenet' : 'Source members'}>{() => <>
      <p className="source-answer-scope">{fi ? 'Luettelot näyttävät laskennan lähdejäsenet. Havaintoehdokkaat voivat olla mukana myös ratkaisemattomissa jäsenissä; nämä luettelot eivät muodosta uutta kokonaismäärää.' : 'Lists show the executor’s source members. Detection candidates may also appear as unresolved; these evidence lists do not form a new total.'}</p>
      {response.parts.map((part) => {
        const bundle = response.evidence_contexts?.find((context) => context.id === part.evidence_context_id)?.bundle;
        const groups = partMemberGroups(response, part.key);
        const units = new Map((bundle?.units ?? []).map((unit) => [unit.id, unit.symbol]));
        const propertyLabels = new Map((bundle?.properties ?? []).map((property) => [property.key, property.labels[0]?.text ?? property.key]));
        return groups.length > 0 && <div key={part.key}>
          {response.parts.length > 1 && <h3>{response.interpretation.requested_parts.find((requested) => requested.key === part.key)?.question}</h3>}
          {groups.map((group) => <MemberGroup key={`${response.request_id}:${part.key}:${group.id}`} group={group} fi={fi} onLocate={onLocate} units={units} propertyLabels={propertyLabels} />)}
        </div>;
      })}
    </>}</LazyDetails>}
    <LazyDetails className="source-answer-structured" summary={fi ? 'Arvot ja laskennan lähtötiedot' : 'Values and calculation inputs'}>{() => <>
      {response.parts.map((part) => <PartCalculations key={`${response.request_id}:${part.key}`} response={response} partKey={part.key} fi={fi} />)}
      <p>{fi ? 'Vienti sisältää kaikki jäsenet, lähtötiedot ja laskentavaiheet.' : 'Export includes all members, source facts and calculation steps.'}</p>
    </>}</LazyDetails>
    <details className="source-answer-structured"><summary>{fi ? 'Analyysin vaiheet ja kustannukset' : 'Analysis steps & usage'}</summary>
      <p>{formatResponseTime(response.metrics.elapsed_ms, fi ? 'fi' : 'en')} · {response.metrics.external_attempts ?? 0} {fi ? 'mallikutsua' : 'model calls'}{response.metrics.cache_hit ? (fi ? ' · Välimuistista' : ' · Cached result') : ''}</p>
      {(response.metrics.calls ?? []).length === 0 && <p>{fi ? 'Lähdetiedot ja laskenta käsiteltiin paikallisesti.' : 'Source facts and calculations were processed locally.'}</p>}
      <ol>{response.metrics.calls?.map((call) => <li key={call.id}><strong>{call.purpose.replaceAll('_', ' ')}</strong> · {call.returned_model ?? call.requested_model} · {call.outcome}<br /><small>{call.prompt_tokens == null ? 'Input usage unavailable' : `${call.prompt_tokens} input tokens`} · {call.completion_tokens == null ? 'Output usage unavailable' : `${call.completion_tokens} output and thinking tokens`}</small></li>)}</ol>
      <p>{fi ? 'Kustannusarvio' : 'Estimated cost'}: {cost.amount == null ? (fi ? 'Ei saatavilla' : 'Unavailable') : cost.currency === 'USD' ? formatEstimatedUsd(cost.amount, fi ? 'fi' : 'en') : `${cost.amount} ${cost.currency ?? ''}`}</p>
      {cost.unknownCalls > 0 && <p>{fi ? 'Osasta mallikutsuja puuttuu kustannustieto.' : 'Cost information is missing for some model calls.'}</p>}
    </details>
    <details className="source-answer-revision"><summary>{fi ? 'Lähteen tunniste' : 'Source identity'}</summary><dl><dt>Original SHA-256</dt><dd><code>{response.source.source_sha256}</code></dd>{response.source.display_sha256 && <><dt>Display SHA-256</dt><dd><code>{response.source.display_sha256}</code></dd></>}</dl></details>
    </>}</LazyDetails>
    <button className="text-button source-answer-export" onClick={() => exportAnswer(response, 'answer-evidence.json', sourcePreview)}><Download size={13} />{fi ? 'Vie vastaus' : 'Export answer'}</button>
  </section>;
}

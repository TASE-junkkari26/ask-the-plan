import { useState } from 'react';
import { Check, CircleAlert, Download, Focus } from 'lucide-react';
import type { AnswerResponse } from '../contracts/AnswerResponse';
import type { Output } from '../contracts/QueryResult';
import { answerStatusLabel, partMemberGroups, sentenceEvidence } from '../lib/answerEvidence';
import type { AnswerEvidenceLocation, AnswerMemberGroup } from '../lib/answerEvidence';
import './AnswerPanel.css';

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
  return <details className={`source-answer-locators source-answer-members source-answer-members-${group.role}`} open={group.role !== 'intermediate'}>
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
  return <section className="source-answer" aria-label={fi ? 'Vastaus ja lähteet' : 'Answer and source evidence'} aria-live="polite">
    <p className="source-answer-question">{response.question}</p>
    <div className={`source-answer-outcome${complete ? '' : ' source-answer-outcome-partial'}`}>
      {complete ? <Check size={14} /> : <CircleAlert size={14} />}
      {complete ? (fi ? 'Vastattu' : 'Answered') : (fi ? 'Rajoitettu vastaus' : 'Qualified answer')}
    </div>
    {response.interpretation.requested_parts.map((requested) => {
      const part = response.parts.find((item) => item.key === requested.key)!;
      const sentences = (response.narrative ?? []).filter((sentence) => sentence.part_key === part.key);
      return <div className="source-answer-part" key={part.key}>
        {response.parts.length > 1 && <h3>{requested.question}</h3>}
        {part.status !== 'answered' && <p className="source-answer-part-status">{answerStatusLabel(part.status, language)}</p>}
        {sentences.map((sentence) => {
          const evidence = sentenceEvidence(response, sentence);
          return <div className="source-answer-sentence" key={sentence.id}>
            <p>{sentence.text}</p>
            {evidence.length > 0 && <button type="button" className="source-answer-evidence-link" aria-pressed={selectedSentence === sentence.id}
              onClick={() => { setSelectedSentence((current) => current === sentence.id ? null : sentence.id); setEvidenceLimit(50); onLocate?.(evidence[0]); }}>
              <Focus size={12} />{fi ? 'Näytä lähde' : 'Show evidence'} <span>{evidence.length}</span>
            </button>}
          </div>;
        })}
        {!sentences.length && <p>{part.message?.text ?? part.result?.explanation?.text ?? answerStatusLabel(part.status, language)}</p>}
      </div>;
    })}
    <p className="source-answer-scope"><strong>{fi ? 'Rajaus' : 'Scope'}</strong> {response.source.scope_label}</p>
    {response.interpretation.ambiguities?.map((item, index) => <p className="source-answer-part-status" key={index}>{item}</p>)}
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
    {response.parts.some((part) => partMemberGroups(response, part.key).length > 0) && <section aria-label={fi ? 'Sisällytetyt, poissuljetut ja ratkaisemattomat jäsenet' : 'Included, excluded and unresolved source members'}>
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
    </section>}
    <details className="source-answer-structured"><summary>{fi ? 'Arvot ja laskennan lähtötiedot' : 'Values and calculation inputs'}</summary>
      {response.parts.map((part) => {
        const bundle = response.evidence_contexts?.find((context) => context.id === part.evidence_context_id)?.bundle;
        const units = new Map((bundle?.units ?? []).map((unit) => [unit.id, unit.symbol]));
        return <div key={part.key}>
          {response.parts.length > 1 && <h3>{response.interpretation.requested_parts.find((item) => item.key === part.key)?.question}</h3>}
          {part.result?.claims?.map((claim) => <div className="source-answer-claim" key={claim.id}><strong>{claim.name}</strong><div><AnswerValue value={claim.value} units={units} /></div>{claim.count_policy && <small>{claim.count_policy.grain.replaceAll('_', ' ')} · {claim.count_policy.hierarchy.replaceAll('_', ' ')}</small>}</div>)}
          {part.result?.calculations?.map((calculation) => <div className="source-answer-calculation" key={calculation.id}>
            <strong>{calculation.operation.replaceAll('_', ' ')}</strong><div><AnswerValue value={calculation.output} units={units} /></div>
            {calculation.rule_key && <code>{calculation.rule_key}</code>}
            {!!calculation.fact_ids?.length && <details><summary>{fi ? 'Lähdetiedot' : 'Source inputs'} ({calculation.fact_ids.length})</summary>{calculation.fact_ids.map((id) => { const fact = bundle?.facts?.find((item) => item.id === id); return <div key={id}><code>{fact?.original_property_path?.join('.') || fact?.property_key || id}</code>{fact?.value && <AnswerValue value={fact.value} units={units} />}</div>; })}</details>}
          </div>)}
        </div>;
      })}
      <p>{fi ? 'Vienti sisältää kaikki jäsenet, lähtötiedot ja laskentavaiheet.' : 'Export includes all members, source facts and calculation steps.'}</p>
    </details>
    <details className="source-answer-structured"><summary>{fi ? 'Analyysin vaiheet ja kustannukset' : 'Analysis steps & usage'}</summary>
      <p>{Math.round(response.metrics.elapsed_ms)} ms · {response.metrics.external_attempts ?? 0} {fi ? 'mallikutsua' : 'model attempts'}{response.metrics.cache_hit ? (fi ? ' · Välimuistista' : ' · Cached result') : ''}</p>
      {(response.metrics.calls ?? []).length === 0 && <p>{fi ? 'Lähdetiedot ja laskenta käsiteltiin paikallisesti.' : 'Source facts and calculations were processed locally.'}</p>}
      <ol>{response.metrics.calls?.map((call) => <li key={call.id}><strong>{call.purpose.replaceAll('_', ' ')}</strong> · {call.returned_model ?? call.requested_model} · {call.outcome}<br /><small>{call.prompt_tokens == null ? 'Input usage unavailable' : `${call.prompt_tokens} input tokens`} · {call.completion_tokens == null ? 'Output usage unavailable' : `${call.completion_tokens} output and thinking tokens`}</small></li>)}</ol>
      <p>{fi ? 'Kustannusarvio' : 'Estimated cost'}: {response.metrics.cost_amount == null ? (fi ? 'Ei saatavilla' : 'Unavailable') : `${response.metrics.cost_amount} ${response.metrics.cost_currency ?? ''}`}</p>
    </details>
    <button className="text-button source-answer-export" onClick={() => exportAnswer(response, 'answer-evidence.json', sourcePreview)}><Download size={13} />{fi ? 'Vie vastaus ja lähteet' : 'Export answer & evidence'}</button>
    <details className="source-answer-revision"><summary>{fi ? 'Lähteen tunniste' : 'Source identity'}</summary><dl><dt>Original SHA-256</dt><dd><code>{response.source.source_sha256}</code></dd>{response.source.display_sha256 && <><dt>Display SHA-256</dt><dd><code>{response.source.display_sha256}</code></dd></>}</dl></details>
  </section>;
}

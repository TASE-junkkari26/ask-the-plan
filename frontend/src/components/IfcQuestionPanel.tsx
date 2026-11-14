import { useEffect, useRef, useState } from 'react';
import { ArrowUp, Check, CircleAlert, Download, Focus, Search, X } from 'lucide-react';
import type { IfcSource } from '../types';
import type { IfcModelResponse } from '../contracts/IfcModelResponse';
import type { EvidenceAnchor, IfcQuestionResponse } from '../contracts/IfcQuestionResponse';
import type { Output } from '../contracts/QueryResult';
import type { EvidenceElement, HighlightReport } from '../ifc/evidence';
import { sourceReferenceLabel } from '../ifc/answer';
import { askIfcQuestion, IfcApiError, ifcQualityLabel, uploadIfcModel } from '../lib/ifcApi';
import './IfcQuestionPanel.css';

function Value({ value, ...context }: {
  value: Output;
  units: ReadonlyMap<string, string>;
  elements: ReadonlyMap<string, EvidenceElement>;
  onSelect: (id: number) => void;
}) {
  const { units, elements, onSelect } = context;
  switch (value.kind) {
    case 'count': return <>{value.value.toLocaleString('en')}</>;
    case 'quantity': return <>{value.magnitude} {value.unit_id ? (units.get(value.unit_id) ?? value.unit_id) : '(unit unresolved)'} <small>({value.basis.replaceAll('_', ' ')})</small></>;
    case 'text': return <>{value.value.text}</>;
    case 'boolean': return <>{value.value ? 'Yes' : 'No'}</>;
    case 'unavailable': return <>{value.reason.replaceAll('_', ' ')}: {value.explanation}</>;
    case 'references': return <span className="ifc-value-references">{value.entity_ids.length ? value.entity_ids.slice(0, 100).map((id, index) => {
      const element = elements.get(id);
      const label = sourceReferenceLabel(id, elements);
      const stepId = element?.step_id;
      return <span key={`${id}:${index}`}>{index > 0 && '; '}{element && stepId != null
        ? <button type="button" className="ifc-source-reference" title={`${element.ifc_class} · ${element.guid ?? id}`} aria-label={`Inspect ${label}`} onClick={() => onSelect(stepId)}>{label}</button>
        : <span title={id}>{label}</span>}</span>;
    }) : <span>No source objects returned.</span>}{value.entity_ids.length > 100 && <small> First 100 objects shown. Export evidence for all objects.</small>}</span>;
    case 'list': return <><ul>{value.items.slice(0, 100).map((item, i) => <li key={i}><Value value={item} {...context} /></li>)}</ul>{value.items.length > 100 && <small>First 100 items shown. Export evidence for all items.</small>}</>;
    case 'record': return <dl>{Object.entries(value.fields).map(([key, item]) => <div key={key}><dt>{key}</dt><dd><Value value={item} {...context} /></dd></div>)}</dl>;
    case 'table': return <div className="ifc-value-table"><table><thead><tr>{value.columns.map((column) => <th key={column.key}>{column.label.text}</th>)}</tr></thead><tbody>{value.rows.slice(0, 100).map((row, i) => <tr key={i}>{value.columns.map((column) => <td key={column.key}><Value value={row[column.key]} {...context} /></td>)}</tr>)}</tbody></table>{value.rows.length > 100 && <p>First 100 rows shown. Export evidence for all rows.</p>}</div>;
  }
}

function Elements({ title, elements, onSelect }: { title: string; elements: EvidenceElement[]; onSelect: (id: number) => void }) {
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(50);
  const filtered = elements.filter((element) => `${element.name} ${element.ifc_class} #${element.step_id} ${element.guid ?? ''}`.toLowerCase().includes(query.toLowerCase()));
  return <details className="ifc-evidence-group" open={title === 'Included elements'}>
    <summary>{title}<span>{elements.length.toLocaleString('en')}</span></summary>
    {!!elements.length && <>
      {elements.length > 10 && <label className="ifc-evidence-search"><Search size={13} /><input aria-label={`Search ${title.toLowerCase()}`} placeholder="Name, STEP ID or GUID" value={query} onChange={(event) => { setQuery(event.target.value); setLimit(50); }} /></label>}
      <ol className="ifc-evidence-elements">{filtered.slice(0, limit).map((element) => <li key={element.entity_id}>
        <button disabled={element.step_id == null} onClick={() => element.step_id != null && onSelect(element.step_id)} title={element.guid ?? element.entity_id}>
          <span><strong>{element.name || element.ifc_class}</strong><small>{element.ifc_class} · {element.step_id == null ? 'No STEP locator' : `#${element.step_id}`}</small></span><span>Inspect</span>
        </button>
      </li>)}</ol>
      {filtered.length > limit && <button className="text-button" onClick={() => setLimit((value) => value + 50)}>Show next {Math.min(50, filtered.length - limit)} ({limit} / {filtered.length})</button>}
      {!filtered.length && <p className="ifc-note">No matching evidence rows.</p>}
    </>}
  </details>;
}

function SourceAnchors({ anchorIds, anchors, onSelect }: {
  anchorIds: string[];
  anchors: ReadonlyMap<string, EvidenceAnchor>;
  onSelect: (id: number) => void;
}) {
  const uniqueIds = [...new Set(anchorIds)];
  if (!uniqueIds.length) return null;
  return <details className="ifc-source-anchors">
    <summary>Source references <span>{uniqueIds.length.toLocaleString('en')}</span></summary>
    <ol>{uniqueIds.slice(0, 50).map((id) => {
      const anchor = anchors.get(id);
      if (!anchor) return <li key={id}><code>{id}</code> · Source locator unavailable</li>;
      const { selector } = anchor;
      const stepId = selector.kind === 'step_id' && /^\d+$/.test(selector.value) ? Number(selector.value) : null;
      const canInspect = stepId != null && Number.isSafeInteger(stepId) && stepId > 0;
      const locator = selector.kind === 'step_id' ? `#${selector.value}` : selector.value;
      return <li key={id}>
        <span>{selector.kind.replaceAll('_', ' ')}: </span>
        {canInspect
          ? <button type="button" className="ifc-source-reference" aria-label={`Inspect source record ${locator}`} onClick={() => onSelect(stepId)}>{locator}</button>
          : <code>{locator}</code>}
        {!!selector.property_path?.length && <span> · {selector.property_path.join('.')}</span>}
      </li>;
    })}</ol>
    {uniqueIds.length > 50 && <p>First 50 of {uniqueIds.length.toLocaleString('en')} references shown. Export evidence for every source locator.</p>}
  </details>;
}

export default function IfcQuestionPanel({
  source, sourceHash, ready, viewBusy, section, viewRevision, viewLabel,
  getViewStepIds, highlight, clearHighlights, focus, isolate, onSelect,
}: {
  source: IfcSource;
  sourceHash: string;
  ready: boolean;
  viewBusy: boolean;
  section: boolean;
  viewRevision: number;
  viewLabel: string;
  getViewStepIds: () => Promise<number[]>;
  highlight: (elements: EvidenceElement[]) => Promise<HighlightReport | undefined>;
  clearHighlights: () => void;
  focus: (ids: number[]) => void;
  isolate: (ids: number[]) => void;
  onSelect: (id: number) => void;
}) {
  const [question, setQuestion] = useState('');
  const [scope, setScope] = useState<'view' | 'model'>('view');
  const [response, setResponse] = useState<IfcQuestionResponse | null>(null);
  const [report, setReport] = useState<HighlightReport | null>(null);
  const [phase, setPhase] = useState('');
  const [error, setError] = useState('');
  const [stale, setStale] = useState(false);
  const modelRef = useRef<IfcModelResponse | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const previousView = useRef(viewRevision);
  const clearRef = useRef(clearHighlights);
  clearRef.current = clearHighlights;

  useEffect(() => () => { controllerRef.current?.abort(); clearRef.current(); }, []);
  useEffect(() => {
    if (previousView.current === viewRevision) return;
    previousView.current = viewRevision;
    if (controllerRef.current) clearRef.current();
    controllerRef.current?.abort();
    controllerRef.current = null;
    setPhase('');
    setStale(response?.scope === 'view');
  }, [viewRevision]);
  useEffect(() => {
    if (!ready) {
      controllerRef.current?.abort();
      setPhase('');
      setResponse(null);
      setReport(null);
      modelRef.current = null;
    }
  }, [ready, sourceHash]);

  const ask = async () => {
    const text = question.trim();
    if (!text || !source.file || !ready || viewBusy || (scope === 'view' && section)) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const { signal } = controller;
    setError('');
    setResponse(null);
    setReport(null);
    setStale(false);
    clearHighlights();
    try {
      const visibleIds = scope === 'view' ? await getViewStepIds() : null;
      signal.throwIfAborted();
      let model = modelRef.current;
      if (!model || model.source_sha256 !== sourceHash) {
        setPhase('Reading source with the IFC engine…');
        model = await uploadIfcModel(source.file, sourceHash, signal);
        signal.throwIfAborted();
        modelRef.current = model;
      }
      setPhase('Planning the source query; the IFC engine computes the answer…');
      const request = { model_id: model.model_id, source_sha256: sourceHash, question: text, scope, visible_step_ids: visibleIds, view_label: viewLabel };
      let result: IfcQuestionResponse;
      try {
        result = await askIfcQuestion(request, signal);
      } catch (failure) {
        if (!(failure instanceof IfcApiError) || ![404, 410].includes(failure.status)) throw failure;
        modelRef.current = await uploadIfcModel(source.file, sourceHash, signal);
        result = await askIfcQuestion({ ...request, model_id: modelRef.current.model_id }, signal);
      }
      signal.throwIfAborted();
      const highlights = await highlight(result.included_elements ?? []);
      signal.throwIfAborted();
      setReport(highlights ?? null);
      setResponse(result);
    } catch (failure) {
      if (!signal.aborted) setError(failure instanceof Error ? failure.message : 'The IFC question could not be answered.');
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setPhase('');
      }
    }
  };

  const units = new Map((response?.units ?? []).map((unit) => [unit.id, unit.symbol]));
  const facts = new Map((response?.facts ?? []).map((fact) => [fact.id, fact]));
  const anchors = new Map((response?.anchors ?? []).map((anchor) => [anchor.id, anchor]));
  const valueContext = { units, elements: new Map([
    ...(response?.excluded_elements ?? []), ...(response?.unresolved_elements ?? []), ...(response?.included_elements ?? []),
  ].map((element) => [element.entity_id, element])), onSelect };
  const canAsk = ready && !viewBusy && !!source.file && !!sourceHash && !(section && scope === 'view');
  return <div className="ifc-questions">
    <div className="ifc-question-intro"><strong>Ask the model. Check every element.</strong><p>The configured planner interprets your question. The IFC engine calculates from source objects, stored properties and recorded relationships.</p></div>
    <form className="ifc-question-form" onSubmit={(event) => { event.preventDefault(); void ask(); }}>
      <label className="ifc-question-scope">Answer scope<select aria-label="IFC answer scope" value={scope} disabled={!!phase} onChange={(event) => setScope(event.target.value as 'view' | 'model')}><option value="view">Current view</option><option value="model">Entire IFC model</option></select></label>
      <p className="ifc-scope-description">{scope === 'view' ? `${viewLabel}. Includes drawable objects allowed by storey and visibility controls. Orbit, zoom and occlusion do not filter objects.` : 'All extracted objects in this IFC revision, including objects hidden in the preview.'}</p>
      {section && scope === 'view' && <p className="ifc-question-warning" role="status"><CircleAlert size={14} />Reset the horizontal section before asking about this view, or choose Entire IFC model. The cut plane does not establish object membership.</p>}
      <textarea aria-label="Question about IFC model" placeholder="How many windows are there?" value={question} maxLength={4000} onChange={(event) => setQuestion(event.target.value)} disabled={!ready || !!phase} rows={3} />
      <div className="ifc-question-submit"><small>Asking uploads this IFC to the local backend. Your question and bounded source metadata go to the configured analysis provider.</small>{phase ? <button className="secondary-button" type="button" onClick={() => { controllerRef.current?.abort(); controllerRef.current = null; clearHighlights(); setPhase(''); }}><X size={14} />Cancel</button> : <button className="primary-button" type="submit" disabled={!canAsk || !question.trim()}><ArrowUp size={15} />Ask</button>}</div>
    </form>
    {!response && !phase && !question && <button className="ifc-example-question" disabled={!ready} onClick={() => setQuestion('How many windows are there?')}>Try “How many windows are there?”</button>}
    {phase && <p className="ifc-question-progress" role="status"><span className="spinner" />{phase}</p>}
    {error && <p className="ifc-question-warning" role="alert"><CircleAlert size={15} />{error}</p>}
    {response && <div className="ifc-question-answer" aria-live="polite">
      <p className="ifc-asked-question">{response.question}</p>
      <div className={`ifc-answer-status ${response.result.status === 'answered' ? '' : 'ifc-answer-status-incomplete'}`}>{response.result.status === 'answered' ? <Check size={14} /> : <CircleAlert size={14} />}{response.result.status.replaceAll('_', ' ')}</div>
      {!!response.result.claims?.length && response.result.claims.map((claim) => <div className={`ifc-computed-answer ifc-computed-${claim.value.kind}`} key={claim.id}><div>{ifcQualityLabel(claim.quality) && <span>{ifcQualityLabel(claim.quality)} </span>}<Value value={claim.value} {...valueContext} /></div>{claim.count_policy && <small>{claim.count_policy.grain.replaceAll('_', ' ')} · {claim.count_policy.hierarchy.replaceAll('_', ' ')} · Each source object counted once</small>}</div>)}
      {response.result.explanation?.text && <p className="ifc-answer-narrative">{response.result.explanation.text}</p>}
      <p className="ifc-answer-scope"><strong>Scope</strong> {response.scope_label}</p>
      {stale && <p className="ifc-question-warning"><CircleAlert size={14} />View changed. This answer describes its captured scope; ask again for the current view.</p>}
      {response.interpretation && <p className="ifc-answer-interpretation">{response.interpretation}</p>}
      {!!response.result.issues?.length && <ul className="ifc-answer-issues">{response.result.issues.map((issue, index) => <li key={index}>{issue.message.text}{!!issue.options?.length && <ul>{issue.options.map((option, optionIndex) => <li key={optionIndex}>{option.text}</li>)}</ul>}</li>)}</ul>}
      {!!response.warnings?.length && <details className="ifc-evidence-group"><summary>Source & execution notes <span>{response.warnings.length}</span></summary><ul>{response.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></details>}
      {report && <div className="ifc-highlight-summary"><span className="ifc-answer-swatch" /><span><strong>{report.stepIds.length.toLocaleString('en')} elements marked</strong><small>{response.included_elements?.length ?? 0} source elements included in the engine evidence.{!!report.hiddenStepIds?.length && ` ${report.hiddenStepIds.length} marked elements were hidden by the captured view; Isolate matches reveals them.`}{section && ' The active section can clip marked geometry.'}{!!report.unavailable.length && ` ${report.unavailable.length} have no drawable geometry in this preview.`}{!!report.identityMismatches.length && ` ${report.identityMismatches.length} identity mismatches were withheld.`} Markings are separate from the computed answer.</small></span></div>}
      {!!report?.stepIds.length && <div className="ifc-actions"><button className="secondary-button" onClick={() => focus(report.stepIds)}><Focus size={13} />Fit matches</button><button className="secondary-button" onClick={() => isolate(report.stepIds)}>Isolate matches</button></div>}
      <Elements key={`${response.request_id}:included`} title="Included elements" elements={response.included_elements ?? []} onSelect={onSelect} />
      <Elements key={`${response.request_id}:excluded`} title="Excluded elements" elements={response.excluded_elements ?? []} onSelect={onSelect} />
      {!!response.unresolved_elements?.length && <Elements key={`${response.request_id}:unresolved`} title="Unresolved elements" elements={response.unresolved_elements} onSelect={onSelect} />}
      {response.planning && <details className="ifc-evidence-group"><summary>Analysis details</summary><p>{response.planning.provider} · {response.planning.returned_model}{response.planning.thinking_level ? ` · ${response.planning.thinking_level} reasoning` : ''}</p><p>{response.planning.model_requests} planner requests · {response.planning.inspection_count} source inspections</p><p>Input tokens: {response.planning.prompt_tokens == null ? 'unreported' : response.planning.prompt_tokens.toLocaleString('en')} · Output and reasoning tokens: {response.planning.completion_tokens == null ? 'unreported' : response.planning.completion_tokens.toLocaleString('en')}</p></details>}
      {!!response.result.calculations?.length && <details className="ifc-evidence-group"><summary>Calculation & source inputs</summary>{response.result.calculations.map((calculation) => <div className="ifc-calculation" key={calculation.id}><strong>{calculation.operation.replaceAll('_', ' ')}</strong><div><Value value={calculation.output} {...valueContext} /></div>{calculation.rule_key && <code>{calculation.rule_key}</code>}{!!calculation.input_node_ids?.length && <p>Input steps: {calculation.input_node_ids.join(', ')}</p>}{(calculation.fact_ids ?? []).slice(0, 100).map((factId) => { const fact = facts.get(factId); return fact && <div className="ifc-calculation-input" key={factId}><code>{fact.original_property_path?.join('.') || fact.property_key}</code><div>{fact.value ? <Value value={fact.value} {...valueContext} /> : fact.status.replaceAll('_', ' ')}</div>{fact.provenance.anchor_ids?.map((anchorId) => { const anchor = anchors.get(anchorId); return anchor && <small key={anchorId}>{anchor.selector.kind}: {anchor.selector.kind === 'step_id' ? '#' : ''}{anchor.selector.value}{anchor.selector.property_path?.length ? ` · ${anchor.selector.property_path.join('.')}` : ''}</small>; })}</div>; })}{(calculation.fact_ids?.length ?? 0) > 100 && <p>First 100 inputs shown; export contains every input.</p>}<SourceAnchors anchorIds={calculation.anchor_ids ?? []} anchors={anchors} onSelect={onSelect} /></div>)}</details>}
      <button className="text-button ifc-evidence-export" onClick={() => { const url = URL.createObjectURL(new Blob([JSON.stringify(response, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = url; link.download = 'ifc-answer-evidence.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}><Download size={13} />Export answer & evidence</button>
      <small className="ifc-answer-revision">Source SHA-256 <code>{response.source_sha256}</code></small>
    </div>}
  </div>;
}

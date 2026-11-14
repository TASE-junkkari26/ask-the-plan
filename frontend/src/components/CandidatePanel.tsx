import { CircleAlert, Focus, ScanLine } from 'lucide-react';
import type { ImageCandidate, ImageCandidateResponse } from '../contracts/ImageCandidateResponse';
import type { Language } from '../types';
import { DecisionTrace } from './DecisionTrace';
import { ResponseMetrics } from './ResponseMetrics';
import './CandidatePanel.css';

function CandidateCloseUp({
  candidate,
  response,
  imageUrl,
  onFocus,
  language,
}: {
  candidate: ImageCandidate;
  response: ImageCandidateResponse;
  imageUrl: string;
  onFocus: () => void;
  language: Language;
}) {
  const { width, height } = response.image;
  const [xmin, ymin] = candidate.geometry.minimum;
  const [xmax, ymax] = candidate.geometry.maximum;
  const padding = Math.max(width, height) * 0.025;
  const cropWidth = Math.min(width, Math.max(xmax - xmin + padding * 2, width * 0.15));
  const cropHeight = Math.min(height, Math.max(ymax - ymin + padding * 2, cropWidth * 0.55));
  const cropX = Math.max(0, Math.min(width - cropWidth, (xmin + xmax - cropWidth) / 2));
  const cropY = Math.max(0, Math.min(height - cropHeight, (ymin + ymax - cropHeight) / 2));
  const color = candidate.uncertain ? '#a7610a' : '#137567';
  return (
    <section className="candidate-closeup" aria-label={language === 'fi' ? 'Valitun ehdokkaan lähde' : 'Selected candidate source'}>
      <h3><ScanLine size={13} />{language === 'fi' ? 'LÄHDE LÄHELTÄ' : 'SOURCE CLOSE-UP'}</h3>
      <button onClick={onFocus} aria-label={language === 'fi' ? 'Kohdista ehdokkaaseen' : 'Focus selected candidate on drawing'}>
        <svg viewBox={`${cropX} ${cropY} ${cropWidth} ${cropHeight}`} aria-hidden="true">
          <rect width={width} height={height} fill="white" />
          <image href={imageUrl} width={width} height={height} />
          <rect x={xmin} y={ymin} width={xmax - xmin} height={ymax - ymin} fill={color} fillOpacity={0.12} stroke={color} strokeWidth={2} strokeDasharray={candidate.uncertain ? '5 3' : undefined} vectorEffect="non-scaling-stroke" />
        </svg>
        <span><Focus size={13} />{language === 'fi' ? 'Kohdista piirustukseen' : 'Focus on drawing'}</span>
      </button>
    </section>
  );
}

function CheckedSource({
  box, imageUrl, width, height, language,
}: {
  box: number[];
  imageUrl: string;
  width: number;
  height: number;
  language: Language;
}) {
  const [x0, y0, x1, y1] = box;
  const padding = Math.max(20, Math.max(x1 - x0, y1 - y0) * 0.35);
  const left = Math.max(0, x0 - padding);
  const top = Math.max(0, y0 - padding);
  const right = Math.min(width, x1 + padding);
  const bottom = Math.min(height, y1 + padding);
  return (
    <details className="candidate-check-source">
      <summary>{language === 'fi' ? 'Näytä lähde läheltä' : 'View source close-up'}</summary>
      <svg viewBox={`${left} ${top} ${right - left} ${bottom - top}`}
        role="img" aria-label={language === 'fi' ? 'Tarkistetun ehdokkaan sijainti lähdekuvassa' : 'Checked candidate location in the source image'}>
        <rect width={width} height={height} fill="white" />
        <image href={imageUrl} width={width} height={height} />
        <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0}
          fill="#a7610a" fillOpacity={0.1} stroke="#a7610a" strokeWidth={2}
          vectorEffect="non-scaling-stroke" />
      </svg>
    </details>
  );
}

export function CandidatePanel({
  response,
  question,
  selected,
  onSelect,
  onFocus,
  imageUrl,
  language,
  responseTimeMs,
  completedAt,
}: {
  response: ImageCandidateResponse;
  question: string;
  selected: string | null;
  onSelect: (id: string) => void;
  onFocus: (id: string) => void;
  imageUrl: string;
  language: Language;
  responseTimeMs: number;
  completedAt: string;
}) {
  const fi = language === 'fi';
  const candidates = response.candidates ?? [];
  const candidate = candidates.find((item) => item.id === selected);
  const checks = response.detail?.membership_checks ?? [];
  const checkLabels = {
    supported: fi ? 'Säilytetty tarkistuksessa' : 'Kept after check',
    rejected: fi ? 'Poistettu tarkistuksessa' : 'Excluded after check',
    ambiguous: fi ? 'Yhä epävarma' : 'Still uncertain',
    failed: fi ? 'Tarkistus ei onnistunut' : 'Check unavailable',
  };
  const status = {
    ok: fi ? 'Valmis' : 'Complete',
    partial: fi ? 'Osittainen tunnistus' : 'Partial detection',
    unreadable: fi ? 'Kuvaa ei voitu tulkita' : 'Image could not be read',
    unsupported: fi ? 'Kysymystä ei tueta' : 'Question unsupported',
  }[response.status];
  const heading = candidates.length
    ? fi
      ? candidates.length === 1 ? '1 tarkistettava ehdokas' : `${candidates.length} tarkistettavaa ehdokasta`
      : `${candidates.length} ${candidates.length === 1 ? 'candidate' : 'candidates'} to review`
    : fi ? 'Ei tunnistettuja ehdokkaita' : 'No candidates detected';
  return (
    <section className="candidate-panel" aria-label={fi ? 'Tunnistetut ehdokkaat' : 'Detected candidates'}>
      <p className="candidate-question">{question}</p>
      <div className={`candidate-summary candidate-summary-${response.status}`}>
        <h2>{response.status === 'unreadable' || response.status === 'unsupported' ? status : heading}</h2>
        {response.status === 'partial' && <p>{status}</p>}
      </div>
      <ResponseMetrics
        model={response.provenance.returned_model}
        requestedModel={response.provenance.requested_model}
        responseTimeMs={responseTimeMs}
        modelTimeMs={response.metrics.elapsed_ms}
        preparationTimeMs={response.metrics.preparation_ms}
        inputTokens={response.metrics.prompt_tokens}
        outputTokens={response.metrics.completion_tokens}
        completedAt={completedAt}
        language={language}
        decisionTrace={response.decision_trace}
      />
      <DecisionTrace trace={response.decision_trace} language={language} />
      {response.detail && (
        <details className="candidate-detail-trace">
          <summary>
            {fi ? 'Tarkka tunnistus' : 'Detailed scan'}
            <span>
              {response.detail.provider_calls} {fi ? 'mallikutsua' : 'model calls'}
              {' · '}{response.detail.regions.length} {fi ? 'tutkittua aluetta' : 'regions inspected'}
            </span>
          </summary>
          <p>
            {response.detail.selection === 'automatic'
              ? fi ? 'Piirustusalueet valittiin automaattisesti tästä kuvasta.' : 'Drawing regions selected automatically from this image.'
              : fi ? 'Tunnistus rajattiin valittuihin alueisiin tässä kuvassa.' : 'Detection was limited to the selected regions of this image.'}
          </p>
          <svg
            viewBox={`0 0 ${response.image.width} ${response.image.height}`}
            role="img"
            aria-label={fi ? 'Tunnistukseen valitut piirustusalueet' : 'Drawing regions selected for detection'}
          >
            <rect width={response.image.width} height={response.image.height} fill="white" />
            <image href={imageUrl} width={response.image.width} height={response.image.height} />
            {response.detail.selected_regions.map(([x0, y0, x1, y1], index) => (
              <rect key={index} x={x0} y={y0} width={x1 - x0} height={y1 - y0}
                fill="#137567" fillOpacity={0.08} stroke="#137567" strokeWidth={2}
                vectorEffect="non-scaling-stroke" />
            ))}
          </svg>
          {response.detail.selection_limitations && response.detail.selection_limitations.length > 0 && (
            <ul>{response.detail.selection_limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
          )}
        </details>
      )}
      {checks.length > 0 && (
        <details className="candidate-checks">
          <summary>{fi ? 'Ehdokkaiden tarkistukset' : 'Candidate checks'} <span>{checks.length}</span></summary>
          <ol>
            {checks.map((check) => (
              <li key={`${check.region_id}:${check.observation_ids.join(',')}`} className={`candidate-check candidate-check-${check.verdict}`}>
                <div className="candidate-check-heading"><strong>{checkLabels[check.verdict]}</strong><span>{check.category}</span></div>
                <p>{check.reason}</p>
                {check.verdict === 'rejected' && (
                  <CheckedSource box={check.source_box} imageUrl={imageUrl}
                    width={response.image.width} height={response.image.height} language={language} />
                )}
              </li>
            ))}
          </ol>
        </details>
      )}
      <p className="candidate-review-note"><CircleAlert size={15} /><span>{fi ? 'Tarkistamattomat ehdokkaat voivat olla puutteellisia tai epävarmoja.' : 'Unverified candidates may be incomplete or uncertain.'}</span></p>
      {(response.limitations ?? []).length > 0 && (
        <section className="candidate-limitations" aria-label={fi ? 'Rajoitukset' : 'Limitations'}>
          <h3>{fi ? 'Rajoitukset' : 'Limitations'}</h3>
          <ul>{response.limitations?.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
        </section>
      )}
      {candidates.length === 0 && response.status === 'ok' && <p className="candidate-empty-note">{fi ? 'Ehdokkaiden puuttuminen ei tarkoita nollaa kohdetta.' : 'No candidates does not mean zero objects.'}</p>}
      {candidate && <CandidateCloseUp candidate={candidate} response={response} imageUrl={imageUrl} language={language} onFocus={() => onFocus(candidate.id)} />}
      <div className="candidate-list">
        {candidates.map((item, index) => {
          const labels = [...new Set((response.detail?.observations.find((observation) => observation.candidate_id === item.id)?.source_labels ?? [])
            .filter((label): label is string => typeof label === 'string'))];
          return (
          <div className={`candidate-row${selected === item.id ? ' candidate-row-selected' : ''}${item.uncertain ? ' candidate-row-uncertain' : ''}`} key={item.id}>
            <button className="candidate-row-select" onClick={() => onSelect(item.id)} aria-pressed={selected === item.id}>
              <span className="candidate-ordinal">{index + 1}</span>
              <span className="candidate-row-copy">
                <strong>{item.category}{item.source_label && <code>{item.source_label}</code>}</strong>
                <span>{item.visual_cue}</span>
                {labels.length > 1 && (
                  <span className="candidate-label-variants">
                    <span>{fi ? 'Lähdemerkinnät:' : 'Source labels:'}</span>
                    {labels.map((label, labelIndex) => <code key={labelIndex}>{label}</code>)}
                  </span>
                )}
                {item.uncertain && <span className="candidate-uncertainty"><CircleAlert size={12} />{fi ? 'Epävarma' : 'Uncertain'}: {item.uncertainty_reason}</span>}
              </span>
            </button>
            <button className="candidate-row-focus" onClick={() => onFocus(item.id)} aria-label={`${fi ? 'Kohdista' : 'Focus'} ${index + 1}: ${item.source_label || item.category}`} title={fi ? 'Kohdista piirustukseen' : 'Focus on drawing'}><Focus size={16} /></button>
          </div>
          );
        })}
      </div>
      <p className="candidate-provenance">{response.image.width} × {response.image.height} px</p>
    </section>
  );
}

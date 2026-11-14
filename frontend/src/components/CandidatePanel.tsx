import { CircleAlert, Focus, ScanLine } from 'lucide-react';
import type { ImageCandidate, ImageCandidateResponse } from '../contracts/ImageCandidateResponse';
import type { Language } from '../types';
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

export function CandidatePanel({
  response,
  question,
  selected,
  onSelect,
  onFocus,
  imageUrl,
  language,
}: {
  response: ImageCandidateResponse;
  question: string;
  selected: string | null;
  onSelect: (id: string) => void;
  onFocus: (id: string) => void;
  imageUrl: string;
  language: Language;
}) {
  const fi = language === 'fi';
  const candidates = response.candidates ?? [];
  const candidate = candidates.find((item) => item.id === selected);
  const status = {
    ok: fi ? 'Tunnistus valmis' : 'Detection completed',
    partial: fi ? 'Osittainen tunnistus' : 'Partial detection',
    unreadable: fi ? 'Kuvaa ei voitu tulkita' : 'Image could not be read',
    unsupported: fi ? 'Kysymystä ei tueta tässä kuvassa' : 'Question unsupported for this image',
  }[response.status];
  const heading = candidates.length
    ? fi ? `${candidates.length} tarkistettavaa ehdokasta` : `${candidates.length} candidates to review`
    : fi ? 'Ei tunnistettuja ehdokkaita' : 'No candidates detected';
  return (
    <section className="candidate-panel" aria-label={fi ? 'Tunnistetut ehdokkaat' : 'Detected candidates'}>
      <p className="candidate-question">{question}</p>
      <div className={`candidate-summary candidate-summary-${response.status}`}>
        <span className="candidate-eyebrow"><ScanLine size={14} />{fi ? 'NEMOTRON · KUVAN EHDOKKAAT' : 'NEMOTRON · IMAGE CANDIDATES'}</span>
        <h2>{response.status === 'unreadable' || response.status === 'unsupported' ? status : heading}</h2>
        <p>{status} · {fi ? 'Vain valittu kuva' : 'Selected image only'}</p>
      </div>
      <p className="candidate-review-note"><CircleAlert size={15} /><span>{fi ? 'Tarkista ehdokkaat kuvasta. Kohteita voi puuttua, eikä luettelon kattavuutta ole vahvistettu.' : 'Review the highlights against the image. Candidates may be missing or ambiguous; inventory completeness is unverified.'}</span></p>
      {(response.limitations ?? []).length > 0 && (
        <section className="candidate-limitations" aria-label={fi ? 'Rajoitukset' : 'Limitations'}>
          <h3>{fi ? 'Rajoitukset' : 'Limitations'}</h3>
          <ul>{response.limitations?.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
        </section>
      )}
      {candidates.length === 0 && response.status === 'ok' && <p className="candidate-empty-note">{fi ? 'Tyhjä luettelo ei vahvista, että kuvassa on nolla kohdetta.' : 'An empty candidate list does not establish that the image contains zero objects.'}</p>}
      {candidate && <CandidateCloseUp candidate={candidate} response={response} imageUrl={imageUrl} language={language} onFocus={() => onFocus(candidate.id)} />}
      <div className="candidate-list">
        {candidates.map((item, index) => (
          <div className={`candidate-row${selected === item.id ? ' candidate-row-selected' : ''}${item.uncertain ? ' candidate-row-uncertain' : ''}`} key={item.id}>
            <button className="candidate-row-select" onClick={() => onSelect(item.id)} aria-pressed={selected === item.id}>
              <span className="candidate-ordinal">{index + 1}</span>
              <span className="candidate-row-copy">
                <strong>{item.category}{item.source_label && <code>{item.source_label}</code>}</strong>
                <span>{item.visual_cue}</span>
                {item.uncertain && <span className="candidate-uncertainty"><CircleAlert size={12} />{fi ? 'Epävarma' : 'Uncertain'}: {item.uncertainty_reason}</span>}
              </span>
            </button>
            <button className="candidate-row-focus" onClick={() => onFocus(item.id)} aria-label={`${fi ? 'Kohdista' : 'Focus'} ${index + 1}: ${item.source_label || item.category}`} title={fi ? 'Kohdista piirustukseen' : 'Focus on drawing'}><Focus size={16} /></button>
          </div>
        ))}
      </div>
      <p className="candidate-provenance">{response.provenance.returned_model} · {response.image.width} × {response.image.height} px</p>
    </section>
  );
}

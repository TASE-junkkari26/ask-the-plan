import type { ImageCandidateResponse } from '../contracts/ImageCandidateResponse';
import { candidateBounds } from '../lib/candidateGeometry';
import './CandidatePanel.css';

export { candidateBounds } from '../lib/candidateGeometry';

export function CandidateLayer({
  response,
  selected,
  labels,
  onSelect,
}: {
  response: ImageCandidateResponse;
  selected: string | null;
  labels: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <g className="candidate-layer" aria-label="Candidate highlights">
      {(response.candidates ?? []).map((candidate, index) => {
        const [x, y, width, height] = candidateBounds(candidate, response.image);
        const active = candidate.id === selected;
        const color = candidate.uncertain ? '#a7610a' : active ? '#064f43' : '#147d70';
        const label = candidate.source_label || candidate.category;
        const tagY = Math.max(25, y - 24);
        return (
          <g
            key={candidate.id}
            className={`candidate-mark${active ? ' candidate-mark-selected' : ''}${candidate.uncertain ? ' candidate-mark-uncertain' : ''}`}
            data-candidate-id={candidate.id}
            data-source-bounds={`${candidate.geometry.minimum[0]},${candidate.geometry.minimum[1]},${candidate.geometry.maximum[0]},${candidate.geometry.maximum[1]}`}
            role="button"
            tabIndex={0}
            aria-label={`${index + 1}. ${label}${candidate.uncertain ? ' · uncertain' : ''}: ${candidate.visual_cue}`}
            aria-pressed={active}
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(candidate.id);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                event.stopPropagation();
                onSelect(candidate.id);
              }
            }}
          >
            <title>{`${label}: ${candidate.visual_cue}${candidate.uncertainty_reason ? ` · ${candidate.uncertainty_reason}` : ''}`}</title>
            <rect
              className="candidate-box"
              x={x}
              y={y}
              width={width}
              height={height}
              fill={color}
              fillOpacity={active ? 0.19 : 0.065}
              stroke={color}
              strokeWidth={active ? 2.6 : 1.6}
              strokeDasharray={candidate.uncertain ? '5 3' : undefined}
              vectorEffect="non-scaling-stroke"
            />
            <rect x={x} y={tagY} width={30} height={24} rx={4} fill={color} />
            <text x={x + 15} y={tagY + 17} textAnchor="middle" fill="white" fontSize={14} fontWeight={650}>
              {index + 1}{candidate.uncertain ? '?' : ''}
            </text>
            {labels && (
              <>
                <rect x={x + 33} y={tagY} width={Math.min(220, Math.max(62, label.length * 7 + 16))} height={24} rx={4} fill="white" stroke={color} strokeWidth={0.7} />
                <text x={x + 41} y={tagY + 17} fill={color} fontSize={13} fontWeight={550}>
                  {label.length > 28 ? `${label.slice(0, 27)}…` : label}
                </text>
              </>
            )}
          </g>
        );
      })}
    </g>
  );
}

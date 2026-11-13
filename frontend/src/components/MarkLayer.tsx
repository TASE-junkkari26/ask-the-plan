import { areaPath } from '../lib/viewport';
import type { Mark } from '../types';

export function MarkLayer({
  marks,
  selected,
  labels,
  onSelect,
}: {
  marks: Mark[];
  selected: string | null;
  labels: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <g className="mark-layer">
      {marks.map((mark) => {
        const [x, y, w, h] = mark.bounds;
        const active = mark.id === selected;
        const color = active ? '#1743bb' : '#3972f0';
        return (
          <g
            key={mark.id}
            className={`evidence-mark ${active ? 'selected-mark' : ''}`}
            role="button"
            tabIndex={0}
            aria-label={`${mark.label}: ${mark.detail}`}
            aria-pressed={active}
            onClick={(e) => {
              e.stopPropagation();
              onSelect(mark.id);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect(mark.id);
              }
            }}
          >
            <title>{`${mark.label} · ${mark.detail}`}</title>
            {mark.kind === 'area' && mark.polygon ? (
              <>
                <path
                  d={areaPath(mark.polygon, mark.holes)}
                  fill={color}
                  fillOpacity={active ? 0.18 : 0.1}
                  stroke={color}
                  strokeWidth="1.8"
                  fillRule="evenodd"
                  vectorEffect="non-scaling-stroke"
                />
                {mark.holes?.map((hole, i) => (
                  <path
                    key={i}
                    d={areaPath(hole)}
                    fill="#f7b955"
                    fillOpacity="0.3"
                    stroke="#e99d28"
                    strokeWidth="1"
                    vectorEffect="non-scaling-stroke"
                  />
                ))}
                <rect
                  x={x + w / 2 - 66}
                  y={y + h / 2 + 31}
                  width="132"
                  height="35"
                  rx="5"
                  fill={color}
                />
                <text
                  x={x + w / 2}
                  y={y + h / 2 + 54}
                  textAnchor="middle"
                  fill="white"
                  fontSize="18"
                  fontWeight="600"
                >
                  13.23 m²
                </text>
              </>
            ) : mark.kind === 'dimension' ? (
              <>
                <rect
                  x={x - 4}
                  y={y - 22}
                  width={w + 8}
                  height="58"
                  rx="5"
                  fill={color}
                  fillOpacity="0.05"
                />
                <path
                  d={`M${x} ${y}H${x + w} M${x} ${y - 13}V${y + 13} M${x + w} ${y - 13}V${y + 13}`}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  d={`M${x + 10} ${y - 5}L${x} ${y}l10 5m${w - 20}-10 10 5-10 5`}
                  stroke={color}
                  strokeWidth="2"
                  fill="none"
                />
                <text
                  x={x + w / 2}
                  y={y - 16}
                  textAnchor="middle"
                  fill={color}
                  fontSize="20"
                  fontWeight="600"
                >
                  {mark.label}
                </text>
              </>
            ) : (
              <>
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  rx="3"
                  fill={color}
                  fillOpacity={active ? 0.17 : 0.055}
                  stroke={color}
                  strokeWidth={active ? '2.3' : '1.3'}
                  vectorEffect="non-scaling-stroke"
                />
                <rect
                  x={x - 11}
                  y={y - 13}
                  width="30"
                  height="28"
                  rx="6"
                  fill={color}
                  stroke="white"
                  strokeWidth="2"
                />
                <text
                  x={x + 4}
                  y={y + 6}
                  textAnchor="middle"
                  fill="white"
                  fontSize="17"
                  fontWeight="600"
                >
                  {mark.ordinal}
                </text>
                {labels && (
                  <>
                    <rect
                      x={x + 24}
                      y={y - 13}
                      width="58"
                      height="27"
                      rx="4"
                      fill="white"
                      stroke="#dce6ff"
                    />
                    <text
                      x={x + 53}
                      y={y + 5}
                      textAnchor="middle"
                      fill={color}
                      fontSize="14"
                      fontWeight="600"
                    >
                      {mark.label}
                    </text>
                  </>
                )}
              </>
            )}
          </g>
        );
      })}
    </g>
  );
}

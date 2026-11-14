import { useId } from 'react';
import { DOORS, SCHEDULE, WINDOWS } from '../demo/data';
import type { Drawing, ImportedDrawing } from '../types';

const Door = ({ x, y, angle }: { x: number; y: number; angle: number }) => (
  <g transform={`translate(${x} ${y}) rotate(${angle})`}>
    <path d="M0 0H62" stroke="white" strokeWidth="16" />
    <path
      d="M0 0V-62M0-62A62 62 0 0 1 62 0"
      fill="none"
      stroke="#555e69"
      strokeWidth="1.4"
    />
    <path d="M-2 0V-62H2V0" fill="#8f969e" stroke="#343c45" strokeWidth="0.6" />
  </g>
);

function Plan({ first, hatchId }: { first: boolean; hatchId: string }) {
  return (
    <>
      <defs>
        <pattern
          id={hatchId}
          width="7"
          height="7"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <line x1="0" y1="0" x2="0" y2="7" stroke="#b5bcc3" strokeWidth="1" />
        </pattern>
      </defs>
      <g fill="none" stroke="#b8bfc7" strokeWidth="0.7">
        <path d="M150 130V82M950 130V82M150 95H950M145 90L155 100M945 90L955 100" />
        <path d="M965 145H1010M965 575H1010M997 145V575M992 140L1002 150M992 570L1002 580" />
        <path d="M150 595V640M490 595V640M650 595V640M950 595V640M150 627H950" />
        {[150, 490, 650, 950].map((x) => (
          <path key={x} d={`M${x - 4} 623l8 8`} />
        ))}
        <path d="M70 350H150M70 575H150M80 340V585" />
      </g>
      <g fill="#7d8792" fontSize="12" textAnchor="middle">
        <text x="550" y="85" letterSpacing="1">
          12 000
        </text>
        <text x="1020" y="360" transform="rotate(90 1020 360)">
          6 450
        </text>
        <text x="320" y="618">
          5 100
        </text>
        <text x="570" y="618">
          2 400
        </text>
        <text x="800" y="618">
          4 500
        </text>
      </g>
      <rect
        x="80"
        y="350"
        width="70"
        height="225"
        fill="#fafafa"
        stroke="#bec4cb"
      />
      {[365, 390, 415, 440, 465, 490, 515, 540, 565].map((y) => (
        <path key={y} d={`M85 ${y}H145`} stroke="#e3e6e9" />
      ))}
      <g stroke="#323a43" fill="none" strokeWidth="11" strokeLinejoin="miter">
        <path d="M150 145H950V575H150Z" />
        <path d="M490 145V575M650 145V575M150 350H490M650 350H950M490 285H650M150 475H270V575" />
      </g>
      <g stroke="#d1d6db" strokeWidth="5" fill="none">
        <path d="M150 145H950V575H150Z" />
        <path d="M490 145V575M650 145V575M150 350H490M650 350H950M490 285H650M150 475H270V575" />
      </g>
      {/* Built-in kitchen and sanitary fixtures are source linework, not detections. */}
      <g fill="#f7f8f9" stroke="#a4adb6" strokeWidth="1.2">
        <path d="M665 155H940V200H895V180H665Z" />
        <rect x="765" y="156" width="63" height="39" rx="2" fill="white" />
        <rect x="776" y="162" width="18" height="26" rx="6" />
        <rect x="798" y="162" width="18" height="26" rx="6" />
        <rect x="875" y="157" width="52" height="34" fill="white" />
        {[888, 913].flatMap((x) =>
          [165, 182].map((y) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="5" fill="none" />
          )),
        )}
        <rect x="505" y="156" width="54" height="72" rx="4" fill="white" />
        <path d="M510 162l42 60m0-60-42 60" />
        <rect x="595" y="157" width="39" height="19" rx="2" fill="white" />
        <ellipse cx="615" cy="190" rx="14" ry="19" fill="white" />
        <rect x="590" y="235" width="45" height="30" rx="2" fill="white" />
        <ellipse cx="612" cy="250" rx="14" ry="9" />
        <rect x="163" y="489" width="41" height="42" fill="white" />
        <circle cx="183" cy="510" r="14" fill="none" />
        <rect x="209" y="489" width="41" height="42" fill="white" />
        <circle cx="229" cy="510" r="14" fill="none" />
        <rect
          x="420"
          y="165"
          width="20"
          height="20"
          fill={`url(#${hatchId})`}
          stroke="#646e79"
        />
      </g>
      <g stroke="#cbd0d6" fill="none" strokeWidth="1.3">
        <rect x="173" y="174" width="113" height="140" rx="2" />
        <path d="M174 205H285" />
        <rect x="181" y="181" width="44" height="18" rx="4" />
        <rect x="233" y="181" width="44" height="18" rx="4" />
        <rect x="800" y="386" width="115" height="145" rx="2" />
        <path d="M801 419H914" />
        <rect x="808" y="394" width="44" height="18" rx="4" />
        <rect x="860" y="394" width="44" height="18" rx="4" />
        <rect x="316" y="427" width="110" height="43" rx="5" />
        <rect x="326" y="469" width="88" height="49" rx="4" />
        <path d="M329 440H413M353 440v20m37-20v20" />
        <rect x="722" y="250" width="125" height="51" rx="8" />
        {[742, 783, 823].map((x) => (
          <g key={x}>
            <rect x={x - 9} y="234" width="18" height="12" rx="3" />
            <rect x={x - 9} y="305" width="18" height="12" rx="3" />
          </g>
        ))}
      </g>
      {DOORS.slice(0, first ? 6 : 8).map((door, i) => (
        <Door key={i} {...door} />
      ))}
      {WINDOWS.slice(0, first ? 5 : 7).map((win, i) => (
        <g
          key={i}
          transform={`translate(${win.x} ${win.y}) ${win.vertical ? 'rotate(90)' : ''}`}
        >
          <rect
            x="0"
            y="-6"
            width={win.length}
            height="12"
            fill="white"
            stroke="#5e6873"
            strokeWidth="1"
          />
          <path
            d={`M0 0H${win.length}M3-5V5M${win.length - 3}-5V5`}
            stroke="#8a959f"
            strokeWidth="1"
          />
        </g>
      ))}
      <g fill="#5c6672" textAnchor="middle" fontSize="15" fontWeight="500">
        <text x="369" y="242">
          BEDROOM 01
        </text>
        <text x="369" y="265" fontSize="12" fill="#919aa5">
          B01 · 13.23 m²
        </text>
        <text x="369" y="400">
          LIVING ROOM
        </text>
        <text x="369" y="419" fontSize="12" fill="#919aa5">
          L01 · 15.01 m²
        </text>
        <text x="797" y="225">
          KITCHEN / DINING
        </text>
        <text x="727" y="465">
          BEDROOM 02
        </text>
        <text x="727" y="487" fontSize="12" fill="#919aa5">
          B02 · 11.28 m²
        </text>
        <text x="570" y="246" fontSize="11">
          BATHROOM
        </text>
        <text
          x="570"
          y="459"
          transform="rotate(-90 570 459)"
          fontSize="12"
          letterSpacing="1"
        >
          CORRIDOR
        </text>
        <text x="208" y="554" fontSize="10">
          UTILITY
        </text>
        <text
          x="114"
          y="505"
          transform="rotate(-90 114 505)"
          fontSize="10"
          fill="#929ba5"
        >
          TERRACE
        </text>
      </g>
      <g stroke="#b2bbc4" fill="none" strokeWidth="1">
        <path d="M500 355H640M505 350l-5 5 5 5m130-10 5 5-5 5" />
      </g>
      <text x="570" y="344" textAnchor="middle" fill="#98a1ab" fontSize="11">
        2 400
      </text>
      <g
        transform="translate(120 95)"
        stroke="#65717d"
        strokeWidth="1"
        fill="none"
      >
        <path d="M0 12V-13L-5-3M0-13 5-3" />
        <text
          y="-22"
          textAnchor="middle"
          fill="#65717d"
          stroke="none"
          fontSize="11"
        >
          N
        </text>
      </g>
    </>
  );
}

function Schedule() {
  const xs = [140, 250, 470, 570, 690, 810, 960];
  return (
    <>
      <text x="140" y="140" fontSize="24" fontWeight="600" fill="#303b49">
        DOOR SCHEDULE
      </text>
      <text x="140" y="163" fontSize="12" fill="#8b95a1">
        Dimensions in millimetres. All entries refer to the current drawing set.
      </text>
      <rect x="140" y="180" width="820" height="35" fill="#f0f2f5" />
      <g stroke="#9ba5af" strokeWidth="1" fill="none">
        <rect x="140" y="180" width="820" height="371" />
        {xs.slice(1, -1).map((x) => (
          <path key={x} d={`M${x} 180V551`} />
        ))}
        {Array.from({ length: 8 }, (_, i) => (
          <path key={i} d={`M140 ${215 + i * 42}H960`} />
        ))}
      </g>
      {['MARK', 'LOCATION', 'TYPE', 'WIDTH', 'HEIGHT', 'MATERIAL'].map(
        (label, i) => (
          <text
            key={label}
            x={xs[i] + 17}
            y="202"
            fill="#5c6977"
            fontSize="11"
            fontWeight="600"
            letterSpacing="0.6"
          >
            {label}
          </text>
        ),
      )}
      {SCHEDULE.map((row, i) =>
        row.map((cell, j) => (
          <text
            key={`${i}-${j}`}
            x={xs[j] + 17}
            y={241 + i * 42}
            fill={j === 0 ? '#333e4d' : '#6f7986'}
            fontSize="14"
            fontWeight={j === 0 ? 600 : 400}
          >
            {cell}
          </text>
        )),
      )}
      <text x="140" y="600" fontSize="12" fontWeight="600" fill="#5a6471">
        GENERAL NOTES
      </text>
      <text x="140" y="624" fontSize="11" fill="#8b95a1">
        01 Verify dimensions against the corresponding floor plan.
      </text>
      <text x="140" y="646" fontSize="11" fill="#8b95a1">
        02 This is an illustrative schedule for the interactive prototype.
      </text>
    </>
  );
}

function Elevation() {
  return (
    <>
      <g fill="none" stroke="#5b6570" strokeWidth="2">
        <path
          d="M160 550H950M180 540V310L550 180 930 310V540Z"
          fill="#fafbfc"
        />
        <path d="M180 310H930M180 335H930M180 540H930" />
        <path d="M160 310 550 167 950 310" />
      </g>
      <g stroke="#e1e5e9" strokeWidth="1">
        {Array.from({ length: 14 }, (_, i) => (
          <path key={i} d={`M183 ${350 + i * 13}H927`} />
        ))}
      </g>
      {[220, 365, 660, 805].map((x) => (
        <g key={x} stroke="#77828e" fill="white" strokeWidth="2">
          <rect x={x} y="385" width="90" height="94" />
          <path d={`M${x + 45} 385V479M${x} 432H${x + 90}`} strokeWidth="1" />
        </g>
      ))}
      <g stroke="#727e8b" fill="white" strokeWidth="2">
        <rect x="498" y="370" width="78" height="170" />
        <rect x="506" y="381" width="61" height="105" fill="#f0f3f5" />
        <circle cx="562" cy="503" r="2" />
      </g>
      <g stroke="#b7bfc8" strokeWidth="1" fill="none">
        <path d="M160 600H950M180 570V615M930 570V615M175 595l10 10m740-10 10 10" />
      </g>
      <text x="550" y="590" textAnchor="middle" fill="#8793a0" fontSize="13">
        12 000
      </text>
      <text
        x="550"
        y="660"
        textAnchor="middle"
        fill="#64707d"
        fontSize="17"
        letterSpacing="2"
      >
        SOUTH ELEVATION
      </text>
    </>
  );
}

export function DrawingArtwork({
  drawing,
  imported,
  miniature = false,
}: {
  drawing: Drawing;
  imported?: ImportedDrawing | null;
  miniature?: boolean;
}) {
  const artworkId = useId().replaceAll(':', '');
  if (imported)
    return (
      <image
        href={imported.url}
        x="25"
        y="25"
        width="1050"
        height="730"
        preserveAspectRatio="xMidYMid meet"
      />
    );
  return (
    <g className="source-artwork" aria-hidden="true">
      <rect x="0" y="0" width="1100" height="780" fill="white" />
      {!miniature && (
        <>
          <text x="65" y="52" fill="#8b95a2" fontSize="10" letterSpacing="2.4">
            WEST HARBOUR RESIDENCE
          </text>
          <text x="1035" y="52" textAnchor="end" fill="#a4adb7" fontSize="10">
            ARCHITECTURAL DRAWINGS
          </text>
        </>
      )}
      {drawing.kind === 'plan' ? (
        <Plan
          first={drawing.id === 'first'}
          hatchId={`${drawing.id}-${artworkId}-wall-hatch`}
        />
      ) : drawing.kind === 'schedule' ? (
        <Schedule />
      ) : (
        <Elevation />
      )}
      {!miniature && (
        <>
          <g stroke="#dce1e6" fill="none" strokeWidth="1">
            <path d="M65 694H1035V745H65Z M740 694V745M920 694V745" />
          </g>
          <text x="82" y="715" fill="#a2aab4" fontSize="9" letterSpacing="1">
            WEST HARBOUR RESIDENCE · DEMO PROJECT
          </text>
          <text x="82" y="735" fill="#4e5a68" fontSize="13">
            {drawing.title.toUpperCase()} · {drawing.level.toUpperCase()}
          </text>
          <text x="755" y="715" fill="#a2aab4" fontSize="9">
            REVISION {drawing.revision} · 13 NOV 2026
          </text>
          <text x="755" y="735" fill="#6d7986" fontSize="10">
            ILLUSTRATIVE SOURCE
          </text>
          <text x="940" y="727" fill="#3a4858" fontSize="23" fontWeight="600">
            {drawing.code}
          </text>
        </>
      )}
    </g>
  );
}

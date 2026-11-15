import { memo, useMemo, useState } from 'react';
import type { CalculationNode, RouteEvaluation } from '../contracts/IfcQuestionResponse';
import type { EvidenceElement } from '../ifc/evidence';
import { sourceReferenceLabel } from '../ifc/answer';
import { projectRoute } from '../ifc/routeProjection';

function IfcRouteEvidence({ calculations, elements }: {
  calculations: CalculationNode[];
  elements: ReadonlyMap<string, EvidenceElement>;
}) {
  const [expanded, setExpanded] = useState(false);
  const routes = useMemo(() => {
    const seen = new Set<string>(), result: RouteEvaluation[] = [];
    for (const calculation of calculations) {
      for (const route of calculation.route_evidence ?? []) {
        const key = JSON.stringify([route.subject_id, route.target_id, route.path_points_m]);
        if (seen.has(key) || !route.path_points_m?.length) continue;
        seen.add(key);
        result.push(route);
        if (result.length === 10) return result;
      }
    }
    return result;
  }, [calculations]);
  if (!routes.length) return null;
  return <details className="ifc-evidence-group" onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary>Modeled walking paths <span>{routes.length}</span></summary>
    {expanded && routes.map((route, index) => {
      const display = projectRoute(route);
      if (!display) return <p key={index}>The source path cannot be displayed in metres.</p>;
      const origin = sourceReferenceLabel(route.subject_id, elements);
      const target = route.target_id ? sourceReferenceLabel(route.target_id, elements) : 'Unresolved target';
      return <div className="ifc-route-evidence" key={index}>
        <p><strong>{origin} → {target}</strong></p>
        <p>Estimated path length: {display.length.toLocaleString('en', { maximumFractionDigits: 3 })} m</p>
        <svg viewBox="0 0 300 180" role="img" aria-label={`Source plan projection of modeled walking path from ${origin} to ${target}`}>
          <title>IFC world XY projection; +X right, +Y up. Heights are preserved in the coordinate list.</title>
          <polyline points={display.polyline} fill="none" stroke="#2680c2" strokeWidth="3" strokeLinejoin="round" />
          <circle cx={display.start[0]} cy={display.start[1]} r="5" fill="#74aa48" stroke="white" strokeWidth="1.5" />
          <rect x={display.end[0] - 4} y={display.end[1] - 4} width="8" height="8" fill="#14518a" stroke="white" strokeWidth="1.5" />
        </svg>
        <small>Plan projection of the source path: green start, blue destination. Heights appear below. See the answer’s qualifications for exit status and width.</small>
        <details className="ifc-source-anchors"><summary>Path coordinates in source-world metres</summary>
          <div className="ifc-value-table"><table><thead><tr><th>Point</th><th>X</th><th>Y</th><th>Z</th></tr></thead>
            <tbody>{display.points.slice(0, 25).map((point, i) => <tr key={i}><td>{i + 1}</td>{point.map((value, axis) => <td key={axis}>{value.toLocaleString('en', { maximumFractionDigits: 6 })}</td>)}</tr>)}</tbody>
          </table></div>
          <small>Coordinates rounded for display. Export contains every full-precision point{display.points.length > 25 ? ` (${display.points.length} points; first 25 shown)` : ''}.</small>
        </details>
      </div>;
    })}
    {expanded && routes.length === 10 && <p>Up to ten distinct paths shown. Export the answer for every path.</p>}
  </details>;
}

export default memo(IfcRouteEvidence);

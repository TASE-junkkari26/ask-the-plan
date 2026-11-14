import type { ImageDecisionTrace } from '../contracts/ImageCandidateResponse';
import type { Language } from '../types';
import { decisionReason, decisionValue, routeLabel } from '../lib/decisionTrace';
import { estimateCallCosts, formatEstimatedUsd, formatResponseTime, modelName } from '../lib/responseMetrics';
import './DecisionTrace.css';

export function DecisionTrace({ trace, language }: { trace?: ImageDecisionTrace | null; language: Language }) {
  const fi = language === 'fi';
  const labels = {
    capability: fi ? 'Soveltuvuus' : 'Capability fit', route: fi ? 'Analyysireitti' : 'Analysis route',
    preparation: fi ? 'Kuvan valmistelu' : 'Image preparation', analysis: fi ? 'Suoritus' : 'Execution',
    evidence: fi ? 'Lähteen rajoitukset' : 'Evidence limits',
  };
  const states = { evaluated: fi ? 'Arvioitu' : 'Evaluated', selected: fi ? 'Valittu' : 'Selected',
    skipped: fi ? 'Ohitettu' : 'Skipped', reused: fi ? 'Käytetty uudelleen' : 'Reused',
    completed: fi ? 'Valmis' : 'Completed', failed: fi ? 'Epäonnistui' : 'Failed', unavailable: fi ? 'Ei saatavilla' : 'Unavailable' };
  const percent = (n: number) => new Intl.NumberFormat(language, { style: 'percent', maximumFractionDigits: 1 }).format(n);
  const cost = trace ? estimateCallCosts(trace.calls ?? []) : null;
  const threshold = trace?.nodes?.find((node) => node.criterion === 'capability')?.threshold;
  const overallFitOnly = trace?.policy_version === 'capability-routing-v2';
  const legacyGates = trace?.policy_version === 'capability-routing-v1';
  return <details className="decision-trace">
    <summary>{fi ? 'Näin kuva analysoitiin' : 'How this was analyzed'}<span>{trace ? routeLabel(trace.selected_profile, language) : fi ? 'Ei tallennettua polkua' : 'No recorded path'}</span></summary>
    {trace ? <>
      {trace.mode === 'shadow' && <p>{fi ? 'Seurantatila. Suositeltu reitti:' : 'Observation mode. Recommended route:'} {trace.recommended_profile ? routeLabel(trace.recommended_profile, language) : fi ? 'Ei saatavilla' : 'Unavailable'}. {fi ? 'Alla näkyy toteutunut suoritus.' : 'The path below shows what actually ran.'}</p>}
      {Object.entries(trace.assessments ?? {}).length > 0 && <dl className="decision-assessments">
        {Object.entries(trace.assessments ?? {}).map(([key, value]) => <div key={key}><dt>{({ document_kind: fi ? 'Kuvatyyppi' : 'Image type', task_kind: fi ? 'Tehtävä' : 'Task', count_grain: fi ? 'Laskennan kohde' : 'Counting unit', target_kind: fi ? 'Kohteet' : 'Targets', scope: fi ? 'Laajuus' : 'Scope', normal_fit: fi ? 'Soveltuvuus' : 'Standard fit' } as Record<string, string>)[key] ?? key}</dt><dd>{decisionValue(value, language)}{trace.assessment_probabilities?.[key] != null && <> · {percent(trace.assessment_probabilities[key])}</>}</dd></div>)}
      </dl>}
      {threshold != null && <p>{overallFitOnly
        ? fi ? 'Vain kokonaisarviota soveltuvuudesta verrataan rajaan:' : 'Only overall capability fit is compared with the threshold:'
        : legacyGates
          ? fi ? 'Jokaisen vaaditun arvion on ylitettävä raja:' : 'Every required assessment must meet the threshold:'
          : fi ? 'Tallennettu reititysraja:' : 'Recorded routing threshold:'} {percent(threshold)}.</p>}
      {overallFitOnly && <p className="decision-score-note">{fi
        ? 'Kuvatyypin, tehtävän, kohteiden, laskentayksikön ja laajuuden arviot ovat taustatietoa. Ne eivät yksin valitse vaativaa mallia.'
        : 'Image type, task, target, counting unit and scope scores are descriptive. They do not independently select advanced analysis.'}</p>}
      <ol>{trace.nodes?.map((node) => <li key={node.id}>
        <strong>{labels[node.criterion]}</strong> <span className="decision-state">{states[node.state]}</span>
        <p>{decisionReason(node, language)}</p>
        {node.value && <span className="decision-value">{decisionValue(node.value, language)}</span>}
        {node.probability != null && <p>{fi ? 'Tavalliseen analyysiin soveltuvuuden todennäköisyys' : 'Probability of standard capability fit'}: {percent(node.probability)}{node.threshold != null && <> · {fi ? 'Vaadittu raja' : 'Required threshold'}: {percent(node.threshold)}</>}</p>}
      </li>)}</ol>
      <p className="decision-score-note">{fi ? 'Reititysarviot eivät ole vastauksen oikeellisuusprosentteja.' : 'Routing scores are not answer accuracy percentages.'}</p>
      {(trace.calls?.length ?? 0) > 0 && <section aria-label={fi ? 'Toteutuneet mallikutsut' : 'Recorded model calls'}>
        <h4>{fi ? 'Mallikutsut' : 'Model calls'}</h4>
        <ul>{trace.calls?.map((call) => <li key={call.id}>{call.purpose === 'routing' ? fi ? 'Reititys' : 'Routing' : fi ? 'Analyysi' : 'Analysis'}: {modelName(call.returned_model ?? call.requested_model)} · {call.outcome === 'completed' ? fi ? 'Valmis' : 'Completed' : call.outcome === 'cancelled' ? fi ? 'Peruttu' : 'Cancelled' : fi ? 'Epäonnistui' : 'Failed'} · {formatResponseTime(call.elapsed_ms, language)}</li>)}</ul>
        {cost && <p>{fi ? 'Kaikkien kutsujen hinta-arvio' : 'Estimated cost of all calls'}: {formatEstimatedUsd(cost.knownUsd, language)}{cost.unknownCalls > 0 && <> + {fi ? 'tuntematon osuus' : 'unknown component'}</>}</p>}
      </section>}
      <p className="decision-version">{fi ? 'Päätössäännöt' : 'Policy'}: {trace.policy_version} · {fi ? 'Ominaisuudet' : 'Capabilities'}: {trace.capability_version}</p>
    </> : <p>{fi ? 'Tämän pyynnön päätöspolkua ei tallennettu.' : 'No decision path was recorded for this request.'}</p>}
  </details>;
}

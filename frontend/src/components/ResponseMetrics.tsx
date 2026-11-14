import type { ImageDecisionTrace } from '../contracts/ImageCandidateResponse';
import { CircleDollarSign, Clock3, Cpu } from 'lucide-react';
import type { Language } from '../types';
import {
  estimateCallCosts, estimateTokenCost, formatEstimatedUsd, formatResponseTime, modelName,
  modelRates, PRICING_SOURCE_URL, PRICING_VERIFIED_ON,
} from '../lib/responseMetrics';
import './ResponseMetrics.css';

export function ResponseMetrics({
  model, requestedModel, responseTimeMs, modelTimeMs, preparationTimeMs,
  inputTokens, outputTokens, completedAt, language, decisionTrace,
}: {
  model: string;
  requestedModel: string;
  responseTimeMs: number;
  modelTimeMs: number;
  preparationTimeMs?: number | null;
  inputTokens?: number | null;
  outputTokens?: number | null;
  completedAt: string;
  language: Language;
  decisionTrace?: ImageDecisionTrace | null;
}) {
  const fi = language === 'fi';
  const rates = modelRates(model, completedAt);
  // Tool totals can mix a cheap layout model and a stronger detector. A single
  // returned-model rate must never reprice those aggregate tokens.
  const cost = decisionTrace ? null : estimateTokenCost(model, inputTokens, outputTokens, completedAt);
  const allCalls = decisionTrace ? estimateCallCosts(decisionTrace.calls ?? []) : null;
  const routingCalls = decisionTrace?.calls?.filter((call) => call.purpose === 'routing') ?? [];
  const tokens = (value: number | null | undefined) => value == null
    ? fi ? 'Ei raportoitu' : 'Not reported'
    : value.toLocaleString(language);
  const rate = (value: number) => new Intl.NumberFormat(language, {
    style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(value);

  return <section className="response-metrics" aria-label={fi ? 'Vastauksen tiedot' : 'Response details'}>
    <dl className="response-metrics-summary">
      <div className="response-metrics-model">
        <dt><Cpu size={12} />{fi ? 'Malli' : 'Model used'}</dt>
        <dd title={model}>{modelName(model)}</dd>
      </div>
      <div>
        <dt><Clock3 size={12} />{fi ? 'Vastausaika' : 'Response time'}</dt>
        <dd>{formatResponseTime(responseTimeMs, language)}</dd>
      </div>
      <div>
        <dt><CircleDollarSign size={12} />{fi ? 'Hinta-arvio' : 'Estimated cost'}</dt>
        <dd>{allCalls ? <>{formatEstimatedUsd(allCalls.knownUsd, language)}{allCalls.unknownCalls > 0 && <> + {fi ? 'tuntematon osuus' : 'unknown component'}</>}</> : cost ? formatEstimatedUsd(cost.totalUsd, language) : fi ? 'Ei saatavilla' : 'Unavailable'}</dd>
      </div>
    </dl>
    <details className="response-metrics-details">
      <summary>{fi ? 'Tokenit ja hinnoittelu' : 'Tokens & pricing'}</summary>
      <dl>
        <div><dt>{fi ? 'Analyysin syötetokenit' : 'Analysis input tokens'}</dt><dd>{tokens(inputTokens)}</dd></div>
        <div><dt>{fi ? 'Analyysin tulostokenit' : 'Analysis output tokens'}</dt><dd>{tokens(outputTokens)}</dd></div>
        {routingCalls.map((call) => <div key={call.id}><dt>{fi ? 'Reitityksen syötetokenit' : 'Routing input tokens'}</dt><dd>{tokens(call.prompt_tokens)}</dd></div>)}
        {rates && <>
          <div><dt>{fi ? 'Syöte / 1 milj. tokenia' : 'Input / 1M tokens'}</dt><dd>{rate(rates.inputUsdPerMillion)}</dd></div>
          <div><dt>{fi ? 'Tuloste / 1 milj. tokenia' : 'Output / 1M tokens'}</dt><dd>{rate(rates.outputUsdPerMillion)}</dd></div>
        </>}
        {cost && <>
          <div><dt>{fi ? 'Syötteen hinta-arvio' : 'Estimated input cost'}</dt><dd>{formatEstimatedUsd(cost.inputUsd, language)}</dd></div>
          <div><dt>{fi ? 'Tulosteen hinta-arvio' : 'Estimated output cost'}</dt><dd>{formatEstimatedUsd(cost.outputUsd, language)}</dd></div>
        </>}
        <div><dt>{fi ? 'Mallikutsun aika' : 'Model request time'}</dt><dd>{formatResponseTime(modelTimeMs, language)}</dd></div>
        {preparationTimeMs != null && Number.isFinite(preparationTimeMs) && preparationTimeMs >= 0 && <div><dt>{fi ? 'Kuvan esikäsittely' : 'Image preprocessing'}</dt><dd>{formatResponseTime(preparationTimeMs, language)}</dd></div>}
      </dl>
      {decisionTrace && <p>{fi ? 'Hinta-arvio käyttää kunkin tallennetun reititys- ja työkalukutsun toteutunutta mallia. Raportoimattomat veloitukset jäävät tuntemattomiksi.' : 'The total uses the actual model of each recorded routing and tool call. Unreported charges remain unknown.'}</p>}
      <p>{fi
        ? 'Vastausaika sisältää kuvan valmistelun, lähetyksen ja analyysin.'
        : 'Response time includes image preparation, upload and analysis.'}</p>
      {rates ? <>
        <p>{fi
          ? 'Arvio maksullisen standardihinnaston mukaan ennen välimuistialennuksia, hyvityksiä ja veroja. Geminin tulostokenit sisältävät ajattelutokenit.'
          : 'Paid standard rate estimate before cache discounts, credits and taxes. Gemini output includes thinking tokens.'}</p>
        {!cost && !allCalls && <p>{fi
          ? 'Hinta-arvio edellyttää sekä syöte- että tulostokenien määrää.'
          : 'Both input and output token usage are needed to estimate cost.'}</p>}
        <p><a href={`${PRICING_SOURCE_URL}#${model}`} target="_blank" rel="noreferrer">{fi ? 'Googlen hinnasto' : 'Google pricing'}</a> · {fi ? 'Tarkistettu' : 'Checked'} <time dateTime={PRICING_VERIFIED_ON}>{PRICING_VERIFIED_ON}</time></p>
      </> : <p>{fi ? 'Tälle vastaukselle ei ole vahvistettua hintaa.' : 'Pricing is unavailable for this response.'}</p>}
      <p className="response-metrics-id">{fi ? 'Mallin tunniste' : 'Model ID'}: <code>{model}</code></p>
      {requestedModel !== model && <p className="response-metrics-id">{fi ? 'Pyydetty malli' : 'Requested model'}: <code>{requestedModel}</code></p>}
    </details>
  </section>;
}

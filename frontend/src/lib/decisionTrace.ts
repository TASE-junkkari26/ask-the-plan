import type { AnalysisDecisionNode, CandidateImage, ImageDecisionTrace } from '../contracts/ImageCandidateResponse';
import type { Language } from '../types';

const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const text = (v: unknown, max = 200): v is string => typeof v === 'string' && v.trim().length > 0 && v.length <= max;
const hash = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v);
const positive = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) > 0;
const number = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0;
const tokens = (v: unknown) => v == null || (Number.isSafeInteger(v) && (v as number) >= 0);
const choice = (v: unknown, allowed: readonly string[]) => typeof v === 'string' && allowed.includes(v);
const probability = (v: unknown) => v == null || (number(v) && v <= 1);

export function validateDecisionTrace(
  value: unknown, requestId: string, image: Pick<CandidateImage, 'sha256' | 'width' | 'height'>,
  questionSha256: string, inferenceSha256?: string,
): ImageDecisionTrace | null {
  if (value == null) return null;
  const invalid = () => new Error('The analysis service returned an invalid decision trace. Please ask again.');
  if (!object(value) || value.request_id !== requestId || value.question_sha256 !== questionSha256
      || !hash(value.question_sha256) || !object(value.image)
      || value.image.sha256 !== image.sha256 || value.image.width !== image.width || value.image.height !== image.height
      || value.image.coordinate_system !== 'display_pixels_top_left' || !hash(value.image.inference_sha256)
      || (inferenceSha256 !== undefined && value.image.inference_sha256 !== inferenceSha256)
      || !choice(value.mode, ['off', 'shadow', 'auto'])
      || !choice(value.selected_profile, ['normal', 'strong', 'manual', 'pending'])
      || (value.recommended_profile != null && !choice(value.recommended_profile, ['normal', 'strong']))
      || !text(value.policy_version) || !text(value.capability_version)) throw invalid();
  const assessments = value.assessments ?? {};
  if (!object(assessments) || Object.keys(assessments).length > 8
      || !Object.entries(assessments).every(([key, v]) => text(key) && text(v, 120))) throw invalid();
  const scores = value.assessment_probabilities ?? {};
  if (!object(scores) || Object.keys(scores).length > 8
      || !Object.entries(scores).every(([key, v]) => text(key) && Object.hasOwn(assessments, key) && v != null && probability(v))) throw invalid();
  const calls = value.calls ?? [];
  if (!Array.isArray(calls) || calls.length > 13) throw invalid();
  const callIds = new Set<string>();
  for (const call of calls) {
    if (!object(call) || !text(call.id) || callIds.has(call.id)
        || !choice(call.purpose, ['routing', 'analysis', 'region_proposal', 'candidate_verification', 'reinspection'])
        || !choice(call.outcome, ['completed', 'failed', 'cancelled'])
        || !text(call.requested_model) || (call.returned_model != null && !text(call.returned_model))
        || !text(call.completed_at, 40) || !Number.isFinite(Date.parse(call.completed_at))
        || !number(call.elapsed_ms) || !hash(call.input_sha256)
        || !positive(call.input_width) || !positive(call.input_height)
        || !tokens(call.prompt_tokens) || !tokens(call.completion_tokens)) throw invalid();
    if (call.source_box == null) {
      if (call.input_sha256 !== value.image.inference_sha256) throw invalid();
    } else {
      const box = call.source_box;
      if (!Array.isArray(box) || box.length !== 4 || !box.every(number)) throw invalid();
      const [x0, y0, x1, y1] = box as number[];
      if (!(x0 < x1 && y0 < y1 && x1 <= image.width && y1 <= image.height)) throw invalid();
      const width = x1 - x0, height = y1 - y0;
      // Native crops and smaller overviews retain the source rectangle's aspect
      // ratio. Allow the one-pixel rounding from an overview's integer size.
      if ((call.input_width as number) > Math.ceil(width) || (call.input_height as number) > Math.ceil(height)
          || Math.abs((call.input_width as number) * height - (call.input_height as number) * width) > Math.max(width, height)) throw invalid();
    }
    callIds.add(call.id);
  }
  const nodes = value.nodes ?? [];
  if (!Array.isArray(nodes) || nodes.length > 20) throw invalid();
  const ids = new Set<string>();
  for (const node of nodes) {
    if (!object(node) || !text(node.id) || ids.has(node.id)
        || (node.parent_id != null && (!text(node.parent_id) || !ids.has(node.parent_id)))
        || !choice(node.criterion, ['capability', 'route', 'preparation', 'analysis', 'evidence'])
        || !choice(node.state, ['evaluated', 'selected', 'skipped', 'reused', 'completed', 'failed', 'unavailable'])
        || !text(node.reason_code, 120) || (node.value != null && !text(node.value, 120))
        || !probability(node.probability) || !probability(node.threshold)
        || (node.call_id != null && (!text(node.call_id) || !callIds.has(node.call_id)))) throw invalid();
    ids.add(node.id);
  }
  return value as unknown as ImageDecisionTrace;
}

const reasons: Record<string, [string, string]> = {
  budget_exhausted: ['The request time budget was exhausted.', 'Pyynnön aikabudjetti ylittyi.'],
  normal_supported: ['The task meets the standard capability criteria.', 'Tehtävä täyttää tavallisen analyysin kriteerit.'],
  strong_confident: ['The need for advanced interpretation meets the Carbon threshold.', 'Vaativan tulkinnan tarve täyttää Carbonin valintarajan.'],
  hydrogen_preferred: ['The evidence does not meet the Carbon threshold; Hydrogen is preferred.', 'Arvio ei täytä Carbonin valintarajaa; Hydrogen on ensisijainen.'],
  routing_fallback_normal: ['Routing did not return a usable classification; the fallback recommendation is Hydrogen.', 'Reititys ei palauttanut käyttökelpoista luokittelua; varasuositus on Hydrogen.'],
  fit_below_threshold: ['One or more required capability assessments fell below the threshold.', 'Yksi tai useampi vaadittu soveltuvuusarvio alitti rajan.'],
  overall_fit_below_threshold: ['Overall standard capability fit was below the required threshold.', 'Kokonaisarvio tavalliseen analyysiin soveltuvuudesta alitti vaaditun rajan.'],
  difficult_or_uncertain: ['The image or task needs advanced interpretation or remains uncertain.', 'Kuva tai tehtävä vaatii vaativampaa tulkintaa tai on epävarma.'],
  capability_not_enabled: ['This task is outside the enabled standard capabilities.', 'Tehtävä ei kuulu käytössä oleviin tavallisiin toimintoihin.'],
  router_timeout: ['Routing reached its time limit; no classification was received.', 'Reitityksen aikaraja ylittyi; luokittelua ei saatu.'],
  router_connect_timeout: ['Connecting to the routing service timed out; no classification was received.', 'Yhteyden muodostaminen reitityspalveluun aikakatkaistiin; luokittelua ei saatu.'],
  router_write_timeout: ['Uploading the routing request timed out; no classification was received.', 'Reitityspyynnön lähetys aikakatkaistiin; luokittelua ei saatu.'],
  router_read_timeout: ['Waiting for the routing response timed out; no classification was received.', 'Reititysvastauksen odotus aikakatkaistiin; luokittelua ei saatu.'],
  router_pool_timeout: ['Waiting for an available routing connection timed out; no classification was received.', 'Vapaan reititysyhteyden odotus aikakatkaistiin; luokittelua ei saatu.'],
  router_failed: ['Routing failed.', 'Reititys epäonnistui.'],
  routing_unavailable: ['The routing service is unavailable.', 'Reitityspalvelu ei ole käytettävissä.'],
  shadow_baseline: ['Observation mode: the configured baseline ran; the recommendation did not change execution.', 'Seurantatila: määritetty perusmalli suoritettiin; suositus ei muuttanut suoritusta.'],
  route_selected: ['The host selected this analysis route.', 'Palvelin valitsi tämän analyysireitin.'],
  whole_image: ['The whole selected image was used.', 'Käytettiin koko valittua kuvaa.'],
  preprocessing_deferred: ['Additional preprocessing was skipped for this route.', 'Tällä reitillä ohitettiin ylimääräinen esikäsittely.'],
  detailed_scan_requested: ['Detailed scan uses native regions and reconciles repeated observations.', 'Tarkka tunnistus käyttää alkuperäisiä kuva-alueita ja yhdistää toistuvat havainnot.'],
  detail_selected: ['The selected analyzer inspects native drawing detail.', 'Valittu analyysimalli tutkii alkuperäisen piirustuksen yksityiskohtia.'],
  native_detail_selected: ['The selected analyzer inspects native regions, reconciles repeated objects and checks uncertain candidates.', 'Valittu analyysimalli tutkii alkuperäisiä kuva-alueita, yhdistää toistuvat kohteet ja tarkistaa epävarmat ehdokkaat.'],
  detail_completed: ['Detailed scan completed with source-bound observations.', 'Tarkka tunnistus valmistui lähdekuvaan sidotuilla havainnoilla.'],
  detail_budget_exceeded: ['The selected detail coverage exceeds the available call budget.', 'Valittu tarkka tunnistus ylittää käytettävissä olevan kutsumäärän.'],
  analysis_completed: ['Analysis completed.', 'Analyysi valmistui.'],
  analysis_failed: ['Analysis failed.', 'Analyysi epäonnistui.'],
  analysis_cancelled: ['Analysis was cancelled or reached its deadline.', 'Analyysi peruttiin tai sen aikaraja ylittyi.'],
  strong_unavailable: ['The selected advanced analyzer is unavailable.', 'Valittu vaativa analyysimalli ei ole käytettävissä.'],
  evidence_unverified: ['Candidates remain unverified; completeness and calculations are not established.', 'Ehdokkaita ei ole vahvistettu; kattavuutta ja laskelmia ei ole varmistettu.'],
};
export function decisionReason(node: AnalysisDecisionNode, language: Language): string {
  const entry = Object.hasOwn(reasons, node.reason_code) ? reasons[node.reason_code] : undefined;
  return entry ? entry[language === 'fi' ? 1 : 0] : language === 'fi' ? 'Tallennettu päätös; lisätietoja ei saatavilla.' : 'Recorded decision; no further explanation is available.';
}
export function routeLabel(profile: ImageDecisionTrace['selected_profile'], language: Language): string {
  if (profile === 'pending') return language === 'fi' ? 'Reittiä ei valittu' : 'Route not selected';
  return profile === 'strong' ? language === 'fi' ? 'Vaativa analyysi' : 'Advanced analysis'
    : profile === 'normal' ? language === 'fi' ? 'Tavallinen analyysi' : 'Standard analysis'
      : language === 'fi' ? 'Määritetty analyysi' : 'Configured analysis';
}

const values: Record<string, [string, string]> = {
  supported: ['Supported', 'Tuettu'], needs_strong: ['Advanced interpretation needed', 'Vaativa tulkinta tarpeen'], uncertain: ['Uncertain', 'Epävarma'],
  floor_plan: ['Floor plan', 'Pohjapiirros'], schedule: ['Schedule or table', 'Luettelo tai taulukko'],
  section_or_elevation: ['Section or elevation', 'Leikkaus tai julkisivu'], mixed_panels: ['Multiple views or panels', 'Useita näkymiä'],
  other_or_unclear: ['Other or unclear', 'Muu tai epäselvä'], instance_discovery: ['Locate visible objects', 'Paikanna näkyvät kohteet'],
  literal_lookup: ['Read a label or property', 'Lue tunniste tai ominaisuus'], quantity_value: ['Find a quantity', 'Hae määrä'],
  arithmetic: ['Calculate quantities', 'Laske määriä'], geometry: ['Measure geometry or relationships', 'Mittaa geometriaa tai yhteyksiä'],
  mixed_or_unclear: ['Mixed or unclear task', 'Yhdistelmä tai epäselvä tehtävä'], logical_object: ['Logical object', 'Looginen kohde'],
  assembly: ['Assembly', 'Kokoonpano'], unit_or_leaf: ['Component unit or leaf', 'Osayksikkö tai lehti'],
  schedule_row_or_type: ['Schedule row or type', 'Luettelon rivi tai tyyppi'], room_or_unit: ['Room or apartment', 'Huone tai asunto'],
  not_counting_or_unclear: ['No count or unclear unit', 'Ei laskentaa tai yksikkö epäselvä'],
  doors: ['Doors', 'Ovet'], windows: ['Windows', 'Ikkunat'], fixtures: ['Fixtures', 'Kalusteet'],
  selected_view: ['Selected view', 'Valittu näkymä'], wider_or_named: ['Wider or named source scope', 'Laajempi tai nimetty lähde'],
  ambiguous: ['Ambiguous', 'Monitulkintainen'], normal: ['Standard analysis', 'Tavallinen analyysi'], strong: ['Advanced analysis', 'Vaativa analyysi'],
  pending: ['Route not selected', 'Reittiä ei valittu'],
  manual: ['Configured analysis', 'Määritetty analyysi'], original: ['Original whole image', 'Alkuperäinen koko kuva'],
  whole_image: ['Whole selected image', 'Koko valittu kuva'], unverified: ['Unverified', 'Vahvistamaton'],
  ok: ['Detection completed', 'Tunnistus valmis'], partial: ['Partial detection', 'Osittainen tunnistus'],
  unreadable: ['Image could not be read', 'Kuvaa ei voitu tulkita'], unsupported: ['Task unsupported for this image', 'Tehtävää ei tueta tässä kuvassa'],
  off: ['Whole image', 'Koko kuva'], overview: ['Whole-image overview', 'Koko kuvan yleiskuva'],
  tiles: ['Overlapping native detail', 'Limittäiset alkuperäiset kuva-alueet'],
  regions: ['Selected native regions', 'Valitut alkuperäiset kuva-alueet'],
  auto: ['Automatic detail selection', 'Automaattinen yksityiskohtien valinta'],
};
export function decisionValue(value: string, language: Language): string {
  return Object.hasOwn(values, value) ? values[value][language === 'fi' ? 1 : 0] : language === 'fi' ? 'Ei saatavilla' : 'Unavailable';
}

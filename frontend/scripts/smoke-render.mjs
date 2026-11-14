import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToString } from 'react-dom/server';

// Pure server rendering: this does not launch or automate a browser.
const server = await createServer({
  root: fileURLToPath(new URL('..', import.meta.url)),
  server: { middlewareMode: true, ws: false },
  appType: 'custom',
  logLevel: 'error',
});
try {
  const { default: App } = await server.ssrLoadModule('/src/App.tsx');
  const html = renderToString(createElement(App));
  assert.match(html, /Start with a drawing/);
  assert.match(html, /Select files/);
  assert.match(html, /drag and drop them here/);
  assert.match(html, /type="file"/);
  assert.doesNotMatch(html, /Ground floor|West Harbour|Demo drawings/);
  assert.doesNotMatch(html, /class="drawing-stage|class="answer-panel/);
  assert.doesNotMatch(html, /Question about the drawing/);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(
    new Set(ids).size,
    ids.length,
    'Rendered element IDs must be unique.',
  );
  console.log(
    'Initial import screen rendered without demo drawings or a chat panel.',
  );
  const { DecisionTrace } = await server.ssrLoadModule('/src/components/DecisionTrace.tsx');
  const source = { sha256: 'a'.repeat(64), inference_sha256: 'b'.repeat(64), width: 800, height: 400, coordinate_system: 'display_pixels_top_left' };
  const trace = {
    request_id: 'render-test', question_sha256: 'c'.repeat(64), image: source,
    mode: 'shadow', selected_profile: 'manual', recommended_profile: 'strong',
    policy_version: 'capability-routing-v1', capability_version: 'pilot-v1',
    assessments: { normal_fit: 'supported', task_kind: 'instance_discovery', scope: 'selected_view', target_kind: 'windows' },
    assessment_probabilities: { normal_fit: 0.96, task_kind: 0.62, scope: 0.99, target_kind: 0.99 }, calls: [],
    nodes: [
      { id: 'fit', criterion: 'capability', state: 'evaluated', reason_code: 'fit_below_threshold', probability: 0.96, threshold: 0.9 },
      { id: 'prep', parent_id: 'fit', criterion: 'preparation', state: 'skipped', reason_code: 'preprocessing_deferred' },
      { id: 'execution', parent_id: 'prep', criterion: 'analysis', state: 'failed', reason_code: 'analysis_failed' },
    ],
  };
  const path = renderToString(createElement(DecisionTrace, { trace, language: 'en' }));
  assert.match(path, /<details class="decision-trace"><summary>/);
  assert.doesNotMatch(path, /<details[^>]*open/);
  assert.match(path, /How this was analyzed/);
  assert.match(path, /Observation mode.*Recommended route:.*Advanced analysis/);
  assert.match(path, /96%.*Required threshold.*90%/);
  assert.match(path, /62%/); // Legacy auxiliary task score caused escalation.
  assert.match(path, /Skipped/);
  assert.match(path, /Analysis failed/);
  assert.match(path, /not answer accuracy percentages/);
  assert.match(path, /Every required assessment must meet the threshold/);
  const ordinary = {
    ...trace, mode: 'auto', policy_version: 'capability-routing-v2',
    selected_profile: 'normal', recommended_profile: 'normal',
    assessment_probabilities: { ...trace.assessment_probabilities, normal_fit: 0.72, task_kind: 0.52 },
    nodes: [{ id: 'fit', criterion: 'capability', state: 'evaluated', reason_code: 'normal_supported',
              value: 'supported', probability: 0.72, threshold: 0.6 }],
  };
  const current = renderToString(createElement(DecisionTrace, { trace: ordinary, language: 'en' }));
  assert.match(current, /Standard analysis/);
  assert.match(current, /Only overall capability fit is compared with the threshold:.*60%/);
  assert.match(current, /They do not independently select advanced analysis/);
  assert.doesNotMatch(current, /Every required assessment/);
  const currentFi = renderToString(createElement(DecisionTrace, { trace: ordinary, language: 'fi' }));
  assert.match(currentFi, /Vain kokonaisarviota soveltuvuudesta verrataan rajaan/);
  const hard = { ...ordinary, selected_profile: 'strong', recommended_profile: 'strong',
    nodes: [{ ...ordinary.nodes[0], reason_code: 'overall_fit_below_threshold', probability: 0.55 }] };
  assert.match(renderToString(createElement(DecisionTrace, { trace: hard, language: 'en' })),
    /Overall standard capability fit was below the required threshold/);
  const cautious = {
    ...ordinary, policy_version: 'capability-routing-v3',
    assessments: { ...ordinary.assessments, normal_fit: 'needs_strong' },
    assessment_probabilities: { ...ordinary.assessment_probabilities, normal_fit: 0.79 },
    nodes: [{ id: 'fit', criterion: 'capability', state: 'evaluated', reason_code: 'hydrogen_preferred',
              value: 'needs_strong', probability: 0.79, threshold: 0.8 }],
  };
  const v3 = renderToString(createElement(DecisionTrace, { trace: cautious, language: 'en' }));
  assert.match(v3, /Standard analysis/);
  assert.match(v3, /Carbon recommendation requires a clear need.*80%/);
  assert.match(v3, /Probability that advanced interpretation is needed.*79%/);
  assert.match(v3, /Hydrogen is the default recommendation, including uncertain classifications or routing timeouts/);
  assert.doesNotMatch(v3, /Probability of standard capability fit|Every required assessment|Only overall capability fit/);
  const v3Fi = renderToString(createElement(DecisionTrace, { trace: cautious, language: 'fi' }));
  assert.match(v3Fi, /Carbon-suositus vaatii selvän tarpeen/);
  assert.match(v3Fi, /Vaativan tulkinnan tarpeen todennäköisyys/);
  const confident = { ...cautious, selected_profile: 'strong', recommended_profile: 'strong',
    assessment_probabilities: { ...cautious.assessment_probabilities, normal_fit: 0.91 },
    nodes: [{ ...cautious.nodes[0], reason_code: 'strong_confident', probability: 0.91 }] };
  assert.match(renderToString(createElement(DecisionTrace, { trace: confident, language: 'en' })),
    /need for advanced interpretation meets the Carbon threshold/);
  const fallback = { ...cautious, assessments: {}, assessment_probabilities: {},
    nodes: [{ id: 'fit', criterion: 'capability', state: 'failed', reason_code: 'router_read_timeout' },
      { id: 'route', parent_id: 'fit', criterion: 'route', state: 'selected', reason_code: 'routing_fallback_normal', value: 'normal' }] };
  const fallbackHtml = renderToString(createElement(DecisionTrace, { trace: fallback, language: 'en' }));
  assert.match(fallbackHtml, /Waiting for the routing response timed out; no classification was received/);
  assert.match(fallbackHtml, /fallback recommendation is Hydrogen/);
  assert.doesNotMatch(fallbackHtml, /Probability that advanced interpretation is needed/);
  const fi = renderToString(createElement(DecisionTrace, { trace, language: 'fi' }));
  assert.match(fi, /Näin kuva analysoitiin/);
  assert.match(fi, /Valittu näkymä/);
  assert.match(fi, /Paikanna näkyvät kohteet/);
  assert.match(fi, /96/);
  const pending = renderToString(createElement(DecisionTrace, { trace: { ...trace, selected_profile: 'pending', mode: 'auto', nodes: [{ id: 'timeout', criterion: 'capability', state: 'failed', reason_code: 'router_timeout' }] }, language: 'en' }));
  assert.match(pending, /Route not selected/);
  assert.match(pending, /Routing reached its time limit; no classification was received/);
  assert.doesNotMatch(pending, /advanced analysis was selected/i);
  const legacy = renderToString(createElement(DecisionTrace, { language: 'en' }));
  assert.match(legacy, /No decision path was recorded/);
  console.log('Collapsed decision trace renders shadow, thresholds, skipped steps, failures, Finnish and legacy states.');
} finally {
  await server.close();
}

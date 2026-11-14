# Sprint-one verification record

## Decisions routing and current main integration, 14 November 2026

Integrated the routing/loading work with main through `361c639`, preserving its
independent IFC planners, geometry/spatial execution and DXF preview/import flow.
The merged app retains streamed image handoff, private provider diagnostics,
source-bound contracts and format-specific upload limits. Carbon image profiles
cannot change the separate Hydrogen IFC planner. Shutdown attempts every owned
source/client cleanup even if another cleanup raises.

Validation on Linux, Python 3.12.3 and Node 24.22.3:

- **487 Python tests passed**, no skips, in 51.368 seconds. New integration
  regressions combine manual/auto Carbon image streaming with Hydrogen IFC
  execution and verify client cleanup after a close failure. Provider requests
  were mocked; the suite includes the newer IFC and DXF checks from main.
- All **18 frontend test files**, TypeScript/production build and SSR checks
  passed. Existing optional Three/IFC export and bundle-size warnings remain.
- **11 Firefox 142.0 loading checks passed** against synthetic responses after
  the UI merge, including both model handoffs, narrow/Finnish layouts,
  source/page/cancel clearing and final overlays/export. Five synthetic requests,
  no JavaScript errors and no live inference calls. Owned test servers stopped.
- All **14 generated contracts** are current; Markdown links and whitespace
  checks passed. The project's API extras installed the new DXF dependency in
  the local virtual environment; local credentials were unchanged.
- Exactly **one Astra-6 Max** reviewer inspected both-parent integration and
  the five new screenshots with their source-bound packets. Final verdict:
  **pass (`agent_reviewed`)**, with no unresolved findings.

Ignored evidence: `experiments/runs/decision-routing-main-merge/20261114T210320Z/`.
These are integration and synthetic UI checks, not routing calibration or
live-model accuracy measurements. Automatic preprocessing remains planned.

## Immediate model handoff during loading, 14 November 2026

The image/PDF loading states now show **Preparing image…**, **Choosing analysis
model…**, then **Handing to [actual selected model]…** immediately before analyzer
dispatch. Both the viewer overlay and chat loading state update before candidate
output finishes, with English/Finnish text. The post-result decision disclosure
remains available. Shadow/manual modes name the actual baseline, not the router's
unexecuted recommendation; unavailable routes emit no handoff.

The existing POST endpoint supports opt-in `application/x-ndjson` streaming with
source/request/question-bound handoff and terminal result/error contracts. The
JSON default and pre-stream HTTP validation errors remain compatible. There is
no extra inference, polling or automatic resubmission. Cancel/source/page/new
request guards reject stale status and final output. Streaming cleanup awaits
asynchronous provider cancellation before image cleanup and admission release,
including ASGI 2.3/2.4 disconnect and send-failure cases.

Validation on Linux, Python 3.12.3 and Node 24.22.3:

- **363 Python tests passed**, no skips, in 33.391 seconds. Eleven new stream
  tests drive ASGI sends directly, proving handoff delivery while an analyzer is
  deliberately blocked, rather than relying on a buffering test transport. They
  also cover actual models across modes, cached routes, unavailable Carbon,
  validation/errors, deadlines, admission and disconnect cleanup.
- All **17 frontend test files**, TypeScript/production build and SSR checks
  passed. Client tests include blocked-terminal progress, arbitrary UTF-8 chunk
  boundaries, malformed/truncated streams, request/source/model bindings,
  cancellation, strict versions and JSON fallback without retries. Existing
  optional Three/IFC export and bundle-size warnings remain.
- **11 Firefox 142.0 checks passed** with a private synthetic streaming backend
  and controlled routing/analysis barriers. Both Hydrogen and Carbon handoffs
  were visible in viewer/chat while terminal output remained blocked; narrow,
  Finnish, source/page/cancel/new-request and overlay/export checks passed.
  Five synthetic browser requests, no JavaScript errors and no live inference.
- Exactly **one Astra-6 Max** reviewer inspected implementation, lifecycle cases
  and five screenshots with their bound packets. All findings were addressed;
  final verdict pass (`agent_reviewed`). Its own sandbox-stalled full-app check
  was stopped; the successful API suites ran outside the known worker-wakeup
  restriction with mocked providers. Independent isolated cleanup checks passed.
- All **13 generated contracts** are current; Markdown and whitespace checks
  passed. Owned temporary browser/test servers were stopped; the requested
  preview backend was restarted; the frontend preview was restored on its free
  port and both were left running.

Evidence/review packet: ignored `experiments/runs/model-handoff-loading/20261114T204644Z/`.
These checks establish loading/protocol/lifecycle behavior, not model accuracy,
routing calibration or a provider latency improvement. No live model calls or
local credential-file edits were needed for this change.

## Routing over-escalation correction, 14 November 2026

The initial gate sent too many ordinary cases to Carbon: it demanded 90%
confidence on every independent classification and then admitted only direct
floor-plan door/window/fixture discovery at logical-object/assembly grain.
Uncertainty over a taxonomy label could therefore force strong analysis even
when the overall image/task assessment favored the standard analyzer.

Policy `capability-routing-v2` now uses one overall-fit gate: `supported` with
probability at least **0.6** selects Hydrogen-low. Explicit difficulty or genuine
capability uncertainty, lower overall fit and router errors/timeouts still select
Carbon directly. Layout, task, target, grain and scope labels are diagnostics,
without separate confidence/category vetoes. The provisional criteria include
ordinary room/object, label, schedule and printed-quantity candidate work. Both
profiles retain the original question, submitted raster, candidate-only contract
and unsupported/missing-information outcomes; no new source or executor is added.

The capability/policy versions and cache inputs changed. Explicit threshold
overrides remain honored. The UI explains the overall-only v2 threshold, while
historical v1 traces retain the all-assessments explanation and failure reason.

Validation on Linux (Python 3.12.3, Node 24.22.3):

- **352 Python tests passed**, no skips, in 38.527 seconds. Regressions cover
  threshold boundaries/overrides, lower diagnostic confidence, alternate ordinary
  families, explicit difficulty, source/question and unsupported-status preservation
  on both profiles, cache invalidation, failures, budgets and IFC isolation.
- All **17 frontend test files**, TypeScript/production build and server-rendered
  v1/v2 explanation checks passed. Existing IFC/Three optional-export and large
  bundle warnings remain. The SSR script now locates its frontend root portably
  when invoked from the repository root.
- **14 headless Firefox checks passed** against a synthetic local HTTP backend,
  including display of a synthetic Hydrogen route with 72% overall fit, 52%
  diagnostic scores and a 60% threshold, keyboard disclosure, no inference on opening, overlays/JSON export, narrow
  layout, failures, shadow mode and source/PDF-page trace clearing. No JavaScript
  errors or live inference calls. Owned temporary servers/browser were stopped.
- Replaying fixed historical Decisions scores changes the saved window request
  from Carbon to Hydrogen: P(supported)=0.6591, v1 threshold 0.9 versus v2 threshold 0.6.
  This is a counterfactual host-policy check. The changed prompt was not sent to
  Decisions; live predictions may differ. It establishes neither Hydrogen output
  quality, a calibrated threshold nor aggregate cost/accuracy improvement.

- Exactly one Astra-6 Max reviewer inspected the routing change, source-bound
  synthetic desktop/narrow traces and historical replay. All findings were
  addressed; final verdict **pass (`agent_reviewed`)**. The owned preview backend
  was restarted with v2 while the existing frontend remained running.

Counterfactual report and review/browser artifacts are preserved in ignored
`experiments/runs/decision-routing-policy-v2/20261114T202021Z/`. No new provider
calls, user source edits, commits or deployment are part of this correction.

## Experimental Decisions routing, 14 November 2026

Implemented the first capability-routing slice on `feature/gemini-decisions-routing`:
native Decisions transport; explicit Hydrogen-low/Carbon-medium profiles; opt-in
shadow/auto routing; bounded session decision caching; one selected analyzer;
source/question-bound traces on success, failures and deadlines; expandable
English/Finnish UI path and per-call cost estimates. Routing defaults to off;
thresholds/capabilities are provisional pending paired dataset evaluation.

Checked on Linux with Python 3.12.3 and Node 24.22.3:

- Full Python suite: **345 tests passed**, no skips, in 34.408 seconds, including
  synthetic IFC fixtures and mocked provider transports. New checks cover direct
  strong dispatch, registry/threshold guards, shadow/cache accounting, trace
  identity/invalid inputs, failure/cancellation and the finalization reserve.
- All **17 frontend test files** passed. TypeScript and production build passed;
  existing optional Three/WebGPU export and large-chunk warnings remain.
  Server-rendered checks cover collapsed traces, shadow/pending states, scores,
  skipped preparation, errors, Finnish and missing legacy traces.
- Headless Firefox 142.0 automated checks used a synthetic local HTTP backend:
  initially collapsed disclosure, keyboard open/close without inference, unchanged
  overlays and trace export, no narrow horizontal overflow, source/PDF-page
  trace clearing, terminal-error traces without candidates and error-text contrast. Twelve
  checks passed; no JavaScript errors and no live inference. Screenshots and
  matching normal/strong/shadow/error traces were collected under `/tmp/decisions-ui-*` for the single
  Astra-6 Max reviewer; these temporary files are not tracked benchmark data.
- Generated schemas/types, Markdown links and whitespace checks passed. Sandbox
  async thread wakeups stalled the HTTP tests; the successful suite ran outside
  that restriction with mocked external transports. Owned temporary browser and
  test servers were stopped.
- Exactly one Astra-6 Max subagent reviewed the implementation and seven
  screenshot artifacts against saved traces. All findings were addressed and
  the final verdict was pass (`agent_reviewed`). Evidence and the review record
  are preserved in ignored `experiments/runs/decision-routing-implementation/20261114T193509Z/`.

The automatic approval reviewer initially blocked the live checks pending
specific egress approval. The user then approved exactly two calls; the live
record below supersedes that pending status. Paired evaluation, routing
calibration and automatic preprocessing remain future work.

## Approved live smoke and Carbon thinking correction, 14 November 2026

Sent the selected preview raster `colorful-11397.png` (475 × 650) and the question
“Locate one clearly visible window assembly. Return at most one candidate.” to
Decisions and Carbon, one attempt each without retries. No reference answer or
filename/dataset identity entered either model's input. This checks protocol and
access; it is not a paired model-quality comparison.

- Decisions completed in **1.011 s**, using 2,108 input tokens and zero output.
  The returned task/target/grain/scope assessments were discovery/windows/assembly/
  selected-view. Normal fit was 0.6591; the provisional 0.9 policy selected strong.
  Applied policy/criteria versions and threshold are recorded in the run report.
- The initial **Carbon-high** request was accepted, but returned `incomplete`
  after **55.765 s**. Its 4,093 thinking and three output tokens exactly reached
  the approved **4,096-token** cap; it also reported 2,188 input tokens. No
  candidate JSON or candidate boxes were returned. The API correctly rejected it
  with `invalid_model_output`; no continuation or automatic retry ran.
- Following the user's correction, Carbon now defaults to **medium** on the strong
  route, with **low** selectable through
  `IMAGE_API_ROUTING_STRONG_THINKING_LEVEL=low`. High is outside the application
  allowlist. Hydrogen remains low. The saved high-thinking run is retained as
  historical evidence; the separate corrective medium check is recorded below.
- Fixed the failed-response accounting gap exposed by this call: retain validated
  usage and allowlisted model metadata through client, adapter and error trace,
  including incomplete or malformed candidate output. Invalid counters remain
  unknown; raw bodies and continuation tokens stay out of public errors/traces.
  Replaying the saved response offline still rejects it and retains the known
  2,188 input / 4,096 generated tokens. No extra provider call was needed.
- After the profile/accounting changes, the full Python suite passed **348
  tests**, no skips, in 32.260 seconds. Focused mocked regressions also cover
  incomplete usage preservation and completed malformed candidates with untrusted
  model metadata. Contract export, Markdown and whitespace checks passed; these
  are offline checks, not medium/low live-quality measurements.
- One Astra-6 Max reviewer inspected the source and raw/parsed results. Clear
  window assemblies are visible, but two side-by-side floor plans make the
  router's single-dominant-plan classification questionable. Candidate support
  and normal-versus-strong benefit remain undetermined because Carbon returned
  no candidates. Keep this as a development/calibration observation; no threshold
  or prompt was tuned from it.

Ignored artifacts: `experiments/runs/decision-routing-smoke/20261114T193754Z/`,
including raw replies, source/question hashes, settings, report and offline
replay. Estimated standard-rate cost from the project's dated tariff table is
$0.0455468 for those initial two calls, including the failed Carbon output; this
is not an invoice.

Following the user's instruction to use low/medium, one separate corrective
**Carbon-medium** call used the same raster/question and 4,096-token cap, reusing
the saved Decisions recommendation rather than making another router call:

- Completed in **55.994 s**, with 2,188 input and 3,838 generated tokens (3,745
  thinking plus 93 output), returning `ok` and **one candidate**. Its source and
  inference hashes, response contract and raw-to-display coordinates matched.
- The same Astra-6 Max reviewer found the window assembly source-supported at
  `[423.7, 189.8]–[439.85, 277.55]`, excluding the adjacent balcony doorway and
  other openings. The null source label avoids inventing an identifier.
- Medium completed under the cap; the similar elapsed time to the incomplete high
  call does not demonstrate faster inference. This is one source-checked proposal,
  not a dataset-accuracy or normal-versus-strong comparison. Low remains untested.
- Corrective artifacts: `experiments/runs/decision-routing-smoke/20261114T195038Z-medium/`.
  Estimated additional standard-rate cost: $0.042756; all three live calls total
  $0.0883028 before invoice adjustments. No further live calls ran.
## Spatial implementation and upstream integration, 14 November 2026

Integrated the uncommitted spatial composition/geometry implementation based on
`9db07ec` with upstream `b4cc92d`, including `89dbae1`. The combined service keeps
independent IFC providers, source discovery and one preflight repair within shared
request, inspection, context and planning-deadline budgets. Exterior-door lower
bounds remain distinct from unresolved spatial topology; Gemini's native plan
schema now accepts `related_entities`. Generated contracts were rebuilt from the
merged Python models. No implementation commit or push was made.

Checked on Linux with Python 3.12.3, IfcOpenShell 0.9.0.post1, Pydantic 2.14.3,
FastAPI 0.162.7 and Node 24.22.3:

- Full Python suite: **421 tests, 420 passed and one skipped**, in 19.444 seconds,
  using `.venv/bin/python -m unittest discover -s tests -v`. The optional
  Esplanades test skipped because its required preview path is absent. Provider
  credentials were disabled and inference transports mocked. Normal local
  socket/thread access was enabled; no asyncio heartbeat workaround was needed.
  The suite includes the 24-case offline planner replay, geometry regressions,
  exterior lower-bound propagation and candidate-topology aggregate rejection.
- Final planning/API/provider check: **47 tests passed** in 2.502 seconds after
  adding four integration regressions. These verify shared discovery/repair
  budgets, unchanged captured scope/catalog, cumulative token accounting,
  unreported usage and sanitized diagnostics. This focused check followed minor
  cleanup of the proposal exception and exhausted-budget wording.
- All **17 frontend test files** passed with `npm run test:frontend`.
  `npm run build` passed TypeScript checks and Vite bundling; existing optional
  Three/WebGPU exports and large-chunk warnings remain.
- All 12 generated schemas are current, frontend types were regenerated, and
  local Markdown links and whitespace checks passed.

These are offline integration checks. Browser interaction, Windows behavior and
live provider compatibility were not rerun for this merge. Original drawing
assets and reference answers were unchanged.

## Gemini Hydrogen 100-image count evaluation, 14 November 2026

Ran 100 supplied image/count-question pairs through the current production HTTP
candidate route with real `gemini-4-hydrogen`, low thinking, original full-source
preprocessing and no retries. The isolated server admitted six concurrent
requests; model prompts, schemas and production source code were unchanged.

- 100 distinct files and submitted image hashes; 60 CubiCasa PNGs and 40
  single-page PDFs, spanning 29 question families and eight languages. Whole-model
  IFC questions were excluded from this image-only test.
- All 100 requests returned HTTP 200 and validated responses bound to the
  submitted image hashes/dimensions. Raw provider outputs were saved before
  validation, and references were used for scoring only after all outputs existed.
- **79/100 exact candidate-count matches**, also 79/100 with strict `ok` status;
  98 `ok` and two `partial` responses. This is not final-answer or box-localization
  accuracy. One selected derived quantity requires arithmetic outside this API.
- Median HTTP round trip 5.79 s; p95 15.19 s; live run wall time 125.48 s.
  Reported input/output-plus-thinking tokens: 219,400 / 117,397. Estimated paid
  standard-rate cost: $1.2095775 USD before discounts, credits and taxes.
- Five offline benchmark harness tests passed. Documentation links and whitespace
  checks passed. Platform: Windows, Python 3.14.10. No browser/manual full-sample
  geometry verification is claimed. The isolated evaluation server was stopped.

The [detailed report](../experiments/image_questions/GEMINI_100_RESULTS.md)
records sampling, source/family results, failure examples, pricing, limitations
and the ignored local artifact directory. Original drawings/reference answers
were not modified, and the workbench servers were left running.

## IFC exterior doors and independent planners, 14 November 2026

Implemented native exterior-door membership, an independent Nemotron/Hydrogen
planner selector, bounded source discovery/inspection and a paired evaluation
harness. Source parsing and final computations remain in the native executor.

Checked on Linux with Python 3.14.10, IfcOpenShell 0.9.0.post1, Pydantic 2.14.3,
Node 26.13.1 and Firefox 160.0:

- Full Python suite: **367 tests passed**, no skips, in 31.958 seconds. Credentials
  were disabled; providers were mocked. Checks cover inherited/overridden flags,
  door/opening boundary paths, duplicate boundaries, unknown/conflicting membership,
  exact scope, lower-bound propagation, native proof anchors, independent provider
  lifetimes/configuration, inspection budgets/cancellation and safe diagnostics.
  Normal local socket/thread access was needed for asynchronous/server checks.
- All **17 frontend test files** and the TypeScript/Vite production build passed.
  Existing optional Three/WebGPU export and chunk-size warnings remain. Generated
  JSON Schemas and TypeScript were refreshed; all 12 contracts are current.
- The six-model, **24-case offline replay** passed every declared fixture check
  with zero external inference. It checks authored plans, source memberships,
  boundary anchors, exact scope and non-answer/partial outcomes. This is not a
  natural-language accuracy score. The runner records code fingerprints and saves
  predictions before importing evaluator-only reference values.
- Executed all three exterior bases on supplied models without inference:
  FZK-Haus combined gives **at least 2**, with three unresolved doors; Esplanades
  combined gives **at least 5**, with 36 unresolved doors and no native boundaries;
  Dental architecture gives **18** by combined/classification and **12 recorded**
  by boundary-only evidence. The unequal Dental sets are not a demonstrated
  contradiction. Source hashes and proof counts are saved locally under
  `build/ifc-exterior-implementation.json`.
- Firefox imported and rendered the actual FZK model, uploaded it only to the
  local backend and used an injected synthetic planner. It displayed **At least 2**,
  two included doors, zero exclusions and three separately unresolved doors;
  eight native boundary-record links and the original source hash were present.
  JSON export preserved the bound and membership. A boundary-only follow-up
  returned **2 recorded doors** with the source limitation. No uncaught page errors
  occurred. Artifacts are under `build/ifc-exterior-browser/`; owned servers and
  browser profiles were cleaned up. The main count was subsequently moved ahead
  of the long explanatory narrative, then rebuilt.

Live structured-planning smoke checks used **only generated IFC metadata**, not
supplied building files or their catalogs. Across development there were five
explicit requests: one Nemotron and four Hydrogen-low requests, without SDK
retries. Nemotron returned the correct two exterior doors on the generated case.
Two initial Hydrogen requests produced provider-configuration errors; their
upstream status/code was not retained, so the exact rejection cause is unproven.
A kind-only native envelope reached the model but its output failed strict local
plan validation. The final shallow typed-operation schema succeeded: requested
and returned `gemini-4-hydrogen`, correct two source doors and native proofs,
17,502 input tokens, 933 combined output/thinking tokens including 616 thought
tokens, and 4,823 ms total for that selected request. These iterations are API
compatibility checks, not a controlled quality or latency ranking.

Hydrogen now constrains the envelope and six operation branches natively while
the full recursive plan schema remains supplied in instructions and strictly
validated before execution. Safe private diagnostics retain recognized upstream
categories/static validation locations; public errors omit them and all raw
provider bodies. No broad live provider benchmark, geometry inference or visual
IFC-reasoning model experiment is claimed. Existing backend `.env` values were
preserved. See [IFC usage](IFC_QUESTIONS.md) and
[comparison commands](../experiments/ifc_planners/README.md).

## IFC spatial composition and bounded geometry, 14 November 2026

Checked on Linux with Python 3.12.3, IfcOpenShell 0.9.0.post1, Pydantic 2.14.3,
FastAPI 0.162.7, httpx 0.28.1 and Node 24.22.3. Executor identity is
`ifc-engine/0.3.0`; extraction and geometry cache identities were also updated.

- Selected Python suite: **159 tests, 158 passed and one skipped**, in 6.343
  seconds. Modules were `test_contracts`, `test_ifc_engine`,
  `test_ifc_spatial_extraction`, `test_ifc_spatial_queries`,
  `test_ifc_spatial_composition`, `test_ifc_geometry`, `test_ifc_api` and
  `test_ifc_spatial_api`. The optional real-model unittest skipped because its
  exact preview path is absent. A separate CLI check of the installed full
  Esplanades source returned **211 modeled doors** with status `answered`.
- API tests used mocked inference. This sandbox failed to wake asyncio loops
  after thread completion, so the combined suite used a temporary guarded
  runner scheduling a 10 ms loop heartbeat. Application code and test assertions
  were unchanged by that workaround. An earlier unguarded temporary runner
  re-entered tests in spawned geometry workers; it was corrected before the
  passing result above.
- All **17 frontend test files** and the TypeScript/Vite production build
  passed. Existing optional Three/WebGPU export and large-chunk warnings remain.
  All 12 generated JSON Schemas are current; frontend types were regenerated.
- Regression coverage includes connected-room counting/deduplication, candidate
  cell bindings, per-relation coverage, mixed known/unknown inputs, undefined
  boundary flags, captured-scope reference projection, plan repair, upload
  ownership/cancellation, source hashes, rotated/millimetre geometry, long shared
  walls, wall-thickness checks, thin overlap rejection, and closed-object/convex-room
  containment prerequisites.
- An offline source probe on `dental_clinic_arc.ifc` compared native and `auto`
  neighbors of literal room `1B07`. Native mode returned eight rows, seven of
  them candidates. Auto returned four supported rows: `1BC2` via native door
  evidence and `1B05`, `1B09`, `1B04` via finite boundary patches. Four disjoint
  shared-wall candidates were excluded. All 49 source anchors resolved and
  result validation passed. Cold extraction took 12.82 seconds and the query
  8.03 seconds. The ignored local artifact
  `build/ifc-spatial-geometry-verification.json` retains the source evidence and
  calculation inputs; supplied QA answers were not used.

These are selected executor/integration checks, not dataset-wide accuracy or a
live natural-language planner evaluation. Browser and Windows behavior were not
rerun. Unsupported shapes remain unknown; generic metric predicates, measured
routes, orientation and compliance remain explicit non-answers.

## Frontend response metrics, 14 November 2026

Checked on Windows with Node 24.22.3 and Python 3.14.10. This frontend-only
change adds actual-model display, browser-measured total response time, and a
token-based USD estimate for image/PDF responses. Shared wire contracts and
backend model selection are unchanged.

- All **97 frontend tests** passed, including six pricing/timing regressions:
  model-specific arithmetic, the Carbon December rate change, missing versus
  zero usage, unknown model IDs, sub-cent amounts and localized timings.
- TypeScript and production build passed. Existing optional Three/WebGPU export
  and large-chunk warnings remain. Markdown links and whitespace checks passed.
- Server-rendering checks passed for Hydrogen with live token usage, Carbon
  pricing before/after 1 December, missing usage, unknown models, Finnish labels,
  candidate-panel integration and the initial import screen. These checks do
  not establish browser layout or interaction behavior.
- One live synthetic 256 × 256 PNG request through the running Vite proxy
  returned HTTP 200 from `gemini-4-hydrogen`: 2,181 input tokens, 349 output
  tokens (including thinking), and a 2,324 ms backend model-request time. The
  standard-rate calculator estimated $0.005889 USD, displayed as $0.0059.
  This was a connectivity/usage check, not a drawing-accuracy evaluation.
- Browser automation could not proceed: the browser connector was unavailable
  and native Firefox access was not approved by the computer-use tool. No
  Windows visual browser verification is claimed for this change.

## Gemini and main integration, 14 November 2026

Completed the interrupted merge of Gemini branch `e3fba25` with main `e68301f`.
The existing Nemotron image-question experiment explicitly retains its baseline
provider when the workbench selects Gemini; a regression checks the request and
saved provider metadata together.

Checked on Linux with Python 3.12.3, IfcOpenShell 0.9.0.post1, Pydantic 2.14.3,
FastAPI 0.162.7, httpx 0.28.1 and Node 24.22.3:

- Full Python suite: **313 tests passed**, no skips, in 37.682 seconds. Provider
  credentials were disabled; inference transports were mocked. Local socket and
  thread access was enabled for the server and lifecycle checks.
- All **16 frontend test files** passed, and TypeScript/production build passed.
  Existing optional Three/WebGPU export and large-chunk warnings remain.
- All 12 generated contracts are current. Local Markdown links, dependency
  consistency and whitespace checks passed.

This pass did not rerun browser or live inference checks. Earlier Gemini smoke
and browser observations remain in the
[provider verification record](../image_api/GEMINI_PLAN.md#implementation-and-verification-record).

## IFC spatial and descriptive questions, 14 November 2026

Extended the existing uncommitted IFC integration with native topology queries,
file/project/site metadata, compound query outputs and deterministic prose from
executed results. The [question-family audit](IFC_QUESTIONS.md#supplied-question-families)
records the supplied examples and remaining capability gaps.

Checks used Linux, Python 3.12.3, IfcOpenShell 0.9.0.post1, Pydantic 2.14.3,
FastAPI 0.162.7, httpx 0.28.1 and Node 24.22.3:

- Full Python suite: **274 tests passed**, no skips, in 16.990 seconds. The
  27 added regressions cover extraction across IFC2X3/IFC4/IFC4X3, spatial paths,
  door/opening identity, corresponding boundaries, duplicate boundaries, partial
  shared-wall candidates, missing topology, exact view membership, source
  coordinates/units, metadata narratives and compound API outputs. Provider
  responses were mocked; each new API answer used one planning request.
- All **16 frontend test files** passed, and TypeScript/production build passed.
  The existing optional Three/WebGPU export and chunk-size warnings remain.
  References now show literal names/STEP locators, and calculation details expose
  native relationship anchors even when no scalar facts are involved.
- All 12 JSON Schemas are current, and frontend contracts were regenerated.
  Markdown links and whitespace checks passed. Async/thread and HTTP-server
  tests required local socket access outside this environment's restricted
  sandbox; a sandbox-stuck owned test process was stopped afterward.
- Selected offline queries on supplied preview IFCs: `duplex_arc.ifc` returned
  four distinct rooms with recorded exterior-door boundaries and a native direct
  doorway connection from `A101`. `digital_hub_arc.ifc`, which lacks usable space
  boundaries, returned `missing_information` for outdoor access. No supplied QA
  answer lookup or provider call was used. The local source hashes/outcomes are
  recorded in `build/ifc-spatial-verification.json`.

This pass did not run a browser or live natural-language planner evaluation.
It does not establish complete IFC-Bench accuracy. Metric geometry, orientation,
nearest-distance and navigable routes remain unsupported; shared-element
adjacency remains an explicitly partial candidate answer. Existing browser/live
observations below belong to the earlier integration pass.

## IFC questions and answer verification, 14 November 2026

Connected the IFC viewer to a bounded Nemotron planner and the existing CPU IFC
executor. Checks used Linux, Python 3.12.3, IfcOpenShell 0.9.0.post1,
Pydantic 2.14.3, FastAPI 0.162.7, httpx 0.28.1 and Node 24.22.3.

- Full Python suite: 247 tests passed with no skips. This includes 23 new IFC
  API/exact-scope cases, three request-limit regressions, the existing real
  Esplanades engine check, image API/lifecycle tests and contract checks. API
  inference in this suite was mocked. Local socket access was required for the
  server tests and asynchronous thread completion in this execution environment.
- All 15 frontend test files passed, including 11 new identity and IFC API test
  cases. TypeScript and the production build passed. The existing SDK optional
  Three/WebGPU export and large-chunk warnings remain.
- All 12 JSON Schemas are current; the new IFC response/request types were
  generated from them. Local Markdown links, whitespace checks, and the initial
  import-screen server-rendering smoke check passed.
- Headless Firefox on Linux exercised a generated IFC with actual geometry,
  local upload/extraction/execution and a mocked Nemotron HTTP transport. The
  answer changed from three windows to two after storey filtering, to one after
  hiding an element, and back to three with explicit model scope. STEP/GUID
  inspection, persistent blue answer highlights, separate object selection,
  cached upload reuse, panel collapse/reopen, isolate matches, narrow-screen
  layout and absence of uncaught page errors were checked. This establishes the
  tested UI/API behavior, not natural-language accuracy on supplied models.
- Separate live Nemotron calls on the generated source returned three windows
  with STEP IDs 33/37/41, the widest window at STEP 37 with stored width 1.5 m,
  and two windows for a Finnish current-view question with STEP IDs 33/37.
  Source hashes matched. Selected successful planning/execution times were
  879, 991 and 1041 ms, with 10,253/199, 10,258/311 and 10,587/202 input/output
  tokens respectively. These are individual observations, not cost or latency
  benchmarks. The Finnish question initially exposed an ambiguous internal scope
  flag; renaming and clarifying that flag produced the final passing check.

Automatic approval review rejected the optional live supplied-model check because
authorization to send source-derived catalog data to the external provider was
unverified. That action was not retried, and no supplied-model data was sent in
these live checks. Five synthetic live calls were made, including the two Finnish
non-answer attempts before the correction. Supplied-corpus natural-language
accuracy, Windows graphics, and large-model Q&A memory/latency remain unverified.
Temporary owned browser/API/frontend servers were stopped after verification.

## Linux merge verification, 14 November 2026

Merged upstream `ba72858` (raster preprocessing and candidate API diagnostics)
with local `94c2776` (IFC native-abort recovery). The shared README and verification
records retain both sets of changes. IFC runtime code, recovery assets and viewer
dependencies are unchanged by this merge.

Checked on Linux with Python 3.14.10, IfcOpenShell 0.9.0.post1 and Node 26.13.1:

- Full Python suite: 221 tests passed, no skips, in 21.424 seconds. API inference
  was mocked; local HTTP server tests ran with loopback socket access.
- All 13 frontend test files passed, including IFC geometry recovery and candidate
  API diagnostics. TypeScript and the Vite production build passed, retaining the
  existing optional Three/WebGPU export and chunk-size warnings.
- The server-rendering smoke check passed for the initial import screen. IFC
  browser graphics were not rerun for this merge.
- All nine JSON Schemas are current. Regenerating the five frontend wire types
  produced no changes. Python dependency consistency, local Markdown links and
  staged whitespace checks passed.

## Candidate API preprocessing integration, 14 November 2026

Integrated the preprocessing work after fast-forwarding to fetched main
`6629086` (candidate UI/API and local IFC viewer). All overlapping contracts,
generators, dependency settings and docs were reconciled; no integration commit
was created during this pass.

- Full Python suite: 220 tests ran, 218 passed and two Windows symlink-permission
  fixtures skipped. This includes the existing API/lifecycle checks and 14 new
  preprocessing integration regressions. One further cached-overview corruption
  regression was added afterward and passed independently (15 integration cases
  now exist). Source normalization, whole-page overview behavior, original-frame
  coordinates/hashes, cache hits/eviction, request-local image safety, cancellation,
  deadline handling and session cleanup were checked with mocked inference.
- All 40 frontend logic tests and the TypeScript/Vite production build passed.
  The fetched IFC dependencies emitted missing optional Three/WebGPU export
  warnings and a large-chunk warning. Build success does not verify IFC browser
  graphics; this backend integration did not change IFC rendering code.
- The initial locked frontend install hit an esbuild binary held by an existing
  developer process. An incremental scripts-disabled install completed without
  terminating it; npm reported retained locked cleanup directories.
- All nine exported JSON Schemas are current; five frontend wire types were
  generated. Local Markdown checks, `pip check`, and `git diff --check` passed.
  The API extras were installed in the existing Windows environment.

Default `original` mode prepares a bounded session cache but preserves the
canonical model image. Opt-in `overview` mode sends the full-source overview,
including every panel/footer, and maps boxes to unchanged display pixels. The
cache is deleted at backend shutdown; preparation metrics and inference-image
provenance are exposed without internal paths. OCR stays off in this path.

No live provider calls, token-cost comparison, end-to-end browser check, or Linux
execution was performed in this integration pass. The reviewed 50-image gallery
and its loopback server were left intact.

## Raster preprocessing follow-up, 14 November 2026

The standalone [raster preprocessor](DRAWING_PREPROCESSOR.md) was added after the
original hardening pass below. On the existing Windows environment:

- `python -m unittest discover -s tests`: 161 tests ran, 160 passed, one skipped.
  The skip is a new symlink-escape regression because Windows denied test symlink
  creation (WinError 1314). New executable checks cover source snapshots,
  pixel/crop/overview mapping, cache corruption/reuse, EXIF stored-pixel handling,
  source-frame OCR parsing/failure states, tool dispatch, artifact contracts,
  language-data cache invalidation, and human-review sampling/gallery controls.
- `python -m contracts.export --check`: all seven exported schemas current.
  PreparedDrawing TypeScript was generated from the new schema.
- `npm.cmd run build`: TypeScript and production build passed. As before,
  Vite/esbuild required normal filesystem access after an ancestor-directory
  sandbox denial. Frontend runtime integration was not added or browser-tested.
- Local Markdown checks and `python -m pip check` passed. The editable package
  reinstalled successfully and its console entry point worked from another
  directory. A separate fresh environment containing only the standalone
  Pydantic/Pillow/NumPy requirements ran all 55 preprocessing/contract/review tests
  (54 passed, the same one skipped); IFC and the inference SDK were absent.
  Linux was not rerun in this pass.
- Prepared five real images from Swiss, CubiCasa (two), HABS, and Finna. Reused
  their cached artifacts and checked that whole-overview inspection mapped back
  to the selected source bounds. Observed cold times were approximately
  0.07-1.24 seconds and cached times 0.04-0.10 seconds in this single sample pass;
  these are not a throughput or corpus accuracy benchmark.
- Inspected the Swiss debug layout and footer crop visually: the main drawing
  and separate legend/scale/title region remain available. Original dimensions
  were 1753 x 2480; the drawing crop was 527 x 1534. Uncertain sample layouts
  conservatively retained the full source.

Raw sample artifacts/report are local under `build/prepared/` and
`build/preprocess_validation.json`, excluded from Git. No inference APIs were
called and no token/cost saving was measured. The initial real unavailable-engine
state was checked, then optional Tesseract 5.5.3.20260724 was installed locally
using the hash-verified portable setup script, with six official fast language
models. Live recognition returned 140 words from the Swiss sample, including
literal room `5.10` and both printed `1:200` labels, in about 1.18 seconds. The
symbol-heavy CubiCasa sample returned 19 mostly irrelevant tokens in about
1.09 seconds. These observations support evaluating OCR selectively; they are
not an OCR-accuracy benchmark. Raw summaries are in `build/ocr_live_check.json`.

The seed-20261114 gallery at `build/preprocess-review-50/index.html` prepared all
50 sampled images successfully, with OCR off: eight Wikimedia cases and seven
each from Swiss, CubiCasa, HABS, Europeana, IFC raster plans, and Finna. It includes
original overviews, candidate crops, warnings, source hashes, copied attribution,
and editable human labels/notes with JSON export. Human visual validation is
pending; successful preparation does not establish a correct crop or scope.

## Review delivery follow-up, 14 November 2026

The first file-based review failed in Firefox: staged PNGs retained restrictive
Windows temporary-file ACLs although the index HTML was readable. The gallery is
now served using the scoped `drawing_preprocessor serve` loopback command. The
existing 50-case sample JSON/review identity were preserved during HTML rerender.
All 144 image URLs in that gallery returned HTTP 200 with image content types
and decoded successfully with Pillow. The 22 targeted server/review tests ran:
21 passed, one symlink-permission fixture skipped. Local Markdown checks passed.
Import/export preserves ratings when changing browser origin; missing image
loads now produce a visible error. Firefox UI verification was attempted but
stopped by the computer-use tool's unsupported-browser URL-policy enforcement,
so no successful automated browser visual check is claimed.

## Original documentation hardening pass

Checked 14 November 2026 on Windows, using the existing virtual environment and
frontend dependencies. This records checks performed during the documentation
hardening pass. It does not establish complete hackathon question coverage.

## Environment and commands

Python 3.14.10, IfcOpenShell 0.9.0.post1, Pydantic 2.14.3; Node 24.22.3 and npm
11.19.1. In the table, `python` means `.\.venv\Scripts\python.exe` on Windows or
`.venv/bin/python` on Linux. Commands run from the repository root except the
explicitly marked frontend smoke check. Linux was not rerun in this pass.

| Check | Observed result |
|---|---|
| `python -m unittest discover -s tests -v` | 106 passed, no skips: contracts, IFC, Nemotron mocked HTTP, cost reporting, and 15 documentation-checker regressions. |
| `python -m pip check` | No broken installed requirements. This is not a fresh-install test or dependency lock. |
| `npm.cmd run test:frontend` | 11 logic tests passed. |
| `npm.cmd run build` | TypeScript check and Vite production build passed. |
| `node scripts/smoke-render.mjs` from `frontend/` | Server-rendered initial workspace: eight marks, eight evidence rows, unique SVG IDs. No browser launched. |
| Demo fixture export followed by Pydantic validation | All 28 exported `QueryResult` envelopes passed. No bundle/plan semantic validation is claimed. |
| `python -m contracts.export --check` | All six generated JSON Schemas current. |
| `python scripts/classify_questions.py --report-date 2026-11-14 --check` | Report reproduced: 127,044 rows, 6,789 literal texts, 234 analysis families, no unclassified rows. |
| Preview audit with its default input, writing under `build/docs-audit/` | 910 assets, 7,990 QA rows, no missing/null answers; also passed from a different working directory. |
| `python scripts/check_docs.py` | All maintained Markdown local links/images and supported anchors passed. |
| `git diff --check` | Passed. |

The audit helper now resolves its default preview relative to the script, rather
than an obsolete nested path relative to the caller. The drawing inputs and
tracked audit reports were left unchanged. Create an output directory before
using its `--output` option.

The real-model test read
`dataset/junction-dataset-preview/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc`
and checked 211 model-wide doors and 42 on `4.korrus`. Without that optional file,
this test skips; another extraction layout is not searched automatically. Other
IFC quantities/counts in the [engine guide](IFC_ENGINE.md) remain separately dated
selected observations, not a corpus-wide accuracy score.

The build and server-rendering check initially hit the execution sandbox's
restriction on Vite/esbuild reading ancestor directories. Both passed when rerun
with normal filesystem access. No Vite configuration or execution policy was
changed to work around that environment restriction.

To repeat the demo-envelope check with the configured Python/Node environment:

```sh
python -c "import json, subprocess; from contracts.models import QueryResult; rows = json.loads(subprocess.check_output(['node', '--experimental-strip-types', 'frontend/scripts/export-demo-fixtures.ts'], encoding='utf-8')); [QueryResult.model_validate(row) for row in rows]; print(len(rows), 'envelopes validated')"
```

## Documentation check boundaries

The [offline checker](../scripts/check_docs.py) inventories tracked/non-ignored
Markdown using Git, including nested checked-in experiment reports. Without Git,
it scans maintained documentation directories. It checks inline/reference links,
images, filename case, Markdown headings, explicit HTML anchors, and `#Lx` or
`#Lx-Ly` source-line bounds. Code examples/comments are ignored. Its regressions
cover the previously missed image/report links, code fences, slug collisions,
encoded filenames, and optional-data handling.

Only links into the two named optional dataset roots can be skipped, and only
when that root is absent. If a root is installed, missing files inside it fail.
Distributed archive documentation is excluded from the project-doc inventory.
External URL availability, arbitrary non-Markdown fragment IDs, and every possible
Markdown extension are outside this automated check. Selected publisher pages
cited by the research guides were opened separately; archive downloads and
inference endpoints were not exercised by this pass.

## Frontend visual refresh on Linux

Checked 14 November 2026 with Node 26.13.1, npm 12.2.2, and the installed Firefox
160.0 in headless mode. This is a separate frontend pass; Python/backend tests
were not rerun. The interface now has a dominant drawing viewport, a native
searchable drawing dialog, a fixed question composer, contextual source close-ups,
and a locally bundled Cantarell font with its license.

| Check | Observed result |
|---|---|
| `npm run test:frontend` | Both existing frontend test files passed. |
| `npm run build` | TypeScript check and Vite production build passed. |
| Frontend server-rendering smoke check | Initial workspace rendered eight marks and eight evidence rows with unique SVG IDs. |
| Desktop Firefox, 1440 × 960 CSS pixels | Drawing search/selection, exact D03 schedule lookup, source close-up, language switching, missing-information response, window/area questions, rotated focus, mark toggles, keyboard evidence/calculation tabs, and panel collapse/reopen passed. |
| Narrow Firefox, 500 × 844 CSS pixels | Drawing remains visible above the answer panel; no horizontal overflow; picker empty-search/close/Escape and a local SVG upload preview passed. Uploaded preview correctly disabled questions and carried no evidence marks. |
| Responsive screenshots | Desktop, selected schedule-cell close-up, drawing picker, and a 390 × 844 mobile layout were inspected. Normal Firefox automation windows clamped to 500 pixels wide; the narrower screenshot used Firefox's screenshot command. |
| Browser error listener | No application `error` events during the exercised interaction sequence. |
| `python scripts/check_docs.py` and `git diff --check` | Passed. |

The browser checks used a temporary local Firefox automation harness and a local
Vite server. No new JavaScript dependency, model request, or backend connection
was introduced. The temporary servers were stopped after checks. This does not
establish real drawing analysis, touch-device behavior, or the roadmap's human
evidence-verification gate.

## Image candidate API on Linux

Checked 14 November 2026 on Linux with Python 3.12.3, FastAPI 0.162.7,
Starlette 1.10.0, Uvicorn 0.54.0, Pillow 12.3.0, Pydantic 2.14.3,
OpenAI SDK 2.54.0, httpx 0.28.1, and python-multipart 0.0.33. Node 24.22.3
was used for frontend checks. The new [image API](../image_api/README.md)
adds candidate extraction, not a final-answer planner or a wired React UI.

| Check | Observed result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -v` | 138 tests passed, no skips, including the existing real IFC fixture. Provider responses in this suite are mocked. |
| New API-specific checks within that suite | 18 HTTP/model integration tests, 5 concurrency/lifecycle tests, and 9 candidate contract tests passed. |
| `.venv/bin/python -m pip check` | No broken installed requirements. |
| JSON Schema generation and `--check` | All eight generated schemas current; existing six schema files unchanged. |
| `npm --prefix frontend run generate:contracts` | New candidate/error TypeScript types generated; existing request/result types unchanged. |
| `npm run build` | TypeScript/Vite production build passed. React components unchanged. |
| `npm run test:frontend` | Both existing frontend test files passed. |
| Real Uvicorn startup over localhost | `/health`, `/docs`, and `/openapi.json` returned 200; multipart candidate route documented. No inference calls made by this startup check. |
| Synthetic example envelopes | Success, empty, partial, and error examples passed Pydantic validation. |

Async checks initially stalled inside the execution sandbox, including a minimal
independent framework/client example. The passing async suite and local TCP
startup check ran outside that sandbox; no application logic was weakened to
work around the restriction. A final change to the configurable question limit
and OpenAPI metadata was followed by focused question-limit/docs checks.

After explicit user approval, one live request used the already-saved pilot
floorplan `experiments/runs/door-labeling/20261113T234605960384Z/input.png` and
the question "Locate the doorways fitted with doors in this floorplan."
The real Uvicorn endpoint returned HTTP 200 and `status: ok`, with five candidate
records in the 2730 by 2048 display frame. The returned model was
`nemotron-3.5-super-vl`; inference-stage elapsed time was 7,731 ms, with 4,411
prompt tokens and 462 completion tokens. No final door count was generated.
The response passed the public contract's box/bounds checks and retained
`inventory_completeness: unverified`. This establishes live wiring on one image;
no manual localization/recall audit or general accuracy claim is made.

The live request initially required explicit payload/destination approval from
automatic review; it ran only after the user's approval. Both temporary Uvicorn
servers were stopped. No API images, credentials, prompts, or raw live responses
were added to the repository. Frontend browser integration was not exercised.

## Local import library on Linux

Checked 14 November 2026 with Node 24.22.3, npm 11.19.1, and the installed Firefox
160.0 in headless mode. This pass changes only the frontend and its documentation;
no backend, model, or real-dataset accuracy checks were run.

| Check | Observed result |
|---|---|
| `npm run test:frontend` | All three test files passed, including seven new import tests. A separate run with `--test-isolation=none` reported all 18 individual tests passing. |
| `npm run build` | TypeScript checks and Vite production build passed. |
| `node scripts/smoke-render.mjs` from `frontend/` | Initial workspace retained eight demo marks, eight evidence rows, and unique SVG IDs. |
| Firefox local file input | Trusted pointer clicks on both header and modal Import buttons opened a native multiple-file chooser. A single selection imported PNG, JPEG, SVG, and PDF with retained thumbnails and original filenames. Separate WebP/GIF/BMP imports also passed. |
| PDF preview and navigation | A generated two-page PDF rendered a 14,400 × 14,400 point first sheet into a bounded 2,829 × 2,829 pixel preview; the portrait second page rendered correctly. Previous preview URLs were released. |
| Mixed valid/invalid batch | Valid files remained imported alongside individual errors for a corrupt image, corrupt PDF, unsupported text, IFC, empty PDF, and a file larger than 35 MB. |
| Preview library | Filename search, selecting retained previews, zoom/rotation/fit controls, removing the selected import, and returning to demos passed. |
| Drag/drop and language | Dispatched browser drag/drop events imported an SVG with a blank MIME type. Finnish import labels left the original filename unchanged. Physical operating-system drag gestures were not automated. |
| Pending source changes | Selecting a demo during a delayed PDF import preserved that selection while retaining the new file. Selecting a demo during page rendering cancelled the stale preview. Removing a file before the rest of its batch finished preserved the current demo and answer. |
| SVG export | The export Blob for a PDF page embedded a PNG data URL with no temporary Blob URL references. The browser's native save-to-disk dialog was not exercised. |
| Desktop and narrow layout | Screenshots inspected at 1,440 × 960 and 390 × 844 CSS pixels. The narrow viewport and drawing picker fit without horizontal overflow. |
| Resource cleanup and refresh | Removing every imported file left no tracked preview URLs unreleased and no uncaught application errors. Refresh returned to the four demo sources. |
| `python3 scripts/check_docs.py` and `git diff --check` | Passed. |

The browser used generated local fixtures and a temporary Firefox WebDriver BiDi
harness, without adding a JavaScript dependency. Vite's temporary local listeners
and the browser required normal local network permissions in this sandbox. The
owned browser and preview server were stopped after verification. Imports are
tab-local previews, not persistent storage or an analysis/ingestion service.

## Import opening flow on Linux

Checked 14 November 2026 with Node 24.22.3, npm 11.19.1, and headless Firefox.
At this pass the application started without synthetic drawings or prepared
answers; those sources remained offline fixtures. The chat panel opened after a
successful local import, with question answering unavailable at that stage.

| Check | Observed result |
|---|---|
| `npm run test:frontend` | All three existing test files passed. |
| `npm run build` | TypeScript checks and Vite production build passed. |
| `node scripts/smoke-render.mjs` from `frontend/` | Initial file import controls rendered without a drawing, demo content, or chat panel. The smoke check no longer starts a WebSocket listener. |
| Firefox opening flow | Initial and refreshed pages showed only import controls. Corrupt/unsupported files stayed on that screen with individual errors. A delayed PDF import showed loading before revealing the preview and right-side chat. |
| Chat and library | Importing a new file reopened a hidden chat panel. The picker contained only imports; mixed valid/invalid batches retained successful files and listed failures. The disabled composer explained the analysis limitation. |
| Preview and lifecycle | PDF page navigation, zoom/rotation/fit, image-data SVG export, final-file removal, and preview URL cleanup passed. Removing the sole selected file during another import returned to the opening screen, then opened the completed file. Source changes during import and PDF rendering preserved the selected source. |
| Responsive and drag/drop | Screenshots inspected at 1,440 × 960 and 390 × 844 CSS pixels. The import screen and preview/chat layout fit without horizontal overflow. Dispatched drag/drop events opened the first file and subsequent imports. Finnish labels preserved original filenames. |
| `python3 scripts/check_docs.py` and `git diff --check` | Passed. |

The temporary Firefox WebDriver BiDi harness used generated local images and a
two-page PDF, browser file-input selection, and dispatched drag/drop events.
Native operating-system file selection and physical drag gestures were not
automated in this pass. No uncaught application errors were observed. These
checks establish selected UI behavior, not uploaded-file analysis or dataset
answer accuracy.

## Imported-drawing candidate UI integration

Checked 14 November 2026 on Linux with Node 24.22.3 and the installed Firefox
142.0 in headless mode. This combines the latest `main` importer with the image
candidate API branch. No new live Nemotron requests were made in this pass;
browser checks used synthetic images and a local mocked API that echoed the
actual uploaded PNG hash/dimensions and returned two candidate records.

| Check | Observed result |
| --- | --- |
| Frontend tests | All five test files passed; a run with `--test-isolation=none` before the file arguments reported 31 individual tests passing. |
| `npm run build` | TypeScript/Vite production build passed, including the PDF.js compatibility build. |
| JSON Schemas and demo envelopes | All eight schemas current; all 28 existing demo answer envelopes still pass `QueryResult` validation. |
| Initial workspace server rendering | Eight demo marks/evidence rows retained. Rerun outside the sandbox removed its Vite HMR-listener permission warning. |
| Browser PNG analysis | File import enabled the question composer; the real browser request traversed Vite's `/api` proxy to the mocked service. Returned hash/dimensions matched the prepared snapshot, and two candidate marks/list rows appeared. |
| Box placement and uncertainty | Landscape first box mapped exactly to `[235,138,84,31.5]` in the existing fitted viewport; the uncertain candidate had an amber dashed box and its reason in the list. No exhaustive-inventory claim or final object count was shown. |
| Selection and view controls | Real pointer pan, zoom, rotation, marking toggles, row/overlay selection, image close-up, and focus worked on the imported snapshot. |
| Exports | Captured marked SVG contained embedded PNG and candidate rectangles/colors; JSON retained the candidate response. No native save-dialog automation is claimed. |
| Errors and result statuses | Mocked 503 displayed an error and allowed retry; empty and partial candidate responses retained their distinct meanings. |
| SVG and stale requests | Imported SVG was rasterized and annotated; changing source during a delayed candidate request aborted/discarded the stale result. |
| PDF pages and cancellation | A two-page synthetic PDF submitted the current landscape page at 1200 by 800 pixels and portrait page at 800 by 1200. Moving pages during a delayed request cleared/aborted the old result; the new page's boxes appeared in its own frame. |
| Narrow layout | At 390 by 844 CSS pixels, the page had no horizontal overflow; source, two boxes, candidate rows and uncertainty remained readable in the stacked layout. |

The standard PDF.js build initially failed in Firefox 142 because it invokes
`Map.getOrInsertComputed`, absent in that browser. The importer now loads the
bundled compatibility main and matching compatibility worker, which supply the
needed platform polyfills. Vite prebundles the lazy compatibility reader so its
first load does not trigger a dependency-optimization reload that loses imported
tab state. Existing file library behavior and tests are retained.

The browser harness and fixtures are temporary diagnostics, not bundled dataset
assets or model accuracy evidence. The API's earlier approved live smoke request
is recorded separately above. No inference credentials were used in browser
code, and no extra dependency was added for browser automation.

## IFC viewer implementation — Linux, 14 November 2026

The [browser IFC viewer](IFC_VIEWER.md) was checked separately from the earlier
backend and 2D passes. Environment: Node 26.13.1, npm 12.2.2, TypeScript 5.9,
Vite 7.3.8, Firefox 160 headless with software WebGL on Linux. An isolated
Python 3.14 / IfcOpenShell 0.9.0.post1 environment supplied source comparisons;
no backend application code or shared contracts were changed.

| Check | Observed result |
|---|---|
| `npm run test:frontend` | Five test files passed, including existing demo/viewport/image tests and nine new source-routing/cache/property-reader cases. New cases also passed when run directly with Node. |
| `npm run build` | TypeScript and Vite production build passed. The SDK emits optional WebGPU export warnings for the WebGL build, plus a large-chunk warning; the resulting WebGL viewer was tested in production. |
| `node scripts/smoke-render.mjs` from `frontend/` | Initial 2D workspace still renders eight marks/evidence rows with unique SVG IDs. |
| `npm --prefix frontend run prepare:ifc-demo` | Generated the checked-in KIT derivative and manifest from the original 2,570,803-byte FZK-Haus IFC. |
| Initial 2D resource inspection | No IFC viewer, Three.js, or WASM resource requested before selecting 3D. |
| Real FZK-Haus demo | Visible geometry, picking, original door name/STEP ID/GUID, two storeys, orthographic projection, horizontal clipping/reset, metadata-only project inspection, and panel collapse/reopen checked. |
| Three repeated 2D/3D switches | One active 3D canvas; worker instrumentation showed no retained IFC workers after returning to 2D. |
| Mixed SVG / invalid text / local IFC batch | Successful entries retained, invalid file reported separately, local IFC converted in its worker, and source switching preserved the library. A modified whitespace-only copy was used to avoid reusing the demo's cached hash. Original dataset files were not changed. |
| Real IFC2X3 | Esplanades loaded; STEP `#8911`, class `IFCBEAM`, name `ARTALA - 001`, and native GUID matched IfcOpenShell. |
| Real IFC4 MEP | DigitalHub heating loaded; STEP `#167979`, class `IFCSENSOR`, original German name, and GUID matched IfcOpenShell. |
| Real IFC4.3 | City House Munich loaded; STEP `#150564`, class `IFCBUILDINGELEMENTPROXY`, original name, and GUID matched IfcOpenShell. |
| Source scalar comparisons | FZK-Haus door `#17468` dimensions and storeys `#479` / `#35065` names/elevations matched IfcOpenShell; storey elevation `2.7` remained the source value. |
| PDF regression | Two-page PDF retained page 2 across model switches. Exported SVG embedded the displayed PNG data URL and contained no temporary blob URL. |
| Invalid IFC | Corrupt-file error remained in the library; retry and removal worked. |
| Production nested base | Built and served under `/viewer-check/`; prepared demo, local IFC conversion, selection, conversion cancel/retry, and self-hosted workers/WASM worked. |
| Missing runtime assets | Temporarily renamed generated production worker/WASM assets. Viewer reported errors, retained source navigation, and recovered after restoration/retry. Tracked source assets were not changed. |
| Missing WebGL | Simulated unavailable WebGL produced the graphics error; 2D source selection and its eight demo marks remained functional. Restoring graphics allowed reopening and inspecting the demo. |
| Responsive layout | Desktop and 500-pixel-wide screenshots inspected. The final model stage and inspector do not overlap; no horizontal document overflow. |

Successful interaction runs recorded no uncaught page errors or unhandled
rejections. These are selected-model viewing and source-identity checks, not
complete geometry/property coverage, QA accuracy, a 100 MiB memory guarantee,
or verification on physical mobile/Windows devices. Backend answer integration,
canonical-ID bridging, persistent storage, and large-model server conversion
remain outside this implementation.

## Import opening flow merged with the IFC viewer

Checked 14 November 2026 on Linux with Node 24.22.3 and headless Firefox against
the production build. The local import-first changes were combined with upstream
`bb1a17c` (IFC viewer). The application library still contains imports only; the
prepared FZK-Haus artifact and synthetic QA sources remain fixtures.

| Check | Observed result |
|---|---|
| `npm run setup:frontend` | Locked dependencies installed with dependency scripts disabled. |
| `npm run test:frontend` | All five test files passed. |
| `npm run build` | TypeScript and Vite build passed; the existing SDK optional-WebGPU export and large-chunk warnings remain. |
| `node scripts/smoke-render.mjs` from `frontend/` | First open renders import controls without a drawing or chat panel. |
| Production image/PDF browser regression | Desktop/narrow import screens, invalid files, delayed PDF loading, chat reopening, import-only library, mixed batches, PDF pages, viewport controls, Finnish labels, drop events, final removal, URL cleanup, stale-selection guards, refresh, and embedded-image SVG export passed. |
| Production synthetic IFC4 browser regression | Import from the opening screen converted a generated wall model locally, rendered one 3D canvas, exposed its original STEP ID/name and storey, and retained the canvas while collapsing/reopening the inspector. |
| IFC/PDF lifecycle | Switching restored PDF page 2, removed the inactive renderer, retained both imported entries, and returned to the opening screen after final removal. Invalid IFC errors stayed inspectable in the library and removal recovered. No uncaught page errors or unhandled rejections were recorded. |
| `python3 scripts/check_docs.py`, `git diff --check`, and Git conflict inventory | Passed; no unresolved merge entries remain. |

The temporary browser harnesses used generated images, a two-page PDF, and a
synthetic IFC4 wall. Desktop PDF/chat and IFC/inspector screenshots were inspected.
These checks cover the combined UI and local conversion path, not real-model
corpus compatibility, backend integration, or dataset QA accuracy. The earlier
real IFC checks above were not repeated. Backend code and contracts were unchanged;
the Python backend suite was not rerun. Owned temporary browser/server processes
were stopped after verification.

## Combined IFC viewer and candidate UI merge

The sections above record the independent implementation and verification passes.
That earlier merge preserved the latest `main` IFC viewer alongside imported
image/PDF candidate analysis and prepared synthetic demo answers; the later
import-first merge below removes those demos from the application. Checked on Linux
with Node 24.22.3 and headless Firefox 142.0 after integrating the incoming
`bb1a17c` IFC viewer commit:

| Check | Observed result |
| --- | --- |
| Locked frontend install | `npm run setup:frontend` completed with dependency scripts disabled; incoming IFC versions/lockfile retained. |
| Frontend regressions | All seven files passed; direct Node execution with `--test-isolation=none` reported 40 individual tests passing. |
| Production build | TypeScript/Vite build passed with prepared self-hosted IFC assets. The incoming SDK's optional WebGPU export and large-chunk warnings remain; the WebGL path was exercised in the browser. |
| Schemas, docs, and initial render | All eight schemas current; Markdown links/anchors and whitespace checks passed. Initial demo retained eight matched marks/evidence rows. |
| Image candidates | A synthetic PNG submitted through the browser/proxy/mock API produced correctly aligned boxes. This retains the detailed image/SVG/error/export checks from the preceding candidate UI pass. |
| Switching to IFC mid-request | A delayed PNG request was cancelled/discarded; its SVG/candidate state disappeared when selecting the IFC demo. IFC loaded cold before PDF.js's compatibility polyfills. |
| IFC view and source inspection | Real FZK-Haus WebGL geometry/storeys appeared. STEP `#17468` selected `IFCDOOR`, original name `Innentuer-1`, GUID `1Oms875aH3Wq$l65H2ZGw`, and source dimensions height `2.01`, width `0.885`. |
| Returning to 2D | The IFC canvas/inspector were disposed; a fresh PNG analysis produced candidates without stale IFC or earlier-candidate content. |
| PDF pages | Landscape/portrait pages submitted 1200 by 800 and 800 by 1200 pixel snapshots. Page navigation cancelled the delayed old-page result and rendered new-page candidates. |

No browser JavaScript errors were recorded. These checks used synthetic drawing
fixtures and a local mock API, plus the bundled real IFC demo. No new external
inference request was made; the earlier API live check is recorded separately.
All owned test browsers, Vite listeners, and mock API servers were stopped.

## Import-first UI with candidate analysis

Checked 14 November 2026 on Linux with Node 24.22.3, npm 11.19.1,
Python 3.12.3, and headless Firefox 160.0. This merge combines local `c254c8b`
(UI cleanup) with upstream `6286ae8` (IFC viewer and Nemotron candidates).
The opening screen and library contain imports only; synthetic sources and
prepared answers remain offline fixtures.

| Check | Observed result |
| --- | --- |
| Frontend regressions | `npm run test:frontend` passed all seven files; direct execution with `--test-isolation=none` passed all 40 individual checks. |
| Python regressions | `python -m unittest discover -s tests -q` passed all 138 tests with no skips, including API/lifecycle, contracts, IFC, mocked Nemotron, and documentation tests. `pip check` found no broken requirements. |
| Production build and initial render | TypeScript/Vite build and server-rendering smoke check passed. First open has import controls with no drawing/chat/demo. Existing optional-WebGPU export and large-chunk warnings remain. |
| Generated contracts and offline fixtures | All eight JSON Schemas current; frontend types regenerated without drift; all 28 offline demo envelopes still pass `QueryResult` validation. |
| Import and candidate UI | Generated PNG/SVG/PDF inputs used the production preview's `/api` proxy and a local mock endpoint. Importing made no analysis call; submitting enabled image-bound candidate overlays/list rows with matching uploaded hashes/dimensions, literal `121.A`/`7.16` labels, uncertainty, selection, close-ups, focus, rotation, and layer toggles. |
| Statuses, errors, and exports | Empty, partial, unreadable, and unsupported results stayed distinct. Mocked service errors allowed retry; mismatched hashes were rejected. Captured SVG embedded the analysed PNG and candidate rectangles; JSON preserved the response. Native save dialogs were not automated. |
| Request and source lifecycle | Explicit cancellation, PDF page changes, source changes to IFC, and final-file removal aborted/discarded delayed results. Reopening hidden chat, PDF page restoration, the import-only library, and preview/snapshot URL cleanup passed. |
| IFC inspection | A generated IFC4 wall loaded locally with one 3D canvas; STEP `#19` retained its original `Merge wall 121.A` name. Collapsing/reopening the inspector preserved the canvas. Returning to PDF disposed the model renderer and restored page 2. |
| Layout and browser errors | Desktop PDF/candidate and 390 by 844 CSS-pixel layouts were inspected; no horizontal overflow or uncaught application errors were observed. Finnish labels preserved original filenames/source labels. |
| Documentation and merge hygiene | Local Markdown links/anchors, whitespace checks, and conflict-marker inventory passed. |

The restricted-sandbox Python run stalled in asynchronous API tests and was
interrupted. The same suite completed in about six seconds with normal local
permissions; no application workaround was introduced. API dependencies were
installed in the existing Linux virtual environment using the declared `api,test`
extras; frontend dependencies and the lockfile were retained.

Browser requests used synthetic fixtures and a local mock endpoint; Python HTTP
tests used mocked provider responses. No new external inference request or
dataset-wide accuracy/cost benchmark was made. All owned temporary preview,
browser, and mock API processes were stopped after verification.

## Remaining verification gaps

- Real-device touch/virtual-keyboard behavior, Windows browser behavior, and
  native file-save interactions still need checks on the demo devices. The Linux
  browser checks above cover selected demo interactions and local import previews,
  including PDF page navigation and the generated SVG export Blob.
- Synthetic sources and prepared results remain offline fixtures. Imported
  image/page candidate detection is connected, but a final-answer planner and a
  question-to-IFC-to-viewer flow remain unimplemented. General raster
  inventory/reconstruction is outside that service.
- Dataset-wide answer accuracy, evidence localization, multilingual robustness,
  latency distributions, and inference cost have not been benchmarked here.
- No billing verification or dataset-wide performance benchmark was performed.
  The [Nemotron guide](nvidia_info.md) and saved
  [door-labeling experiment](../experiments/door_labeling/RESULTS.md) retain their
  separately dated observations and limits.

## IFC viewer bug and performance pass — 14 November 2026

Checked on Linux with Node 26.13.1, npm 12.2.2, Vite 7.3.8 and Firefox 160
headless/software WebGL. The current application opens on imports; the old demo
picker used in the earlier record is no longer part of the visible application.

| Check | Observed result |
|---|---|
| `npm run test:frontend` | All 11 frontend test files passed, including image-candidate/2D checks and IFC routing/cache, worker protocol, STEP validation, bounded properties, rendering policy and update scheduling. |
| New/extended IFC tests | 30 focused cases passed directly with Node: cancellation/stale messages, cache ownership/invalidation, source validation, clipping, coplanar material bias, transparent depth writes, pixel budget, ordered/coalesced updates, and large property graphs. |
| `npm run build` | TypeScript and production bundling passed; existing optional WebGPU export and large SDK chunk warnings remain. |
| Production and fallback | Production worker loading, cached reopening, zero idle draws, projection/sections and graphics recovery passed. Disabling `EXT_clip_control` also rendered and selected correctly with ordinary depth and positive base-material offsets; no page errors. |
| `node scripts/smoke-render.mjs` from `frontend/` | Current import screen rendered without loading the IFC viewer or showing the old demo/chat panel. |
| Source reading/hash instrumentation | Opening the real FZK-Haus model invoked neither `File.arrayBuffer()` nor SHA-256 on the main thread. Reopening its retained library entry after switching to SVG created no conversion worker. |
| Idle GPU instrumentation | After settling, the visible model produced **0 WebGL draw calls over 2 seconds**. Camera/projection, selection, sections, and source changes still redraw. |
| Depth/material handling | Real model rendering used distinct stable polygon offsets, transparent surfaces did not write depth, and selecting the original door retained its native name/GUID. Perspective/orthographic switching and section/reset passed. |
| Large ventilation model | `sixty5_ventilation.ifc`, **109.6 MiB**, opened in **35.1 s**, including worker source reading/hashing/conversion and initial display. |
| Largest supplied model | `sixty5_arc.ifc`, **326.8 MiB**, opened in **68.5 s** and rendered. Both large-model runs recorded no uncaught page errors; their source files remained unchanged. |
| Hierarchy paging | DigitalHub heating category exposed `Show next 57 items (100 / 157)`; opening the next page added exactly 57 DOM rows. |
| Visibility ordering | Rapid storey changes followed by All storeys settled to the final selection without a viewer error. |
| Removing during conversion | Removing an active 109.6 MiB conversion returned to the previous model and did not restore the removed model. |
| Lost graphics context | Simulated context loss produced a recoverable error; Retry reopened and displayed the model without unhandled page errors. |
| STEP validation compatibility | Bounded header/footer checks accepted all 611 supplied IFC files; corrupt/truncated fixtures reject before full-file allocation. |

The IFC input cap is now **512 MiB**, separate from the unchanged 35 MiB 2D cap.
The timings are selected local observations on software WebGL, not a speed promise
or a baseline comparison. No 512 MiB model or physical mobile/Windows device was
validated. The worker still holds the full source; hashing may copy it, and native
geometry/WASM/GPU allocations need additional RAM. Raster bias improves depth
precision and coplanar presentation without repairing contradictory source solids.

## Dental-clinic native abort recovery — 14 November 2026

Reproduced the reported `Aborted(native code called abort())` with the original
`dataset/junction-dataset/data/ifc_bench/dental_clinic_mep.ifc` (125,780,663 bytes,
IFC2X3) on the existing pinned web-ifc 0.0.77. This was not a size-cap or initial
parse failure: metadata opened in about 3 seconds, then native mesh extraction
failed at flexible-duct STEP `#9226`, GUID `0B8zmgmwv0dg357dK6blEx`.
Its face `#613515` reaches polygon loop `#1641100`, which references point IDs
`#76504` / `#78337` absent from the source. An isolated temporary 0.0.79 check
also failed; the application's parser version was not changed.

| Check | Observed result |
|---|---|
| Native topology recovery | Omitted 40,382 unique invalid faces from 1,505 connected/shell face sets. Diagnostics include 40,380 invalid loops and 7,552 native-unresolvable point IDs; a raw-text audit found 7,551 undefined point IDs, so these counts are not asserted to be identical. |
| Native source preservation | Original source was not modified. Only face-list membership changed in the in-memory derivative; native product/property IDs and scalar values remained intact. The derivative was 122,715,822 bytes. |
| Full conversion | Recovery plus the installed Fragments importer completed in about 39 seconds in Node, producing 12,750,033 fragment bytes. All 16,545 geometry-category items attempted afterward completed native mesh reads; this does not mean every item has complete drawable geometry. |
| Production browser reproduction/fix | Before the fix, the real file failed in 4.61 seconds. Afterward, it opened in 49.5 seconds with exactly one fresh-worker recovery. The persistent partial-geometry banner reported 40,382 omitted faces. |
| Original failing object | STEP `#9226` retained `Flex Duct Round:Flex Duct - Round:1115248`, its original GUID, and drawable geometry with Focus enabled. |
| Disclosure/cache/source changes | Warning remained visible with the inspector collapsed; View omissions opened its details. Switching to SVG and back reused cached fragments without another conversion worker and retained the warning. A healthy FZK-Haus import cleared the warning. |
| Recovery cancellation | Cancelling while the fresh worker checked source geometry terminated both conversion workers, left the cancelled state visible, and produced no late model or page errors. |
| Native-WASM fixtures | Five regression tests cover valid-file pass-through, malformed outer/inner loops and wrong/missing references, whole-face omission, original native IDs/Finnish names/tags/quantities, bounded diagnostics and API disposal. |
| Worker/cache policy | Tests cover one-time native retry, ordinary-error/cancellation bypass, cancelled-source guards, no retry loop, typed native failure, report validation and warning retention through cache ownership/eviction. |
| Frontend build/tests | All 13 frontend test files and the TypeScript/Vite production build passed. Existing SDK optional-WebGPU export and large-chunk warnings remain. The prepared FZK artifact/manifest were regenerated for the new converter policy identity. |
| Browser layout/errors | Desktop and 500-pixel-wide partial-preview layouts inspected; no horizontal overflow. No uncaught page errors or unhandled rejections were observed. |

This recovery does not restore the missing source coordinates or establish full
model geometry. It preserves an inspectable partial preview; a corrected export
is needed for a complete model. No dataset originals, QA answers, backend engines
or wire contracts were changed. Tests used Linux Node 26.13.1 and Firefox 160
headless/software WebGL; physical mobile/Windows behavior was not retested here.

## DXF import, preview and visual questions — 14 November 2026

Checked on Linux with Python 3.12.3, ezdxf 1.4.5, Node 24.22.3, npm 11.19.1,
Vite 7.3.8 and Firefox 160 headless. The requested scope is DXF import, selected
layout preview and the existing visual question flow. Native CAD query execution
and measurements are not part of this change; see [DXF support](DXF_PREVIEW.md).

| Check | Observed result |
|---|---|
| Frontend tests | All 18 test files passed, including DXF import/routing, source hash and layout validation, warnings, backend errors, cancellation and URL release. |
| Production build | TypeScript and Vite build passed. Existing optional WebGPU export and large SDK chunk warnings remain. |
| DXF, body-limit, contract and image API regressions | Synthetic DXF rendering/HTTP tests and existing shared image API, lifecycle and preprocessing tests passed. Rendering checks cover binary and legacy text encoding, literal layout names, blocks, hidden layers, source retention, unsupported content and explicit errors/budgets. |
| Generated contracts/docs | JSON Schema export check and local Markdown link/anchor check passed; frontend types regenerated from the Python source model. |
| Production browser flow | Imported a synthetic DXF through the actual local HTTP renderer; checked nonblank source pixels, named layout switching, URL release, source warnings, PNG question submission, candidate overlays and source/layout metadata in JSON export. Inference used a mocked transport, without contacting a model provider. |
| Partial preview and layout scope | Missing external reference produced a persistent partial-preview notice. Switching to the clean paper layout removed that warning. Switching back cleared the candidate response and restored the source warning. |
| Browser layout | Desktop and 500-pixel-wide views inspected; no horizontal overflow or uncaught JavaScript errors. Original visible text retained `121.A Keittiö`; paper layout retained `Piirustus 7.16`. |
| Lifecycle | Timeout, disconnect and cancellation tests verify request-owned worker termination and temporary source cleanup. Busy-slot and independent upload/body limits are covered. All temporary browser/API/preview servers owned by this verification were stopped. |

The initial restricted-sandbox asynchronous test run stalled during cleanup and
was interrupted. API tests completed with normal local process permissions;
no application workaround was introduced. The DXF package was installed in the
project's existing Linux virtual environment and added to the declared `api` extra.
No supplied DXF assets are installed in this checkout, so these checks use
synthetic drawings. They establish integration behavior, not real-dataset rendering
fidelity, candidate accuracy or inference cost. Windows and physical mobile-device
behavior were not tested in this pass.

# Hackathon roadmap: answers you can inspect

Proposed working direction, 14 November 2026, based on the project owner's
priorities. This is a **plan**, not an implementation or accuracy report. The [project scope](PROJECT_SCOPE.md)
defines acceptance; this roadmap sets the next build order and UI direction.
Earlier stack/viewer research remains useful, with training and additional
infrastructure subject to the decision gates here.

## Aim

An engineer opens a drawing, asks a question, gets a concise answer, and can
inspect every contributing object, source value, or calculation input. The
drawing occupies most of the screen. The product should feel like a good drawing
viewer with an answer beside it.

Optimize for Stoa's four equally weighted criteria: accuracy, verifiability,
creativity, and inference cost. Start with hosted models plus native extraction
and deterministic calculations. The lasting work is source identity, scope,
counting conventions, evidence, and evaluation. Better models should improve
this system without requiring its evidence workflow to be rebuilt.

**Default: no overnight bulk labeling and no fine-tuning.** A model-heavy approach
needs a small reviewed evaluation set and reliable inference. Training labels
become worthwhile only after a measured failure justifies a particular specialist.
Source extraction caches can still be useful without becoming a training dataset.

## Starting point

| Available now | Work still needed |
|---|---|
| [React frontend](../frontend/README.md): source viewer, marks, selection, prepared answers | Minimal layout, real source ingestion, backend connection, real evidence resolution |
| [IFC engine](IFC_ENGINE.md): native extraction and structured scalar queries | Natural-language planning, HTTP integration, operations required by uncovered question families |
| [Nemotron client](nvidia_info.md): text/image/JSON calls to the supplied endpoint | Evaluated question workflows, bounded orchestration, caching and service integration |
| [Shared contracts](SCHEMA.md): source, scope, entities, evidence and results | Real adapters populating them; schema validity alone cannot establish source truth |
| [One-image door pilot](../experiments/door_labeling/RESULTS.md) | Broader count, subtype, completeness and localization evaluation; the pilot had clipped boxes and a wrong subtype despite the right count |

The frontend's uploads currently provide previews only. The parser, client, and
UI are independent. Passing component tests does not establish a working
question-to-answer product; see the [verification record](VERIFICATION.md).

## UI direction

Use one source viewport and one compact answer/evidence panel. Begin with roughly
70% drawing and 30% panel on a laptop; adjust after trying real dense drawings.
Collapse source navigation into a file/page picker. On smaller screens, use an
evidence drawer that leaves the selected source region inspectable.

Illustrative layout, not a screenshot of implemented behavior:

```text
 Files / current sheet / page                    Fit   Marks   More
------------------------------------------------------------------
                                              | Ask about this view
                                              | [question       ]
                                              |-------------------
              ORIGINAL DRAWING                | Answer + unit
                                              | Scope / limitation
       small numbered marks for this answer   |-------------------
                                              | Evidence items
       click one to inspect its context       | 1  original label
                                              | 2  original label
                                              | 3  original label
                                              |-------------------
                                              | Selected item crop
                                              | Source value / rule
```

The essential interaction is **answer -> evidence item -> source context**:

- Clicking an item selects its mark and offers a deliberate zoom to the source.
  Clicking a mark selects the same item. Keep previous/next and fit-to-answer
  controls; do not jump the camera on every hover.
- Show a contextual crop for the selected item, including the label, table
  header, dimension endpoints, or neighboring geometry needed to judge it.
  Allow the user to return to the whole drawing and toggle marks off immediately.
- For counts, show the included logical instances and the counting rule. Keep
  exclusions and ambiguous candidates one click away. A double-leaf door can be
  one opening; multiple depictions can refer to the same object.
- For lookups, highlight the exact cell/text/property with its original label
  and unit. For calculations, expose clickable input terms, holes/subtractions,
  conversions, and rounding. An IFC property can be evidence without a 3D box.
- Keep a material limitation beside the answer: partial inventory, unresolved
  ambiguity, missing property, or missing scale. A zero needs support. Avoid
  confidence percentages that have not been calibrated on this task.
- Show marks relevant to the active answer. An optional "Detected items" view
  can expose cached extraction, clearly indicating which classes were examined;
  it must not imply that everything in the drawing has been found.

Use quiet neutral surfaces, readable text, thin dividers, and one selection
accent. Preserve clear keyboard focus and distinguish uncertainty with text or
line style as well as color. Remove the current duplicate project/header/status
chrome, fictional avatar, decorative cards, and prominent workspace branding.
Put history, export, attribution, and diagnostics in secondary controls; keep
source/revision identity accessible and mock examples explicitly identified.

Keep the existing pan/zoom, selection, cancellation, and coordinate work where
useful. Put model names, tokens, tool calls, and raw JSON in a developer inspector.
The main panel shows observable source evidence and calculations. Any human
correction must be visibly identified and kept separate from the original model
output; a correction editor is optional after the inspection flow works.

**Human UI gate:** try three real questions with someone who did not build the
screen. Can they locate the evidence for a selected claim in about five seconds,
and notice a deliberately wrong mark or scope? This is a design target to test,
not a measured result. If a list hides tiny symbols, try a small crop strip. If
crops lose context, keep the list and use click-to-zoom. Both paths retain the
same source IDs, selection model, and full-drawing view.

## Model and tool roles

| Input/task | First approach | Escalation when justified |
|---|---|---|
| IFC objects, properties, quantities | Existing parser/executor; Nemotron proposes a plan using the actual catalog | Add a missing operation for a supplied family, or return the precise source/implementation gap |
| Native PDF schedules and labels | Extract text with positions and reconstruct rows/cells; model interprets the question | OCR or a visual model for rasterized/ambiguous regions, retaining row/header context |
| Swiss paired DXF/PDF/PNG | Recover supplied geometry and literal room/unit labels; calculate with declared units | Visual interpretation for difficult associations; preserve net/gross and holes |
| Raster symbols and room categories | Nemotron proposes a scoped inventory with locations and visual cues | Higher-resolution crops or Gemini on diagnosed failures; count the resolved logical instances in code |
| Scan text | Native text if present; a pretrained OCR engine when text extraction is needed repeatedly | Visual model reads difficult contextual crops and preserves uncertain transcription |
| Page/task routing | File metadata, selected view, question, and available capabilities | Optional Decisions API experiment if routing mistakes become a real bottleneck |

Nemotron receives the question and source catalog when language interpretation is
needed. It can request tools or regions; it need not inspect every original byte
before a parser runs. Models propose facts/interpretations, adapters validate
structure and bind evidence, and code performs supported calculations. Counting
a list correctly does not prove the list is complete: audit missed and duplicate
objects separately. A final model response must not silently change computed
values, units, identifiers, or scope.

Route by **task and available evidence**, not merely by source folder. A Finna
floor plan can use the raster path; an unrelated portrait should produce a clear
unsupported-content outcome. Assets without QA do not add new required families.

The resource choices are independent:

- Start with `nemotron-3.5-super-vl` at the NVIDIA-contact-provided Verda endpoint
  already documented in [the client guide](nvidia_info.md).
- Add one available Gemini deployment as a comparison/escalation provider after
  checking the temporary Google project's actual access. Choose routing from
  observed quality, latency, and cost; a whole family may justify Gemini directly.
- Leave the separate EUR 200 Verda credit unused unless a concrete hosting or
  compute need appears. Antigravity is an optional development tool.
- [Google's Decisions API](https://aistudio.google.com/docs/decisions-api) provides
  typed yes/no, category, and rubric judgments over multimodal inputs. A possible
  experiment is page classification with an explicit unknown/other route. Its
  confidence is not a certificate of complete extraction or a correct answer.

Stoa results determine these choices. If Nemotron remains useful in the working
core, document that real contribution for the optional partner submission.

## Build sequence and decision gates

Timeboxes below are suggested first attempts, not completion estimates. Keep
frontend layout changes and backend/parser changes reviewable separately.

### 1. Establish a small evaluation and a concrete first answer

- [ ] Create an evaluation manifest containing source hashes/paths, question,
  family, scope, split, and reference-row identifier. Keep reference answers in
  the evaluator, outside runtime extraction and planning prompts.
- [ ] Start with 24 cases: 8 CubiCasa, 6 Swiss, 4 IFC models, 4 IFC-Bench, and
  2 Opening Design. Select for variety, including multi-view counts, a double
  object/assembly, literal identifiers, an area with holes, and missing/conflicting
  information. This starter set does not establish all-family coverage.
- [ ] Aim for 12 development and 12 held-out cases. Keep the same project,
  duplicate files, paired formats, floors, and translated questions in one split;
  grouping takes priority over exact split sizes. Select representative source
  regions for manual evidence review, including missed objects on the full view.
- [ ] Create a coverage ledger from the [question classification](QUESTION_CLASSIFICATION.md):
  family, source examples, required operation, current support, failing reason,
  and next action. Its 234 families are an internal taxonomy, not organizer labels.

**Gate, after about 45 minutes:** choose the first visible path. Prefer a real
CubiCasa count using the existing pilot code if its evidence is usable. If visual
inventory is unreliable, begin with a native schedule lookup or supported IFC
query, and retain raster counting as the next required task. All paths must
produce a real result and inspectable source evidence.

### 2. Connect one real question from browser to source evidence

- [ ] Add a thin backend service for registering/serving sources, resolving
  asset/view IDs, accepting `QuestionRequest`, and returning `QueryResult` plus
  resolved presentation evidence. Keep credentials on the backend.
- [ ] Replace `askDemo` for this path with the real client. Pass the selected
  source/view explicitly. Resolve an explicit whole-model question separately;
  if the model is unavailable, say so rather than answer for the visible floor.
- [ ] Use real source dimensions, coordinate frames and crop transforms. Bind
  every displayed claim to actual evidence. Validate bundle/plan/result
  consistency where applicable; visually check localization and source meaning.
- [ ] Deliver the minimal viewer/panel layout above, an answer, item selection,
  contextual evidence, a loading state, cancellation, and an honest failure state.

**Gate, after a 2-3 hour integration attempt:** a different person submits an
uncached question and follows its evidence. If that fails, fix the connection or
evidence mapping before adding more model providers or UI features. If native
property evidence works but 3D does not, ship the property inspection path and
keep the absent visual mapping explicit.

### 3. Choose model routes from observed failures

- [ ] On the same development cases, compare direct Nemotron, available Gemini,
  and the native/model hybrid. Use the same source scope and evidence criteria.
  Save outputs before comparing them with reference answers.
- [ ] Record exact answer agreement, evidence correctness, missed/duplicate
  instances, appropriate abstention, wall time, calls/tokens, and cache state.
- [ ] Classify failures: wrong scope/interpretation, unreadable text, missed
  symbol, duplicate instance, wrong ID association, bad units, incomplete native
  extraction, or information absent from the source.
- [ ] Implement a bounded retry/escalation policy. Start with at most one targeted
  repair/escalation stage; cap its crops, requests and total wall time. Record
  provider retries within that budget. The existing client's network timeout is
  not an end-to-end job deadline.

**Human model gate:** inspect failures, not just totals. If Nemotron's evidence is
good, use it. If Gemini resolves a repeatable class of errors, route that class
directly or escalate on an observable trigger such as unreadable text, unresolved
IDs, invalid geometry, or incomplete view coverage. Do not use an untested model
self-confidence threshold or call a second model on every answer automatically.
Missing source information remains missing whichever model is chosen.

### 4. Expand through the supplied families

Work in small batches that add an extractor/operation and its evidence behavior
together. Prioritize broad reusable paths while keeping known gaps visible:

| Order | Coverage work | Evidence/computation gate |
|---|---|---|
| A | CubiCasa counts: openings, fixtures, room categories, floors shown | Complete relevant-view review; source-specific grouping rules; paired/multiple floors and ambiguous symbols |
| B | Swiss room/unit labels, counts, areas and other supplied measurements | Correct label-to-geometry mapping, units/calibration, holes and exclusions; mapping back to the displayed export |
| C | Opening Design schedules and supplied detail counts | Native rows/cells, exact IDs, type/instance/leaf distinctions, sums with source inputs |
| D | IFC models and IFC-Bench scalar, grouped and relationship queries | Native IDs/property paths, units, assembly grain, requested scope, missing-value semantics |
| E | Remaining known IFC-Bench spatial, quantity, rule and compound questions | Explicit source inputs and required executor; add only the geometry, arithmetic or domain logic those questions need |

CubiCasa and Swiss comprise 96.89% of QA rows, but translated/repeated rows are
not independent examples or a prediction of achieved accuracy. This is a
prioritization aid. Known rare IFC-Bench families remain required coverage work;
mark unresolved ones as gaps, not as completed by an unsupported response.
An unrelated archive image can be a useful negative test; developing art or
machinery expertise for unasked categories is outside this acceptance scope.

**Human specialist gate:** after trying better source access, crops and prompts,
does a recurring visual error still limit a known family? First test an existing
OCR/detection model. Fine-tune only if there are suitable labels, enough time for
review, a separate held-out set, and a plausible improvement over the hosted
baseline. Prefer matching original annotations when available; aggregate QA
counts are not instance labels. Both the hosted and specialist paths must return
the same evidence contract. Otherwise keep the strongest measured hosted path
and record its remaining failure cases.

### 5. Make evidence fast to inspect and answers cheap to repeat

- [ ] Run the human UI gate above with a count, a lookup, and a calculation.
  Include one ambiguous/partial answer. Remove controls that distract from
  finding or checking evidence.
- [ ] Cache source-derived native extraction, OCR, renders and useful inventories
  by source hash, view/frame and pipeline/model/prompt version. Record examined
  classes and completeness; reuse only where the new question's scope permits.
- [ ] Show cold-file and warm-query latency/cost separately. Log model/provider
  usage and cache hits; do not present sponsor credits as intrinsically zero
  inference cost. Label any external tariff estimate as an estimate.
- [ ] Add an existing IFC viewer only where a demonstrated question needs spatial
  inspection that source plans/properties cannot adequately provide. Preserve
  native entity mappings; do not make a new 3D renderer a prerequisite for 2D QA.

**Gate:** choose the simplest presentation a reviewer can verify. A compact
property table may win for an IFC lookup; a source crop for a schedule; a polygon
and subtraction terms for area. They all serve the same answer/evidence flow.

### 6. Freeze, evaluate and rehearse

- [ ] Freeze routing/prompts and run the held-out starter cases, then expand the
  ledger across the known families as capacity permits. New tuning after viewing
  held-out failures needs a fresh held-out check before claiming improvement.
- [ ] Follow the [dataset scoring](../dataset/junction-dataset/README.md#questions):
  exact counts and 2% tolerance for areas, lengths and volumes; review text answers
  against the source. Check evidence and scope independently of answer matching.
- [ ] Report supported, tested, passed, failed and abstained cases by family/source,
  with denominators. Abstentions stay in coverage totals. Record reference
  disputes with source evidence; report raw reference agreement separately.
- [ ] Exercise real browser/API paths: source change during a request, failed
  provider call, zoomed/rotated evidence, original/marked toggle, and cache reuse.
  Run the relevant component/contract checks after changes.
- [ ] Rehearse a short demo: real count -> inspect an object; source lookup or
  calculation -> inspect its inputs; ambiguity/missing fact -> honest outcome.
  Include a same-family paraphrase that was not prepared as a stored answer.
- [ ] If using a cached result during an outage, label it as a saved run. Export
  needed code/artifacts before temporary Google resources expire. Keep provider
  diagnostics available for questions about latency/cost and Nemotron's role.

Milestones 1-3 prove one usable path, not completion of the hackathon scope.
Full coverage requires evidence-backed checks across the supplied families;
describe any remaining gaps explicitly at submission.

## Tonight's decision

| What is true at the end of the session? | Action |
|---|---|
| Real answering/evaluation is not connected | Finish the smallest integration step and stop; no labeling batch |
| A bounded evaluation runner works | Optionally run a fixed comparison set and save raw outputs plus failure crops for morning review |
| Ingestion works and repeated loading is slow | Cache native extraction, renders or OCR for selected sources; record cold preparation separately |
| A specialist has passed the need/label/time gate | Plan a targeted annotation job for that class; manually audit a pilot before scaling |

A suggested first unattended comparison cap is **20 selected source/question
cases, at most two candidate pipelines, 100 total provider requests including
retries, concurrency 1, and a fixed spend/wall-time limit set after a short pilot**.
These are proposed ceilings; the unattended runner remains to be implemented.
Check the temporary account's applicable quotas/usage terms before scaling.
Preserve provenance and separate model proposals from reviewed
annotations. Sleeping without a job running is an entirely valid outcome.

The next concrete work is milestones 1 and 2: choose the starter cases and connect
one real answer in the simplified viewer. Broader labeling is not on the critical
path unless the specialist gate changes that decision.

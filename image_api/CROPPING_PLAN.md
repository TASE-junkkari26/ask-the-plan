# Nemotron cropping and multiple-pass implementation plan

Date: 14 November 2026.
Branch: `feature/nemotron-crop-passes`.
Starting revision: `292cf42` from the fetched `origin/main`, including the latest
import-first UI and IFC work.
Status: **proposed work; no cropping or additional inference passes implemented**.

## Objective and scope

Improve recall and separation of visible door/window candidates from the current
Nemotron endpoint. The reported failure case contains missed doors and regions
that need review for multiple doorways. Evaluate those failures separately from
box placement and false positives. A larger candidate list alone is not success.

The team is investigating Gemini separately. This branch owns the Nemotron crop
planner, pass orchestration, reconciliation, and evaluation. Reuse the current
client and candidate API; avoid a competing provider-router implementation or
changes to the UI/IFC work. Preserve the image/question request and existing
response contract so the current UI can display the results.

Start with the supplied **fitted-doorway and window-assembly** question families,
including English/Finnish wording and paraphrases. They are documented in the
[question inventory](../docs/QUESTION_CLASSIFICATION.md) and bounded by the
[project scope](../docs/PROJECT_SCOPE.md). Cropping does not add measurement,
whole-building, room-relation, or IFC-query capabilities. Candidate proposals
remain unverified; this work does not introduce a final answer/count service.

For doors, one fitted opening is one candidate, including a double-leaf opening.
Two distinct nearby fitted openings must remain two candidates. Exclude open
passages and cabinet doors. For windows, retain the assembly convention. Record
ambiguous membership rather than changing the grain to match a reference count.

## What exists and what needs investigation

- [service.py](service.py) makes one whole-image request with `candidate-v1`.
  There is no systematic regional search, crop mapping, or second-pass review.
- [images.py](images.py) prepares an upright white-background PNG without
  resizing. The model/provider's internal image processing has not been measured;
  do not attribute misses to downsampling without evidence.
- The [frontend importer](../frontend/src/lib/importDocument.ts) renders PDFs
  with bounded resolution. Crop the submitted snapshot in this iteration.
  Upscaling it cannot recover detail already lost during rasterization; higher
  resolution PDF rendering would be a separate, measured follow-up.
- The [saved pilot](../experiments/door_labeling/RESULTS.md) is one development
  example. It found five doors but had box/subtype errors, all marked certain.
  Model uncertainty flags cannot be the only trigger for further inspection.
- The user recently saw `provider_unavailable`. The current service maps
  connection failures, timeouts, rate limits and retryable provider errors to
  that message. The exact cause has **not** been established. More passes could
  increase pressure on the endpoint, so diagnostics and strict budgets come first.

## Strategy to implement and compare

| Mode | Calls per image, proposed initial caps | Purpose |
| --- | --- | --- |
| `single` | 1 | Reproducible existing baseline and rollback option |
| `coverage` | 1 overview + up to 6 coverage crops | Find objects missed by a whole-image pass |
| `refined` | Coverage calls + up to 2 targeted reviews; 9 total maximum | Resolve merged instances, disagreements and clipped symbols |

These are experiment starting points, not measured optimal settings. Build and
measure `coverage` before adding `refined`. Repeating the same full image with a
request to "look harder" is not the initial approach: each additional call must
inspect a specified region or resolve a recorded discrepancy.

Overlapping crops are motivated by small-object detection research such as
[SAHI](https://arxiv.org/abs/2202.06934). That paper evaluates conventional
detectors on aerial datasets; it does not establish an improvement for Nemotron
or floorplans. Use Pillow already present in this project; no SAHI dependency is
needed for the initial crop geometry.

### 1. Establish the baseline and provider diagnostics

Before live comparisons, record the actual model/settings, prompt version,
source hash/dimensions, code revision, response status, usage and latency. Use
fixed settings across paired comparisons; begin with temperature 0 and thinking
disabled, and record that these may differ from a developer's current `.env`.
Do not edit their credentials or silently overwrite environment settings.

Inspect the local API/proxy and distinguish a local configuration failure from
an upstream failure. `/health` only checks local configuration. A bounded CLI
connection check is a live text inference request, not an image accuracy test;
do not launch a batch while connectivity is failing. Preserve safe failure
categories and upstream HTTP status, when present, with request/pass IDs. Never
log the key, SDK exception bodies, source pixels or full model output by default.

Keep SDK retries disabled for this endpoint. A provider outage is not a reason
to schedule more crops or silently switch models. Offline geometry, replay and
lifecycle work can proceed while the provider is unavailable.

### 2. Cover the full drawing with overlapping crops

Use the existing prepared image as the canonical full display frame. Always
retain the overview pass for context and comparison. Build coverage independently
of its detections, including when it finds no candidates: a missed door must
still have an opportunity to appear in a crop.

Initial deterministic crop planner:

1. Partition the full image into nonoverlapping rectangular **cores**, targeting
   a maximum core side of 1,024 native pixels. Use an aspect-aware grid with
   integer edges covering every pixel, including outer borders and separate
   floor panels. Do not rely on room/wall recognition to choose coverage.
2. Expand each core by 12.5% of its width/height on every available side, clipped
   to the image. Adjacent interior crops then overlap by about 20% of their
   expanded width. These margins preserve neighboring wall and swing context.
3. If the target grid needs more than six crops, choose a coarser full-coverage
   grid within the cap, minimizing the largest core side. Record the oversized
   cores and return a detail-budget limitation (`partial`). Do not spend the
   entire budget only on the top-left portion of a large sheet.
4. If a crop would be identical to the overview, reuse that observation. Avoid
   duplicate calls for tiny inputs or identical refinement regions.
5. Send native crop pixels without an extra resize, rotation, or drawn overlays.
   Initially inspect every crop, including mostly white ones. Blank-region
   skipping, connected-component region detection and aggressive whitespace
   removal are later ablations only if they preserve recall.

The crop prompt must explicitly use `bbox_1000` **relative to that attached
crop**, replacing the current whole-image instruction for that call. Ask for all
individual visible instances, distinct neighboring openings, and observable
uncertainty. Do not supply a desired count, overview detections, prior crop
predictions, or reference answers to these independent discovery calls.

Retain the original question and its scope. For experiments, the manifest gives
the supported target family. Before HTTP rollout, make crop eligibility explicit
in the private overview task interpretation: only unconditional visible
doorway/window discovery is eligible. Other/ambiguous tasks use the existing
single-pass path. Test known paraphrases and translations; do not infer broad
eligibility from an English keyword or strip a qualifier such as "in the bedroom".
An overview `unsupported` result stops further analysis. A semantic `unreadable`
overview may still benefit from crops for an eligible task, unlike a transport
failure, which stops the request.

### 3. Keep crop coordinates and provenance exact

Each internal observation needs its pass/crop ID, parent image hash, core and
crop rectangles, crop byte hash/dimensions, prompt version, model, status and
usage. Keep raw proposals separate from final reconciled candidates.

For a crop `(left, top, width, height)` and crop-relative model coordinates:

```text
full_x = left + x_1000 * width / 1000
full_y = top  + y_1000 * height / 1000
```

Apply this to both box corners, validate finite positive geometry in the crop
frame, then validate it in the full frame. Use actual integer crop extents after
rounding/clipping. No padding/rotation/scaling in the first implementation; if
introduced later, store and test the complete inverse transform. Do not repair
out-of-range model boxes by silently clamping them.

The public image hash, full dimensions and display frame remain unchanged.
`inference_sha256` continues to identify the canonical prepared overview image;
the internal pass records identify each crop derived from it. Never replace the
public image identity with a crop identity. Assign final response-local IDs only
after reconciliation, with deterministic ordering independent of async completion.

### 4. Reconcile duplicates without merging adjacent doors

Maintain observation provenance throughout matching. A core containing a box's
center gives a useful ownership preference; it must not discard a candidate
found only in another crop's overlap. Flag boxes touching an internal crop edge
as potentially incomplete, but do not equate the outer image edge with an
artificial crop boundary.

Start with conservative, deterministic matching:

- Collapse exact repeated category/geometry records **across passes**. An exact
  duplicate within one model response remains a validation error.
- Match near-duplicates only across different passes, with compatible category
  and literal labels, high overlap, similar centers and comparable box sizes.
  Initial calibration values: IoU at least 0.8, area ratio within 1.5, and center
  displacement at most 0.2 of the smaller box's short side. Keep them configurable
  and test nearby distinct doors explicitly.
- Permit at most one observation from each pass in a merged group; require
  pairwise compatibility. Avoid transitive A-to-B-to-C merging through a large
  box that covers two separate doors. Same-pass distinct candidates must never
  collapse merely because their swing boxes overlap.
- Prefer an actual complete, interior observation over a clipped edge observation.
  Use crop context/ownership as tie-breakers, not uncalibrated model confidence.
  Do not union or average boxes into a region spanning neighboring doors.
- A broad overview box overlapping two distinct crop candidates is a conflict to
  review, not two duplicates to suppress. Preserve unmatched discoveries. Label
  conflicts and uncertain instance membership remain visible.

Keep both raw and reconciled outputs in experiments so any recall/precision loss
caused by matching is measurable. In production, unresolved competing hypotheses
are uncertain candidates with a `partial` limitation; never present them as an
exhaustive count.

### 5. Spend at most two extra calls on targeted review

Select review regions from evidence of disagreement: one broad box against
multiple smaller boxes, disagreement across overlapping views, truncated symbols
at crop seams, or questionable membership. Use geometry/disagreement as well as
model uncertainty. Prioritize unresolved instance splits and seam truncation.

Expand the implicated region to include surrounding walls and the entire door
swing where possible. Ask Nemotron to independently re-inventory visible
instances in the clean crop, allowing an empty list or several separate boxes.
Avoid yes/no confirmation of an earlier prediction or drawing proposed boxes
onto the input. This is a different view, not independent proof of correctness.

Reconcile the review observations with the affected conflict group. Replace a
broad parent only when the review supports distinct localized openings; never
replace every detection that merely intersects the review crop. New observations
in the context margin still participate in normal reconciliation. A disagreement
that survives the review remains explicit. No recursive self-review loop and no
requirement that two calls agree before retaining a detection.

## Budgets, failures and response semantics

Proposed settings use `IMAGE_API_*` and stay on the backend. Begin with one active
pass per request; maintain a shared limit of two provider calls per worker across
all requests. The existing request concurrency cap alone would not constrain a
future per-request `gather` over crops. Multiple workers multiply these limits.

Keep the existing 180-second total request deadline. Share one absolute deadline
from request handling through all stages; do not reset it for each crop. Reserve
five seconds for finalization and bound each call to the remaining inference
time (initial per-pass ceiling: 40 seconds). Generate/release crops lazily to
bound memory and temporary storage, with the existing image byte/pixel limits.

Hard initial limits: six coverage crops, two review crops, nine total attempts,
and 8,192 output tokens per call. Add a request-wide output allocation ceiling of
24,576 tokens: before a call, reserve its requested maximum from the remaining
allocation; reclaim unused tokens only when reliable usage is reported. All
attempts count, including failed ones. Log measured input/output usage; call
counts and pixel limits bound work but do not constitute an exact currency cap.
Missing usage stays unknown. Do not claim the historic comparison tariff is the
current Verda bill.

| Event | Planned behavior |
| --- | --- |
| Overview connection/auth/rate-limit/server failure | Existing safe HTTP error; no crop fan-out |
| Later 429, transport failure, timeout or server failure | Stop scheduling more calls; preserve usable completed candidates as `partial`, explaining incomplete analysis |
| Invalid/truncated crop output | Reject that pass; no repair call; record the failed region and return `partial` if usable candidates exist |
| Technical failure with no usable candidates | Return a safe HTTP error, not a successful empty inventory |
| Planned detail budget exceeded, review unresolved, or output truncated by the final 100-candidate cap | `partial` with a specific limitation; never silently truncate |
| All planned eligible passes complete with no candidates | `ok` with an empty list; inventory remains unverified |
| Client disconnect or outer hard deadline | Cancel/await all owned work, remove temporary files, preserve existing cancellation/504 behavior |

A partial result must be assembled before the outer hard deadline; do not swallow
task cancellation to manufacture success. Retain the existing 100-candidate public
cap; choose any capped subset deterministically after reconciliation, record the
omitted count internally, and make the limitation visible. Keep limitations
bounded and human-readable rather than exposing backend paths or raw provider data.

Preserve `ImageCandidateResponse` and `ImageCandidateError`. Aggregate elapsed
wall time and token usage across all attempts. If any attempt's usage is missing,
return null for the affected aggregate, retaining known totals in experiment
records. Use a pipeline prompt version resolving to the complete pass/config
manifest. Detect conflicting returned model identities instead of silently
assigning the last model to the combined response. Keep
`inventory_completeness: "unverified"` for every strategy.

## Evaluation that can decide whether this helped

1. Start with 3-5 development drawings: the user's failure case if its original
   can be identified, the saved pilot, and crowded/rotated/multiple-floor cases.
   Do not use the annotated UI screenshot as the inference input. Record the
   unresolved identity of that original until matched; do not guess a filename.
2. Build about 20 varied development plans and a separate held-out set (initial
   target: 10). Split by source drawing/project **before** producing tiles;
   alternate formats, translations and duplicate images stay in the same split.
   This is a pilot comparison, not broad accuracy certification.
3. Review every door/window instance on evaluated images. Store boxes, target
   class, object grain and ambiguity separately from model output. Counts in
   the supplied JSONL are insufficient for localization or completeness review;
   the [data audit](../dataset/FULL_DATASET_FINDINGS.md) documents that the local
   CubiCasa images lack their upstream polygon annotations. Preserve originals.
4. Define the box convention before annotation: for doors, fitted opening plus
   leaf/swing symbol; for windows, the full visible assembly. Score one-to-one
   class-compatible matches at a declared IoU threshold (start at 0.5), report
   stricter localization separately, and visually adjudicate tiny/ambiguous
   symbols with the rule recorded. Never match one broad prediction to two doors.
5. Compare original `candidate-v1` single pass, clarified single pass, coverage
   without review, and coverage with review. This separates prompt changes from
   cropping and review effects. Hold model/sampling/settings and input pixels
   fixed; repeat a small subset to expose run variability.
6. Report recall, precision, missed/false/merged/duplicate instances, localization,
   exact instance-total agreement, partial/error rate, pass count, total tokens
   and p50/p95 latency. Show per-drawing differences and raw denominators. Correct
   totals alone cannot validate detection. Provider errors are not zero-object
   results and must not disappear from the report.
7. Tune on development only; lock settings before the held-out comparison. An
   initial promotion target is at least 25% fewer missed doors overall, no more
   than two percentage points of precision loss, and fewer merged-instance
   errors. These are proposed decision thresholds, not achieved results. Report
   drawing-level regressions and actual cost/latency alongside them; if the
   sample has too few errors for meaningful comparison, enlarge it instead of
   claiming a gain. Check window regressions before enabling the strategy there.

Use a local experiment runner that imports the production crop/reconciliation
functions. Save source/annotation hashes, manifest/split, prompts, settings,
transforms, pass results/errors, overlays, usage and code revision under ignored
`experiments/runs/`. Provide a dry-run crop preview, an explicit live-run mode,
and an offline replay/evaluation mode. Reference answers and reviewed boxes are
loaded only by evaluation, never by discovery or reconciliation. Normal API
requests do not persist uploaded drawings or raw model output.

## Implementation sequence and file ownership

- [x] Create and switch to `feature/nemotron-crop-passes` from current remote main.
- [x] Inspect current code, guides, failure report and evaluation limitations.
- [x] Write this plan; implementation and live accuracy work remain pending.
- [ ] **Baseline and diagnostics:** capture a reproducible single-pass baseline,
  identify the provider availability failure, define the small reviewed manifest
  and safe per-pass failure categories. Continue offline work if live access fails.
- [ ] **Pure crop geometry:** add `image_api/cropping.py` with deterministic core/
  halo planning, crop records and coordinate transforms. Add synthetic geometry
  checks and a crop-preview command before introducing any extra network calls.
- [ ] **Single-pass refactor:** extract proposal validation/call handling from
  `service.py` into a reusable internal pass function without changing `single`
  behavior. Version crop/review prompts separately; include them in package data
  in `pyproject.toml` when added.
- [ ] **Coverage and matching:** add `image_api/passes.py` and
  `image_api/reconcile.py`; wire budgets, safe failure aggregation and cleanup
  through `service.py`, `config.py` and the small necessary `app.py` changes.
  Implement the coverage experiment before targeted review.
- [ ] **Experiment tooling:** add `experiments/candidate_cropping/` for the
  manifest, dry run, live runner, replay and metrics. Follow
  [experiment artifact rules](../experiments/README.md); record findings honestly.
- [ ] **Targeted review:** implement discrepancy selection and bounded reviews
  only after coverage has been measured; compare their incremental benefit.
- [ ] **API rollout:** add a backend strategy setting, initially defaulting to
  `single`. Select the measured strategy after the comparison. Preserve the
  multipart fields, candidate types, full-image coordinates and existing UI.
- [ ] **Handoff:** update this status, API/Nemotron guides, environment example,
  experiment report and verification record with actual commands/results/limits.

Avoid shared contract or frontend edits unless a concrete incompatibility is
found. If a contract change becomes necessary, edit the Python source of truth,
regenerate schemas/TypeScript, and check consumers. Inspect current diffs again
before editing shared files; the Gemini and UI work may advance independently.

## Checks and completion criteria

Offline tests should cover properties and failure modes that affect results:
full pixel coverage, extreme aspect ratios, integer crop edges, full-frame
coordinate round trips, EXIF/transparency, overlapping distinct doors,
double-leaf door grain, one broad box versus two small boxes, same-pass overlap,
unmatched discoveries in crop halos, label conflicts, and deterministic ordering.
Use synthetic fixtures for geometry; they do not establish perception accuracy.

Mock inference checks must cover call/token/deadline ceilings across concurrent
requests, no retry multiplication, failures after successful passes, null usage,
invalid crop output, candidate-cap handling, provider model disagreement,
disconnects during crop preparation/inference, and cleanup after cancellation.
Preserve the existing HTTP, candidate-contract and Nemotron regression checks.

Run relevant Python tests plus the existing lifecycle tests, then
`python -m contracts.export --check` and `python scripts/check_docs.py` with the
configured environment. Check browser overlays on a non-square image and a PDF
page, selection/focus/exports, and stale-result cancellation after a source/page
change. Run frontend checks/build for integration or generated-type changes.
Keep mocked transport checks distinct from live inference and accuracy results.

Completion requires a reproducible baseline-versus-crops report, a measured
decision about the default, correct full-image overlays, bounded failure behavior,
and an immediate `single` rollback option. If the comparison does not improve
accuracy sufficiently, retain the baseline and report the measured limitation.
There is no commit/push/deployment step authorized for this planning task.

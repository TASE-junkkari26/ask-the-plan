# Large scanned plan: door localization failure

14 November 2026. One user-supplied, non-dataset development image. This is an
investigation and proposed implementation order, not a production fix or an
extension of the 100-image benchmark score.

## Finding

**Choose the drawing region and inspect detail before escalating the model.**
The unchanged Hydrogen-low candidate prompt returned well-positioned boxes for
all 13 manually reviewed doorways when given a crop containing the main plan.
On the original full sheet, a new call returned 14 proposals, but only three
matched the reviewed door boxes at IoU >= 0.5. Increasing the full-page visual
budget did not repair this case.

The user's screenshot had 13 candidates, with several misplaced highlights.
The exact response behind that screenshot was not available. These are fresh
calls, so the 14-proposal baseline is not a byte-for-byte replay of that response.

## Source and method

- Local source: `pohjapiirrustus.png`, 4755 x 3364, RGB, no EXIF rotation;
  11,574,740 bytes and 15,995,820 pixels.
- Source SHA256:
  `b1f22265ee380162ac0dd10bf27eef841e3be00467894d9b49e881d2072c8456`.
- Question: `show doors`. Model: `gemini-4-hydrogen`, low thinking, unchanged
  production system prompt/schema, one attempt per condition, no retries.
- Seven authorized calls: three whole-plan comparisons and four detail crops.
  The diagnostic uses the production image normalizer, Gemini client/provider,
  and candidate service; it bypasses HTTP, browser rasterization and the artifact
  cache. It does not exercise the live browser.
- Crops and 13 approximate reference boxes were selected by assistant visual
  review before inference. References include a fitted doorway's leaf/swing
  extent, exclude cupboards and open passages, and were never sent to Gemini.
  These are not independently annotated ground truth.
- All inference images were checked pixel-for-pixel against the corresponding
  original source region. Mapping back adds the crop origin; no resizing,
  enhancement, perspective correction, or scale inference was used.
- The plan crop is `[1680, 500, 4650, 2630]` in original pixels, 2970 x 2130:
  39.55% of the sheet area. It retains the attached storage/carport and both
  northern exterior doors. The removed content includes the site inset, margins,
  page headings and scale footer. The full source remains available separately.

## Results

Localization uses maximum-cardinality, one-to-one box matching against the
manual references at IoU >= 0.5 (intersection area divided by union area).
The threshold measures approximate box placement, not semantic completeness.

| Input | Proposals | Reference doors matched | Provider-stage seconds | Estimated USD |
|---|---:|---:|---:|---:|
| Full page, default visual budget | 14 | 3/13 | 20.31 | 0.02381 |
| Full page, `ultra_high` visual budget | 14 | 2/13 | 14.35 | 0.01737 |
| Main plan crop, default visual budget | 13 | 13/13 | 13.71 | 0.01827 |
| Wet-room crop | 5 | 4/4 fully included | 6.50 | 0.01091 |
| Entry/storage crop | 5 | 4/4 fully included | 9.14 | 0.01173 |
| Bedroom-door crop | 4 | 4/4 fully included | 4.99 | 0.00743 |
| Northern exterior-door crop | 2 | 2/2 fully included | 6.68 | 0.00813 |

At the looser IoU >= 0.25 threshold, full/default matched five doors,
full/ultra-high three, and the plan crop still matched all 13. Mean best IoU per
reference was 0.244, 0.199 and 0.671 respectively. The distinction is visible
in the saved overlays and is not solely an artifact of the 0.5 threshold.

The four detail calls yielded **16 raw proposals**, including one repeated VH
doorway and two clipped-edge proposals. Together they localized all 13 reference
doors, but this union was checked using the references. **An automatic merger
was not implemented or evaluated.** Do not report the raw tile total as a count.

Every response reported `ok`, with zero uncertain candidates. The clipped
proposals nevertheless described themselves as partial in their visual cues.
Self-reported certainty/status did not identify these problems.

Total: 16,224 input tokens and 9,774 output-plus-thinking tokens, estimated
**$0.097641** at standard $1.50/$7.50 per million rates. Cost excludes cache
discounts, credits and tax; it is not an invoice. Timing excludes local image
preparation, queue time and browser work. Conditions were run once, with at most
two calls in flight, so latency/cost differences are observations, not estimates
of average performance. [Official pricing](https://aistudio.google.com/docs/pricing#gemini-4-hydrogen).

## Failure classification

1. **Visual localization/grounding.** The full-page response names real doors
   while placing their boxes elsewhere. Its VARASTO proposal lands below the
   storage room; MH 3 lands on a cupboard. These errors already exist in the
   returned source-pixel boxes, before frontend rendering.
2. **Invented instance.** Both new full-page calls propose a door between SH and
   KHH, where the reviewed source shows an open passage. The current prompt
   already explicitly excludes passages and cabinet doors. The plan crop removes
   this extra proposal without a prompt change.
3. **Page layout and visual budget.** A large native image includes substantial
   irrelevant context and spreads small door symbols across a broad coordinate
   frame. The experiment supports crop-based recovery, but does not isolate
   whether provider resampling, attention, clutter or coordinate prediction
   dominates. It does not establish an internal pixel-resampling algorithm.
4. **Unreliable self-assessment.** `ok` and `uncertain=false` cannot be routing
   gates on their own. A fluent visual cue is not proof that the box contains it.
5. **Evaluation blind spot.** The screenshot's plausible count could pass a
   count-only benchmark despite poor evidence placement. The prior 79/100 count
   result remains unchanged and must not be described as 79% localization accuracy.

The current frontend uploads an upright, full-size raster; `original` backend
mode preserves it. The current client does not set image `resolution`.
Google documents default/high image budgets of approximately 1120 tokens and
`ultra_high` approximately 2240, independent of the upload's megapixel count.
The experiment overrides only that per-image request field for its ultra-high
arm. [Media-resolution documentation](https://aistudio.google.com/docs/media-resolution).

The normalized Y/X provider boxes are reordered once and scaled once by the
backend. The frontend's image and overlay share the same fit and pan/zoom
transform. Three existing frontend coordinate tests and 32 Gemini/preprocessing
tests passed on Windows Python 3.14/Node 24. This supports the code audit;
it is not browser verification. Raw-coordinate overlays reproduce the failure
without the frontend, so changing its offsets would not fix the observed cause.

## What to build next

### First: an explicit drawing-region operation

Add a selected analysis region on top of the existing whole-page source. The
smallest useful product step is a user-adjustable region; automatic layout
proposals can follow and use the same contract. Store source hash, source-frame
ID, integer crop bounds, crop dimensions and the exact crop-to-source transform.
Map model boxes through that transform once. Preserve selection scope and show
the chosen region; do not silently exclude attached storage or exterior doors.

The current preprocessor does not already solve this. Running it on this image
produced a `drawing_candidate` of `[15, 463, 4752, 3364]`, which retains almost
the full sheet width, the site inset and footer. Its roles are explicitly
heuristic. Merely enabling that crop or the 1600-pixel full-page overview is not
the successful intervention tested here.

For an automatic path, use a cheap overview to propose semantic panels, retain
their context, and validate the requested drawing selection. A Decisions yes/no
result can request this operation, but cannot supply or validate precise crop
geometry by itself. The downstream region tool needs actual coordinates.

### Second: wire detail inspection and reconciliation

Reuse the existing preprocessor's `inspect_region`/transform machinery through
a bounded orchestrator. Detect on the selected plan first; inspect dense or
unresolved subregions in parallel only when necessary. Inspect possible
omissions as well as existing proposals: crops around detected doors alone
cannot discover all missed doors.

Add these operations and metadata deliberately to the contracts:

| Operation | Required result |
|---|---|
| `select_analysis_region` | Valid source-bound crop and retained context; explicit user/question scope |
| `detect_instances` | One candidate per fitted doorway, defined box convention, optional opening/hinge anchors, actual source frame |
| `inspect_region` | Native-detail crop, exact transform, included scope and clipping information |
| `verify_candidate` | Crop-supported membership and corrected local geometry; separate unknown from false |
| `reconcile_instances` | Duplicate/partial relationships, surviving source instances and unresolved disagreements |
| `check_coverage` | Regions examined, boundaries needing recentering, unresolved omissions; no claim that coverage proves completeness |

For door prompts, define whether a box covers the opening or full leaf/swing;
use that same convention in annotation and scoring. A hinge/door-opening anchor
can help bind a proposal to linework. Recognize sliding/other fitted doors when
the task needs them; an arc must not become a universal door requirement.

Overlapping crops require instance reconciliation. Mark crop-edge truncation,
inspect a recentered crop, and merge only matching source instances. Blindly
summing boxes gives 16 here; blindly applying a single IoU cutoff can miss
duplicates whose boxes drift. Preserve unresolved alternatives as partial.

### Third: make routing choose the next useful observation

| Observable condition | Next action |
|---|---|
| Small symbols on a large sheet with unrelated panels/margins | Select the plan region and retry Hydrogen at native detail |
| Dense region or unresolved detection/omission within the selected plan | Inspect overlapping detail crops with preserved context |
| Candidate touches a crop boundary | Recenter and recheck before counting/merging |
| Box/cue disagreement, duplicate candidates, incompatible local results | Verify the disputed region and reconcile source instances |
| Readable close-ups still require difficult symbol interpretation | Evaluate higher thinking/Carbon or an independent Nemotron call on that region |
| Necessary linework is absent/illegible in the source | Return an explicit limitation or request better source material |

No Carbon, Nemotron, higher-thinking, OCR, segmentation model, perspective
correction or multi-model adjudication was tested in this investigation. Their
benefit should be measured on remaining failures after detail recovery. A second
model receiving the same poor full-page representation is not the first fix.

### Fourth: measure evidence, then tune the prompt

Add a small reviewed door/window localization set alongside the existing count
set. Measure object precision/recall, one-to-one box matches, localization error,
duplicates, clipping, missing objects, response status, total pipeline cost and
latency. Keep this inspected image in development; use other project-grouped
images for validation. Repeat conditions to measure variability. Test automatic
panel selection separately: these successful crops were selected manually.

Use bounded prompt revisions for evidence/box conventions and partial results.
The successful crop used the current prompt, so this experiment does not justify
searching for a "perfect" system prompt before building detail access.

Preserve the full source for future area questions: its 5 m scale bar and printed
112.0 square-metre value remain available even when the door detector uses a
plan crop. Those are separate evidence sources; neither establishes room
boundaries or the precise net/gross scope by itself.

UI follow-up: show small numbered markers by default and full labels on
selection/hover. The large overlapping `door` tags obscure symbols during review.
This improves inspection but does not repair model geometry.

## Artifacts and verification boundary

Local, ignored run: `experiments/runs/pohjapiirrustus-investigation/`.
It contains `spec.json`, manual reference overlay, the standalone preprocessor
manifest, all seven inputs/requests/replies/mapped boxes/overlays, `evaluation.json`,
`score_and_render.py`, and `review.html`. Private source images were not added to
tracked files. The source hash was rechecked unchanged after testing.

The reusable [diagnostic runner](diagnose_localization.py) requires `--run`, a
source, a JSON case spec and a new output directory. It does not change live
server configuration. After the experiment, its input validation was hardened
and canonical source preparation reused for other formats; the saved run's
runner hash identifies the version used for these seven calls.

Only experiment tooling and research documentation were changed. No production
prompt, frontend, backend, reference dataset, live server or 100-image result
was modified. No commit or deployment was performed.

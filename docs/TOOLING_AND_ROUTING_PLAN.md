# Drawing tools and routing: next implementation plan

14 November 2026. **Proposed work**, informed by the
[100-image Hydrogen evaluation](../experiments/image_questions/GEMINI_100_RESULTS.md),
the supplied [question taxonomy](QUESTION_CLASSIFICATION.md), and source inspection.
This document does not implement a router, tools, calibration, or a new answer API.
It preserves the original benchmark score and original reference answers.

The router should choose an **evidence and computation strategy**, then a model
and reasoning budget. A difficult-looking drawing may have easy native data;
a clear image may require an operation the current endpoint never performs.

## First scope and priorities

Treat “questions with correct answers” as the supplied QA families, with source
evidence checked independently. All 127,044 supplied rows have nonempty answers,
but some answers are estimates, unavailable-information responses, or known
discrepancies. Keep a review ledger rather than assuming every reference is exact.
Unlabelled archival assets and unasked ResBIM room reconstruction come later.
Hard known IFC-Bench families remain required gaps; lower frequency does not
make them optional. See [scope](PROJECT_SCOPE.md) and the
[source audit](../dataset/FULL_DATASET_FINDINGS.md).

CubiCasa and Swiss account for 96.89% of QA rows, although translations and
paired formats repeat tasks. Use both row-weighted and family/project-weighted
evaluation; the organizer's scoring distribution is unknown.

| Priority | Build | Supplied tasks unlocked or improved |
|---|---|---|
| P0 | Typed answer planning, calculation execution, evidence results | Turn observations into actual counts/lookups/quantities with declared grain and scope |
| P0 | Native PDF text/table cells and row arithmetic | Door schedule count (line 89397), `121.A` width (89414), `128.B` dimensions (89416), window multiplicities (89459/Q099) |
| P0 | Detail inspection, coverage ledger, instance reconciliation | Windows and fitted doors: 10 of the 21 benchmark mismatches |
| P1 | Swiss DXF room geometry, labels, units and apartment membership | One-room areas, 3,750 apartment-area rows, 2,080 indoor-floor-area rows, labelled-room sums |
| P1 | IFC metadata discovery and scalar arithmetic | Existing stored quantities, ranking, compound queries; see [object discovery](IFC_OBJECT_DISCOVERY.md) |
| P1 | Raster room boundaries and calibrated measurement fallback | Known area tasks when native geometry or printed quantities are unavailable |
| P2 | Measured stronger-model and multi-model policies | Remaining visual ambiguity after source/detail/tool recovery |
| Tracked next | Metric IFC geometry, orientation, routes and other uncovered known families | Explicit IFC-Bench gaps, with separate capabilities and evaluation |

There are 6,236 one-room-area rows across source cohorts, including 4,152 Swiss
and 2,079 IFC-model-cohort rows. Some of the latter attach to PDFs rather than
IFC files. Prefer a valid stored/printed area to measuring pixels when its scope
and net/gross definition answer the question.

## What the quick test actually tells us

Baseline: 79/100 exact candidate-count matches, not final-answer or localization
accuracy. All requests succeeded, so transport/quota was not the observed failure.
Windows were 3/9, doors 4/8, IFC-derived images 3/7. Nineteen mismatches reported
`ok`; 16 had no uncertain candidates. These are development observations, with
small source/family samples; they do not establish Carbon's advantage.

Two post-baseline source audits change the implementation priority:

**Q099: readable facts, missing computation and imperfect anchors.** Hydrogen's
visual cues contained the six source-correct factors:

```text
QQ: 1 × 16
RR: 1 × 84
SS: 2 × 118
TT: 2 × 4
UU: 2 × 4
VV: 3 × 9
sum = 379 window units
```

The saved native PDF text confirms all factors. Only four of six proposed boxes
contain their own native row-text centres; UU/VV drift. Build typed table cells
with native anchors and a multiply/sum executor. A model upgrade is not needed
to perform this arithmetic, and unverified cue strings are not sufficient evidence.
The original six-region-versus-379 benchmark comparison remains unchanged.

**Q093: information lost in the selected raster depiction.** The companion SVG
contains two cut `IfcStairFlight` groups, each only 10 × 0.125 SVG units. They
become approximately subpixel-high strips in the submitted image. Their linked
IFC parents are Level 2 `IfcStair` objects #21638 and #24618, without their own
shape representations. Native flight-to-stair traversal and parent deduplication
recover the two source objects. This is not clear evidence that Carbon would
recognize complete stairs from the same pixels. Companions must be explicitly
available, revision-matched and registered to the shown view.

The ignored local `postbaseline-source-audit.json` alongside the benchmark run
records native cells/transforms, source hashes and the GUID/STEP parent mappings.
Its checks preserved the original cases, evaluation, CSV and API-output hashes.

Other questions need semantic policies, not just more boxes: utility/laundry
rooms versus kitchens, labelled bedrooms versus inferred bedroom use, terrace
doors versus windows, and continuous drawn walls versus canonical BIM wall objects.

## Current components to reuse

| Component | Implemented | Missing integration/capability |
|---|---|---|
| Image candidate service | Hydrogen-low, full-page proposals, source hashes/frames, usage and safe errors | Final answers, tool loop, inventory resolution, calculations |
| Raster preprocessor | Explicit raster frames, overviews, crops/transforms, optional OCR, preparation cache; API supplies an upright PNG while standalone preprocessing preserves stored orientation | Semantic views, physical scale, semantic inventories |
| `inspect_region` | Registered-view tool specification and backend executor | Delivery and dispatch inside a live model tool loop |
| PDF/DXF experiment probes | A reviewed schedule lookup and one simple Swiss room polygon | Production adapters for varied tables, blocks, arcs, holes, units and registration |
| IFC executor | Selection, traversal, projection, stored-quantity aggregates, grouping, ranking, bounded topology | Better discovery, scalar arithmetic, geometric measurement |
| Shared contracts | Facts, anchors, coverage, frames, calibration and query DAG representations | Executing every represented operation; schema support is not runtime support |

`arithmetic` and `measure` are represented in the shared schema but are not
advertised/executed by the current IFC engine. Extending them needs executor,
capability, unit and evidence handling, not just accepting another JSON variant.
The image client currently rejects tool-call steps; adding tool declarations
alone will not create a functioning conversation loop.

For row-wise products, either compile bounded scalar operations over resolved
cells or deliberately add a typed derived-column operation with contract,
executor, capability and evidence tests. Do not evaluate free-form expressions
generated by a model.

## Tool surface to give the planner

These are proposed bounded interfaces, not current wire contracts. Reuse
[shared concepts](SCHEMA.md) and source IDs. Host code owns files and credentials;
model arguments use registered IDs rather than arbitrary paths or executable code.

| Tool | Inputs | Outputs and requirements |
|---|---|---|
| `profile_source` | asset revision, selected view | Actual formats, native text/vector availability, page rotation/dimensions, available linked assets, capabilities, missing inputs |
| `resolve_related_sources` | source/view, required evidence kind | Validated equivalent same-view assets and registration; never guess correspondence solely from filenames |
| `read_source_text` | view, optional region/query | Native spans first; targeted OCR fallback. Literal text, separate search normalization, units, anchor IDs and source coordinates |
| `inspect_region` | view ID, bounds, coordinate space | Reuse the existing crop/transform mechanism; return image context and source-frame mapping |
| `extract_table` / `query_table` | view/region; table ID, filters, columns | Headers, row identity, typed cells, units, row/cell anchors, repeated-header handling, extraction gaps |
| `detect_instances` | view/regions, target concept, counting policy | Observations, not verified objects; literal labels, regions, ambiguity and examined-region records |
| `reconcile_instances` | observations, grain, view | Canonical instance candidates, observation-to-instance mapping, duplicate decisions, conflicts and exclusions |
| `resolve_room_inventory` | view, apartment/floor filters | Rooms with literal IDs, labels, membership, shells/holes or stored areas, basis and coverage; inferred boundaries remain marked inferred |
| `extract_dimensions` | view/region, native entities or visual proposals | Literal lengths/units, dimension endpoints, scale-bar observations and their source anchors; ambiguous label-to-line association stays unresolved |
| `calibrate_view` | view, anchored dimensional observations | Valid pixel-to-physical transform, units, applicable region, residuals, checks and unresolved ambiguity |
| `measure_geometry` | geometry IDs, calibration/unit references, metric/basis | Area/perimeter/union/difference in code; invalid topology and missing calibration remain explicit |
| `execute_query` | typed, resolved operation DAG | Select/filter, distinct count, rank, aggregate, row expressions, units and scalar arithmetic; materialized included/excluded IDs |
| `check_evidence` | query/results, source/coverage records | Scope, IDs, dimensions, anchors, unit/basis consistency, remaining gaps; structural validation cannot certify source truth |
| `inspect_ifc_catalog` / `discover_ifc_objects` | model revision, bounded catalog search | Complete execution remains over the authorized model; a truncated search preview must not become the counted universe |

Every tool result should carry source revision/hash, applicable view/frame IDs,
extraction version, status, anchors and limitations. Non-geometric file metadata
and scalar IFC facts may legitimately have no view/frame. Geometry results carry
transforms and units/basis; inventories carry grain and examined scope. Keep
missing, not modeled, not extracted, ambiguous, partial and zero separate.

Use a maintained DXF adapter with explicit modelspace/block units rather than
extending the experimental line parser indefinitely; see
[ezdxf's unit model](https://ezdxf.readthedocs.io/en/stable/concepts/units.html).
A planar geometry library can supply polygon area and Boolean operations, but
does not infer real-world units or correct room boundaries; see
[Shapely measurements](https://shapely.readthedocs.io/en/stable/measurement.html).
Pin/evaluate dependencies during implementation rather than treating this plan
as a completed dependency decision.

## Scale, rooms and area

Use this evidence order: source-backed stored/printed quantity with the required
basis; native metric polygon; raster polygon with validated calibration. A bounding
box or the area of its label text is not a room's net floor area.

For raster calibration, associate a dimension's **actual extension/arrow endpoints**
with its literal physical length and unit. Measuring the width of the printed
number or assuming a typical door width does not establish scale. A scale bar is
another usable anchor. A printed `1:100` needs trustworthy page dimensions and
resizing history, followed by dimension checks.

For uniform scale `p` pixels/metre:

```text
p = endpoint_distance_px / annotated_length_m
room_area_m2 = (shell_area_px2 − sum(hole_areas_px2)) / p²
```

Illustrative calculation: a 5,000 mm dimension spanning 1,000 source pixels gives
200 px/m. A net polygon of 800,000 px² then gives 20 m². This is a numerical
example, not an observed benchmark result.

Use additional independent dimensions in different directions to check the fit.
Keep calibration per view/detail: mixed-scale panels cannot share one page-wide
conversion. Nonuniform scaling needs an affine mapping; transform polygon vertices
into physical coordinates before measurement. Perspective/projective mappings need
their own verified procedure; do not apply one constant px/m blindly. About 1%
uniform scale error alone produces about 2% area error, before boundary error.

Room recovery must handle door gaps, shafts, wall thickness, columns, holes,
touching/overlapping outlines, disconnected parts and net/gross meaning. Prefer
native CAD boundaries. Raster wall segmentation/flood filling and model masks
are boundary proposals that need closure/topology and source review. Snapping or
closing a doorway must not silently merge neighboring rooms or invent a wall.
Resizing/enlarging a crop does not create missing source detail.

### “House area with the three smallest rooms removed”

Resolve what “house area” and eligible rooms mean. Sum of net indoor rooms,
gross floor area and footprint are different quantities. Use an explicitly
requested mixed-basis calculation only when that meaning is intended.

```text
R = complete eligible room inventory in the selected scope
areas = source-backed net areas for every room in R
T = sum(areas)
S = rank(R, area ascending, limit 3)
E = sum(area of each room in S)
answer = T − E
```

Return T, the three excluded original IDs/areas, E, remaining membership and the
calculation trace. Missing room areas can invalidate the ranking, not just the
sum. Require at least three eligible rooms; declare tie handling. Exact equal
areas allow a stable ID tie rule without changing the numeric result; rounded
or uncertain overlapping areas may require an ambiguous-ranking result.

Stored IFC quantities already support much of this path; scalar subtraction
is an executor gap. For raster inputs, room inventory and calibrated boundaries
are the difficult work. General set difference is useful for evidence but is
not required to calculate `total − sum(bottom three)`. No supplied wording of
this exact example was found; it composes known ranking/area/aggregation families
and the user's explicitly requested extension. Related reference examples are
largest room (85568), three widest doors (86029) and ceiling-height ranking
(86102/86103). No reference answer lookup belongs in execution.

## Decisions the coordinator needs

Give the decision-tree implementer [these draft question cards](routing/decision_questions.v1.json).
They classify observable task traits; they do not calculate an answer or prove
it correct. Deterministic source metadata should bypass unnecessary model questions.
An area/length/volume request is a quantity intent, not automatically a geometry
measurement strategy: probe stored/printed quantities before choosing measurement.

| Stage | Decision | Branch/action |
|---|---|---|
| 1 | Requested operation, entity grain, exact IDs, units/basis and scope | Compile typed intent; preserve original language/IDs; clarify material ambiguity |
| 2 | Required evidence actually available in the authorized view/model? | Use it, resolve an explicit link, or return the specific missing-input state |
| 3 | Native text/table, vector geometry, BIM facts or raster observations? | Select extractor/tool family before selecting a larger vision model |
| 4 | Sufficient target detail and one coherent view? | Full-source fast pass, contextual crop, semantic panel split or overlapping tiles |
| 5 | Computation over extracted facts? | Run the typed executor; do not obtain arithmetic by asking models for a prose total |
| 6 | Unresolved membership, omitted regions, bad anchors or conflicting values? | Reinspect disputed source regions; check grain, units, row identity and canonical IDs |
| 7 | Remaining ambiguity recoverable by stronger reasoning/vision? | Test Hydrogen higher thinking, Carbon or a targeted independent checker |
| 8 | Required evidence/calibration still absent or contradictory? | Partial/clarification/missing-information result; model escalation does not supply absent facts |
| 9 | Executed result satisfies scope/unit/evidence requirements? | Return computed values and inspectable memberships/inputs with honest coverage |

Google's [Decisions API](https://aistudio.google.com/docs/decisions-api) uses
`gemini-decision-1` at `/v1beta/decisions`, with `noul`, `choice` and `score`
judgments. Questions are independent; code must compose dependent stages.
Include an `other`/review option. Binary `noul` is P(yes); high confidence can
mean confident no. Score values and confidence are different. Calibrate thresholds
on labeled drawing/task traits and measured outcomes, not vendor examples.
Shared input is counted once within a request, plus each question's instructions;
that does not provide cache reuse across separate requests.

Implement Decisions separately from a tool-using Interactions adapter. The latter
needs validated dispatch, function-call IDs/results, bounded rounds, cancellation,
opaque state preservation and safe source handles. It must not weaken the existing
strict candidate-response parser. Native backend function tools are sufficient;
public MCP hosting is not a prerequisite.

## Divide and conquer, preprocessing and escalation

1. Preserve original pixels, source identity and transforms. Create lightweight
   overviews for locating views; use native detail for recognition. Global
   deskew/contrast/binarization are experiments, not universal improvements: line
   thinning or thresholding can erase symbols, hatches or color semantics.
2. Split semantic panels before tiling where possible. Retain title, legend,
   table headers, neighboring context and individual panel scales. Existing
   heuristic layout regions are candidates, not automatically trusted views.
3. Use overlapping tiles for dense door/window inventories. Map observations
   back to source coordinates and reconcile logical objects across seams.
   Neither naive IoU merging nor summing tile counts handles all adjacent or
   split objects. Record gaps and disputed merges. Examining all tiles alone
   does not prove that every target instance was recognized.
4. Ask a targeted omission/false-positive check on unresolved regions. Verify
   zero results against examined scope and source readability. Avoid telling an
   independent verifier the expected answer or first model's desired total.
5. Escalate only the unresolved work. Supported future profiles include Hydrogen
   higher thinking and Carbon; the current configuration permits only Hydrogen-low.
   Both support tools/structured output according to their official
   [Hydrogen](https://aistudio.google.com/docs/models/gemini-4-hydrogen) and
   [Carbon](https://aistudio.google.com/docs/models/gemini-4-carbon) pages.
   These profiles have not been compared on our drawings.
6. Parallel Hydrogen/Nemotron calls are an experimental arm for hard cases.
   Compare object sets, labels, source cells and disputed regions. Do not average
   totals, take the larger count, or treat agreement as independent proof. Resolve
   disagreements with source tools/detail; return unresolved conflict when needed.
   A third model's vote without new evidence may repeat the same mistake.
7. Cache extracted source facts by revision/view/extractor/parameters and counting
   policy. Reuse them across questions/translations. Current preprocessing cache
   does not cache semantic inventories. Provider context caching, local extraction
   caching and answer caching have different correctness and billing behavior.
8. Track call count, input/output/thinking tokens, latency and cost for the entire
   route, including the decision model, crops, verification and abandoned calls.
   Quota headroom enables parallelism; it does not make repeated work cost-free.
9. Additional experiments include source-derived text search/retrieval, legend
   and symbol association, image-resolution controls, OCR variants, rotation
   ensembles and class-specific detectors/room segmentation. Measure these on
   diagnosed failure slices. Specialized training or fine-tuning is later work
   only if simpler tools plateau; CubiCasa pretrained models can overlap our
   evaluation sources, and supplied QA must not become training leakage.

### A first routing experiment, not a proven policy

Retrospectively, routing windows/doors, uncertainty/partial cases, IFC-derived
images and derived arithmetic would select 25/100 cases and cover 16/21 existing
mismatches. Nine selected cases were already count-correct. This measures error
coverage only, not repairs, gains or actual classifier performance. The IFC-image
label came from benchmark metadata; a production route must obtain equivalent
traits from authorized metadata/content, not dataset folder names.

Test this selective policy against full escalation and the unchanged baseline.
Choose by measured additional evidence-backed correctness per extra cost and
latency. No benchmark here establishes that Carbon or Nemotron fixes those 16.

## Prompt work

Start from the [planner prompt draft](prompts/drawing_planner.v1.md), which is
not a drop-in replacement for the existing detector prompt. Keep separate
contracts for routing, planning, observation extraction and evidence checking.
Supply the real tool/capability catalog and source profile; avoid a giant prompt
claiming tools or quantities that do not exist. Version domain policies for
door openings/leaves, assemblies/units, room labels/functions, wall segments and
net/gross areas. Definitions must come from task/source conventions, not memorized
reference values. Prompt-only arithmetic and confident completeness wording do
not fill the executor or source-information gaps.

No prompt is “perfect” in advance. Freeze the current baseline, change one prompt
or tool policy at a time, and measure exact answers, source anchors, abstentions,
latency and total token cost. Tests should include paraphrases/translations within
known families, literal IDs, empty/missing sources, crop seams and conflicting scales.

## Evaluation and implementation handoff

1. Preserve the 100 cases as development data and the original 79/100 result.
   Reproduce Q099 with native cells plus arithmetic; Q093 with same-view native
   objects; door/window misses with crop/coverage/reconciliation. Record each
   repair and any regressions without rewriting baseline outputs.
2. Add actual final-answer/evidence scoring and new area cases. Use each reference
   case's stated unit, grain and tolerance; count matches alone are insufficient.
   Audit source anchors independently, including a random sample of correct totals.
3. Use fresh source/project-grouped holdouts where available. Keep translations,
   paired formats, duplicate files and related building floors in one split.
   All three referenced Opening Design sheets are now development sources;
   withheld questions on them test new questions on seen sheets, not unseen-sheet
   generalization. Do not invent an independent 20-sheet holdout from three sheets.
4. Compare matched cases across baseline, native/tool enrichment, crop/tiles,
   Hydrogen higher thinking, Carbon and selective dual-model reconciliation.
   Report accepted-answer accuracy, coverage/abstention, all-case accuracy,
   per-family/project results, evidence correctness and cost per correct answer.
5. Give the routing implementer profile fields, available capability IDs, draft
   question cards, route reason codes and tool outcomes. The source/tool team
   owns extraction/geometry/execution/evidence; router work should not duplicate it.
6. First integration target: an actual schedule lookup, a computed schedule total,
   and a Swiss room area with source evidence. Then the composite area/ranking
   example and the selected door/window repair experiment. Broader room
   reconstruction and unlabelled assets follow demonstrated requirements.

Planning validation: repository/source inspection, post-baseline Q099/Q093 source
audits, and official API documentation. No new model comparison, Decisions call,
prompt A/B test, production tool implementation or area-accuracy result is claimed.

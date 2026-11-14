# Live Nemotron 2D evaluation and recommended direction

14 November 2026, Europe/Helsinki. Eight baseline questions on six real challenge
drawings, followed by six diagnostic calls. IFC was excluded. This is a small
development experiment, not a held-out or corpus-wide accuracy estimate.

**Nemotron can identify useful objects and read labels, but the current whole-image
candidate path is not reliable enough to compute trusted answers from its boxes.**
Three of six count cases matched their reference totals. Wrong counts, invented
IDs, incorrect coordinates and confident omissions appeared in the same run.
Focused crops improved recognition substantially, but did not make localization
or exact field lookup consistently correct. Native PDF text and paired 2D DXF
geometry gave the strongest results on the structured cases.

## What was actually tested

- Current repository revision: `ba72858`; no production code changes.
- Real loopback HTTP requests to the production `/api/v1/candidates` route, real
  preprocessing and real Verda `nemotron-3.5-super-vl` completions; no mock provider.
- Prompt `candidate-v2`; default `original` preprocessing; OCR off; temperature
  0.2; thinking disabled; 8,192 maximum output tokens; no retries; concurrency one.
- Four PNG inputs at native size, and first-page PDF renders using the frontend's
  PDF.js version and resolution policy. Node canvas replaces browser canvas.
- Exact supplied English questions; no reference answers in any prompt. Baseline
  outputs were saved before reading the selected QA references. Source evidence
  was inspected independently. The sample procedure is in [the guide](README.md).
- All eight baseline calls returned HTTP 200 and schema-valid candidate results.
  This proves the transport/contract path worked, not semantic correctness.

The endpoint explicitly forbids final answers, counts and measurements. The
count comparisons below use candidate-list length as a diagnostic. They must not
be described as end-to-end answer accuracy. No final user answer was produced by
this endpoint, by design. Browser interaction was not tested in this evaluation.

## Baseline results

| Case | Source/question | Source/reference | Production result | Evidence review |
|---|---|---|---|---|
| Q01 | CubiCasa `high_quality-11211.png`: fitted doors | 6 | 6 candidates; `ok` | All six point to the visible fitted doorways; usable locations. Some cue wording about adjoining rooms is imprecise. |
| Q02 | CubiCasa `high_quality_architectural-12008.png`: windows | 1 | 2 candidates; `partial` | Both boxes cover small hatched rectangular symbols in the balcony, not the actual window assembly. The actual window was missed. |
| Q03 | CubiCasa `high_quality_architectural-9109.png`: toilet bowls | 2 | 1 candidate; `ok` | Missed the angled toilet in the upper-left WC. The returned box covers the lower WC's label/area text rather than its toilet bowl. |
| Q04 | CubiCasa `high_quality_architectural-6045.png`: bedrooms | 3 | 3 candidates; `ok` | Correctly locates all three rotated MH labels. These are label boxes, not room boundaries. |
| Q05 | Swiss `site670_bldg1429_floor6253.pdf`: Schlafzimmer rooms | 2 | 2 candidates; `ok` | Correct labels/IDs `2.06` and `2.09`, with approximate room boxes. |
| Q06 | Same Swiss floor: net area of `2.09` | 9.59 m2 | `unsupported`, no candidates | Appropriate abstention under this endpoint's measurement restriction. No printed area is present. The paired DXF supports the calculation. |
| Q07 | Xcel A-801: door-schedule entries | 38 | 31 candidates; `ok` | Only 16 of the 31 literal IDs exist in the actual schedule. Others are invented or altered, including `100.A`, `100.C`, `103.B`. Boxes drift beyond the table. |
| Q08 | Same A-801: width of `121.A` | 5 feet 10 3/8 inches | One candidate; `ok`, no final width | The literal ID is right, but its box points to an unrelated row and the cue claims width `118`. The actual width cell is elsewhere. |

All 46 baseline candidates have `uncertain=false`. Q02 has a global partial
warning, but its two false-positive candidates are individually marked certain.
Q03 and Q07 report `ok` with empty limitations despite omissions and fabrication.
The API's explicit `inventory_completeness: unverified` is therefore essential.
Neither an `ok` status nor the model's uncertainty flag is an approval signal.

Q07's 16 matching strings are not 16 correct localized detections: none of their
boxes contains the center of its matching native PDF ID text. This is a simple
source-anchor sanity check, not a ground-truth segmentation/IoU benchmark.

## Diagnostic calls: what improved, and what did not

These six follow-ups used the same approved source set after failure review.
They are not independent accuracy samples or fair comparisons of final systems.

| Diagnostic | Change | Observed result |
|---|---|---|
| D01 | Ask the window question directly on the same full image | Abstains, saying it cannot identify clear windows. Did not recover the real window. |
| D02 | Ask the toilet question directly on the same full image | Still says 1. Also calls the WC area 3.2, apparently borrowing the neighboring VH room's number; the WC says 2.4. |
| D03 | Existing candidate prompt on a manually selected detail of the missed WC, enlarged 4x | Finds the missed toilet and places a useful box around its bowl. This establishes recognition on that supplied detail, not complete coverage of the original plan. |
| D04 | Existing candidate prompt on the complete door-schedule crop | Returns all 38 literal IDs, each matching the native PDF text. However, only 3 of the 38 boxes contains its matching ID's text center; vertical row spacing drifts. |
| D05 | Ask `121.A` width directly on the original full sheet | Abstains, incorrectly claiming `121.A` is absent and inventing a highest ID `139.D`. |
| D06 | Ask the same width question directly on the table crop | Still abstains. Invents a different width and contradicts itself about whether the identical string `121.A` exists. It also objects that the cropped view lacks the sheet title. |

D04 is the clearest lesson: **correct count and correct ID list still do not
establish correct evidence boxes.** Its last `130.B` proposal is at crop y=491-501,
well above the actual final row. Fixing coordinate normalization in application
code cannot fix coordinates that the model predicted incorrectly.

Cropping helped one missed symbol and schedule reading. It did not solve precise
field association or grounding. These observations support a crop-inspection
tool, but not automatic acceptance after a second model call. Preserve the whole
page identity, crop transform and surrounding context; the direct crop response
shows why dropping sheet context can cause another class of failure.

## Source-only comparison

The [native probe](native_probe.py) uses source geometry/text, never QA answers.
It is an exploratory proof on these sheets, not a production importer.

| Same task | Deterministic source result | Verifiable inputs |
|---|---|---|
| Q05: labelled bedrooms | 2 | Two exact `Schlafzimmer` PDF text anchors. |
| Q06: net room area | 9.5922785913 m2, rounds to 9.59 | Paired floor DXF: literal room `2.09`, TEXT handle `11A`, one containing closed ROOM_OUTLINE handle `9A`, four vertices, `$INSUNITS=6` (metres), shoelace area. |
| Q07: schedule entries | 38 | 38 distinct literal door IDs and their native PDF positions within the reviewed table. |
| Q08: door width | `5' - 10 3/8"` | Row `121.A`, its Width column, native text and cell coordinates. |

All four match the supplied references; the area is within the dataset's 2%
tolerance. Computation consumed no model tokens. Parsing the already-extracted
text plus this DXF took about 9 ms; that excludes PDF extraction, rendering,
initial imports and any production pipeline setup. It is not an end-to-end latency
benchmark. Pairing the DXF keeps the same selected floor; it does not broaden
scope to another view or a building.

The source probe deliberately supports this table layout and simple polygon.
Production work still needs unit/topology checks, holes when present, stable source
anchors, and an explicit mapping back to the displayed page. PDF text extraction
also produced mojibake for some accented Swiss words; preserve the raw source
string and handle normalized concepts separately from literal IDs.

## Latency and inference usage

- Eight baseline calls: 24,460 prompt tokens + 4,241 completion tokens = 28,701.
- Measured HTTP median: 1.04 s; range 0.53-6.89 s; sum: 15.01 s. Startup and PDF
  rendering are excluded; provider/cache/load conditions were not controlled.
- Four of the six baseline count cases are CubiCasa, two are structured PDF cases.
  Do not project the 3/6 agreement rate to the dataset.
- Six diagnostics add 12,183 tokens; all 14 successful calls total 40,884 tokens.
- Q07 whole sheet used 4,434 prompt tokens; its schedule crop used 1,728 (61%
  fewer). Total prompt+completion tokens fell from 7,150 to 4,617 (35% fewer),
  while recovering the correct ID list. Geometry remained wrong.
- Repeated source preparation hit the existing cache for Q06/Q08, but both still
  made full model requests. That cache does not cache extracted semantic facts.
- No dollar charge is inferred from these tokens. Sponsor access is not a measure
  of intrinsic inference cost. A preliminary sandbox connection failure produced
  no completion and is excluded from the successful-run totals.

## Recommended 2D direction

Build a source extraction and computation path with Nemotron choosing operations
and inspecting difficult details. Keep useful model observations separate from
validated source facts. This follows the challenge's equally weighted accuracy,
verifiability, creativity and inference-cost criteria: the reusable contribution
is the source/evidence/execution layer, which remains useful as models improve.

1. **Implement native PDF and paired 2D CAD paths first.** Extract schedule cells,
   room labels and stable page coordinates; use the appropriate same-floor DXF
   layers for room/unit boundaries and quantities. Calculate counts, lookups,
   sums and areas in code. The four source-only results above are a concrete
   development starting point. Resolve companions explicitly; image-only uploads
   cannot assume that a DXF exists. For the supplied Swiss DXFs, use a maintained
   parser and account for units, closed boundaries and arc segments; see the
   primary [ezdxf unit](https://ezdxf.readthedocs.io/en/stable/concepts/units.html)
   and [polyline documentation](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html).
2. **Use Nemotron for bounded question interpretation and targeted inspection.**
   Produce a typed request containing operation, object category, literal IDs,
   filters and selected-view scope. Let code execute it over extracted facts.
   Give an inspection call the source crop plus its page identity/context. Check
   claimed IDs against source text and attach native/OCR coordinates to strings
   rather than asking the model to invent an evenly spaced box list.
3. **For raster-only plans, combine label OCR with a reviewed symbol pipeline.**
   OCR can supply room-label locations; door/window/toilet symbols need separate
   detection and grouping. Test whole-page plus bounded detail inspection with
   coordinate-preserving crops, deduplication and explicit examined-region records.
   Add a specialist only after measuring recurring failures. The original
   [CubiCasa repository](https://github.com/CubiCasa/CubiCasa5k) supplies a relevant
   floorplan model/data starting point; no specialist was run here, and possible
   training overlap must be reported. Do not launch mass pseudo-labeling from the
   current unchecked model boxes.
4. **Make evidence and completeness explicit before returning a final answer.**
   A count needs a reconciled instance set and known examined scope; a lookup
   needs the exact row/cell; an area needs a boundary, units and exclusions. The
   UI should highlight those objects or cells and show calculation inputs. Model
   confidence, schema validity and a visually plausible rectangle are insufficient.
5. **Cache extracted source facts and evaluate a new fixed set.** Key by source
   hash, view and extraction version. Reuse facts across wording/language changes.
   Next test about 20 new source/question cases within the supplied 2D families,
   including multi-panel plans, false-positive traps, room holes and exact schedule
   identifiers, plus Finnish/German paraphrases of the same families. Track count
   agreement, identifier fidelity, localization, abstentions and latency/tokens
   separately. These eight cases are now development cases, not a future holdout.

The immediate implementation milestone should deliver a schedule count/lookup
and a Swiss room-area answer with exact source anchors, then a reviewed raster
count using the same answer/evidence flow. A larger training job or a default
second-model cascade is not supported by this sample. No alternative model,
automatic crop selector, OCR pipeline or specialist detector was evaluated here.

## Reproducibility and limits

The [case manifest](cases.json), [runner](run.py), [PDF render script](render_pdfs.mjs),
[diagnostics](diagnose.py), [PDF anchor extraction](pdf_anchors.mjs) and
[native probe](native_probe.py) are retained. Raw responses, input hashes,
environment/code hashes, source licences, overlays, source snapshots and reference
checks are local under `experiments/runs/image-questions/20261114-live/` (ignored).
Visual review was performed by the assistant; this is not independent human
annotation. No original assets or supplied reference answers were modified.

The experiment ran on Windows. Browser graphics, device behavior, provider
repeatability, translated prompts and corpus coverage were not tested. Baseline
and diagnostics use different prompts where explicitly noted. The diagnosis
supports an engineering direction, not a claim of achieved hackathon coverage.

# Raster identity and preprocessing improvements

14 November 2026. This work targets supplied raster and schedule questions.
IFC-derived cases were excluded; IFC work remains with the separate deterministic
engine. No reference answers or source drawings were modified or used at runtime.

## Implemented changes

- Separate source observations from object identity. Normalize comparison keys
  while preserving literal source labels. Stable schedule IDs and typed category
  aliases link repeated rows/floors; fixed spatial anchors avoid chain merges.
- Group strongly corroborated clipped doorway observations and near-identical
  O/0 label readings as **uncertain identity hypotheses**, retaining all original
  readings and observation IDs. Genuine different IDs and distant repeated labels
  stay distinct.
- Give local detection the source-page dimensions, selected-panel bounds,
  counting grain and crop frame. Require consistent object/category conventions.
- Keep floors, rooms and schedule rows as complete panels instead of counting
  fragments in separate tiles.
- Reuse cached preprocessor overviews and unverified local layout proposals for
  semantic panel selection. Detection and evidence retain native pixels.
- Skip layout inference when a source fits a native pass. Allow 20% native tile
  edge slack and balanced seams, avoiding almost identical tail crops.
- Skip reinspection of an identical source rectangle/pixel hash. Identical pixels
  in different source positions still represent separate possible objects.
- Verify an uncertain object's membership with supported/rejected/ambiguous
  output, without creating a new regional inventory. Only an explicit rejection
  removes a proposal; reasons and source boxes remain in the response/UI.
- Expose optional local OCR word anchors through `read_source_labels`, preserving
  original text, frames and failure states. OCR stays off by default: it was noisy
  on door linework and imperfect even on clear schedule identifiers.

These are callable tools and bounded tool behavior, not the external decision
tree. See [integration](../../image_api/DETAIL_TOOLS.md).

## Evidence in three stages

### Saved-observation replay

Applying identity changes to saved replies across all 93 non-IFC cases improved
count matches from 72 to 75, with three repaired cases and no regressions. It
fixed Q043 toilets 3->1, Q051 floors 2->1 and Q098 schedule rows 87->29. This
replay supplied typed target families explicitly for analysis; it is not fresh
inference or an evaluated automatic classification policy.

### First live targeted pass

Fourteen frozen cases: seven regressions, two other failures and five controls.
The original single-call run matched 12/14, previous Detailed scan 5/14, and the
first revision 10/14. All five controls stayed correct. It made 27 calls versus
54 previously, estimated USD 0.316916. This preceded focused membership checks
and the final uncertain doorway-identity rules.

### Broader live targeted validation

All 21 failures from the previous non-IFC Detailed scan plus six previously
correct controls. Exact baseline PNG bytes and question text were reused.
Cases and provider calls were serialized; no retries or per-case answer tuning.
References were scored after all 27 responses were saved.

| Metric on the same 27 cases | Original single call | Previous Detailed scan | Revised tools |
|---|---:|---:|---:|
| Count matches | 13/27 | 6/27 | **15/27** |
| Previously correct controls retained | 6/6 | 6/6 | **6/6** |
| Provider calls | 27 | 98 | **58** |
| Estimated standard USD | Not recomputed | 1.047318 | **0.718476** |
| Median HTTP seconds | Not recomputed | 18.604 | **10.594** |

The revision repaired **nine previously failed cases**, with no control
regressions. Six of the seven prior regressions were repaired. All 27 requests
returned HTTP 200; all 58 replies included complete usage. Thirteen matches had
status `ok`, and two had status `partial`. The run took 368.433 seconds serially.

Examples:

| Case | Reference | Previous Detailed | Revised |
|---|---:|---:|---:|
| Q043 toilets | 1 | 3 | 1 |
| Q047 fitted doorways | 17 | 18 | 17 |
| Q050 kitchens | 1 | 3 | 1 |
| Q051 floors shown | 1 | 2 | 1 |
| Q054 balconies | 1 | 2 | 1 |
| Q059 fitted doorways | 12 | 15 | 12, with uncertain label hypotheses |
| Q067 windows | 18 | 36 | 18 |
| Q087 doors | 22 | 21 | 22 |
| Q098 finish-schedule rows | 29 | 87 | 29 |

This is failure-focused development testing, **not a new full-100 score**, an
unbiased test set or localization accuracy. These results cannot establish how
the untested previously correct cases will behave under the new prompt.

## Additional experiments and remaining limitations

The original user-supplied large house was retested through the running frontend
proxy/backend after the revision. It returned 13 candidates and localized all
13 approximate assistant-reviewed door boxes at IoU >= 0.5, in 26.599 seconds,
seven calls and estimated USD 0.070674. Status remains partial; this is a
development regression check rather than independently verified ground truth.
Artifacts are under `experiments/runs/raster-v2-house-control/`.

A finer native grid (`tile_size=320,overlap=64`) was tested on Q004 windows,
Q046 showers/baths and Q003 as a control. It used 19 calls and USD 0.155642,
matching only the control. Q004 returned 11 versus reference 15; Q046 returned
zero versus reference one. Finer tiling therefore remains optional rather than
the default; more crops alone did not repair those errors.

Visual inspection suggests Q004 contains tiny openings across two panels despite
its modest 1076x520 size, with both missed openings and probable false positives
on continuous hatched walls. Pixel dimensions alone cannot establish whether
detail is sufficient. Counting grain for adjacent window segments also needs
source adjudication; no definitive replacement reference was created.

Q046 illustrates an omission limitation. The proposed lower fixture is visibly
a basin with a faucet; rejecting it is useful, but a plausible actual shower tray
is partly clipped at the source's bottom edge and was never proposed. Verifying
existing boxes cannot establish absence or recover missed objects. Empty
candidates remain an unverified detection result, not a proven physical zero.

Other remaining cases include small-symbol undercounts, semantic room/unit
membership, and Q099's arithmetic quantity (six assembly regions versus 379
units). Candidate-box tools do not execute the required row multiplicities.

Next bounded work should evaluate independent omission checks for relevant
sectors/wet rooms, opening/frame evidence for windows, native PDF table/row
extraction and typed arithmetic, and specialist or stronger-model comparisons
on remaining visual failures. Those proposed improvements are not implemented
or credited by the scores above.

## Artifacts and checks

Final Windows verification: 219 relevant Python tests, 101 frontend tests,
generated-schema checks, TypeScript and production build passed. Existing
Three/WebGPU export and large-chunk build warnings remain. The UI was checked by
static rendering; the house inference exercised real HTTP through the preview
proxy. Both preview servers remain running on ports 5173 and 8000.

Ignored local directories:

- `experiments/runs/identity-replay-20261114/`: saved-output identity replay.
- `experiments/runs/detail-target-v2-pass1/`: first 14-case live pass.
- `experiments/runs/detail-target-v2-validation/`: 27-case inputs, code snapshot,
  prompts/schemas/provider crops/replies, HTTP outputs, evaluation and report.
- `experiments/runs/detail-target-fine-grid/`: optional fine-grid experiment.
- `experiments/runs/detail-ocr-anchor-check/`: local OCR diagnostics.

Both prior 100-case runs are protected by stored hashes and remained unchanged.
Costs use recorded standard token rates before implicit-cache discounts, credits
and tax. No new runtime answer lookup, training or reference modification was
introduced. Relevant offline tests cover identity, neighboring-object guards,
typed aliases, native pixels, optimized coverage, context frames, membership
decisions, source-label anchors, cancellation, token accounting and harness
completion guards. The frontend shows literal variants and rejected-source
close-ups; browser interaction was not verified in this pass.

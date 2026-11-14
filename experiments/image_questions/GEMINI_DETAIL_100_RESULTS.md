# Detailed scan versus the same 100-image baseline

14 November 2026. Exact same 100 images/questions as the
[79/100 baseline](GEMINI_100_RESULTS.md), with byte-identical saved input PNGs.
**Detailed scan reached 72/100 count matches, seven fewer than the baseline.**
It corrected three cases and regressed on ten. The one successful large-house
demonstration did not predict an overall count-score improvement.

## Fixed experiment

- Current production `POST /api/v1/tools/detect-detail`, `mode=tiles`,
  `max_calls=9`, default tile edge 1400, overlap 200, reinspection enabled.
- Gemini 4 Hydrogen, low thinking, same candidate prompt; no retries, fallback
  model or per-case tuning. The region-selection prompt and reconciliation are
  part of the implemented Detailed scan.
- Exactly one case and one provider call at a time, as requested. An isolated
  loopback server on port 8014 was stopped after the run. The workbench preview
  servers were left running.
- The baseline manifest, questions, raster bytes and source metadata were copied,
  without resampling/rerendering. References were read for scoring only after all
  new responses were saved. The original baseline files remain unchanged.
- Score is exact candidate-list count agreement, including `partial` responses,
  using the same scorer. It is not final-answer or localization accuracy.

## Paired results

| Metric | Original | Detailed scan |
|---|---:|---:|
| Exact count matches | 79/100 | **72/100** |
| Matching count with status `ok` | 79/100 | 61/100 |
| `ok` / `partial` responses | 98 / 2 | 74 / 26 |
| HTTP 200 responses | 100 | 100 |
| Provider calls | 100 | 292 |
| Input tokens | 219,400 | 620,182 |
| Output including thinking | 117,397 | 238,557 |
| Estimated standard USD | 1.209578 | **2.719451** |
| Estimated USD per matching case | 0.01531 | 0.03777 |
| Median case HTTP seconds | 5.792 | 11.403 |
| P95 case HTTP seconds | 15.187 | 49.948 |

69 cases matched in both runs; 18 were wrong in both. All cases stayed in the
denominator. There were no provider, budget, deadline or validation failures.
All 292 calls returned complete usage and the Hydrogen model identifier.
Detailed scan took **1790.553 seconds (29 minutes 50.6 seconds)** serially.
The baseline used six parallel cases, so wall time is not a controlled latency
comparison. Prices are the recorded standard rates before cache/credit/tax.

| Source | Images | Original | Detailed | Change |
|---|---:|---:|---:|---:|
| CubiCasa | 60 | 50 | 46 | -4 |
| Swiss dwellings | 30 | 24 | 25 | +1 |
| IFC-derived floor PDFs | 7 | 3 | 0 | -3 |
| Opening Design | 3 | 2 | 1 | -1 |

Door count matches fell from 4/8 to 2/8; windows from 3/9 to 2/9. Detailed scan
did not improve those count families in this rerun. Across 99 direct-count cases,
excluding the one assembly-multiplicity calculation, it matched 72/99 with mean
absolute error 1.7475, versus 79/99 and 0.5152 previously. The derived case still
returned six assembly candidates rather than computing the 379-unit quantity.

## Changed cases

| Case | Family | Reference | Original | Detailed |
|---|---|---:|---:|---:|
| Q007 | WC fixtures | 1 | 0 | 1 |
| Q038 | Kitchens | 1 | 2 | 1 |
| Q076 | Bathtubs | 3 | 1 | 3 |
| Q043 | WC fixtures | 1 | 1 | 3 |
| Q046 | Showers and bathtubs | 1 | 1 | 3 |
| Q047 | Fitted doorways | 17 | 17 | 18 |
| Q051 | Floors shown | 1 | 1 | 2 |
| Q054 | Balconies | 1 | 1 | 2 |
| Q059 | Fitted doorways | 12 | 12 | 15 |
| Q094 | Columns | 5 | 5 | 8 |
| Q095 | Rooms/spaces | 26 | 26 | 55 |
| Q097 | Windows | 54 | 54 | 56 |
| Q098 | Finish-schedule rows | 29 | 29 | 87 |

## Mechanisms visible in the saved traces

These are post-run diagnoses, not repaired scores or new inference experiments.

- **Reinspection can inflate candidate inventories.** Q043's initial crops each
  report one toilet. Geometry disagreement and another inspection leave three
  uncertain toilet candidates in the final list. Q046 similarly ends with three
  shower candidates for a one-object reference. An unresolved hypothesis is
  currently still another countable candidate.
- **Category drift prevents identity reconciliation.** Q051 sends the same full
  rectangle twice. Each reply finds one floor, but uses `floor_plan` and `floor`.
  Both survive, producing two candidates. Vocabulary must normalize separately
  from literal source labels, and full-page boundary contact should not by itself
  make a large semantic object require reinspection.
- **Almost identical schedule crops are repeated.** Q098's selected region is
  1428 pixels wide, just beyond the 1400 tile edge. Two tiles differ by only
  28 pixels horizontally, and a third reinspection sees the same table. Each
  returns 29 rows; the final list contains 58 `room_schedule_row` and 29 `room`
  candidates. The result is 87, all uncertain. Stable row identities/native text
  extraction and table-specific handling are needed.
- **Global objects fragment under local crops.** Q095 produces 55 room
  candidates, 54 uncertain, against 26. Crops report cut-off spaces and missing
  floor labels. Q094 similarly reports missing `UG1` context and overlapping
  column observations. Those replies directly show context/identity gaps;
  individual false-positive assignments have not all been visually adjudicated.
- **Seam deferral is not the only problem.** Only three responses contain
  deferred fragments (eight total), while 26 responses are partial and 42
  suggested reinspection regions remain. Better edge ownership alone will not
  fix semantic identity and geometry disagreements.

The detector is nondeterministic and this is one paired development run. The
experiment does not isolate layout selection, tiling, reinspection and merging
as separate causal effects, nor does it measure localization across all cases.

## Consequences for the next iteration

Do not treat Detailed scan as a universal accuracy upgrade. Keep whole-page
reasoning available, and evaluate selective escalation after repairing the
reconciliation contract:

1. Separate object instances from alternative observations/hypotheses. An
   unresolved repeat must not automatically increase the final answer count.
2. Normalize target categories, retain source labels, and use stable row/room
   identities or anchors when available; keep conflicting objects inspectable.
3. Pass whole-view context and scope into local analysis. Avoid applying object
   tiling to floor counts, large room polygons and schedule-row totals unchanged.
4. Avoid near-identical tile calls and repeated inspection of the identical
   rectangle. Use native table text/row extraction for schedules.
5. Measure region-only, tiling-only and reinspection/merge changes separately on
   the fixed development cases, followed by project-grouped validation.

No production behavior was changed during this experiment or in response to its
score. The tools remain available to the separately developed decision system.

## Audit and reproduction

Local ignored run:
`experiments/runs/gemini-hydrogen-detail-100/20261114T195020Z/`.

It includes `comparison-plan.json`, exact inputs/source metadata, a production
code snapshot, every actual provider crop/prompt/schema/reply/usage, all HTTP
responses, `evaluation.json`, `results.csv`, `REPORT.md`, `comparison.json`,
`COMPARISON.md` and `audit.json`. The audit verifies all 100 input hashes, question
binding, all returned crop hashes, model configuration, unchanged baseline files,
and nonoverlapping case/provider timelines. Private images remain ignored.

See [rerun commands](README.md#exact-input-detailed-scan-rerun). Twelve offline
harness/scoring tests pass; documentation links and whitespace checks pass.

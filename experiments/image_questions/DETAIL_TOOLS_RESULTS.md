# Automatic detail tools: implementation result

Follow-up: the [same-100 Detailed scan rerun](GEMINI_DETAIL_100_RESULTS.md)
reached 72/100 versus the original 79/100. The single-image result below does not
establish a general accuracy improvement; repeated observations and semantic
identity gaps caused regressions in the broader development sample.

14 November 2026. Windows Python 3.14 / Node 24. The tools and frontend are
implemented; the decision tree is developed separately. See
[tool integration](../../image_api/DETAIL_TOOLS.md).

The final scan was tested through the running Vite proxy on port 5173 and backend
on port 8000 using the authorized `pohjapiirrustus.png`, 4755 x 3364. Panels were
selected automatically. No manual crop or reference annotation entered inference.

| Observation | Result |
|---|---|
| HTTP | 200, valid source-bound response |
| Model | Gemini 4 Hydrogen, low thinking |
| Calls | 7: one panel-selection and six native-detail calls |
| Displayed candidates | 13 |
| Reviewed door boxes localized at IoU >= 0.5 | 13/13, with distinct matching predictions |
| Tool elapsed | 32.553 seconds |
| Total HTTP elapsed | 34.525 seconds |
| Input tokens | 15,035 |
| Output plus thinking tokens | 5,899 |
| Estimated standard cost | USD 0.066795 |
| Status | Partial: four clipped seam observations deferred to overlapping interior views |

The 13 approximate reference boxes were reviewed by the assistant during the
[earlier investigation](LARGE_SCAN_LOCALIZATION.md). They are not independently
verified ground truth. Scoring occurred after saving the model response. This is
one development image and one final HTTP run, not a general reliability score.
The original count-only 100-image benchmark remains unchanged.

The earlier full-page comparison localized 3/13 reference doors despite a
plausible candidate count. A manually selected crop localized 13/13. The final
implemented result uses model-selected panels and host-generated tiles.

Intermediate automatic selection plus one regional detection returned 13
candidates but localized 11/13. Tiling then produced good localized detections
alongside clipped duplicate fragments, yielding 14/15 proposals. Recentered
inspection alone did not consistently resolve them.

The final tile-ownership operation defers a clipped detection when a successful
neighbor sees its center farther from crop edges. Deferred IDs, categories and
source boxes remain in the response and make it partial. Full observations stay
available for conservative reconciliation. No threshold or runtime lookup uses
the expected number of doors.

Source SHA256:
`b1f22265ee380162ac0dd10bf27eef841e3be00467894d9b49e881d2072c8456`.

Ignored local run artifacts:

- `experiments/runs/detail-tools-auto-20261114/`: automatic regional run,
  recorded inputs/prompts/schemas/replies, response, overlay and evaluation.
- `experiments/runs/detail-tools-tiles-20261114/`: first tiled run.
- `experiments/runs/detail-tools-reinspect-20261114/`: recentered-check iteration.
- `experiments/runs/detail-tools-http-20261114/`: final HTTP response,
  per-reference overlap evaluation and original-source overlay.

Intermediate results are preserved. Cost is an estimate before credits, implicit
cache discounts and tax. The final HTTP result was checked without a live browser
interaction; frontend logic/build checks are recorded separately.

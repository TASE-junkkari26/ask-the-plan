# Optional OpenCV window checks

Implemented 15 November 2026. This backend CPU proof of concept consumes only the
submitted upright raster. It does not use DXF, supplied answers, physical units,
new trained models or a stronger inference model.

## Install

Use the project's existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[api,preprocess,vision]"
```

On Linux:

```sh
.venv/bin/python -m pip install -e '.[api,preprocess,vision]'
```

The optional `vision` extra installs CPU-only `opencv-python-headless`, without
GUI/X11 dependencies. Install only one OpenCV wheel family in an environment.
Windows testing used OpenCV 4.14.0.94, NumPy 2.5.4 and Python 3.14.10. Linux
execution was not tested. Standalone drawing-preprocessor/OCR requirements are
unchanged. Without OpenCV, these optional checks skip cleanly.

## Retained path: verify strong raster contradictions

Detailed scan defaults to `opencv_window_checks=true`. On a window question,
OpenCV checks existing window boxes for a predominantly solid dark interior with
no longitudinal bright frame channel. Thin 1–4-pixel glazing is left alone. The
heuristic returns candidate indices; it does not remove or classify objects.

Flagged candidates become uncertain and receive **at most one additional
Hydrogen membership check per question**, within the existing total call budget.
Only an explicit source-aware model rejection removes a candidate. Supported or
ambiguous checks preserve it, and other flagged boxes remain uncertain. There is
no automatic escalation or repeated verification of those unresolved boxes.
Non-window queries and other selected analyzers keep their existing path.

The standard frontend options need no change. To disable the check explicitly:

```json
{"mode":"tiles","max_calls":9,"opencv_window_checks":false}
```

The CPU analysis is bounded to 100 boxes and the existing native source frame.
Its solid-interior threshold is a screening rule, not calibrated confidence.
Dark or unusual glazing can be real; visual verification remains necessary.

## Experimental path: propose omission-inspection strips

`propose_window_regions` uses bounded local-contrast morphology and connected
components to propose at most two native crop regions, including internal
balcony/loggia boundaries. Known window boxes are excluded from proposal work.
Analysis is bounded to an 1800-pixel longest edge; returned half-open bounds map
back to original pixels. Crops remain native, with source hashes and transforms.

This path is **disabled by default** because the live proof of concept did not
improve accuracy. Explicit experiments can request:

```json
{"mode":"tiles","max_calls":9,"opencv_windows":true,"opencv_window_checks":false}
```

It allows at most two extra Hydrogen crop detections inside the total budget.
Empty or failed rescues preserve earlier detections. Crop-edge fragments remain
deferred evidence, not new complete candidates. Optional rescue does not trigger
further membership/edge-inspection cascades. Observations use existing source-frame
reconciliation; CPU lines never become window counts.

## Measured proof of concept

A fixed development set used nine window failures/controls and three non-window
controls, with identical frozen input PNGs, Hydrogen-low and routing disabled.
Source references were read after outputs were saved.

| Original strip trial | Before | OpenCV rescue |
|---|---:|---:|
| Exact reference-count matches | 4/12 | 4/12 |
| Provider calls | 14 | 35 |
| Nominal inference cost | $0.180746 | $0.346957 |

There were 18 CV crop calls; 12 returned no candidates. Source review found three
clear false windows on pedestrian/garage openings, many repeated/cropped
observations, one unresolved framed subunit and one real but clipped glazing
segment. The important Swiss thin-glazing case recovered none of eight audited
misses. This failed trial also exposed downstream-call cascades and clipped
fragment inflation; the integrated experimental path now prevents those, but
no improved score is claimed for the safeguards. The original proposer stays off.

The narrower solid-box check inspected 98 saved window candidates from the
previous 90-drawing evaluation. It flagged only three boxes, all on one source;
agent crop review found all three enclosed solid wall. No apparent real-window
box in that small development sample was flagged. This is not a general precision
or recall guarantee.

For a causal live check, the already saved detector reply was replayed locally,
and only the new membership check called Hydrogen. It rejected one solid-wall
false window. The candidate list changed from 12 to 11; remaining suspicious
boxes stayed uncertain and the response stayed `partial`. The supplied count
also happens to be 11, but this does not establish a complete/correct inventory:
other false positives and omissions can cancel.

Ignored evidence is under `experiments/runs/opencv-windows-20261115/` (`before-12`,
`after-12`, `solid-check-replay`) and the earlier hardening run's
`opencv-region-offline.json` / `opencv-solid-box-offline.json`. Costs use the
recorded nominal tariff, not credits or invoice charges. No stronger model was
used. Synthetic transport tests are distinct from these live/source-reviewed
development observations.

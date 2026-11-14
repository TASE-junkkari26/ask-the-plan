# Live 2D question evaluation

See [results and recommendations](RESULTS.md) for the 14 November 2026 pilot.
This is evaluation tooling, not a new production answer planner. The production
candidate API, prompt, preprocessing defaults and frontend were not changed.

## 100-image Gemini Hydrogen benchmark

See [the 100-image results](GEMINI_100_RESULTS.md): 79/100 exact candidate-count
matches, with complete per-case artifacts and measured usage/timing.

`benchmark.py` runs a fixed, answer-blind count evaluation through the production
HTTP candidate route with the configured Gemini Hydrogen-low client. Its sample
contains 100 distinct drawings: 60 CubiCasa PNGs, 30 Swiss PDFs, seven IFC-derived
floor-plan PDFs and three Opening Design sheets. Sampling cycles through question
families within each source, using seed `20261114`; it does not select by answers.
IFC-derived PDF questions must explicitly concern the shown floor/view.

From the repository root, choose a fresh output directory:

```powershell
$evaluationRun = 'experiments/runs/gemini-hydrogen-100/my-run'
.\.venv\Scripts\python.exe -m experiments.image_questions.benchmark plan --run-dir $evaluationRun
node experiments/image_questions/render_pdfs.mjs $evaluationRun dataset/junction-dataset
.\.venv\Scripts\python.exe -m experiments.image_questions.benchmark run --run-dir $evaluationRun --workers 6
.\.venv\Scripts\python.exe -m experiments.image_questions.benchmark score --run-dir $evaluationRun
```

The isolated loopback server uses port 8012 by default and shuts down after the
run. Only its concurrent-request admission setting changes. The production
prompt/schema, full-source `original` preprocessing, OCR-off behavior, model,
low thinking and output budget remain as configured. There are no retries,
fallback models, repair calls or changes to the running workbench server.
The recording Gemini subclass saves exact instructions/question/schema, image
hashes, raw replies and usage before candidate validation. Credentials and image
data URIs are excluded. Reusing a started run is refused to prevent duplicate calls.

All outputs are saved before the scoring step accesses selected reference
answers. Successful responses must pass the shared contract and match their
submitted image hash/dimensions. Scoring reports exact candidate-list count
agreement and the stricter subset with status `ok`; an abstention or HTTP error
never becomes a predicted zero. Equal counts do not establish correct boxes or
verified final answers. The sample is stratified across sources/families and is
not a corpus-wide or held-out accuracy estimate.

Run artifacts include an answer-free manifest, input PNGs and licenses, source
hashes, API/provider outputs, settings and code snapshots, `REPORT.md`,
`evaluation.json` and a per-case `results.csv`. Standard-rate cost uses reported
input plus output/thinking tokens, before cache discounts, credits and taxes;
missing usage and provider errors are reported separately.

Offline harness checks: `.\.venv\Scripts\python.exe -m unittest tests.test_image_benchmark -v`.

## Earlier Nemotron pilot

The fixed [case manifest](cases.json) contains eight supplied questions and six
source paths, without reference answers. Four CubiCasa families were sampled
independently with Python `random.Random(20261114)` over dataset file order:
doors, windows, toilet bowls and bedrooms. The next draw chose a Swiss
Schlafzimmer-count row; another chose one English room-area question on that
sheet. Two fixed A-801 questions exercise schedule counting and exact lookup.
This stratified development sample is not representative accuracy estimation.

## Reproduce

Use the existing configured Python environment, frontend dependencies and backend
credentials. Each live run sends the named source snapshots and questions to the
configured provider. These commands use eight baseline and six diagnostic calls,
with concurrency one and no retries. There is no training or runtime QA lookup.

From the repository root in PowerShell, choose a fresh run directory:

```powershell
$evaluationRun = 'experiments/runs/image-questions/my-run'
New-Item -ItemType Directory -Path $evaluationRun
Copy-Item experiments/image_questions/cases.json "$evaluationRun/cases.json"
node experiments/image_questions/render_pdfs.mjs $evaluationRun dataset/junction-dataset
.\.venv\Scripts\python.exe -m experiments.image_questions.run run --run-dir $evaluationRun
```

The PDF renderer uses the frontend's installed PDF.js and the same scale/pixel
limits, with Node canvas. Raster sources use upright, white-background PNGs at
source dimensions. This reproduces the API input policy, not a browser interaction
test or a claim of byte-identical browser font rasterization.

`run.py` starts an owned loopback Uvicorn server on port 8011, posts multipart
requests through the real HTTP route and shuts it down gracefully. Its recording
Nemotron subclass changes no inference parameters; it saves the exact system
prompt, question, image hash, raw provider completion and usage before production
parsing. API errors and provider results remain separate. Credentials, request
authorization headers and image data URIs are not written to artifacts.
The runner explicitly selects Nemotron for this baseline, including its saved
API settings, even when the workbench uses `IMAGE_API_PROVIDER=gemini`.

Read reference answers only after baseline responses have been saved. Count
agreement uses the number of candidate records for analysis; it is not a product
answer or proof of inventory completeness. Review original images, boxes, literal
IDs and unsupported states separately.

Optional, post-baseline diagnostics and source-only probes:

```powershell
.\.venv\Scripts\python.exe -m experiments.image_questions.diagnose $evaluationRun
node experiments/image_questions/pdf_anchors.mjs $evaluationRun dataset/junction-dataset
.\.venv\Scripts\python.exe -m experiments.image_questions.native_probe $evaluationRun
```

Diagnostics use fixed crops selected after observing this pilot's failures. They
test two cropped candidate requests and four direct-answer requests. They are
exploratory follow-ups, not an automatic crop policy or held-out improvement.
Crop offsets and resampling factors are saved in each `method.json`.

The native probe reads PDF text positions and one paired Swiss DXF. It handles
this reviewed schedule layout and a single closed straight room polygon in
explicit metre units. It rejects ambiguous containing polygons, bulges, and
nested/overlapping room outlines. It is not a general CAD geometry engine and
does not read `questions.jsonl`. The requested literal room/door IDs are taken
from the fixed case specification. A production importer needs deliberate
contracts, topology/units, page registration and evidence handling.

## Artifacts and boundaries

The local pilot lives at `experiments/runs/image-questions/20261114-live/`.
It contains source hashes/licences, display images, API and provider responses,
exact prompts, timing/usage, overlays, reference comparison, native text anchors,
DXF coordinates, and source snapshots of the experiment scripts. Run artifacts
are ignored by Git. The earlier `20261114-pilot/` contains one sandbox connection
failure with no model completion; it is excluded from accuracy and token totals.

Selected sources retain their supplied attribution: CubiCasa5K (CC BY-NC-SA 4.0),
Swiss Dwellings/Archilyse and organizer renderings (CC BY 4.0), OpeningDesign and
the Xcel project team (CC BY-SA 4.0). Original assets and reference files remain
unchanged. PDF text/paired DXF are source evidence, not reference-answer inputs.

The pilot is Windows/Python 3.14.10 with the installed PDF.js 5.5.207. No browser,
mobile, full-corpus, multilingual or alternative-model evaluation is claimed.

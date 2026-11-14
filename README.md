# Ask the Plan

An evidence-backed construction drawing and BIM question-answering project for
Stoa's **Make Blueprints Talk** challenge. See the [challenge brief](dataset/task.md)
and [repository instructions](AGENTS.md).

Questions default to the drawing/view currently shown, following the organizer
clarification reported on 14 November 2026. Explicit whole-model questions retain
their stated scope. Answers should link to their source objects, properties,
regions, and calculation steps.

## Project scope

**A system that works for the supplied dataset's question families is sufficient
for the hackathon's technical scope.** Its materials and questions define the
required categories, operations, languages, and formats. We do not assume surprise
question classes outside that set. Support different wording within the known
families, with correct answers and inspectable evidence. Broader capabilities are
optional extensions unless a supplied question needs them. See the
[scope and acceptance guide](docs/PROJECT_SCOPE.md).

## Current state

| Component | Implemented | Boundary |
|---|---|---|
| Frontend | Import opening screen, image/PDF/DXF candidate review, IFC 3D inspection and questions with persistent answer highlights and source evidence, searchable import library, exports | Imports last until refresh. DXF preview uses the local backend. Asking uploads the selected image/page/layout or IFC. Synthetic sources stay offline fixtures. |
| DXF preview | Source-bound SVG rendering, model/paper layout selection, omission warnings, existing visual questions and exports | Uses ezdxf on the local backend; 2D previews and unverified image candidates, without native CAD counts or measurements. See [DXF support](docs/DXF_PREVIEW.md). |
| IFC engine | CPU extraction, native metadata and boundary records, bounded topology and boundary-patch/convex-room geometry, related-object projection, scalar queries, exact view scopes and evidence | Independent Python/CLI executor, also used by the IFC question API. Unverified shared-element neighbors remain candidates; incomplete spatial results cannot become exact totals. Generic metric predicates, orientation and routes remain unsupported. |
| Shared contracts | Pydantic models, generated JSON Schemas/TypeScript, reference/unit/scope/evidence validation | Validation cannot prove source completeness or correctness. |
| Nemotron access | Backend sync/async Verda client, local `.env` loading, text/image/validated JSON requests, connection-check CLI, bounded IFC question planning | The IFC engine computes answers from validated plans; image detections remain candidate proposals. Credentials stay on the backend. |
| IFC question API | Revision-bound session uploads, independently selected Nemotron/Gemini planning, bounded source discovery and plan repair, spatial prerequisites, exterior-door queries and deterministic answers | Uses the same local server as image analysis. Exact view scope and explicit model scope remain authoritative. Original sources remain temporary session artifacts for bounded geometry checks. Unknown exterior classifications stay separate; partial counts show lower bounds. Unsupported operations remain non-answers. |
| Image candidate API | Local HTTP image/question endpoint returning candidate boxes from Nemotron or Gemini Hydrogen-low, with uncertainty, image hashes and display coordinates | Connected to imported 2D drawings; one selected image provider per request, candidate proposals only, with no final counts/answers or IFC analysis. |
| Raster preprocessing | Standalone source/crop/overview artifacts, coordinate transforms, optional local Tesseract OCR, inspection-tool adapter, and bounded image-API session preparation | API defaults to unchanged model input with OCR off; optional full-source overview mode preserves page layout. No semantic room segmentation, physical calibration, or agent tool loop. |
| Perception | Research plans and a saved one-image door-labeling experiment | No evaluated general raster inventory/reconstruction or model routing. Standalone optional OCR is documented separately. |

## Configure Nemotron

First [install the Python project](#install-and-use-the-ifc-engine). The frontend
prototype runs independently and does not need credentials. From the repository root,
create `.env` from [.env.example](.env.example) only if it does not already exist:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

On Linux, use `test -f .env || cp .env.example .env`. Set `VERDA_INFERENCE_KEY`
in that local file. It is ignored by Git; the endpoint/model defaults are supplied
hackathon settings, not a guarantee of deployment availability. Existing shell
settings override file values. Credentials stay on the backend.

Check the connection with one short live inference request:

```powershell
.\.venv\Scripts\python.exe -m nemotron check
```

On Linux, use `.venv/bin/python -m nemotron check`. This sends a request to Verda;
local tests do not require a key or make inference calls. Installation also
provides the `nemotron` console command. See [Nemotron setup and usage](docs/nvidia_info.md)
for image, JSON, and async examples.

## Run the image candidate API

Choose the image provider in the existing backend `.env`. To use Gemini, keep
your existing `GEMINI_API_KEY` and add:

```dotenv
IMAGE_API_PROVIDER=gemini
```

Gemini image analysis uses `gemini-4-hydrogen` with low thinking. The default
provider is `nemotron`, which uses the existing `VERDA_*` settings. IFC questions
use the separate `IFC_API_PROVIDER` selector, defaulting to Nemotron. To use
Hydrogen for IFC planning, set `IFC_API_PROVIDER=gemini`; its independent
`IFC_GEMINI_THINKING_LEVEL` defaults to `high`. Preserve both
keys and existing settings; see [provider setup](image_api/README.md#choose-the-image-provider).

Install the API extra and start the service:

```sh
.venv/bin/python -m pip install -e '.[api,preprocess,test]'
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

On Windows, use `.\.venv\Scripts\python.exe` for both commands. Open
<http://127.0.0.1:8000/docs> to submit one image and one question. The API returns
image-bound candidate boxes, not a final answer/count. Leave this backend running
and start `npm run dev` in a second terminal. In the UI, import a drawing, select
its image/PDF page or DXF layout, and submit a question to see candidate boxes and a review list.
Images/PDFs preview in the browser; DXF import uploads the original to the local backend
for layout rendering, without inference. Image/PDF/DXF questions send the
displayed raster to the selected image provider through the backend. The backend prepares a canonical
upright PNG before optional raster preprocessing. Its default `original` mode
caches preparation without changing model input; opt-in `overview` mode sends
only the uncropped full-source overview and maps boxes back to the original
display coordinates. OCR stays off in this path. IFC questions use separate
`/api/ifc` endpoints on this same server: the local backend extracts the original
model, the selected IFC planner proposes a query, and the IFC engine returns the answer and
highlightable source elements. See [IFC questions](docs/IFC_QUESTIONS.md) and
[image API usage and UI handoff](image_api/README.md) for multipart
examples, generated types, coordinates, limits, and errors.

## Start the frontend

Run these commands from this repository root, `ask-the-plan/`. Node.js **22.12+**
is required; the frontend has been built with **24 LTS**. Install Node/npm before
running npm commands; dependency installation does not install Node itself.

Windows PowerShell:

```powershell
node --version
npm.cmd --version
npm.cmd run setup:frontend
npm.cmd run dev
```

Linux:

```sh
node --version
npm --version
npm run setup:frontend
npm run dev
```

Open the Local URL printed by Vite, normally <http://127.0.0.1:5173/>. The server
binds to localhost. These root scripts forward to `frontend/`; its lockfile and
dependencies live there. **Do not run `npm ci` at the repository root.** The
`setup:frontend` script uses the frontend lockfile with dependency install scripts
disabled. It can be skipped if dependencies are already installed and unchanged.

For Windows terminals opened before Node was installed, restart the parent
terminal/VS Code, or refresh just the current process with:

```powershell
$env:Path += ';C:\Program Files\nodejs'
```

Use `npm.cmd` if PowerShell blocks the `npm.ps1` wrapper; no execution-policy
change is needed. See [frontend details](frontend/README.md) for import behavior,
keyboard controls, generated types, and the backend integration boundary.

## Prepare a raster drawing

Install the CPU preprocessing dependencies with the configured Python. From a
checkout, this standalone path also works without the IFC/inference dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r drawing_preprocessor/requirements.txt
.\.venv\Scripts\python.exe -m drawing_preprocessor prepare "path/to/drawing.png" --output build/prepared
```

On Linux, create a separate environment and run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r drawing_preprocessor/requirements.txt
.venv/bin/python -m drawing_preprocessor prepare path/to/drawing.png --output build/prepared
```

This creates a portable manifest, an exact copy
of the original, a full-resolution PNG, candidate content crops, smaller
overviews, and a layout preview. `inspect` crops original detail using a registered
view ID. OCR is off by default and is not required for preprocessing. To enable it:

```powershell
.\.venv\Scripts\python.exe scripts/setup_tesseract.py
.\.venv\Scripts\python.exe scripts/setup_tesseract.py --check
```

Windows setup extracts a hash-verified engine into the ignored `.tools/` folder
and installs English, Finnish, German, French, Italian, and Swedish data. The
preprocessor discovers it automatically. On Debian/Ubuntu, optional OCR needs
`sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-fin`;
then use `--ocr tesseract --ocr-languages eng+fin` on either OS. This recognizes
text and word boxes; it does not measure rooms or validate dimensions.

Generate a portable human-review gallery with:

```text
python -m drawing_preprocessor review dataset/junction-dataset --output build/preprocess-review --count 50 --seed 20261114
```

Use the configured Python path above in place of `python`. Serve the gallery:

```text
python -m drawing_preprocessor serve build/preprocess-review --port 8765
```

Open <http://127.0.0.1:8765/>, mark pass/problem/uncertain, add notes, and download
the review JSON. This serves only the chosen gallery on loopback and works on
Windows/Linux. Prefer it over opening `index.html` directly: local-file access
or Windows artifact permissions can prevent browser image loading. Existing
file-page ratings can be exported there and imported into the HTTP gallery.
No inference API is called. See the
[preprocessor guide](docs/DRAWING_PREPROCESSOR.md) for coordinate semantics,
OCR setup, function-tool registration, and limitations.

## Install and use the IFC engine

Python **3.10+** and a compatible IfcOpenShell wheel are required. Python 3.12 is
the reported Linux backend baseline. Create a separate virtual environment for
each OS; do not copy virtual environments or native `node_modules` across OSes.

Windows PowerShell (no environment activation required):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m ifc_engine --help
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m ifc_engine --help
.venv/bin/python -m unittest discover -s tests -v
```

The dataset is optional for the synthetic IFC regression fixtures. The real-model
test uses `dataset/junction-dataset-preview/data/ifc_models/` and skips if its
Esplanades file is absent. A full-only or nested extraction does not satisfy that
particular test path. See the [IFC engine guide](docs/IFC_ENGINE.md) for real-file commands, supported operations,
scope/unit semantics, and limitations. The CLI remains independent; the IFC
question API reuses the same executor.

The [verification record](docs/VERIFICATION.md) gives the latest commands,
platform versions, results, and limits. Windows Python, frontend logic, schema,
and build checks passed on 14 November 2026, including the installed preview's
real-model test. Separate Linux checks cover the image candidate API, candidate
UI integration, local imports/PDF previews, and IFC inspection. The verification
record distinguishes those passes from checks of their combined merge and from
target-device checks that remain outstanding.
Nemotron's HTTP tests use mocked responses; earlier live text/image observations
and the saved door-labeling pilot are recorded separately from this offline pass.

## Checks and generated contracts

From the root, use `npm.cmd` on Windows and `npm` on Linux:

| Command | Purpose |
|---|---|
| `npm.cmd run test:frontend` | Frontend fixture, cancellation, identity, and viewport logic tests |
| `npm.cmd run build` | TypeScript checks and production frontend bundle |
| `npm.cmd run preview` | Serve the production build after building |
| `python scripts/check_docs.py` | Check project Markdown links/images, heading and source-line anchors offline |
| `python -m contracts.export --check` | Detect stale generated JSON Schemas |

For Python checks, `python` in this table means the configured interpreter
(for example `.venv/bin/python` or `.\.venv\Scripts\python.exe`). If only editing
contracts, install `contracts/requirements.txt` and run
`python -m unittest tests.test_contracts -v`; the full suite needs the project's
`.[test]` installation, including IfcOpenShell and the Nemotron client dependencies.

After modifying `contracts/models.py`, regenerate both schema and frontend types:

```text
python -m contracts.export
python -m contracts.export --check
npm.cmd --prefix frontend run generate:contracts
```

Replace `npm.cmd` with `npm` on Linux. Generated files are tracked; edit their
Python source models rather than editing the generated output.

## Repository map

```text
frontend/       Browser prototype and generated TypeScript wire types
ifc_engine/     Local IFC extraction and structured query execution
nemotron/       Backend Verda text/vision client and connection-check CLI
gemini/         Backend Gemini Hydrogen image and structured-text transport
image_api/      Local image/question HTTP service returning candidate boxes
ifc_api/        Local IFC upload, bounded source discovery and selectable planner
dxf_api/        Local DXF layout rendering for preview and visual questions
drawing_preprocessor/  CPU raster preparation and source-inspection tool adapter
experiments/    Reproducible model experiments, prompts, and findings
contracts/      Shared models, validation, JSON Schemas, synthetic examples
tests/          Contract, IFC, Nemotron, reporting, and documentation checks
scripts/        Repository maintenance and dataset-question analysis
docs/           Implementation guides and dated design/research notes
dataset/        Challenge brief, audit reports, optional local drawing archives
```

The drawing archives are excluded from Git. See the brief for download links;
keep each source's attribution/license and leave original drawings/reference
answers unchanged. The examples use `dataset/junction-dataset/` for the full data
and `dataset/junction-dataset-preview/` for the preview. Each root must contain
`questions.jsonl` and `data/`. Some extraction tools add another directory level;
adjust commands to the actual root rather than assuming that layout.

## Documentation

| Guide | Role |
|---|---|
| [Hackathon roadmap](docs/ROADMAP.md) | Current build order, minimal evidence UI, model decision gates, and overnight-work choices |
| [Project scope](docs/PROJECT_SCOPE.md) | Dataset-defined acceptance boundary and required work versus extensions |
| [Verification record](docs/VERIFICATION.md) | Checks rerun for this hardening pass and remaining verification gaps |
| [Question classification](docs/QUESTION_CLASSIFICATION.md) | Generated, exhaustive analysis taxonomy; no runtime answers |
| [Dataset research](docs/DATASET_RESEARCH.md) | Template concentration and proposed answering pipeline |
| [Schema](docs/SCHEMA.md) | Contract structure, invariants, query/result types, and validation boundaries |
| [IFC viewer](docs/IFC_VIEWER.md) | Browser 3D viewing, local conversion, inspector, controls, assets, and limits |
| [IFC questions](docs/IFC_QUESTIONS.md) | Independent planner settings, source discovery, exterior doors, exact scopes and engine evidence |
| [IFC planner comparison](experiments/ifc_planners/README.md) | Credential-free 24-case replay and explicit live provider comparison |
| [IFC engine](docs/IFC_ENGINE.md) | Current backend/CLI behavior and supported operations |
| [Frontend](frontend/README.md) | Current local-preview UI, startup, testing, and integration boundary |
| [DXF preview](docs/DXF_PREVIEW.md) | DXF import, selected layouts, rendering limits, visual questions and source hashes |
| [Computational capabilities](docs/COMPUTATIONAL_CAPABILITIES.md) | Capability backlog with implemented versus planned status |
| [Frontend visualization](docs/FRONTEND_VISUALIZATION.md) | Viewer architecture and future answer/evidence integration |
| [Evidence and platform requirements](docs/FRONTEND_EVIDENCE_REQUIREMENTS.md) | Q01-Q20 evidence requirements and Linux/Windows boundaries |
| [Tech stack recommendation](docs/TECH_STACK_RECOMMENDATION.md) | Dated architecture rationale and candidate components |
| [OCR recommendations](docs/ocr_recs.md) | Perception candidates and evaluation gates; not an installed pipeline |
| [Nemotron configuration](docs/nvidia_info.md) | Implemented backend client, local key setup, usage, and live-verification boundary |
| [Image candidate API](image_api/README.md) | HTTP setup, candidate contracts, image coordinates, and frontend handoff |
| [Raster preprocessor](docs/DRAWING_PREPROCESSOR.md) | Cached content crops/overviews, optional local OCR, coordinates and backend inspection-tool adapter |
| [Experiments](experiments/README.md) | Reproducible investigations, starting with raster door labeling |
| [Full dataset findings](dataset/FULL_DATASET_FINDINGS.md) | Full-corpus audit and source-specific pitfalls |
| [Preview findings](dataset/DATASET_FINDINGS.md) | Historical preview-only audit |
| [Compute notes](dataset/compute.md) | Reported credit grants; not a live balance |

Keep credentials in backend environment variables. No credentials or private
source files are required to start the frontend. A documented endpoint, a schema
variant, or a mock answer does not establish a working integration or model accuracy.

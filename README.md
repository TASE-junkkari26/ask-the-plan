# Ask the Plan

An evidence-backed construction drawing and BIM question-answering project for
Stoa's **Make Blueprints Talk** challenge. See the [challenge brief](dataset/task.md)
and [repository instructions](AGENTS.md).

Image/PDF/DXF questions use the drawing/page/layout currently shown. IFC questions
always use the entire imported IFC model, regardless of viewer filters or section
cuts. Answers should link to their source objects, properties, regions, and
calculation steps.

## Quick start

Run these commands from the **repository root**. Install **Node.js 22.12+**
(24 LTS is the tested frontend baseline) and **Python 3.10+** with an available
IfcOpenShell wheel (3.12 is the reported Linux backend baseline).

### 1. Install dependencies once

Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[api,preprocess,vision]'
npm run setup:frontend
test -f .env || cp .env.example .env
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[api,preprocess,vision]"
npm.cmd run setup:frontend
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

These commands preserve an existing `.env`. Virtual-environment activation is
not required; create a separate native environment on each OS.

### 2. Configure the backend

In the root `.env`, update the existing entries below and fill in your Gemini
API key locally:

```dotenv
IMAGE_API_PROVIDER=gemini
IFC_API_PROVIDER=gemini
GEMINI_API_KEY=
```

The workbench's **Detailed scan** requires the Gemini image provider. This quick
start also selects Gemini for IFC planning; to use Nemotron for IFC instead, set
`IFC_API_PROVIDER=nemotron` and configure `VERDA_INFERENCE_KEY` as described in
[Configure Nemotron](#configure-nemotron). Keep credentials in the backend `.env`.

### 3. Start both servers

**Terminal 1 — backend** (leave it running):

Linux:

```sh
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend**, also from the repository root:

Linux:

```sh
npm run dev
```

Windows PowerShell:

```powershell
npm.cmd run dev
```

Open the URL printed by Vite, normally <http://127.0.0.1:5173/>, import an IFC,
image, PDF or DXF file, and ask a question. Backend API documentation is at
<http://127.0.0.1:8000/docs>. Keep both servers running while using questions or
DXF previews; `npm run dev` starts the frontend only.

For later launches, repeat **step 3**. Restart the backend after changing `.env`.
Stop each server with **Ctrl+C** in its terminal. For connection errors, see
[troubleshooting](image_api/README.md#troubleshoot-the-frontend-connection).

## Project scope

**A system that works for the supplied dataset's question families is sufficient
for the hackathon's technical scope.** Its materials and questions define the
required categories, operations, languages, and formats. We do not assume surprise
question classes outside that set. Support different wording within the known
families, with correct answers and inspectable evidence. Broader capabilities are
optional extensions unless a supplied question needs them. See the
[scope and acceptance guide](docs/PROJECT_SCOPE.md).

## Current state

The workbench uses a shared [natural-language answer pipeline](docs/NATURAL_LANGUAGE_ANSWERS.md)
with source-bound parts, deterministic wording, clickable evidence and exports.
It reuses IFC execution, adds scalar arithmetic and independent compound outputs,
and supports native PDF text/schedule tools. Drawing detections remain qualified
observations. The [implementation plan](docs/NATURAL_LANGUAGE_ANSWERS_PLAN.md)
and offline family ledger retain the remaining acceptance work; complete
dataset-family coverage has not been established.

The frontend uses **Detailed scan** by default for drawing questions, without a
mode checkbox. It requires the Gemini image provider. It uses automatic
panel selection, native overlapping tiles and source-bound reconciliation through
the [callable detail tools](image_api/DETAIL_TOOLS.md). These operations are
integrated with the fetched capability router: it selects
Hydrogen or Carbon once, then the detail tools inspect native crops with per-call
model/cost evidence. The individual tools remain independently callable.

| Component | Implemented | Boundary |
|---|---|---|
| Frontend | Import opening screen, image/PDF/DXF candidate review, IFC 3D inspection and questions with persistent answer highlights and source evidence, searchable import library, exports | Imports last until refresh. DXF preview uses the local backend. Asking uploads the selected image/page/layout or IFC. Synthetic sources stay offline fixtures. |
| DXF preview | Source-bound SVG rendering, model/paper layout selection, omission warnings, existing visual questions and exports | Uses ezdxf on the local backend; 2D previews and unverified image candidates, without native CAD counts or measurements. See [DXF support](docs/DXF_PREVIEW.md). |
| IFC engine | CPU extraction, native metadata and boundary records, bounded topology and geometry, scalar/table arithmetic, source measurements, modeled walking routes, distribution-network metrics and evidence | Independent Python/CLI executor, also used by the IFC question API. Unverified neighbors remain candidates; incomplete results cannot become exact totals. Measurements and potential routes retain explicit methods and uncertainty; generic orientation and compliance checks remain unsupported. |
| Shared contracts | Pydantic models, generated JSON Schemas/TypeScript, reference/unit/scope/evidence validation | Validation cannot prove source completeness or correctness. |
| Nemotron access | Backend sync/async Verda client, local `.env` loading, text/image/validated JSON requests, connection-check CLI, bounded IFC question planning | The IFC engine computes answers from validated plans; image detections remain candidate proposals. Credentials stay on the backend. |
| IFC question API | Revision-bound session uploads, conservative zero-call native planning, independently selected Nemotron/Gemini planning, bounded source discovery and plan repair, deterministic execution and evidence | Uses the same local server as image analysis. The common answer UI uses the whole model with question-defined filters; direct IFC clients can request exact view scope. Original sources remain temporary session artifacts. Unknown exterior classifications stay separate; partial counts show lower bounds. Unsupported operations remain non-answers. |
| Image candidate API | Local HTTP image/question endpoint returning candidate boxes from Nemotron or Gemini Hydrogen-low/Carbon-medium, with uncertainty, image hashes, display coordinates and optional capability routing | Connected to imported 2D drawings; one selected analyzer per question with bounded detail calls, candidate proposals only, with no final counts/answers or IFC analysis. |
| Raster preprocessing | Standalone source/crop/overview artifacts, coordinate transforms, optional local Tesseract OCR, inspection-tool adapter, and bounded image-API session preparation | API defaults to unchanged model input with OCR off; optional full-source overview mode preserves page layout. No semantic room segmentation, physical calibration, or agent tool loop. |
| Perception | Experimental opt-in Gemini capability routing, recorded expandable decision path, research plans and saved image experiments | Routing is off by default pending paired evaluation/calibration. No evaluated general raster inventory/reconstruction. Standalone optional OCR is documented separately. |

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

Experimental [capability routing](image_api/README.md#experimental-capability-routing)
can recommend or select Hydrogen-low versus Carbon-medium from the selected image
and question. It is off by default; its threshold is provisional. The UI exposes
the recorded decision path, including failures, with per-call cost accounting.
During analysis the loading screen also shows the actual selected model as soon
as routing dispatches it, before its candidate response finishes.

Install the API extra and start the service:

```sh
.venv/bin/python -m pip install -e '.[api,preprocess,test,vision]'
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

On Windows, use `.\.venv\Scripts\python.exe` for both commands. Open
<http://127.0.0.1:8000/docs> for the source/answer and existing candidate routes.
The candidate endpoint returns proposals; the common answer endpoint returns
qualified observations or executed source-backed values. Leave this backend running
and start `npm run dev` in a second terminal. In the UI, import a drawing, select
its image/PDF page or DXF layout, and submit a question to see an answer and inspectable evidence.
Images/PDFs preview in the browser; DXF import uploads the original to the local backend
for layout rendering, without inference. Image/PDF/DXF questions send the
displayed raster to the selected image provider through the common answer coordinator,
after registering the original and snapshot at `/api/v1/sources`. Native PDF tools
read the registered original. The backend prepares a canonical
upright PNG before optional raster preprocessing. Its default `original` mode
caches preparation without changing model input; opt-in `overview` mode sends
only the uncropped full-source overview and maps boxes back to the original
display coordinates. OCR stays off in this path. IFC questions register the
original through `/api/ifc` and use the common `/api/v1/answers` coordinator on
this same server. The local backend extracts the model, compiles supported
questions or asks the selected IFC planner for a query, and executes it with
highlightable source elements. Direct `/api/ifc` question endpoints remain available.
See [IFC questions](docs/IFC_QUESTIONS.md) and
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
document_engine/  Temporary original/display sessions and native PDF/table tools
answer_api/     Common answer coordination, budgets and deterministic wording
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
| [Natural-language answers](docs/NATURAL_LANGUAGE_ANSWERS.md) | Implemented common pipeline, native tools, evidence and remaining acceptance gaps |
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

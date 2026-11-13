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
| Frontend | React workbench, synthetic drawings/answers, selectable overlays, calculations, local image/PDF preview, export | Mock adapter; no backend/model calls or IFC 3D viewer. Uploaded files are not analysed. |
| IFC engine | CPU extraction, structured selection/traversal, scalar properties/quantities, counts, grouping/ranking, evidence and caching | Standalone Python/CLI; no natural-language planner, HTTP API, or geometry-measurement engine. |
| Shared contracts | Pydantic models, generated JSON Schemas/TypeScript, reference/unit/scope/evidence validation | Validation cannot prove source completeness or correctness. |
| Perception and services | Research and capability plans | OCR, raster detection/reconstruction, model routing, and frontend/backend HTTP integration remain work to implement. |

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
change is needed. See [frontend details](frontend/README.md) for demo behavior,
keyboard controls, generated types, and the backend integration boundary.

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

The dataset is optional for the synthetic IFC regression fixtures. Tests using
real model files may skip if their expected dataset layout is absent. See the
[IFC engine guide](docs/IFC_ENGINE.md) for real-file commands, supported operations,
scope/unit semantics, and limitations. This CLI is independent of the mock UI.

Checks on 14 November 2026: Windows Python 3.14 passed 63 tests with one optional
dataset-layout skip; separate full-dataset IFC CLI checks reproduced the selected
door counts and stored-area total in the guide. Frontend logic tests and the
production build passed with Node 24 LTS. Reported Linux backend checks used
Python 3.12.3. Browser/end-to-end UI verification remains outstanding.

## Checks and generated contracts

From the root, use `npm.cmd` on Windows and `npm` on Linux:

| Command | Purpose |
|---|---|
| `npm.cmd run test:frontend` | Frontend fixture, cancellation, identity, and viewport logic tests |
| `npm.cmd run build` | TypeScript checks and production frontend bundle |
| `npm.cmd run preview` | Serve the production build after building |
| `python scripts/check_docs.py` | Check project Markdown links and heading anchors, without network access |
| `python -m contracts.export --check` | Detect stale generated JSON Schemas |

For Python checks, `python` in this table means the configured interpreter
(for example `.venv/bin/python` or `.\.venv\Scripts\python.exe`). If only editing
contracts, install `contracts/requirements.txt` and run
`python -m unittest tests.test_contracts -v`; the full suite also needs IfcOpenShell.

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
contracts/      Shared models, validation, JSON Schemas, synthetic examples
tests/          Python contract and IFC regression tests
scripts/        Repository maintenance checks
docs/           Implementation guides and dated design/research notes
dataset/        Challenge brief, audit reports, optional local drawing archives
```

The drawing archives are excluded from Git. See the brief for download links;
keep each source's attribution/license and leave original drawings/reference
answers unchanged. Extracted archive layouts can differ: this checkout has the
full dataset at `dataset/junction-dataset/` and the preview nested under
`dataset/junction-dataset-preview/junction-dataset-preview/`.

## Documentation

| Guide | Role |
|---|---|
| [Project scope](docs/PROJECT_SCOPE.md) | Dataset-defined acceptance boundary and required work versus extensions |
| [Schema](docs/SCHEMA.md) | Contract structure, invariants, query/result types, and validation boundaries |
| [IFC engine](docs/IFC_ENGINE.md) | Current backend/CLI behavior and supported operations |
| [Frontend](frontend/README.md) | Current mock UI, startup, testing, and integration boundary |
| [Computational capabilities](docs/COMPUTATIONAL_CAPABILITIES.md) | Capability backlog with implemented versus planned status |
| [Frontend visualization](docs/FRONTEND_VISUALIZATION.md) | Viewer architecture and future IFC integration |
| [Evidence and platform requirements](docs/FRONTEND_EVIDENCE_REQUIREMENTS.md) | Q01-Q20 evidence requirements and Linux/Windows boundaries |
| [Tech stack recommendation](docs/TECH_STACK_RECOMMENDATION.md) | Dated architecture rationale and candidate components |
| [OCR recommendations](docs/ocr_recs.md) | Perception candidates and evaluation gates; not an installed pipeline |
| [Nemotron configuration](docs/nvidia_info.md) | Supplied endpoint notes; access/integration still needs verification |
| [Full dataset findings](dataset/FULL_DATASET_FINDINGS.md) | Full-corpus audit and source-specific pitfalls |
| [Preview findings](dataset/DATASET_FINDINGS.md) | Historical preview-only audit |
| [Compute notes](dataset/compute.md) | Reported credit grants; not a live balance |

Keep credentials in backend environment variables. No credentials or private
source files are required for the frontend demo. A documented endpoint, a schema
variant, or a mock answer does not establish a working integration or model accuracy.

# Repository instructions

All paths below are relative to this checkout (`ask-the-plan/`), not its parent.
Read [the challenge brief](dataset/task.md), [README](README.md), and the relevant
component guide before changing behavior.

## Product and scope

- The supplied dataset defines the hackathon acceptance scope. A working system
  for its demonstrated question families is sufficient; do not add requirements
  for hypothetical unknown evaluation classes. Read [project scope](docs/PROJECT_SCOPE.md).
  Trace required capabilities to supplied questions. Broader schema support and
  possible product extensions are not mandatory hackathon work. Paraphrase and
  translation checks stay within those known families.
- Answer questions about construction drawings/BIM accurately, cheaply, and with
  source evidence a person can inspect. The four judging criteria are equally
  weighted: accuracy, verifiability, creativity, and inference cost.
- Organizer clarification reported on 14 November 2026: questions should mostly
  concern what is shown. The frontend defaults to the selected drawing/view.
  Never silently broaden that to a whole model/building. Existing reference rows
  that explicitly ask model-wide questions still require their stated scope.
- Preserve literal source identifiers and original language. Normalize concepts
  separately; do not translate identifiers such as `121.A` or `7.16`.
- Keep missing, not modeled, not extracted, ambiguous, partial, and zero distinct.
  Counts state their grain; quantities retain units and net/gross meaning.
- Return source anchors, included/excluded objects, and calculation inputs. An
  explanation or highlight alone does not establish a correct answer.

## Component boundaries

- `frontend/`: React/TypeScript/Vite workbench that opens on local import;
  synthetic sources and the mock adapter `src/demo/engine.ts` remain offline
  fixtures. Imported images/PDFs/DXFs submit their displayed raster/page/layout to `image_api/`
  and render unverified candidate boxes. IFC imports render locally; asking uploads
  the original model to `ifc_api/` for source-backed query execution and evidence.
  See [the viewer guide](docs/IFC_VIEWER.md).
- `dxf_api/`: bounded local ezdxf rendering of one source layout into a source-hash-bound
  SVG preview. DXF import uploads the original to this credential-free endpoint;
  visual questions use the existing image candidate flow. Preserve selected layout
  names, source visibility, partial-rendering warnings and hashes. This is not a
  native CAD query executor. See [the DXF guide](docs/DXF_PREVIEW.md).
- `image_api/`: internal HTTP adapter for one image and one question, using the
  selected Nemotron or Gemini image provider. Returns candidate regions, not
  final counts/answers.
  Its bounded session preprocessor cache consumes the already-upright display
  PNG. Default `original` mode preserves inference pixels; optional `overview`
  mode uses the full page, never heuristic region roles. Public source hashes,
  display dimensions and box coordinates remain bound to the submitted snapshot.
- `ifc_engine/`: independent CPU IFC extractor/structured query executor. See
  [its guide](docs/IFC_ENGINE.md) for supported operations and limitations. It is
  not an HTTP service or natural-language planner.
- `ifc_api/`: revision-bound temporary source sessions, bounded metadata
  discovery/inspection, independently selected Nemotron or Hydrogen planning,
  and deterministic engine answers. Preserve exact captured view scope and
  distinct doors/rooms/counting grain. Exterior-door unknowns remain unresolved;
  partial membership produces lower bounds, never an exact total or physical zero.
- `nemotron/`: backend-only sync/async Verda client and text/image/JSON CLI.
  See [its guide](docs/nvidia_info.md). Loads local `.env` settings; model outputs
  are proposals, not validated source evidence. IFC planning uses this client by
  default; the native executor computes the answer.
- `gemini/`: backend-only native Gemini Interactions transport. Images use
  Hydrogen-low or Carbon-low/medium with optional capability routing;
  independently configured Hydrogen IFC planning uses `IFC_API_PROVIDER` and
  `IFC_GEMINI_THINKING_LEVEL`. Keep image/IFC settings and client lifetimes separate.
  Use the same source discovery, plan validation, executor and evidence for both
  planners. Never interpret top-k search results as a complete count inventory.
- `contracts/models.py`: source of truth for shared wire contracts.
  `contracts/validation.py` checks consistency, not source truth or all geometry.
- `drawing_preprocessor/`: standalone raster preparation, optional local OCR,
  and source inspection. See [its guide](docs/DRAWING_PREPROCESSOR.md). Layout
  candidates are not semantic views, complete object inventories, or calibration.
  Standalone setup is `python -m pip install -r drawing_preprocessor/requirements.txt`.
  OCR stays optional/off by default. On Windows, `python scripts/setup_tesseract.py`
  installs a verified local engine/data under ignored `.tools/`; on Debian/Ubuntu
  use `apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-fin` when needed.
  Use `TESSERACT_CMD`/`TESSDATA_PREFIX` only as backend overrides. Preserve source
  frames when preparing review crops; human review exports are not runtime QA.
  View generated galleries with `python -m drawing_preprocessor serve DIRECTORY`
  on loopback rather than direct file links; preserve existing review IDs/notes.
- `contracts/jsonschema/` and `frontend/src/contracts/`: generated files. Change
  the Python models, regenerate both outputs, and check relevant consumers.
- `dataset/`: supplied challenge inputs and investigation reports. Leave drawing
  assets, licenses, and reference answers unchanged unless explicitly asked.
  Do not turn supplied QA into a runtime answer lookup or training leakage.
- `docs/`: guides, capability inventory, and dated design/research notes. Keep
  implemented behavior, proposed work, synthetic examples, and reported tests
  clearly distinguished.

Keep frontend changes separate from parser/backend changes when possible. Other
developers may be working in this checkout; preserve their work and inspect the
current diff before editing shared files.

## Commands

Run commands from the repository root. Node.js 22.12+ is required; 24 LTS is the
project's tested frontend baseline. Use `npm.cmd` in Windows PowerShell to avoid
the blocked `npm.ps1` wrapper; use `npm` on Linux. Do not weaken execution policy.

```text
npm.cmd run setup:frontend   # locked frontend install, dependency scripts disabled
npm.cmd run dev              # root entry point; forwards to frontend/
npm.cmd run build
npm.cmd run test:frontend
```

The root `package.json` contains forwarding scripts. The dependency lockfile is
`frontend/package-lock.json`; do not run root `npm ci` expecting app dependencies.

Python requires 3.10+ and an IfcOpenShell wheel for the chosen version/platform;
3.12 is the reported Linux backend baseline. Use a virtual environment and the
commands in README. Without backend dependencies, the contract-only check is
`python -m unittest tests.test_contracts -v` after installing
`contracts/requirements.txt`. The full Python suite also requires IfcOpenShell.

After contract changes, using the configured Python/Node environment:

```text
python -m contracts.export
python -m contracts.export --check
npm.cmd --prefix frontend run generate:contracts
```

Use `python scripts/check_docs.py` for local Markdown links/anchors. Validate
checks relevant to the change; do not describe schema checks or synthetic
fixtures as end-to-end model accuracy or browser verification.

## Development and delivery

- Keep Windows/Linux paths portable with `pathlib` and source IDs/resource URLs.
  Do not hardcode a developer's machine paths in application code. Create native
  dependencies/virtual environments separately per OS.
- Keep credentials in backend environment variables. The supplied Nemotron
  configuration is documented in [nvidia_info.md](docs/nvidia_info.md); access
  and model behavior are not verified merely by that note. Never expose API keys
  in browser code, `VITE_*` variables, examples, or logs.
- Respect source hashes, revision-scoped IDs, coordinate frames, and calibration.
  One canonical object can have many depictions; visible mark counts must not
  become the answer computation.
- New query operations require deliberate contract, executor, capability, and
  evidence handling. Do not advertise an operation because its UI can draw it.
- Keep docs synchronized when startup commands, integration status, or component
  boundaries change. Record test platform and any skipped checks honestly.
- Leave a requested preview server running; otherwise clean up owned temporary
  servers. Do not terminate another developer's server or process.
- Do not commit or deploy unless requested for the current work.

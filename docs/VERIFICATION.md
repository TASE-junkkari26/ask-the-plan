# Sprint-one verification record

Checked 14 November 2026 on Windows, using the existing virtual environment and
frontend dependencies. This records checks performed during the documentation
hardening pass. It does not establish complete hackathon question coverage.

## Environment and commands

Python 3.14.10, IfcOpenShell 0.9.0.post1, Pydantic 2.14.3; Node 24.22.3 and npm
11.19.1. In the table, `python` means `.\.venv\Scripts\python.exe` on Windows or
`.venv/bin/python` on Linux. Commands run from the repository root except the
explicitly marked frontend smoke check. Linux was not rerun in this pass.

| Check | Observed result |
|---|---|
| `python -m unittest discover -s tests -v` | 106 passed, no skips: contracts, IFC, Nemotron mocked HTTP, cost reporting, and 15 documentation-checker regressions. |
| `python -m pip check` | No broken installed requirements. This is not a fresh-install test or dependency lock. |
| `npm.cmd run test:frontend` | 11 logic tests passed. |
| `npm.cmd run build` | TypeScript check and Vite production build passed. |
| `node scripts/smoke-render.mjs` from `frontend/` | Server-rendered initial workspace: eight marks, eight evidence rows, unique SVG IDs. No browser launched. |
| Demo fixture export followed by Pydantic validation | All 28 exported `QueryResult` envelopes passed. No bundle/plan semantic validation is claimed. |
| `python -m contracts.export --check` | All six generated JSON Schemas current. |
| `python scripts/classify_questions.py --report-date 2026-11-14 --check` | Report reproduced: 127,044 rows, 6,789 literal texts, 234 analysis families, no unclassified rows. |
| Preview audit with its default input, writing under `build/docs-audit/` | 910 assets, 7,990 QA rows, no missing/null answers; also passed from a different working directory. |
| `python scripts/check_docs.py` | All maintained Markdown local links/images and supported anchors passed. |
| `git diff --check` | Passed. |

The audit helper now resolves its default preview relative to the script, rather
than an obsolete nested path relative to the caller. The drawing inputs and
tracked audit reports were left unchanged. Create an output directory before
using its `--output` option.

The real-model test read
`dataset/junction-dataset-preview/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc`
and checked 211 model-wide doors and 42 on `4.korrus`. Without that optional file,
this test skips; another extraction layout is not searched automatically. Other
IFC quantities/counts in the [engine guide](IFC_ENGINE.md) remain separately dated
selected observations, not a corpus-wide accuracy score.

The build and server-rendering check initially hit the execution sandbox's
restriction on Vite/esbuild reading ancestor directories. Both passed when rerun
with normal filesystem access. No Vite configuration or execution policy was
changed to work around that environment restriction.

To repeat the demo-envelope check with the configured Python/Node environment:

```sh
python -c "import json, subprocess; from contracts.models import QueryResult; rows = json.loads(subprocess.check_output(['node', '--experimental-strip-types', 'frontend/scripts/export-demo-fixtures.ts'], encoding='utf-8')); [QueryResult.model_validate(row) for row in rows]; print(len(rows), 'envelopes validated')"
```

## Documentation check boundaries

The [offline checker](../scripts/check_docs.py) inventories tracked/non-ignored
Markdown using Git, including nested checked-in experiment reports. Without Git,
it scans maintained documentation directories. It checks inline/reference links,
images, filename case, Markdown headings, explicit HTML anchors, and `#Lx` or
`#Lx-Ly` source-line bounds. Code examples/comments are ignored. Its regressions
cover the previously missed image/report links, code fences, slug collisions,
encoded filenames, and optional-data handling.

Only links into the two named optional dataset roots can be skipped, and only
when that root is absent. If a root is installed, missing files inside it fail.
Distributed archive documentation is excluded from the project-doc inventory.
External URL availability, arbitrary non-Markdown fragment IDs, and every possible
Markdown extension are outside this automated check. Selected publisher pages
cited by the research guides were opened separately; archive downloads and
inference endpoints were not exercised by this pass.

## Frontend visual refresh on Linux

Checked 14 November 2026 with Node 26.13.1, npm 12.2.2, and the installed Firefox
160.0 in headless mode. This is a separate frontend pass; Python/backend tests
were not rerun. The interface now has a dominant drawing viewport, a native
searchable drawing dialog, a fixed question composer, contextual source close-ups,
and a locally bundled Cantarell font with its license.

| Check | Observed result |
|---|---|
| `npm run test:frontend` | Both existing frontend test files passed. |
| `npm run build` | TypeScript check and Vite production build passed. |
| Frontend server-rendering smoke check | Initial workspace rendered eight marks and eight evidence rows with unique SVG IDs. |
| Desktop Firefox, 1440 × 960 CSS pixels | Drawing search/selection, exact D03 schedule lookup, source close-up, language switching, missing-information response, window/area questions, rotated focus, mark toggles, keyboard evidence/calculation tabs, and panel collapse/reopen passed. |
| Narrow Firefox, 500 × 844 CSS pixels | Drawing remains visible above the answer panel; no horizontal overflow; picker empty-search/close/Escape and a local SVG upload preview passed. Uploaded preview correctly disabled questions and carried no evidence marks. |
| Responsive screenshots | Desktop, selected schedule-cell close-up, drawing picker, and a 390 × 844 mobile layout were inspected. Normal Firefox automation windows clamped to 500 pixels wide; the narrower screenshot used Firefox's screenshot command. |
| Browser error listener | No application `error` events during the exercised interaction sequence. |
| `python scripts/check_docs.py` and `git diff --check` | Passed. |

The browser checks used a temporary local Firefox automation harness and a local
Vite server. No new JavaScript dependency, model request, or backend connection
was introduced. The temporary servers were stopped after checks. This does not
establish real drawing analysis, touch-device behavior, or the roadmap's human
evidence-verification gate.

## Local import library on Linux

Checked 14 November 2026 with Node 24.22.3, npm 11.19.1, and the installed Firefox
160.0 in headless mode. This pass changes only the frontend and its documentation;
no backend, model, or real-dataset accuracy checks were run.

| Check | Observed result |
|---|---|
| `npm run test:frontend` | All three test files passed, including seven new import tests. A separate run with `--test-isolation=none` reported all 18 individual tests passing. |
| `npm run build` | TypeScript checks and Vite production build passed. |
| `node scripts/smoke-render.mjs` from `frontend/` | Initial workspace retained eight demo marks, eight evidence rows, and unique SVG IDs. |
| Firefox local file input | Trusted pointer clicks on both header and modal Import buttons opened a native multiple-file chooser. A single selection imported PNG, JPEG, SVG, and PDF with retained thumbnails and original filenames. Separate WebP/GIF/BMP imports also passed. |
| PDF preview and navigation | A generated two-page PDF rendered a 14,400 × 14,400 point first sheet into a bounded 2,829 × 2,829 pixel preview; the portrait second page rendered correctly. Previous preview URLs were released. |
| Mixed valid/invalid batch | Valid files remained imported alongside individual errors for a corrupt image, corrupt PDF, unsupported text, IFC, empty PDF, and a file larger than 35 MB. |
| Preview library | Filename search, selecting retained previews, zoom/rotation/fit controls, removing the selected import, and returning to demos passed. |
| Drag/drop and language | Dispatched browser drag/drop events imported an SVG with a blank MIME type. Finnish import labels left the original filename unchanged. Physical operating-system drag gestures were not automated. |
| Pending source changes | Selecting a demo during a delayed PDF import preserved that selection while retaining the new file. Selecting a demo during page rendering cancelled the stale preview. Removing a file before the rest of its batch finished preserved the current demo and answer. |
| SVG export | The export Blob for a PDF page embedded a PNG data URL with no temporary Blob URL references. The browser's native save-to-disk dialog was not exercised. |
| Desktop and narrow layout | Screenshots inspected at 1,440 × 960 and 390 × 844 CSS pixels. The narrow viewport and drawing picker fit without horizontal overflow. |
| Resource cleanup and refresh | Removing every imported file left no tracked preview URLs unreleased and no uncaught application errors. Refresh returned to the four demo sources. |
| `python3 scripts/check_docs.py` and `git diff --check` | Passed. |

The browser used generated local fixtures and a temporary Firefox WebDriver BiDi
harness, without adding a JavaScript dependency. Vite's temporary local listeners
and the browser required normal local network permissions in this sandbox. The
owned browser and preview server were stopped after verification. Imports are
tab-local previews, not persistent storage or an analysis/ingestion service.

## Remaining verification gaps

- Real-device touch/virtual-keyboard behavior, Windows browser behavior, and
  native file-save interactions still need checks on the demo devices. The Linux
  browser checks above cover selected demo interactions and local import previews,
  including PDF page navigation and the generated SVG export Blob.
- The frontend uses prepared results. A real question-to-planner-to-IFC-to-viewer
  flow, HTTP integration, and general raster extraction are not implemented.
- Dataset-wide answer accuracy, evidence localization, multilingual robustness,
  latency distributions, and inference cost have not been benchmarked here.
- No fresh dependency installation, Linux backend run, live inference request,
  or billing check was performed in these passes. The [Nemotron guide](nvidia_info.md) and saved
  [door-labeling experiment](../experiments/door_labeling/RESULTS.md) retain their
  earlier observations and limits.

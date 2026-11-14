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

## Image candidate API on Linux

Checked 14 November 2026 on Linux with Python 3.12.3, FastAPI 0.162.7,
Starlette 1.10.0, Uvicorn 0.54.0, Pillow 12.3.0, Pydantic 2.14.3,
OpenAI SDK 2.54.0, httpx 0.28.1, and python-multipart 0.0.33. Node 24.22.3
was used for frontend checks. The new [image API](../image_api/README.md)
adds candidate extraction, not a final-answer planner or a wired React UI.

| Check | Observed result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -v` | 138 tests passed, no skips, including the existing real IFC fixture. Provider responses in this suite are mocked. |
| New API-specific checks within that suite | 18 HTTP/model integration tests, 5 concurrency/lifecycle tests, and 9 candidate contract tests passed. |
| `.venv/bin/python -m pip check` | No broken installed requirements. |
| JSON Schema generation and `--check` | All eight generated schemas current; existing six schema files unchanged. |
| `npm --prefix frontend run generate:contracts` | New candidate/error TypeScript types generated; existing request/result types unchanged. |
| `npm run build` | TypeScript/Vite production build passed. React components unchanged. |
| `npm run test:frontend` | Both existing frontend test files passed. |
| Real Uvicorn startup over localhost | `/health`, `/docs`, and `/openapi.json` returned 200; multipart candidate route documented. No inference calls made by this startup check. |
| Synthetic example envelopes | Success, empty, partial, and error examples passed Pydantic validation. |

Async checks initially stalled inside the execution sandbox, including a minimal
independent framework/client example. The passing async suite and local TCP
startup check ran outside that sandbox; no application logic was weakened to
work around the restriction. A final change to the configurable question limit
and OpenAPI metadata was followed by focused question-limit/docs checks.

After explicit user approval, one live request used the already-saved pilot
floorplan `experiments/runs/door-labeling/20261113T234605960384Z/input.png` and
the question "Locate the doorways fitted with doors in this floorplan."
The real Uvicorn endpoint returned HTTP 200 and `status: ok`, with five candidate
records in the 2730 by 2048 display frame. The returned model was
`nemotron-3.5-super-vl`; inference-stage elapsed time was 7,731 ms, with 4,411
prompt tokens and 462 completion tokens. No final door count was generated.
The response passed the public contract's box/bounds checks and retained
`inventory_completeness: unverified`. This establishes live wiring on one image;
no manual localization/recall audit or general accuracy claim is made.

The live request initially required explicit payload/destination approval from
automatic review; it ran only after the user's approval. Both temporary Uvicorn
servers were stopped. No API images, credentials, prompts, or raw live responses
were added to the repository. Frontend browser integration was not exercised.

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

## Imported-drawing candidate UI integration

Checked 14 November 2026 on Linux with Node 24.22.3 and the installed Firefox
142.0 in headless mode. This combines the latest `main` importer with the image
candidate API branch. No new live Nemotron requests were made in this pass;
browser checks used synthetic images and a local mocked API that echoed the
actual uploaded PNG hash/dimensions and returned two candidate records.

| Check | Observed result |
| --- | --- |
| Frontend tests | All five test files passed; a run with `--test-isolation=none` before the file arguments reported 31 individual tests passing. |
| `npm run build` | TypeScript/Vite production build passed, including the PDF.js compatibility build. |
| JSON Schemas and demo envelopes | All eight schemas current; all 28 existing demo answer envelopes still pass `QueryResult` validation. |
| Initial workspace server rendering | Eight demo marks/evidence rows retained. Rerun outside the sandbox removed its Vite HMR-listener permission warning. |
| Browser PNG analysis | File import enabled the question composer; the real browser request traversed Vite's `/api` proxy to the mocked service. Returned hash/dimensions matched the prepared snapshot, and two candidate marks/list rows appeared. |
| Box placement and uncertainty | Landscape first box mapped exactly to `[235,138,84,31.5]` in the existing fitted viewport; the uncertain candidate had an amber dashed box and its reason in the list. No exhaustive-inventory claim or final object count was shown. |
| Selection and view controls | Real pointer pan, zoom, rotation, marking toggles, row/overlay selection, image close-up, and focus worked on the imported snapshot. |
| Exports | Captured marked SVG contained embedded PNG and candidate rectangles/colors; JSON retained the candidate response. No native save-dialog automation is claimed. |
| Errors and result statuses | Mocked 503 displayed an error and allowed retry; empty and partial candidate responses retained their distinct meanings. |
| SVG and stale requests | Imported SVG was rasterized and annotated; changing source during a delayed candidate request aborted/discarded the stale result. |
| PDF pages and cancellation | A two-page synthetic PDF submitted the current landscape page at 1200 by 800 pixels and portrait page at 800 by 1200. Moving pages during a delayed request cleared/aborted the old result; the new page's boxes appeared in its own frame. |
| Narrow layout | At 390 by 844 CSS pixels, the page had no horizontal overflow; source, two boxes, candidate rows and uncertainty remained readable in the stacked layout. |

The standard PDF.js build initially failed in Firefox 142 because it invokes
`Map.getOrInsertComputed`, absent in that browser. The importer now loads the
bundled compatibility main and matching compatibility worker, which supply the
needed platform polyfills. Vite prebundles the lazy compatibility reader so its
first load does not trigger a dependency-optimization reload that loses imported
tab state. Existing file library behavior and tests are retained.

The browser harness and fixtures are temporary diagnostics, not bundled dataset
assets or model accuracy evidence. The API's earlier approved live smoke request
is recorded separately above. No inference credentials were used in browser
code, and no extra dependency was added for browser automation.

## Remaining verification gaps

- Real-device touch/virtual-keyboard behavior, Windows browser behavior, and
  native file-save interactions still need checks on the demo devices. The Linux
  browser checks above cover selected demo interactions and local import previews,
  including PDF page navigation and the generated SVG export Blob.
- Demo sources use prepared results. Imported image/page candidate detection is
  connected, but a final-answer planner and a question-to-IFC-to-viewer flow remain
  unimplemented. General raster inventory/reconstruction is outside that service.
- Dataset-wide answer accuracy, evidence localization, multilingual robustness,
  latency distributions, and inference cost have not been benchmarked here.
- No billing verification or dataset-wide performance benchmark was performed.
  The [Nemotron guide](nvidia_info.md) and saved
  [door-labeling experiment](../experiments/door_labeling/RESULTS.md) retain their
  separately dated observations and limits.

# Ask the Plan frontend

A local React/TypeScript drawing workbench. It opens on a file import screen,
then shows an image/PDF with a chat panel on the right or an IFC model with its
3D inspector. No demo drawings or prepared answers are shown. Submitting a
question about an image/PDF uses the internal image API with its selected
Nemotron or Gemini Hydrogen-low provider and shows
candidate boxes, uncertainty, and source close-ups. Inference credentials stay
on the Python backend. IFC viewing stays local until a question uploads the model
to that backend for the independently selected IFC planner and CPU engine execution.
Unambiguous supported IFC count/quantity grammar can compile locally on the
backend with zero inference; other questions use its configured planner. The
analysis details report the actual path and model-request/token usage.

The [project scope](../docs/PROJECT_SCOPE.md) is the supplied dataset's question
families. Build real integrations and evidence views for that set; unknown
evaluation classes and every possible renderer are not requirements. The offline
demo fixtures alone do not establish dataset coverage.

The frontend follows the [roadmap's UI direction](../docs/ROADMAP.md#ui-direction):
one dominant source viewport, a searchable drawing picker, and a right-side chat
panel with a fixed question composer. Imported-file detection returns candidate
proposals for review. IFC questions return engine-computed answers, source
evidence and matching-element highlights; see [IFC questions](../docs/IFC_QUESTIONS.md).

## Run

Install Node.js 22.12 or later (24 LTS is the tested baseline). From the
**repository root**, Windows PowerShell:

```powershell
npm.cmd run setup:frontend
npm.cmd run dev
```

For imported-file analysis, also start the backend in a separate terminal from
the repository root (Linux):

```sh
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

On Windows use `.\.venv\Scripts\python.exe`. First install the project's `api`
extra and configure the backend `.env` as described in the
[API guide](../image_api/README.md#install-and-run). Vite proxies `/api` to that
local server; the browser never receives the inference key.

`npm run dev` starts only the frontend. If asking a question fails with an
unreadable response or an HTTP/proxy error, keep the Python API running too;
see [analysis connection troubleshooting](../image_api/README.md#troubleshoot-the-frontend-connection).

On Linux, use `npm` instead of `npm.cmd`. These root scripts forward to this
directory. The root has no dependency lockfile; do not run root `npm ci`. If
already inside `frontend/`, use `npm.cmd ci --ignore-scripts` followed by
`npm.cmd run dev` (or `npm` on Linux). Dependency installation does not install
Node itself. See the [root README](../README.md#start-the-frontend) for Windows
PATH troubleshooting; `npm.cmd` avoids PowerShell's blocked `npm.ps1` wrapper.

Open the printed local URL, normally <http://127.0.0.1:5173/>. From this directory,
`npm.cmd run build` performs TypeScript checking and creates `dist/`;
`npm.cmd run preview` serves the production build. Browser/graphics behavior
still needs verification on the target demo devices.

## Included

- Opening screen with a keyboard-accessible file selector and drag-and-drop area. Loading and invalid-file states stay on this screen until a preview is ready.
- Local image/SVG/PDF previews with pan, zoom, fit, quarter-turn rotation, and PDF page navigation.
- IFC imports with a separate 3D renderer, original object properties/IDs, storey filtering, visibility controls, sectioning, and engine-backed questions. Questions and the inspector share the right panel for models.
- Chat panel opens automatically after an image/PDF loads or is selected. It displays the original filename and preview details, and sends the selected image/page for candidate analysis when a question is submitted.
- Completed image/PDF responses show the returned model, total response time, and estimated USD token cost, with an expandable usage and pricing breakdown.
- Searchable drawing picker containing only imported files, with thumbnails and removal. The native dialog supports focus containment, Escape, and the `/` or Ctrl/Cmd+K shortcuts.
- English/Finnish core UI labels; original filenames and source text stay unchanged.
- Current-drawing scope by default, following the organizer clarification reported on 14 November 2026. Whole-building requests do not aggregate unseen drawings.
- Multiple local files through a file picker or drag and drop, marked SVG export, and candidate JSON export. Importing alone makes no analysis call.
- Cancellation on source changes, keyboard shortcuts, help dialog, and responsive styles. On narrow screens the chat panel sits below the drawing and can be hidden from the viewer toolbar.

The interface uses the existing Lucide icons and a bundled Cantarell variable
font, with a neutral drawing surface and a green selection accent. No external
font request is required; the IFC SDK loads only when a model is selected. The font's copyright
and SIL Open Font License are included in
[Cantarell-LICENSE.txt](public/fonts/Cantarell-LICENSE.txt).

PDF.js is loaded only for local PDF preview. The lazy IFC viewer uses That Open
Components/Fragments and self-hosted workers/WASM. See the [IFC viewer guide](../docs/IFC_VIEWER.md)
for controls, architecture, runtime assets, and limits. Synthetic drawings remain
offline fixtures. The retained prepared FZK-Haus artifact has [KIT attribution](public/models/README.md)
and is not listed in the import-only application library.

## Import and preview local drawings

On first open, click **Select files** or drop files onto the import screen.
After loading, use **Import drawings** in the header or drawing picker, or drop
files anywhere on the workbench. Select multiple files at once. Supported previews are **PDF,
PNG, JPEG, WebP, SVG, GIF, and BMP**, with a **35 MiB limit per file**. **IFC** models
have a separate **512 MiB limit** and are converted locally when selected. The importer
also recognizes supported filename extensions when the browser omits the MIME
type. DWG/DXF drawings need a PDF or SVG export. IFCZIP and binary IFC are not supported.
Model conversion has progress, cancellation, retry, and removal controls. A native geometry abort can trigger one recovery attempt: malformed source faces are omitted only from a derived preview, with a persistent **Partial geometry** warning and inspectable omission counts. The original IFC is retained; complete geometry requires a corrected source. Source reading/hashing and conversion run in a worker; reopening the most recent model reuses its converted buffer. The size cap is a desktop input target, with actual memory use depending on model complexity.

Open **Drawings** to search imported filenames, select a thumbnail, or remove a
file. The library contains only your imports. The last successfully imported file
opens automatically unless a different source was selected during the import.
Valid files remain available when other files in the same batch fail; the picker
lists each failure and its filename. Before any file has loaded, failures appear
directly on the import screen. Removing the selected file opens another import,
or returns to the import screen with the chat/inspector hidden when no imports remain.

Imported images/PDFs have pan, zoom, fit, and rotation controls.
The footer navigates PDF pages; each PDF remembers its current page while you
browse other drawings. PDF previews limit their canvas size for large sheets.
Exported SVGs embed the displayed image or rendered PDF page, so they do not
depend on a temporary browser URL.

IFC models use orbit/pan/zoom, perspective or orthographic projection, storeys,
focus, hide/isolate/show all, and horizontal sectioning. The inspector preserves
original attributes, property/type/quantity links, units, GUIDs, and STEP IDs;
metadata-only items remain inspectable. IFC has no SVG export or PDF pagination.

Files stay in memory in the current tab and are cleared on refresh. For an
image/PDF, submitting a question rasterizes the selected image/page onto white
PNG and sends that snapshot and question to the API. The same frozen snapshot
appears beneath candidate boxes. Analysis limits are 20 MiB for that PNG and 40
megapixels; larger previews receive an explicit analysis-limit error.

Select a numbered box or candidate row to inspect its original label, visual
cue, uncertainty, and source close-up. Focus, pan, zoom, rotation, marking/label
toggles, marked SVG export, and candidate JSON export work with these proposals.
An empty list does not establish a true object count of zero. Partial, unreadable,
unsupported, and error results remain distinct.

The chat panel opens for each selected image/PDF, including after it was manually
hidden. Source/page changes abort analysis, clear candidates, and discard stale
responses. Returned image hashes/dimensions must match the submitted snapshot.
Preview URLs are released when a file is removed, a PDF page is replaced, or the
workbench unmounts. Switching sources cancels pending page rendering without
allowing it to restore an old selection. Asking about IFC uploads the original
file to the local backend. Its source hash binds answers and source element
identities to the displayed revision. Current-view scope follows enabled
objects, and whole-model scope is an explicit choice. Answer highlights remain
separate from clicked-object selection; source facts and calculation inputs are
inspectable, and unavailable geometry is reported separately from matches.
Descriptive and spatial responses can include a source-backed natural-language
summary above their structured results. Object references show original names
and STEP IDs; select a reference to inspect its source object. The full canonical
identities, facts and calculations remain available in the evidence export.
Switching away from IFC cancels conversion/loading and disposes its scene and
workers. Only the most recent converted model buffer is cached in memory.

The `dev` and `build` commands prepare the pinned WASM asset explicitly, so
installing with `--ignore-scripts` works. Regenerating the retained FZK-Haus
fixture is separate from startup: `npm --prefix frontend run prepare:ifc-demo`
from the root requires its optional dataset source.

## Backend integration boundary

### Response metrics and cost estimates

Image/PDF responses show elapsed time measured in the browser, from question
submission through image preparation, upload and the validated response. The
details also show the backend's model-request and raster-preparation timings.
These timings measure different parts of the request and are not added together.

Cost is an estimate for the image analysis call: `(input tokens × input rate +
output tokens × output rate) / 1,000,000`. The existing Gemini adapter includes
thinking tokens in output usage. Missing usage or an unpriced model displays
**Unavailable**, while explicitly reported zero usage remains zero.

[The pricing catalog](src/lib/responseMetrics.ts) uses the actual returned model
ID and the response's completion timestamp. Standard paid Gemini API rates were
verified against [Google's pricing](https://ai.google.dev/gemini-api/docs/pricing)
on 14 November 2026: Hydrogen is $1.50 input / $7.50 output per million tokens;
Carbon is $2 / $10 through 30 November, then $4 / $20 from 1 December UTC.
Estimates precede cache discounts, credits and taxes. Update this catalog when
rates change. Both model IDs are priced so a future backend router can use the
same display; this frontend change does not implement model routing or enable
Carbon in the current Hydrogen-only backend.

### API and source evidence

The application does not call `src/demo/engine.ts`. Its `askDemo` adapter and
synthetic sources remain for offline fixture and contract checks. Imported
images/PDF pages use `/api/v1/candidates`, the generated `ImageCandidateResponse`,
and a separate candidate overlay. Select the image provider on the backend with
`IMAGE_API_PROVIDER`; see [provider setup](../image_api/README.md#choose-the-image-provider).
Response-local candidate IDs are not canonical
building entity IDs. IFC uses `/api/ifc/models` and `/api/ifc/questions`, generated
IFC wire contracts and the engine's `QueryResult` with source evidence. The configured
Nemotron or Hydrogen planner uses bounded source inspection before proposing
queries; the backend validates and executes them. Exterior-door partial counts
show “At least” and unresolved doors separately from exclusions. Select the IFC
provider using [the independent settings](../docs/IFC_QUESTIONS.md#choose-the-ifc-planner).
Final answers
for image/PDF questions remain pending.

`src/types.ts` defines UI-only `Mark` and `DemoResponse` presentation records. They resolve the canonical entity, source geometry, label, ordinal, and calculation display. They are not additional physical facts or changes to the shared Python contracts. `src/contracts/` is generated from the committed request/result JSON Schemas.

From `frontend/` (`npm` on Linux):

```text
npm.cmd run generate:contracts
```

Mock result IDs/anchors/coverage references are presentation fixtures. Sample envelopes pass Pydantic `QueryResult` validation; this prototype does not provide the complete source `KnowledgeBundle` and matching plans needed for semantic `validate_result` checks, or establish real extraction completeness. The area example's geometric dimensions and subtraction are internally consistent, and matching plan/schedule doors share canonical identities.

Preserve this separation during integration:

1. The backend owns the answer, scope, inventory completeness, source identity, unit conversion, and calculation trace.
2. Resolve source regions into the displayed source frame. Local previews fit the image into a fixed 1100 × 780 frame; candidate boxes use the returned pixel dimensions and that same centered fit. Final evidence must preserve declared source frames/transforms.
3. The frontend formats values, renders evidence, and manages selection. It must not infer the answer from the currently visible mark count.
4. Candidate detections are unreviewed, response-local observations; they do not establish canonical object identities or exhaustive inventories for final answers.

## Checks

From `frontend/` (`npm` on Linux):

```text
npm.cmd test
npm.cmd run build
node scripts/smoke-render.mjs
```

Tests cover import format/size validation, image decoding failures, preview URL
cleanup, viewport helpers, separate IFC/2D limits, bounded converted-model caching,
cycle-safe property inspection, candidate API validation/cancellation, and pixel-to-view
coordinate mapping. Retained offline demo tests also cover per-drawing
scope, multilingual object consistency, logical identity across source
appearances, area arithmetic, schedule lookup, missing information, and
cancellation. `scripts/export-demo-fixtures.ts` emits sample result envelopes for
validation against the Python contracts. The server-rendering smoke check
asserts that first open contains file import controls and no drawing or chat.

The latest checks are recorded in the [verification record](../docs/VERIFICATION.md).
The frontend logic checks, production build, and initial server-rendering smoke
check pass. The import-first flow was exercised in headless Firefox on Linux:
desktop and narrow-screen layouts, first-load errors, loading before chat opens,
PDF navigation, mixed valid/invalid batches, reopening hidden chat on import,
drag/drop events, and returning to the import screen after the last removal or
refresh. Earlier library checks are retained as historical observations in the
verification record. The combined import-first/candidate merge was checked with
a local mock API for PNG/SVG/PDF analysis, hashes, box placement, uncertainty,
status/error handling, exports, cancellation, IFC switching, and URL cleanup.
These browser checks establish UI behavior, not live model or dataset accuracy.
Actual mobile touch/keyboard behavior and Windows browser checks remain pending.

Earlier IFC checks with real IFC2X3, IFC4, and IFC4.3 models, original property/ID
comparisons, cancellation, repeated source switches, and nested-base production
assets are recorded separately in the verification record.

2D keyboard shortcuts: `+`/`-` zoom, `0` fit, `R` rotate, `/` or Ctrl/Cmd+K opens
source search (or the file selector before any import), and `Escape` closes the
picker.

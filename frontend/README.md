# Ask the Plan frontend

**Detailed scan** is enabled in the image/PDF/DXF question panel. It selects drawing
regions, analyzes overlapping native detail and combines source instances through
the [detail tools](../image_api/DETAIL_TOOLS.md). Uncheck it for the standard
whole-image detector. When backend routing is enabled, the selected Hydrogen or
Carbon analyzer uses the chosen scan mode. Results expose model-call count,
selected regions and candidate checks; the recorded calls show each actual model
and its cost contribution, including region selection and verification. Deferred
crop fragments stay partial. DXF questions use only the displayed layout's raster;
IFC questions retain their separate planner and deterministic engine path.

A local React/TypeScript drawing workbench. It opens on a file import screen,
then shows an image/PDF/DXF with a chat panel on the right or an IFC model with its
3D inspector. No demo drawings or prepared answers are shown. Submitting a
question about an image/PDF/DXF uses the internal image API with its selected
Nemotron or Gemini provider and shows candidate boxes, uncertainty, and source
close-ups. Optional backend capability routing chooses Hydrogen or Carbon and
records the path for the expandable explanation. While analysis is loading, the
workbench shows image preparation, model selection and then **Handing to [model]**
as soon as the backend dispatches the selected analyzer. Inference credentials stay
on the Python backend. DXF previews upload the original to the local backend for
2D rendering without inference. IFC viewing stays local until a question uploads the model
to that backend for the independently selected IFC planner and CPU engine execution.

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
- DXF previews rendered by the local backend, with source layout selection, original source hashes and persistent partial-rendering warnings. See [DXF support](../docs/DXF_PREVIEW.md).
- IFC imports with a separate 3D renderer, original object properties/IDs, storey filtering, visibility controls, sectioning, and engine-backed questions. Questions and the inspector share the right panel for models.
- Chat panel opens automatically after an image/PDF/DXF loads or is selected. The workspace shows the original filename and preview details; the composer identifies the selected view sent for candidate analysis.
- Loading image/PDF/DXF requests announce the backend-selected model immediately in the viewer and chat panel, in English/Finnish. A source/page change, cancellation or new request clears that status. The opt-in NDJSON response carries progress and the final result in one POST; JSON-only backends remain compatible without resubmitting analysis.
- Completed image/PDF/DXF responses show the returned model, total response time, and estimated USD token cost, with an expandable usage and pricing breakdown. The collapsed **How this was analyzed** panel displays the recorded capability check, chosen route, preparation and execution. Failed requests retain their recorded path too; responses without a trace explicitly say so.
- Searchable drawing picker containing only imported files, with thumbnails and removal. The native dialog supports focus containment, Escape, and the `/` or Ctrl/Cmd+K shortcuts.
- English/Finnish core UI labels; original filenames and source text stay unchanged.
- Image/PDF/DXF questions use the selected drawing/page/layout. IFC questions always use the entire imported model, including objects hidden in the preview. Whole-building requests do not aggregate separate imports.
- Multiple local files through a file picker or drag and drop, marked SVG export, and candidate JSON export. Importing alone makes no analysis call.
- Cancellation on source changes, keyboard shortcuts, help dialog, and responsive styles. On narrow screens the chat panel sits below the drawing and can be hidden from the viewer toolbar.

The interface keeps instructions brief: import limits, question scope, upload
disclosures and active progress stay visible. Repeated subtitles and file cards
are omitted; analysis details, source evidence and calculation inputs remain
available alongside explicit uncertainty and partial-result warnings.

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
PNG, JPEG, WebP, SVG, GIF, BMP, and DXF**, with a **35 MiB limit per file**. **IFC** models
have a separate **512 MiB limit** and are converted locally when selected. The importer
also recognizes supported filename extensions when the browser omits the MIME
type. DXF needs the running local backend and its `api` dependencies, including
ezdxf. DWG drawings need a DXF, PDF or SVG export. IFCZIP and binary IFC are not supported.
Model conversion has progress, cancellation, retry, and removal controls. A native geometry abort can trigger one recovery attempt: malformed source faces are omitted only from a derived preview, with a persistent **Partial geometry** warning and inspectable omission counts. The original IFC is retained; complete geometry requires a corrected source. Source reading/hashing and conversion run in a worker; reopening the most recent model reuses its converted buffer. The size cap is a desktop input target, with actual memory use depending on model complexity.

Open **Drawings** to search imported filenames, select a thumbnail, or remove a
file. The library contains only your imports. The last successfully imported file
opens automatically unless a different source was selected during the import.
Valid files remain available when other files in the same batch fail; the picker
lists each failure and its filename. Before any file has loaded, failures appear
directly on the import screen. Removing the selected file opens another import,
or returns to the import screen with the chat/inspector hidden when no imports remain.

Imported images/PDFs/DXFs have pan, zoom, fit, and rotation controls.
2D zoom ranges from 50% to 1000% using the toolbar, mouse wheel, or keyboard.
Rapid toolbar clicks preserve the view; double-click the drawing, click the zoom
percentage or **Fit drawing**, or press `0` to reset it.
The footer navigates PDF pages; each PDF remembers its current page while you
browse other drawings. PDF previews limit their canvas size for large sheets.
DXF previews have a named layout selector; only its displayed layout is analysed.
Exported SVGs embed the displayed image or rendered PDF/DXF view, so they do not
depend on a temporary browser URL.

IFC models use orbit/pan/zoom, perspective or orthographic projection, storeys,
focus, hide/isolate/show all, and horizontal sectioning. The inspector preserves
original attributes, property/type/quantity links, units, GUIDs, and STEP IDs;
metadata-only items remain inspectable. IFC has no SVG export or PDF pagination.

Files stay in memory in the current tab and are cleared on refresh. For an
image/PDF/DXF, submitting a question rasterizes the selected image/page/layout onto white
PNG and sends that snapshot and question to the API. The same frozen snapshot
appears beneath candidate boxes. Analysis limits are 20 MiB for that PNG and 40
megapixels; larger previews receive an explicit analysis-limit error.

Select a numbered box or candidate row to inspect its original label, visual
cue, uncertainty, and source close-up. Focus, pan, zoom, rotation, marking/label
toggles, marked SVG export, and candidate JSON export work with these proposals.
An empty list does not establish a true object count of zero. Partial, unreadable,
unsupported, and error results remain distinct.

The chat panel opens for each selected image/PDF/DXF, including after it was manually
hidden. Source/page/layout changes abort analysis, clear candidates, and discard stale
responses. Returned image hashes/dimensions must match the submitted snapshot.
Preview URLs are released when a file is removed, a PDF page is replaced, or the
workbench unmounts. Switching sources cancels pending page rendering without
allowing it to restore an old selection. Asking about IFC uploads the original
file to the local backend. Its source hash binds answers and source element
identities to the displayed revision. IFC questions always use the entire model;
storey filters, hidden objects and section cuts affect only the preview. Answer
highlights remain separate from clicked-object selection; source facts and calculation inputs are
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

Image/PDF/DXF responses show elapsed time measured in the browser, from question
submission through image preparation, upload and the validated response. The
details also show the backend's model-request and raster-preparation timings.
These timings measure different parts of the request and are not added together.

For legacy responses, cost is an estimate for the image analysis call: `(input tokens × input rate +
output tokens × output rate) / 1,000,000`. The existing Gemini adapter includes
thinking tokens in output usage. Missing usage or an unpriced model displays
**Unavailable**, while explicitly reported zero usage remains zero. When a decision trace is present, the summary totals the recorded routing and analysis calls using each call's model and completion timestamp. Missing usage or rates leave an explicit unknown component; failed calls are retained. The usage breakdown keeps routing tokens separate from analysis tokens.

[The pricing catalog](src/lib/responseMetrics.ts) uses the actual returned model
ID and the response's completion timestamp. Standard paid Gemini API rates were
verified against [Google's pricing](https://ai.google.dev/gemini-api/docs/pricing)
on 14 November 2026: Hydrogen is $1.50 input / $7.50 output per million tokens;
Carbon is $2 / $10 through 30 November, then $4 / $20 from 1 December UTC.
Estimates precede cache discounts, credits and taxes. Update this catalog when
rates change. Both model IDs are priced so a future backend router can use the
same display. Gemini Decisions is estimated at $0.10 per million input tokens and zero output cost, following the [Decisions plan](../image_api/DECISIONS_PLAN.md#3-gemini-decisions-protocol). The backend owns model routing and allowlisted profiles.

### API and source evidence

The application does not call `src/demo/engine.ts`. Its `askDemo` adapter and
synthetic sources remain for offline fixture and contract checks. Imported
images/PDF pages/DXF layouts use `/api/v1/candidates`, the generated `ImageCandidateResponse`,
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
for image/PDF/DXF questions remain pending. DXF import uses the independent,
credential-free `/api/dxf/preview` endpoint and generated `DxfPreviewResponse`.
DXF candidate exports include source/layout metadata and `candidate_response`
as separate records, retaining the original source hash alongside the PNG hash.

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
cycle-safe property inspection, candidate API validation/cancellation, request/source/question-bound decision traces, mixed-model accounting, and pixel-to-view
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

# Ask the Plan frontend

A React/TypeScript workbench for the drawing currently shown. Demo sources use
prepared answers. Imported images/PDFs connect to the internal Nemotron image API
and show candidate boxes, uncertainty, and source close-ups. Inference credentials
stay on the Python backend. Imported IFC models use a separate local 3D viewer
and source-property inspector; they are not submitted for candidate analysis.

The [project scope](../docs/PROJECT_SCOPE.md) is the supplied dataset's question
families. Build real integrations and evidence views for that set; unknown
evaluation classes and every possible renderer are not requirements. The prepared
demo answers alone do not establish dataset coverage.

The frontend follows the [roadmap's UI direction](../docs/ROADMAP.md#ui-direction):
one dominant source viewport, a searchable drawing picker, and an answer/evidence
panel with a fixed question composer. Selecting evidence opens a contextual source
close-up. Imported-file detection returns candidate proposals rather than final
answers/counts; illustrative demo sources retain their prepared behavior.

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

- Searchable drawing picker with four synthetic sources: two floor plans, a door schedule, and an elevation. The native dialog supports focus containment, Escape, and the `/` or Ctrl/Cmd+K shortcuts.
- Shared SVG source/mark viewport with pan, zoom, fit, quarter-turn rotation, overlay and label toggles.
- Clickable numbered objects, synchronized evidence selection, source close-ups, focus controls, room polygons with a column hole, and dimension marks. Source crops preserve area holes and use unique SVG IDs alongside the full drawing and picker thumbnails.
- Prepared door/window counts, bedroom net-area subtraction, corridor width, exact door-schedule lookup, and missing-information responses.
- English/Finnish question examples and core UI labels; original source text/IDs stay unchanged.
- Current-drawing scope by default, following the organizer clarification reported on 14 November 2026. Whole-building requests do not aggregate unseen drawings.
- Multiple local image/SVG/PDF imports through a file picker or drag and drop, a searchable library with thumbnails and removal, PDF page navigation, and marked-SVG/result-JSON export. Asking about an imported drawing sends its displayed raster/page to Nemotron and renders unverified candidate regions.
- IFC imports and the prepared FZK-Haus model use a separate local 3D renderer with original object properties, storeys, visibility controls and sectioning. IFC models are not uploaded or analysed by Nemotron.
- Loading states, cancellation on source changes, recent questions, keyboard shortcuts, help dialog, and responsive styles. On narrow screens the answer panel sits below the drawing and can be hidden from the viewer toolbar; answers scroll independently of the composer.

The interface uses the existing Lucide icons and a bundled Cantarell variable
font, with a neutral drawing surface and a green selection accent. No external font request is required; the IFC SDK is loaded only when a 3D source is selected. The font's copyright
and SIL Open Font License are included in
[Cantarell-LICENSE.txt](public/fonts/Cantarell-LICENSE.txt).

PDF.js is loaded only for local PDF preview. The lazy IFC viewer uses That Open Components/Fragments and self-hosted workers/WASM. **Drawings → FZK-Haus** opens a prepared real model with [KIT attribution](public/models/README.md). The 2D demo graphics remain synthetic. See the [IFC viewer guide](../docs/IFC_VIEWER.md) for controls, architecture, runtime assets, and limitations.

## Import and preview local drawings

Click **Import drawings** in the header or drawing picker, or drop files anywhere
on the workbench. Select multiple files at once. Supported previews are **PDF,
PNG, JPEG, WebP, SVG, GIF, BMP, and IFC**. Images/PDFs have a **35 MiB limit per file**; IFC has a separate **100 MiB limit**. The importer
also recognizes supported filename extensions when the browser omits the MIME
type. DWG/DXF drawings need a PDF or SVG export. IFC conversion starts on selection, with progress, cancellation, retry, and removal.

Open **Drawings** to search imported filenames, select a thumbnail, or remove a
file. Imports appear above the demo drawings. The last successfully imported file
opens automatically unless a different source was selected during the import.
Valid files remain available when other files in the same batch fail; the picker
lists each failure and its filename. Removing the selected file opens another
import, or returns to a demo drawing when no imports remain.

Imported images/PDFs use the same pan, zoom, fit, and rotation controls as the demo. IFC uses orbit/pan/zoom, storeys, perspective/orthographic projection, focus, hide/isolate/show all, and horizontal sectioning; its inspector shows original object attributes, property/type/quantity links, units, GUIDs, and STEP IDs. Metadata-only items remain inspectable. IFC does not offer SVG export or PDF pages.
The footer navigates PDF pages; each PDF remembers its current page while you
browse other drawings. PDF previews limit their canvas size for large sheets.
Exported SVGs embed the displayed image or rendered PDF page, so they do not
depend on a temporary browser URL.

Imports stay in memory in the current tab and are cleared on refresh. Importing
alone makes no analysis call. For an image/PDF, submitting a question rasterizes the selected view
onto white PNG, sends that image/question to the API, and displays the same frozen
snapshot beneath candidate boxes. This works with the supported image formats
and the displayed PDF page. API limits are 20 MiB for the rendered PNG and 40
megapixels; previews can be larger and will receive a clear analysis-limit error.

Select a numbered box or candidate row to inspect its visual cue, original label,
uncertainty, and image close-up. Focus, pan, zoom, rotation, marking/label toggles,
marked SVG export, and raw candidate JSON export work for detected candidates.
An empty list does not establish a true object count of zero. Partial/unreadable/
unsupported results and request errors stay distinct.

Source/page changes abort analysis, clear candidate state, and discard stale
responses. The client checks returned image hashes/dimensions against the actual
submitted raster. Preview and snapshot URLs are released on replacement/removal
or unmount. The original demo answer flow remains separate.

IFC remains local inspection: its files are not uploaded and its question composer
is disabled. Switching away from IFC cancels conversion/loading and disposes the
scene and workers. Only the most recent converted model buffer is cached in
memory. The `dev` and `build` commands prepare the pinned WASM asset explicitly,
so installing with `--ignore-scripts` works. The checked-in FZK-Haus demo needs no
dataset at startup. To regenerate it from the optional dataset, run
`npm --prefix frontend run prepare:ifc-demo` from the root.

## Backend integration boundary

`src/demo/engine.ts` exports `askDemo`, the asynchronous fixture adapter used only
by synthetic sources. A future final-answer API would accept the generated
`QuestionRequest` and return a `QueryResult` plus resolved presentation evidence.

The [image candidate API](../image_api/README.md) is connected through
`src/lib/candidateApi.ts`. It returns `ImageCandidateResponse` proposals,
not final `QueryResult` claims, with generated candidate/error TypeScript types.
`CandidateLayer` and `CandidatePanel` render these separately from demo answers.
The development/preview proxy targets `http://127.0.0.1:8000` by default;
`IMAGE_API_PROXY_TARGET` can override the Vite server process's backend target.
A hosted build needs its server to forward `/api` to the Python service.

`src/types.ts` defines UI-only `Mark` and `DemoResponse` presentation records. They resolve the canonical entity, source geometry, label, ordinal, and calculation display. They are not additional physical facts or changes to the shared Python contracts. `src/contracts/` is generated from the committed request/result JSON Schemas.

From `frontend/` (`npm` on Linux):

```text
npm.cmd run generate:contracts
```

Mock result IDs/anchors/coverage references are presentation fixtures. Sample envelopes pass Pydantic `QueryResult` validation; this prototype does not provide the complete source `KnowledgeBundle` and matching plans needed for semantic `validate_result` checks, or establish real extraction completeness. The area example's geometric dimensions and subtraction are internally consistent, and matching plan/schedule doors share canonical identities.

Preserve this separation during integration:

1. The backend owns the answer, scope, inventory completeness, source identity, unit conversion, and calculation trace.
2. Resolve source regions into the displayed source frame. The demo sources use a fixed 1100 × 780 frame. Candidate boxes in uploaded-image pixels use the same centered fit into the imported image's 1050 × 730 area at (25,25), with shared pan/zoom/rotation. Close-ups use the actual submitted snapshot.
3. The frontend formats values, renders evidence, and manages selection. It must not infer the answer from the currently visible mark count.
4. Candidate detections are unreviewed, response-local observations; they do not establish canonical object identities or exhaustive inventories for final answers.

## Checks

From `frontend/` (`npm` on Linux):

```text
npm.cmd test
npm.cmd run build
node scripts/smoke-render.mjs
```

Tests cover per-drawing scope, multilingual object consistency, logical identity across source appearances, polygon/column area arithmetic, precise schedule lookup, missing information, cancellation, rotated focus coordinates, bounded zoom, import format/size validation, image decoding failures, preview URL cleanup, candidate response validation and display mapping, separate IFC/2D limits, bounded converted-model caching, and cycle-safe property inspection. `scripts/export-demo-fixtures.ts` emits sample result envelopes for validation against the Python contracts.

The latest checks are recorded in the [verification record](../docs/VERIFICATION.md).
The frontend logic checks, production build, and initial server-rendering smoke
check pass. The visual refresh was also exercised in headless Firefox on Linux:
desktop and narrow-screen drawing selection, query/evidence interactions, and
responsive screenshots. The import library was separately checked in Firefox on
Linux with real browser file selection, mixed valid/invalid batches, all supported
formats, PDF page navigation, source-switch cancellation, drag/drop events, and
removal. The IFC viewer has also been checked with real IFC2X3, IFC4, and IFC4.3 models, original property/ID comparisons, repeated source switches, cancellation, and production assets under a nested base URL. This is UI verification, not a real backend or dataset accuracy test.
Actual mobile touch/keyboard behavior and Windows browser checks remain pending.

2D keyboard shortcuts: `+`/`-` zoom, `0` fit, `R` rotate, `O` toggle marks, `/` or Ctrl/Cmd+K opens source search, `Escape` closes the picker or clears selection/menus. Enter submits the question; Shift+Enter inserts a line break. Arrow keys and Home/End switch the evidence/calculation tabs when a tab is focused.

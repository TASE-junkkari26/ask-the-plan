# Ask the Plan frontend

A local React/TypeScript drawing workbench. It opens on a file import screen,
then shows an image/PDF with a chat panel on the right or an IFC model with its
3D inspector. No demo drawings or prepared answers are shown. No backend, model
endpoint, or credentials are used; the chat composer remains disabled until
uploaded-file analysis is connected.

The [project scope](../docs/PROJECT_SCOPE.md) is the supplied dataset's question
families. Build real integrations and evidence views for that set; unknown
evaluation classes and every possible renderer are not requirements. The offline
demo fixtures alone do not establish dataset coverage.

The frontend follows the [roadmap's UI direction](../docs/ROADMAP.md#ui-direction):
one dominant source viewport, a searchable drawing picker, and a right-side chat
panel with a fixed question composer. The real backend and evidence connection
remain planned; the features below describe the current local-preview prototype.

## Run

Install Node.js 22.12 or later (24 LTS is the tested baseline). From the
**repository root**, Windows PowerShell:

```powershell
npm.cmd run setup:frontend
npm.cmd run dev
```

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
- IFC imports with a separate 3D renderer, original object properties/IDs, storey filtering, visibility controls, and sectioning. The inspector occupies the right panel for models.
- Chat panel opens automatically after an image/PDF loads or is selected. It displays the original filename and preview details, and explains why question answering is not available yet.
- Searchable drawing picker containing only imported files, with thumbnails and removal. The native dialog supports focus containment, Escape, and the `/` or Ctrl/Cmd+K shortcuts.
- English/Finnish core UI labels; original filenames and source text stay unchanged.
- Current-drawing scope by default, following the organizer clarification reported on 14 November 2026. Whole-building requests do not aggregate unseen drawings.
- Multiple local files through a file picker or drag and drop, and SVG preview export. Local files are not analysed or sent anywhere.
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
have a separate **100 MiB limit** and are converted locally when selected. The importer
also recognizes supported filename extensions when the browser omits the MIME
type. DWG/DXF drawings need a PDF or SVG export. IFCZIP and binary IFC are not supported.
Model conversion has progress, cancellation, retry, and removal controls.

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

Files stay in memory in the current tab and are cleared on refresh. They are not
uploaded, stored on a server, or analysed; question answering is disabled. The
chat panel opens for each selected image/PDF, including after it was manually
hidden. Preview URLs are released when a file is
removed, a PDF page is replaced, or the workbench unmounts. Switching sources
cancels pending page rendering without allowing it to restore an old selection.
Switching away from IFC cancels conversion/loading and disposes its scene and
workers. Only the most recent converted model buffer is cached in memory.

The `dev` and `build` commands prepare the pinned WASM asset explicitly, so
installing with `--ignore-scripts` works. Regenerating the retained FZK-Haus
fixture is separate from startup: `npm --prefix frontend run prepare:ifc-demo`
from the root requires its optional dataset source.

## Backend integration boundary

The application does not call `src/demo/engine.ts`. Its `askDemo` adapter and
synthetic sources remain for offline fixture and contract checks. A future chat
integration needs real uploaded-file ingestion and an API client accepting the
generated `QuestionRequest` and returning a `QueryResult` plus resolved
presentation evidence.

`src/types.ts` defines UI-only `Mark` and `DemoResponse` presentation records. They resolve the canonical entity, source geometry, label, ordinal, and calculation display. They are not additional physical facts or changes to the shared Python contracts. `src/contracts/` is generated from the committed request/result JSON Schemas.

From `frontend/` (`npm` on Linux):

```text
npm.cmd run generate:contracts
```

Mock result IDs/anchors/coverage references are presentation fixtures. Sample envelopes pass Pydantic `QueryResult` validation; this prototype does not provide the complete source `KnowledgeBundle` and matching plans needed for semantic `validate_result` checks, or establish real extraction completeness. The area example's geometric dimensions and subtraction are internally consistent, and matching plan/schedule doors share canonical identities.

Preserve this separation during integration:

1. The backend owns the answer, scope, inventory completeness, source identity, unit conversion, and calculation trace.
2. Resolve source regions into the displayed source frame. Local file preview fits the original file into a fixed 1100 × 780 display frame with no evidence overlays. Real imported-file annotations must use the backend's declared frames/transforms.
3. The frontend formats values, renders evidence, and manages selection. It must not infer the answer from the currently visible mark count.
4. Uploaded files require a real ingestion service before question answering can be enabled for them.

## Checks

From `frontend/` (`npm` on Linux):

```text
npm.cmd test
npm.cmd run build
node scripts/smoke-render.mjs
```

Tests cover import format/size validation, image decoding failures, preview URL
cleanup, viewport helpers, separate IFC/2D limits, bounded converted-model caching,
and cycle-safe property inspection. Retained offline demo tests also cover per-drawing
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
verification record. This is UI verification, not a real backend or dataset accuracy test.
Actual mobile touch/keyboard behavior and Windows browser checks remain pending.

Earlier IFC checks with real IFC2X3, IFC4, and IFC4.3 models, original property/ID
comparisons, cancellation, repeated source switches, and nested-base production
assets are recorded separately in the verification record.

2D keyboard shortcuts: `+`/`-` zoom, `0` fit, `R` rotate, `/` or Ctrl/Cmd+K opens
source search (or the file selector before any import), and `Escape` closes the
picker.

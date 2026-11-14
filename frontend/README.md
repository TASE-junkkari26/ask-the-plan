# Ask the Plan frontend

A local React/TypeScript prototype for answering questions about the drawing currently shown. Sources and answers are explicitly illustrative. No backend, model endpoint, or credentials are used.

The [project scope](../docs/PROJECT_SCOPE.md) is the supplied dataset's question
families. Build real integrations and evidence views for that set; unknown
evaluation classes and every possible renderer are not requirements. The prepared
demo answers alone do not establish dataset coverage.

The [hackathon roadmap](../docs/ROADMAP.md#ui-direction) sets the next UI direction:
one dominant source viewport, a compact answer/evidence panel, and contextual
inspection of individual objects and calculation inputs. That redesign and the
real backend connection remain planned; the features below describe the current
prototype.

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

- Drawing navigator with four synthetic sources: two floor plans, a door schedule, and an elevation.
- Shared SVG source/mark viewport with pan, zoom, fit, quarter-turn rotation, overlay and label toggles.
- Clickable numbered objects, synchronized evidence selection, focus controls, room polygons with a column hole, and dimension marks.
- Prepared door/window counts, bedroom net-area subtraction, corridor width, exact door-schedule lookup, and missing-information responses.
- English/Finnish question examples and core UI labels; original source text/IDs stay unchanged.
- Current-drawing scope by default, following the organizer clarification reported on 14 November 2026. Whole-building requests do not aggregate unseen drawings.
- Local image/SVG/PDF preview, PDF page navigation, and marked-SVG/result-JSON export. Local uploads are not analysed and are not sent anywhere.
- Loading states, cancellation on source changes, recent questions, keyboard shortcuts, source search, help dialog, and responsive styles.

PDF.js is loaded only for local PDF preview. This version does not embed an IFC/3D viewer; the existing viewer plan remains the integration guide. Source graphics are authored in code; no licensed dataset assets are bundled.

## Backend integration boundary

`src/demo/engine.ts` exports `askDemo`, the asynchronous fixture adapter. Replace it with an API client accepting the generated `QuestionRequest` and returning a `QueryResult` plus resolved presentation evidence.

`src/types.ts` defines UI-only `Mark` and `DemoResponse` presentation records. They resolve the canonical entity, source geometry, label, ordinal, and calculation display. They are not additional physical facts or changes to the shared Python contracts. `src/contracts/` is generated from the committed request/result JSON Schemas.

From `frontend/` (`npm` on Linux):

```text
npm.cmd run generate:contracts
```

Mock result IDs/anchors/coverage references are presentation fixtures. Sample envelopes pass Pydantic `QueryResult` validation; this prototype does not provide the complete source `KnowledgeBundle` and matching plans needed for semantic `validate_result` checks, or establish real extraction completeness. The area example's geometric dimensions and subtraction are internally consistent, and matching plan/schedule doors share canonical identities.

Preserve this separation during integration:

1. The backend owns the answer, scope, inventory completeness, source identity, unit conversion, and calculation trace.
2. Resolve source regions into the displayed source frame. The demo sources use a fixed 1100 × 780 frame; local file preview currently fits the original file into that frame with no evidence overlays. Real imported-file annotations must use the backend's declared frames/transforms.
3. The frontend formats values, renders evidence, and manages selection. It must not infer the answer from the currently visible mark count.
4. Uploaded files require a real ingestion service before question answering can be enabled for them.

## Checks

From `frontend/` (`npm` on Linux):

```text
npm.cmd test
npm.cmd run build
node scripts/smoke-render.mjs
```

Tests cover per-drawing scope, multilingual object consistency, logical identity across source appearances, polygon/column area arithmetic, precise schedule lookup, missing information, cancellation, rotated focus coordinates, and bounded zoom. `scripts/export-demo-fixtures.ts` emits sample result envelopes for validation against the Python contracts.

The latest checks are recorded in the [verification record](../docs/VERIFICATION.md). The 11 frontend logic tests and production build pass; server rendering and sample envelopes are checked separately. Earlier browser automation was reported blocked by the available Windows browser tooling. Responsive appearance, file-upload controls, and exported artifacts still need browser verification. Logic tests, Pydantic validation, and server rendering do not establish completed end-to-end UI tests.

Keyboard shortcuts: `+`/`-` zoom, `0` fit, `R` rotate, `O` toggle marks, `/` source search, `Escape` clear selection/menus. Enter submits the question; Shift+Enter inserts a line break.

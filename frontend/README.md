# Ask the Plan frontend

A local React/TypeScript prototype for answering questions about the drawing currently shown. Sources and answers are explicitly illustrative. No backend, model endpoint, or credentials are used.

The [project scope](../docs/PROJECT_SCOPE.md) is the supplied dataset's question
families. Build real integrations and evidence views for that set; unknown
evaluation classes and every possible renderer are not requirements. The prepared
demo answers alone do not establish dataset coverage.

The frontend follows the [roadmap's UI direction](../docs/ROADMAP.md#ui-direction):
one dominant source viewport, a searchable drawing picker, and an answer/evidence
panel with a fixed question composer. Selecting evidence opens a contextual source
close-up. The real backend connection remains planned; the features below describe
the current prototype with illustrative sources and prepared answers.

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

- Searchable drawing picker with four synthetic sources: two floor plans, a door schedule, and an elevation. The native dialog supports focus containment, Escape, and the `/` or Ctrl/Cmd+K shortcuts.
- Shared SVG source/mark viewport with pan, zoom, fit, quarter-turn rotation, overlay and label toggles.
- Clickable numbered objects, synchronized evidence selection, source close-ups, focus controls, room polygons with a column hole, and dimension marks. Source crops preserve area holes and use unique SVG IDs alongside the full drawing and picker thumbnails.
- Prepared door/window counts, bedroom net-area subtraction, corridor width, exact door-schedule lookup, and missing-information responses.
- English/Finnish question examples and core UI labels; original source text/IDs stay unchanged.
- Current-drawing scope by default, following the organizer clarification reported on 14 November 2026. Whole-building requests do not aggregate unseen drawings.
- Local image/SVG/PDF preview, PDF page navigation, and marked-SVG/result-JSON export. Local uploads are not analysed and are not sent anywhere.
- Loading states, cancellation on source changes, recent questions, keyboard shortcuts, help dialog, and responsive styles. On narrow screens the answer panel sits below the drawing and can be hidden from the viewer toolbar; answers scroll independently of the composer.

The interface uses the existing Lucide icons and a bundled Cantarell variable
font, with a neutral drawing surface and a green selection accent. No additional
JavaScript dependency or external font request is required. The font's copyright
and SIL Open Font License are included in
[Cantarell-LICENSE.txt](public/fonts/Cantarell-LICENSE.txt).

PDF.js is loaded only for local PDF preview. This version does not embed an IFC/3D viewer; the existing viewer plan remains the integration guide. Source graphics are authored in code; no licensed dataset assets are bundled.

## Backend integration boundary

`src/demo/engine.ts` exports `askDemo`, the asynchronous fixture adapter. Replace it with an API client accepting the generated `QuestionRequest` and returning a `QueryResult` plus resolved presentation evidence.

The separate [image candidate API](../image_api/README.md) is available for
image/question-to-box integration. It returns `ImageCandidateResponse` proposals,
not final `QueryResult` claims, and provides generated candidate/error TypeScript
types. Wiring this service into the React components remains frontend work;
the demo adapter and local-upload behavior are unchanged.

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

The latest checks are recorded in the [verification record](../docs/VERIFICATION.md).
The frontend logic checks, production build, and initial server-rendering smoke
check pass. The visual refresh was also exercised in headless Firefox on Linux:
desktop and narrow-screen drawing selection, query/evidence interactions, and
responsive screenshots. This is demo UI verification, not a real backend or
dataset accuracy test. Actual mobile touch/keyboard behavior, PDF page navigation,
and downloaded artifacts still need checks on the demo devices.

Keyboard shortcuts: `+`/`-` zoom, `0` fit, `R` rotate, `O` toggle marks, `/` or Ctrl/Cmd+K opens source search, `Escape` closes the picker or clears selection/menus. Enter submits the question; Shift+Enter inserts a line break. Arrow keys and Home/End switch the evidence/calculation tabs when a tab is focused.

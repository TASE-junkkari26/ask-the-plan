# DXF import and visual questions

Implemented on 14 November 2026: import DXF files, select one layout, inspect its
2D preview, and ask visual questions using the existing image candidate flow.
This enables direct viewing of the supplied Swiss DXF drawings. Native room
areas and counts, including the Swiss area questions discussed in the
[sample findings](TECH_STACK_RECOMMENDATION.md#findings-from-the-sample), still
need structured geometry extraction and execution; this preview does not compute them.

## Start and use

From the repository root on Linux:

```sh
.venv/bin/python -m pip install -e '.[api,preprocess,test]'
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

Use `.\.venv\Scripts\python.exe` on Windows. Start `npm run dev` in another
terminal (`npm.cmd run dev` in Windows PowerShell). The `api` extra includes
`ezdxf>=1.4.3,<2`. Previewing needs no inference credentials. Asking a question
uses the [configured image provider](../image_api/README.md#choose-the-image-provider).

Select or drop a `.dxf` file, up to 35 MiB. **DXF import sends the original file
to the local backend for rendering.** The preview appears in the drawing viewer
with pan, zoom, fit, rotation and SVG export. Use the **Layout** selector below
the preview to switch between nonempty source layouts. Modelspace comes first
when populated; empty default paper layouts are omitted. Layout names and
source identifiers retain their original spelling/language.

Questions concern only the displayed layout. Changing layouts cancels analysis
and clears candidates. Each question submits a white-background PNG of that
layout; the same snapshot stays visible beneath the candidate boxes. Proposals
remain unverified, including empty responses.

The candidate JSON export for DXF contains `source` metadata (original filename,
source SHA-256, layout index/names, preview dimensions, `$INSUNITS`, status and
warnings) alongside the unchanged `candidate_response` contract. The candidate
response identifies the submitted PNG by its own hash. Original DXF bytes remain
in the tab until removal/refresh and are never rewritten by the preview service.

## Renderer and evidence boundary

[`dxf_api/`](../dxf_api/) uses ezdxf's
[SVG drawing backend](https://ezdxf.readthedocs.io/en/stable/addons/drawing.html).
ASCII and binary DXF inputs use the library's encoding detection. Supported
linework, curves, text, hatches, transformed blocks and top-view paper layouts
render into a self-contained SVG. Text uses font outlines; substituted fonts
and formatting can differ from the source CAD application.

Hidden layers/entities stay hidden. External drawings, raster images, underlays
and OLE content are omitted rather than loaded. Detected omissions produce a
persistent **Partial preview** notice, with feature types and example native
handles where available. Renderer diagnostics also mark the preview partial.
Layouts without renderable visible geometry fail explicitly. Invalid files are
not automatically repaired. Unsupported features require a corrected DXF or a
PDF/SVG export for inspection.

This is a 2D top view, including for 3D source entities. ACIS bodies and non-top
paper viewports are unsupported. A rendered preview does not prove that all
source features were faithfully rendered, or that a candidate inventory is complete.
Pixel coordinates belong to the displayed raster, not native CAD coordinates.
`$INSUNITS` is preserved as source metadata (null when absent, zero when unitless)
and does not establish raster calibration. No native CAD measurements, logical
door/room inventories, semantic layer interpretation or final answer executor
is introduced. DWG still requires an export.

## HTTP and resource limits

`POST /api/dxf/preview` accepts exactly one multipart `file` and a 1-based `page`
index. It returns the generated
[`DxfPreviewResponse`](../frontend/src/contracts/DxfPreviewResponse.ts) contract:
SVG, display dimensions, original source hash, selected layout index, layout
names, literal units metadata, rendering status and warnings. Errors reuse the
existing `ImageCandidateError` envelope. The browser checks the source hash and
layout before registering a preview. This endpoint is independent of image/IFC
provider readiness.

Each preview runs in a disposable local Python process with a 45-second total
request deadline, at most two concurrent requests per backend process, a
35 MiB source cap and separate 36 MiB multipart cap. Stored DXF records and
expanded rendered entities each have a 200,000 limit; SVG output is limited to
8 MiB. Preview dimensions fit within 4096 pixels per edge and 8 megapixels.
The image/question endpoint retains its existing smaller upload/body limits.

The renderer and its font cache use request-owned temporary files. Cancellation,
disconnect and timeout terminate the owned renderer before deleting those files.
No persistent DXF session or render cache is introduced. Switching layouts
uploads the original again for rendering; importing or switching layouts makes
no inference call.

## Checks

```sh
.venv/bin/python -m unittest tests.test_dxf_api tests.test_api_body_limits tests.test_contracts -v
.venv/bin/python -m contracts.export --check
npm run test:frontend
npm run build
.venv/bin/python scripts/check_docs.py
```

Tests use synthetic DXFs and mock provider responses. They check layout/source
binding, rendering budgets, original source retention, omissions, hidden layers,
encoding, validation and worker cleanup; they do not establish dataset accuracy.
See the [verification record](VERIFICATION.md) for the actual platform/results.

# Browser IFC viewer

Implemented 14 November 2026. This is a local viewing and inspection feature,
independent of the Python IFC engine and question-answering contracts. Image/PDF
previews use the existing 2D viewer. The application opens on a file import screen;
synthetic question demos remain offline fixtures.

## Open a model

From the repository root:

```sh
npm run setup:frontend
npm run dev
```

Use `npm.cmd` in Windows PowerShell. Select or drop one or more `.ifc` files on the
opening screen, or use **Import drawings** after opening a file. IFC files may be up to
**100 MiB each**; images/PDFs retain their **35 MiB** limit. IFCZIP and binary IFC
are not supported. Files register in the existing searchable import library;
conversion starts only when a model is selected. Other successful imports remain
available if one file fails. Failed model entries retain their error and can be
opened again to retry or removed.

Only the active source has a renderer. Switching to a drawing disposes the 3D
scene and workers; switching to IFC removes the SVG renderer, PDF pagination,
marked-SVG export, and 2D camera handlers. Imported PDFs retain their current page.
IFC models are not uploaded. Image/PDF imports can separately submit a displayed
raster to the [candidate API](../image_api/README.md) when a question is asked.
Local files and the converted-model cache are cleared by refreshing the tab.
The library contains only imports; removing the last file returns to the opening
screen.

## Controls and source properties

- Drag to orbit, right-drag to pan, scroll or use the zoom buttons to zoom.
- **Fit model**, **Perspective / Orthographic**, and the storey selector control
  the view. A storey filters its spatial descendants; objects without that
  membership are not silently assigned to a floor.
- Click geometry, use the expandable model structure, or find an original STEP ID
  to inspect an object. Selection highlights without moving the camera.
- **Focus**, **Hide**, **Isolate**, and **Show all objects** are deliberate actions.
  Show all resets floor/visibility filtering; the horizontal section has its own
  reset. The cut-height slider is in viewer metres, not a source quantity.
- The inspector preserves original names, IFC classes, GUIDs, STEP IDs, scalar
  properties, quantities, and unit references. Type/style definitions are labelled
  separately inside the source references. Metadata-only items remain inspectable.

Properties follow only forward property/type/unit links. Inverse IFC graphs can
be cyclic and very large; the inspector limits a property read to 512 items and
8 reference levels and reports truncation. This is an extracted preview, not a
complete IFC inventory. Missing properties are not displayed as zero. The SDK's
supported class/geometry set can omit or fail to draw source items.

The source SHA-256 identifies the file revision. Its native GUID and STEP IDs are
**not** the Python backend's canonical entity IDs. Internal viewer model/item IDs
are separate. Geometry is rebased for display; original property values and storey
and site elevations are retained. No quantities are inferred from displayed meshes.

## Implementation and runtime assets

The pinned stack is Components 3.6.0, Components Front 3.6.1, Fragments 3.6.1,
Three.js 0.184.0, web-ifc 0.0.77, and camera-controls 3.1.2.

- [Source routing](../frontend/src/lib/importSource.ts) dispatches IFC before the
  existing 2D importer enforces its size limit.
- [Workbench](../frontend/src/components/IfcWorkbench.tsx) is lazy loaded. Its
  inspector uses a React portal so collapsing the panel does not reload the scene.
- [Adapter](../frontend/src/ifc/adapter.ts) owns camera, renderer, selection,
  visibility, clipping, worker lifecycle, and asynchronous selection guards.
- [Property reader](../frontend/src/ifc/properties.ts) constructs a bounded,
  acyclic inspection tree from source attributes and allowed relation names.
- [Loader](../frontend/src/ifc/load.ts) hashes files and runs IFC-to-Fragments
  conversion in a dedicated module worker. Cancel terminates that worker; source
  switches also abort in-flight Fragment loading and discard late results.
- A single in-memory converted buffer is keyed by source hash and converter/
  configuration identity. It is evicted when another model is converted. Inactive
  library entries retain the original `File` and lightweight status only.

Both workers and WASM are served from the application origin. `dev` and `build`
explicitly run `prepare:ifc-assets` to copy the pinned single-thread web-ifc WASM
and its license to the ignored `public/ifc-runtime/` directory. This works with
`npm ci --ignore-scripts`; there is no dependency postinstall requirement or CDN
fallback. Vite emits the version-matched Fragments worker and the conversion
worker and respects its configured base URL.

The 3D library and WASM are not requested during a 2D-only session. The 3D bundle
is substantially larger than the initial workbench bundle. WebGL 2 and sufficient
browser memory are required; 100 MiB is an input limit, not a guarantee that every
model will fit a device's memory. Failed loading, unavailable graphics, and missing
runtime assets produce a recoverable viewer error. The file picker remains usable.

## Prepared demo and attribution

The checked-in [FZK-Haus fragment](../frontend/public/models/fzk-haus.frag) and
[manifest](../frontend/public/models/fzk-haus.json) are retained as prepared viewer
fixtures. They are not shown in the import-only application library. See their
[attribution](../frontend/public/models/README.md). Ordinary startup does not
require the dataset.

To regenerate from the optional local dataset:

```sh
npm --prefix frontend run prepare:ifc-demo
```

A different path to the same source can be supplied after `--`. The preparation
command is separate from install/dev/build because those commands must not depend
on the dataset. After changing converter settings or versions, bump the converter
identity and regenerate the artifact. The loader rejects a mismatched demo manifest.

## Boundaries

This IFC viewer has no backend connection or real question answering for IFC
sources, federation, editing, measurement, new IFC export, server conversion,
generated floor drawings, or persistent upload storage. This viewer does not
change the Python IFC engine or its query contracts; the separate image API adds
candidate contracts for 2D analysis. See the [verification record](VERIFICATION.md)
for checks actually run; selected-model tests are not corpus-wide compatibility.

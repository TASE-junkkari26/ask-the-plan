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
**512 MiB each**; images/PDFs retain their **35 MiB** limit. IFCZIP and binary IFC
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
8 reference levels and reports truncation. Very wide relations are bounded before
copying or expanding them, and hierarchy branches show 100 children at a time
with a **Show next** control. Closed property groups are mounted only when opened. This is an extracted preview, not a
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
  conversion in a dedicated module worker. Source reading and SHA-256 hashing also
  run inside that worker, with progress messages limited to ten per second. Cancel terminates that worker; source
  switches also abort in-flight Fragment loading and discard late results.
- A single in-memory converted buffer is keyed by source hash and converter/
  configuration identity. A weak `File` identity cache lets the most recently
  converted file reopen without rereading, rehashing, or starting a conversion
  worker. Identical revisions share the converted buffer; removal tracks every
  source using it. The buffer is evicted when another model is converted. Inactive
  library entries retain the original `File` and lightweight status only.

Both workers and WASM are served from the application origin. `dev` and `build`
explicitly run `prepare:ifc-assets` to copy the pinned single-thread web-ifc WASM
and its license to the ignored `public/ifc-runtime/` directory. This works with
`npm ci --ignore-scripts`; there is no dependency postinstall requirement or CDN
fallback. Vite emits the version-matched Fragments worker and the conversion
worker and respects its configured base URL.

The 3D library and WASM are not requested during a 2D-only session. The 3D bundle
is substantially larger than the initial workbench bundle. WebGL 2 and sufficient
browser memory are required; 512 MiB is a desktop input ceiling, not a guarantee that every
model will fit a device's memory. Failed loading, unavailable graphics, and missing
runtime assets produce a recoverable viewer error. The file picker remains usable.

## Depth precision and rendering performance

The viewer now uses camera/model-aware near and far planes for both camera
projections, rather than the SDK's fixed range. Close inspection also replaces
the SDK's six-metre camera minimum with a model-scaled distance. Reverse depth
is enabled on WebGL implementations supporting `EXT_clip_control`; other devices
use the normal depth buffer with the adaptive clipping planes.

Coplanar surface materials receive small, stable, material-specific polygon
offsets. Transparent glass/space/selection materials do not write depth, and
selection has its own forward bias. LOD line materials retain their SDK behavior.
This follows the SDK's [coplanar surface handling](https://docs.thatopen.com/Tutorials/Components/Front/Highlighter)
using deterministic offsets instead of random ones. The source geometry and
properties are retained; raster depth bias does not repair overlapping objects
or conflicting geometry in a source file.

The renderer draws on camera, model, selection, visibility, clipping, or resize
changes. It does not draw continuously while idle. The drawing buffer is limited
to approximately three million pixels and at most 1.5 device pixels per CSS pixel;
React controls keep their normal resolution. Clipping updates coalesce at frame
boundaries, and visibility operations run in order so a delayed floor isolation
cannot override a later **Show all** action. A lost graphics context produces a
recoverable error with **Retry**.

[Rendering policy](../frontend/src/ifc/rendering.ts) and
[update scheduling](../frontend/src/ifc/tasks.ts) have focused regression tests.
The required copy before passing cached fragments to the SDK is retained because
the SDK transfers and detaches its input buffer.

The worker still holds the complete source and WebCrypto can temporarily copy
it while hashing. web-ifc geometry/WASM and rendering require additional memory,
often several times the input size. The higher cap admits the supplied 326.8 MiB
model but does not establish that every 512 MiB model fits every device. See the
[verification record](VERIFICATION.md) for measured large-model checks.

## Native geometry failures and partial previews

Some IFC exports contain dangling or malformed face geometry even though their
header, schema and product metadata parse correctly. The supplied
`dental_clinic_mep.ifc` is one such file: flexible duct STEP `#9226` reaches a
polygon loop containing unresolved CartesianPoint references, which aborts the
native tessellator.

After a recognized native geometry abort, the failed WASM worker is terminated.
The loader makes at most one recovery attempt in a fresh worker. The
[recovery helper](../frontend/src/ifc/geometryRecovery.ts) inspects polygon loops,
face bounds and connected/shell face lists. It omits entire invalid faces from
an in-memory rendering derivative; a malformed inner bound causes the whole face
to be omitted rather than inventing a filled hole. It does not invent point
coordinates or alter the original file. Product/property STEP IDs, GUIDs, names,
quantities and units remain available; the source SHA-256 still identifies the
original file, not the derivative.

A recovered model is explicitly **partial geometry**. An amber viewport banner
remains visible when the inspector is collapsed. **View omissions** shows unique
source-face/loop/reference counts and bounded samples of original STEP IDs.
These are source records, not counts of rendered triangles or physical objects.
The cached fragment retains its diagnostics, so reopening it cannot hide the
warning. A healthy source has no partial-geometry banner.

This is a viewing fallback, not a source repair or completeness claim. Correcting
or re-exporting the source is necessary for complete geometry. Unrelated native
failures with no safely isolatable invalid faces still report an error. Ordinary
validation failures/cancellation do not enter recovery, and a failed recovery is
not retried indefinitely. Valid models use the original single-pass pipeline;
recovery requires an additional native parse/export and therefore takes longer.

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

# Frontend visualization and evidence plan

Prepared 13 November 2026; implementation status updated 14 November. This is a design guide using the [shared schema](SCHEMA.md). The [frontend README](../frontend/README.md) describes the implemented mock 2D workbench: synthetic sources, prepared answers, selectable overlays, local file preview, and exports. Backend integration, real-source annotation resolution, and IFC 3D viewing remain planned. The recommendations below are the target architecture, not a list of shipped features.

Update, 14 November 2026: the user reports that the challenge organizer expects questions to be mostly limited to what is shown. The [mock frontend](../frontend/README.md) therefore defaults to the selected drawing/view and does not silently aggregate the whole model. Broader scope remains an explicit future capability. This clarification does not change the scope of existing reference rows that explicitly ask whole-model questions.

The [project scope](PROJECT_SCOPE.md) is the supplied dataset's demonstrated
question families, with no requirement to anticipate unknown evaluation classes.
See the [evidence requirements](FRONTEND_EVIDENCE_REQUIREMENTS.md) for presentation
patterns across Q01-Q20. Implement the patterns needed by known questions;
revision comparison and other extensions are optional. A custom 3D engine is not
required when a simpler view provides adequate source verification.

Build a drawing/evidence workbench with one selection model, several source renderers, and a shared overlay vocabulary. Make 2D the default for drawing questions. Add an existing IFC viewer with a small application-specific evidence layer for questions where depth, systems, or multiple floors matter.

## Recommended frontend stack

| Component | Choice | Purpose |
|---|---|---|
| Application | React + TypeScript + Vite | Workbench, result cards, source navigation, shared selection. Generate wire types from the committed JSON Schemas. |
| Common 2D overlay | SVG above the source renderer | Numbered boxes, polygons with holes, paths, callouts, text/cell highlights, and hit targets. Keep source and marks separate. |
| Raster renderer | Image element initially; tiled renderer when needed | PNG/JPEG scans and photos. Keep intrinsic image coordinates and source identity. For very large scans, OpenSeadragon supplies deep zoom and overlays. [OpenSeadragon overlays](https://openseadragon.github.io/examples/ui-overlays/). |
| PDF renderer | PDF.js | Sharp page rendering, pagination, rotation, and coordinate transforms; add selectable text when useful. [Viewport example](https://mozilla.github.io/pdf.js/examples/index.html). |
| CAD/IFC plan renderer | Backend-generated SVG or PDF | Preserve the original drawing/export, CAD handles/IFC GUIDs, and exact mappings. The browser need not parse general DWG/DXF. |
| IFC 3D renderer | That Open Components + Fragments | Existing BIM scene, object selection/highlighting, camera navigation, and sectioning. [Fragments](https://docs.thatopen.com/Tutorials/Fragments/), [Highlighter](https://docs.thatopen.com/Tutorials/Components/Front/Highlighter), [section styling](https://docs.thatopen.com/Tutorials/Components/Front/ClipStyler). |

SVG is the initial overlay choice because marks remain DOM elements with straightforward pointer events, accessibility hooks, and exportable vectors. If profiling shows that many changing marks are the bottleneck, replace the overlay renderer with Konva while retaining the same evidence model. Canvas is a performance choice, not an extra requirement. [SVG/Canvas tradeoffs](https://konvajs.org/docs/posts/canvas-vs-svg.html).

Keep the IFC viewer behind a lazy-loaded adapter. A raster question should not download a 3D engine or model. Share selection IDs with React; keep camera animation, renderer state, and GPU objects inside the viewer instance rather than updating React on every frame. Dispose workers, event listeners, and GPU resources when replacing a model.

## Workbench layout and behavior

Use a large central source viewport, a narrow source/page/floor navigator, and a right panel containing the question, answer, and evidence list. An expandable inspector can show raw properties and calculations without competing with the drawing. On narrow screens, collapse the side panels into drawers.

The source toolbar shows document/revision, current page/view/floor, zoom, rotation, overlay visibility, and 2D/3D availability. The answer card shows the requested scope, value/unit, method, and completeness. Model-wide totals and current-sheet subsets must be visibly different.

Selecting a result row selects its entity and marks in the current view. Selecting a mark selects the result row and property inspector. Selecting a 3D object uses the same entity selection. Provide previous/next result and a focus action that fits the relevant source region or selected 3D objects. Do not move the camera repeatedly while the user is inspecting several related properties.

One illustrative interaction is a whole-model door answer: show the total, a floor breakdown, and how many matched entities can be located on the current sheet. Preserve the whole-model total while switching floors. If some objects have no visual representation, keep them in the evidence inventory and identify the gap rather than fabricating boxes.

## What each answer should visualize

| Answer/evidence type | Drawing presentation | Additional evidence |
|---|---|---|
| Door/window/fixture count | Numbered boxes or precise object outlines; hover label; selected object emphasized | Stable entity list, floor/view membership, included/excluded status, count rule |
| Room/apartment area | Transparent polygon fill, outline, and area label; holes remain unfilled | Net/gross definition, subtractions, unit conversion, sum terms |
| Length/distance | Polyline or dimension line, endpoints, label | Source dimension or calibration reference; computed versus specified method |
| Volume | Selected 3D geometry, clipping/isolation as useful | Quantity/property path or geometry method; unit and scope |
| Schedule lookup | Highlight the requested row and cell/column | Original cell text and linked door-type/keynote diagram where relevant |
| Text/material/property lookup | Highlight source text; in IFC, select the element and show its property row | Original property-set name/path, raw value/unit, normalized value |
| Grouped/multipart result | Clickable result table and selectable group layers | Per-cell evidence, totals, and scope |
| Estimated/partial/missing result | Retain the source; distinguish uncertain candidates and missing evidence | Explicit status and available facts; unknown information is not zero |

Support polygons and paths from the beginning. A box-only design can show counts but cannot explain net areas, holes, pipe routes, or distances adequately. For photographed drawings or actual photos, image-space boxes still work; projecting IFC onto a real camera photograph requires camera registration and is a separate capability.

## Shared overlay rules

1. Use the canonical entity ID as the selection identity. Several CAD primitives, shapes, tiles, and floor appearances may refer to it. Source anchors remain separately inspectable.
2. Assign a stable ordinal per entity within a result. Preserve it across zooming, filtering, pages, and 2D/3D; do not infer the answer from the visible number of shapes. Multiple parts of one assembly can share one result ordinal.
3. Separate semantic roles (included, excluded, ambiguous, reference/calibration) from interaction states (hovered, selected). Use labels/dashes/icons as well as color. A selected excluded object remains excluded.
4. Show only the current claim's relevant marks initially. Make other groups and excluded candidates available as layers.
5. Keep line widths and number badges readable in screen pixels. Anchor them in source coordinates, with inverse-scale styling or a separate screen-space label layer. Use leader lines, hover details, and zoom-dependent label density where objects overlap.
6. Provide an original/marked toggle or opacity control. Marks must not obscure the text or geometry needed to verify them.
7. Keep source text/identifiers unchanged. Translate UI labels and explanations; preserve original labels such as `7.16` and `121.A` and allow translated descriptions alongside them.
8. An answer must remain inspectable when an anchor has only a native ID/property path and no drawable geometry. Show the source property evidence instead of inventing a location.

Bounding boxes and labels should be structured UI data, not burned into source images. Export can composite the current marked view while retaining source/revision attribution and the corresponding structured result.

## Coordinates: the important implementation boundary

Every geometry must retain its frame ID. For a 2D mark:

```text
screen point = viewport transform * geometry-to-base-frame transform * source point
```

This uses the schema's homogeneous column-vector convention. Compose crop, tile, rotation, resize, CAD-to-sheet, and camera transforms in the correct order. Transform the actual vertices; an axis-aligned source box may become a rotated quadrilateral. Apply homogeneous division for a projective transform. SVG matrix transforms alone cover affine mappings; more general homographies require transformed vertices or a suitable renderer.

The source renderer and overlays share the same viewport. A PDF canvas and SVG overlay must use the same CSS dimensions and page transform. PDF.js accounts for page rotation and its native PDF-to-canvas coordinate convention. Some extraction tools already use top-left coordinates, so use the declared frame rather than flipping every PDF Y coordinate blindly. Device pixel ratio affects the canvas backing resolution, not the source coordinates or CSS-space annotation positions. [PDF.js rendering example](https://mozilla.github.io/pdf.js/examples/index.html).

Store display transforms independently from physical calibration. A fitted-on-screen image is not thereby measurable in metres. Each floor/detail/site inset can have its own calibration. When no mapping exists, report that the evidence cannot be located in that view; never guess a mapping using an unrelated image's dimensions.

## IFC: use a viewer SDK and customize the evidence behavior

For floor counts and room areas, rendered plans are usually the clearest evidence. 3D becomes useful for multistorey scope, heights/volumes, concealed components, MEP systems, structural assemblies, and spatial relationships. It complements the source plans and property evidence.

The first 3D integration needs:

- highlight a result set by object IDs;
- click/pick an object and select its canonical entity;
- fit the camera to selected objects;
- isolate selected objects and ghost/hide unrelated geometry;
- choose a storey and create/reset a clipping view;
- open the selected object's source properties;
- show a few numbered callouts, prioritizing the selected/visible objects;
- restore the full model and original materials.

That Open's Highlighter already supports named styles and programmatic item selection; its clipping components support section views. Build the result-driven controls and ID bridge around those features. Avoid displaying hundreds of permanent 3D text labels through walls; use the result list and only a limited set of screen-space callouts. [Highlighter](https://docs.thatopen.com/Tutorials/Components/Front/Highlighter), [ClipStyler](https://docs.thatopen.com/Tutorials/Components/Front/ClipStyler).

Convert each IFC revision once to a viewer artifact and cache it. Fragments can be generated using That Open's importer and loaded repeatedly; the documentation explicitly recommends reusing the converted model instead of repeating IFC conversion. This can be a small Node preprocessing job or a browser worker for a prototype. The Python backend remains authoritative for question answering. [IFC conversion/reuse](https://docs.thatopen.com/Tutorials/Components/Core/IfcLoader).

Agree on this mapping with the IFC developers immediately:

```text
canonical entity ID
  -> source IFC asset/revision + native GUID or STEP ID
  -> viewer artifact revision + viewer model ID + item IDs[]
  -> available 2D views/anchors
```

Viewer item IDs are not canonical entity IDs and need not survive conversion changes. Include artifact/source hashes and support one-to-many mappings. An assembly with no own shape should select its descendants while the UI still says one assembly. Preserve per-object identity through export; a building merged into one unlabelled mesh cannot support reliable object highlighting.

Keep model units, origin rebasing, axis conventions, object placements, and any federation transforms explicit. Screen-space annotations must use the loaded viewer's camera and transforms. Do not assume a direct conversion between a 3D coordinate and a page position without an explicit projection/view mapping.

If the IFC team already produces GLB with dependable per-object mappings, a small Three.js viewer is an alternative. Choose based on the artifact pipeline actually available; avoid implementing both 3D stacks during the hackathon. Run a short integration spike with an architectural, assembly-heavy, and MEP model, including the IFC schema versions the team intends to support. SDK availability alone does not prove every distributed export will render correctly.

## Frontend/backend agreement

Use the committed contracts as the source of truth. Add a thin presentation response or adapter that resolves the relevant records, without redefining entities or facts. Large models should not force every browser to load an entire `KnowledgeBundle` before displaying one answer.

Agree on these responses/endpoints with the backend; names below are proposals:

| Response | Required content |
|---|---|
| `GET /views/{id}/manifest` | Exact asset/revision/hash, display resource URL/type, page index where relevant, base frame, intrinsic dimensions, required transforms, available 3D mapping |
| `GET /results/{id}` | Existing `QueryResult`: claims, entity sets, calculations, issues, and output IDs |
| `GET /results/{id}/evidence?view_id=...` | Relevant entities/ordinals, anchors, geometry and frames, transforms, roles, missing-location information, and pagination |
| `GET /entities/{id}` | Original labels, property facts/provenance, relations, and available 2D/3D representations |

An evidence mark needs an annotation ID, claim ID, canonical entity ID when applicable, source anchor ID, geometry/frame reference, role, optional stable ordinal, and a label. The UI derives style and interaction state. For 3D, resolve the same entity to viewer item IDs instead of forcing a 2D bounding box.

Expose result-wide matched count, matched entities located in the current view, and entities without visual anchors separately. Use structured memberships from the backend. UI pagination, hidden labels, culled marks, and missing representations must not change the answer. The frontend formats values and shows calculation steps; it does not recount the model or silently recompute quantities with JavaScript floating-point values.

Treat lifecycle states explicitly: source loading, extraction running, question running, partial evidence, conversion unavailable, unsupported visualization, no geometry for a selected entity, and a genuine empty result. Switching result/view must cancel stale work or ignore stale responses so marks from the previous source never appear over a new one.

## Suggested build order

1. Build the application shell with one shared entity/claim selection store and mocked responses from the existing examples.
2. Implement a raster viewport and shared SVG marks: pan, zoom, fit, rotation, boxes, ordinals, hover/click, and the evidence list.
3. Add polygon holes, paths, dimensions, excluded/ambiguous roles, and the original/marked toggle.
4. Integrate PDF.js and SVG plan sources, page/floor navigation, schedule cell evidence, and coordinate regression fixtures.
5. Connect the real result/evidence endpoints. Verify object totals, view subsets, and missing-geometry behavior.
6. Add the lazy-loaded IFC adapter, initially just load/pick/highlight/focus; then isolation, floor clipping, and property inspection.
7. Finish multilingual UI, screenshot/export, keyboard selection, loading/error states, and representative performance checks.

A second frontend developer can run the IFC integration spike while the common 2D work proceeds. The highest-value shared work is the ID/selection/coordinate bridge; this serves every source renderer.

## Acceptance checks

- An image mark stays on the same door through zoom, pan, resize, and quarter-turn rotation.
- A PDF mark remains aligned with a rotated page/crop box and on a high-DPI screen.
- A column hole stays unfilled and is excluded from the shown room-area calculation.
- A schedule answer selects the correct row and width cell without marking similar text in another table.
- One canonical door depicted in two sources retains one ordinal and one counted identity.
- Whole-model answers show the current-sheet subset without presenting it as complete model evidence.
- Selecting an assembly highlights its parts while keeping the requested assembly count.
- A property-only IFC object can show evidence even without geometry.
- Partial extraction and absent properties produce appropriate UI states, not exact zeros.
- Clicking a result, a 2D mark, or a 3D object synchronizes the same selection.
- Rapid source/result switching cannot leave stale marks behind.

The recommendation is based on the observed data and current viewer documentation. A representative integration test is still required before selecting exact package versions and declaring format/rendering coverage.

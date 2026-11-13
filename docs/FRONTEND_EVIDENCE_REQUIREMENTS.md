# Cross-platform frontend and evidence requirements

Reviewed 13 November 2026 against [COMPUTATIONAL_CAPABILITIES.md](COMPUTATIONAL_CAPABILITIES.md), the [shared schema](SCHEMA.md), the [frontend plan](FRONTEND_VISUALIZATION.md), and the supplied [Nemotron configuration](nvidia_info.md).

This specifies required behavior. It does not establish that the extractors, computations, viewer, or all question families are implemented. Preserve that distinction when presenting capabilities.

## Linux and Windows support

The product should be a browser application available to users on either OS, with a common backend API and stable evidence artifacts. Most CPU components can also be developed natively on either platform. GPU inference should remain a separate deployment concern.

| Layer | Linux | Windows | Decision |
|---|---|---|---|
| React/TypeScript/Vite frontend | Node development tools and browser | Node development tools and browser | Same source, package lock, and npm scripts; avoid shell-specific scripts. |
| Images, SVG annotations, PDF.js | Browser | Browser | Same view/annotation logic; no local Python/GPU installation for end users. |
| IFC 3D viewer | Browser with required graphics features | Browser with required graphics features | Check WebGL 2 and worker availability; preserve 2D/property evidence if 3D cannot load. |
| FastAPI/Pydantic/SQLite API | Native or container | Native, WSL, or remote API | One wire contract; isolate extraction/inference dependencies. |
| IfcOpenShell/ezdxf/Shapely/PyMuPDF | Supported packages/builds | Supported packages/builds | Choose matching Python/architecture wheels and pin a tested dependency combination. |
| GPU OCR/detection/HTR | Recommended worker environment | Possible for selected runtimes; installation/runtime compatibility varies | Invoke through an API or job queue; an optional specialist must not block the viewer startup. |
| vLLM self-hosted model serving | Supported deployment OS | No official native support; WSL is an option | Use a Linux worker if self-hosting. |
| Supplied Nemotron service | HTTP client in backend | HTTP client in backend | Use the provided endpoint adapter; keep credentials on the backend. No local frontier-model serving is required. |

IfcOpenShell documents Windows/Linux builds; Shapely provides binary wheels for both, and PyMuPDF documents both platforms. ezdxf also documents cross-platform dependency installation. These establish available packaging routes, not a tested application release. [IfcOpenShell](https://docs.ifcopenshell.org/ifcopenshell-python/installation.html), [Shapely](https://shapely.readthedocs.io/en/stable/installation.html), [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/installation.html), [ezdxf](https://ezdxf.readthedocs.io/en/stable/setup.html).

The current vLLM installation guide requires Linux and explicitly describes WSL for Windows. Its availability must not be presented as native Windows support. [vLLM requirements](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).

Three.js's current WebGL renderer requires WebGL 2. Test the actual model viewer on the demo devices and handle unavailable graphics capabilities without losing source/property inspection. [Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html).

Use API resource URLs/opaque IDs rather than transmitting `C:\...` or `/home/...` paths as browser resources. Keep source hashes, units, coordinate frames, fonts, artifact/converter versions, and model-origin transforms consistent across machines. Use one authoritative computed result; clients must not independently recalculate geometry and produce different platform-dependent answers.

The supported browser list and exact Python/Node/package versions need to be fixed after integration. The original contract review ran on Windows. The preliminary [IFC backend](IFC_ENGINE.md) has since passed contract/query tests on Linux with Python 3.12, including real-model counts; Windows IFC execution and application/browser integration remain untested. Native DWG conversion and legacy model runtimes remain optional adapters whose platform support must be verified separately.

## What showing reasoning means

Display a reproducible evidence-and-calculation trace. The executor produces structured steps and source references; explanatory prose can summarize them. Fluent prose or a colored object alone does not establish the answer.

For each claim, present:

1. **Scope:** source/revision, selected building/floor/view, interpretation of identifiers, requested unit and quantity definition.
2. **Inputs:** object membership, source quantities/properties/text/cells, geometry, relationships, and original units.
3. **Rules:** inclusion/exclusion, counting grain, assembly handling, missing-value treatment, and assumptions.
4. **Operations:** lookup, grouping, arithmetic, geometry, unit conversion, graph traversal, or other supported procedure with intermediate values.
5. **Outcome:** answer and unit, exact/estimated/bounded status, completeness, conflicts, or the specific missing input preventing an answer.

The source remains the central viewport. The evidence panel uses readable steps, expandable input tables, and source links. Clicking a step highlights its inputs and exclusions; clicking a table row or source mark selects the same canonical entity. Large DAGs should not be rendered as an unreadable graph by default.

An illustrative net-area explanation can show a shell, two excluded column holes, the expression `48.070375 - 0.0611037 - 0.0641318`, the unrounded result, and display rounding to `47.95 m2`. Each term needs its corresponding geometry. The source example is documented in the stack report; the frontend must obtain the actual terms from a real backend trace, not hardcode that example.

## Evidence required for every query capability

The IDs below match the capability inventory. This is a UI coverage map, not an assertion that all executors exist.

| Capability | Evidence the user must be able to inspect | Visual form |
|---|---|---|
| **Q01 Question/scope compilation** | Resolved source, revision, floor/model scope, exclusions, literal IDs, requested outputs | Scope chips and a short interpretation; clarification options when unresolved |
| **Q02 Property retrieval/inheritance** | Original property path/value/unit; occurrence or type source; inheritance/precedence | Object selection plus source property rows and links to the source type |
| **Q03 Schedules** | Table, header, exact row/column/cell; related type/keynote definition when used | Cell/row highlights, original text, and linked diagram jump |
| **Q04 Selection/filtering/exclusions** | Included and excluded sets with their filter reasons | Selectable layers, numbered marks, and membership table |
| **Q05 Counting** | Unique canonical members, grouping rule, grain, assembly/part policy, coverage | Numbered objects, total, per-view subset, explicit empty inventory for a supported zero |
| **Q06 Area lookup/calculation/estimate** | Stored area or shell/holes, unit mapping, scale evidence, method and basis | Polygon fills with holes, source property/calibration, calculation terms |
| **Q07 Geometry union/subtraction** | Input regions, intersections/overlap removal, exclusions, resulting geometry | Toggle input/result layers and excluded regions; operation steps |
| **Q08 Length/perimeter** | Source curve/path, segments/arcs, deductions, centerline/face definition, quantities | Highlighted paths, endpoints, segment labels, summed lengths |
| **Q09 Distances/dimensions/elevations/angles** | Selected points/faces/axes, elevations, distance convention, rise/run or angle convention | Dimension lines, witness points, angle arc or elevation section, formula |
| **Q10 Volume** | Stored net/gross quantity or solid/mesh/extrusion inputs, openings, assembly exclusions | Selected solid, clipping/sections, quantity rows, method and sum terms |
| **Q11 Surface/finish area** | The particular faces/sides, deducted openings, finish assumptions, source quantities | Face/patch highlights or extracted face views, section views, deduction table |
| **Q12 Materials/layers** | Material assignments, layers/thicknesses, component volumes, decomposition assumptions | Selected members, layer/section diagram or property table, per-material subtotals |
| **Q13 Grouping/ranking** | Group membership, subtotal terms, missing values, ordering, ties | Clickable grouped table and optional chart linked to source objects |
| **Q14 Ratios/arithmetic/cost** | Numerator/denominator or per-item quantities/prices, price source, currency, rounding/assumptions | Formula and input table with source links; cost rows preserve original currency |
| **Q15 Spatial predicates** | Both geometries, common frame, tolerance, chosen predicate and geometric result | Paired highlights, intersection/contact region or near-distance line |
| **Q16 Connectivity/system traversal** | Nodes/ports/edges and relation sources; direction and selected path through the system | Network/adjacency overlay on source and an optional small graph inset |
| **Q17 Navigable routes** | Start/end, portal/free-space graph, selected segments, floor transitions, distance weights, approximations | Route polyline/arrows on plans or model, segment lengths, stair/floor transitions |
| **Q18 Rules/constraints** | Supplied rule text/source/version, applicability, measured input, threshold, missing context | Local dimension/clearance marks plus a rule/input/comparison table |
| **Q19 Revisions/conflicts** | Both immutable source versions, correspondence/registration, differences and tolerance | Synchronized side-by-side views or a registered difference layer, plus property diffs |
| **Q20 Missing information/completeness** | Searched scope, available fields/coverage, what is missing, estimated versus unsupported | Explicit partial/missing/conflict state; source/property inventory; no invented zeros or boxes |

For Q18, a narrow dimensional comparison must identify its actual supplied rule and scope. A single threshold check cannot support a broad statement that a building is compliant. The UI should accurately name the performed check and leave missing context visible.

## Extraction and support capabilities also need evidence

- **E01-E03:** preserve native selectors, original text/OCR crops, detection boxes/masks, extraction method/version, and qualified scores. A text transcription is not proof of an unseen symbol count.
- **E04:** show several source features grouped into one logical instance and any duplicate-removal rule. Multiple appearances keep one count identity.
- **E05-E07:** show inferred room/unit boundaries, literal versus inferred room use, separated views, and excluded legends/neighbouring drawings. A processing tile must not appear as another floor.
- **E08-E10:** expose the calibration reference, original coordinate/unit conventions, registered mapping, raw values, and conversion. Display alignment is different from metric calibration.
- **T01-T02:** link claim cells to trace nodes, distinguish computed and inferred inputs, and propagate estimation/bounds. Do not show detection scores as completeness probabilities.
- **T03:** preserve source revision/hash and stale-result handling; a cached answer remains tied to its exact inputs.
- **T04:** use the runtime manifest to decide whether a question can be executed. UI renderability does not imply computational support.
- **T05:** keep optional latency/cost/provenance details available. Preserve benchmark reference disputes separately from the source-supported answer.

## Shared visualization primitives

The frontend needs a bounded set of composable renderers:

1. Numbered boxes, points, and object outlines.
2. Multipolygons with holes and included/excluded/result layers.
3. Polylines, arrows, dimension lines, witness points, and angle arcs.
4. Text spans, table cells, and property rows.
5. Selected meshes, faces/patches, sections, and layer representations.
6. Connectivity nodes/edges and navigable route segments.
7. Registered/synchronized comparison views.
8. Formula steps, subtotals, rule comparisons, assumptions, and coverage notices.

These can share entity selection, source anchors, stable ordinals, and interaction state. Q11/Q12 need face/layer-level evidence: coloring an entire wall does not identify which face or material contributed to a finish-area/material calculation. Q16/Q17 need topology/route evidence: highlighting the start and end objects alone does not explain the path.

## Contract gaps to coordinate with the backend team

The committed schema already covers source objects, most shapes, quantities, properties, basic relations, claims, calculations, and evidence bindings. The capability inventory correctly identifies gaps. Do not encode a new computation as an unrelated existing operation merely to make validation pass.

Coordinate explicit versioned extensions for:

- physical surface/face selection and `surface_area` semantics, including stable face/patch selectors;
- material-layer contributions and their thickness/source relationships;
- geometry Boolean operation inputs/results where needed beyond the current `union_area` measurement;
- navigable graph/route operations, segment provenance, and traversal weights;
- supplied rule/applicability/threshold records and individual comparison results;
- money/currency semantics, sourced prices, and row-wise arithmetic where needed;
- registered cross-revision correspondence and independently scoped comparison results;
- calculation-node operation variants for new algorithms and any structured metadata required to interpret them.

Some evidence can initially be supplied as derived geometry, generic typed tables, ordinary relations, and source anchors. That is enough to display it, but it does not replace a defined operation or its provenance. Frontend presentation data may add badges, styles, and layout; it must not invent physical facts or conceal unsupported execution.

For meshes, a face identifier must be scoped to the specific geometry artifact/hash, since tessellation changes can alter triangle indices. Preserve a source-to-render mapping rather than treating a transient triangle number as a stable model identifier.

## Definition of ready for a capability

A question family is ready for demonstration when its extractor supplies the required facts, its executor computes a supported result, its evidence is independently inspectable, and the UI locates the actual source inputs. A contract or mock result alone does not meet that bar.

Test the same fixture on Windows and Linux browsers for image zoom/rotation, PDF page/crop alignment, polygon holes, table-cell selection, IFC ID mapping and clipping, and rapid source switching. Check keyboard/touchpad interactions, font/glyph rendering, graphics fallback, and stable result numbering. Compare exact IDs/counts and tolerance-aware measurements rather than expecting byte-identical rendering from different GPUs.

Prefer a complete supported answer or a clear partial/missing outcome over a rendered illustration that cannot be traced to source data. The demo should make the distinction visible without requiring judges to understand implementation details.

# Questions about IFC models

Implemented 14 November 2026. The IFC workbench connects the existing Nemotron
client to the CPU [IFC query engine](IFC_ENGINE.md). Nemotron proposes a structured
query; the engine executes it against the uploaded source. The language model
does not supply the final count or calculate quantities from a screenshot.

## Run and ask

Use the same local backend as image analysis, with the project's `api` extra and
backend `.env` configured as described in the [README](../README.md#configure-nemotron):

```sh
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
npm run dev
```

Run the commands in separate terminals from the repository root. On Windows,
use `.\.venv\Scripts\python.exe` and `npm.cmd`. Import an IFC file, open the
question panel, and ask, for example, “How many windows are there?”

Opening a model continues to use local conversion and rendering. Asking uploads
the original IFC to the local Python backend for extraction. Only the question
and a bounded source catalog are sent to the configured Nemotron provider.
Credentials stay on the backend. Uploaded files and extracted model sessions are
temporary and bounded; they are removed when the backend shuts down. Browser
imports remain in memory until refresh.

## Scope and verification

The default **Current view** scope uses the objects enabled by storey and
visibility controls. It includes objects occluded by other geometry or outside
the camera viewport; orbiting and zooming do not change its inventory. **Whole
model** must be selected deliberately to query the complete extracted model,
including objects unavailable in the renderer. Horizontal clipping is a visual
cut, not an exact object inventory; reset it before asking about the current
view. A request that needs a wider scope must not silently include hidden floors.

Answer elements receive a persistent highlight independently of the selected
object. Use the evidence list to inspect an original STEP ID, GUID, name,
properties and units. Focus or isolate matching elements to reveal objects
inside the model. The answer comes from backend entity sets and stored source
properties; the number of visible highlights is not used to compute it.

The panel reports matched elements separately from elements available for 3D
highlighting. Renderer omissions, metadata-only objects and partial recovered
geometry remain explicit limitations. A visual highlight establishes the link
to a source object; inspecting its source facts and calculation inputs is still
necessary for quantity or filtered answers.

## API and evidence

- `POST /api/ifc/models` accepts multipart `file` and `source_sha256`. The backend
  hashes the original bytes and rejects a mismatch. The upload limit matches the
  viewer's 512 MiB ceiling; this is not a device memory guarantee.
- `POST /api/ifc/questions` accepts a model handle, matching revision hash,
  question, `view` or `model` scope, and exact `visible_step_ids` for view scope.
  An explicit empty list stays empty. Cached handles may expire; resubmit the
  source when needed.
- Responses contain the validated query plan and `QueryResult`, included and
  excluded element identities, source facts, anchors, units, source revision
  assets, property definitions, coverage and extraction-run metadata. Shared
  wire models are defined in [contracts/models.py](../contracts/models.py);
  JSON Schemas and TypeScript are generated from them.

`Scope.exact_entity_ids` preserves the submitted view inventory in the executable
plan. It intersects the normal scope, including traversal results. It is distinct
from `entity_ids`, whose existing semantics include spatial descendants.

Completed answers retain their captured scope. Changing the view marks a view
answer as historical; ask again to compute a new answer. Pending requests are
cancelled on view/source changes. Closing the inspector preserves the answer and
its highlights while the same model stays open. Export answer and evidence as
JSON to review the complete element sets and source inputs.

## Supported behavior and limits

The planner can compose the engine's supported selection, filtering, traversal,
grouping, ranking, property lookup, stored-quantity aggregation and bounded
native-topology `spatial_query` operations.
Its catalog contains literal source labels and identifiers alongside normalized
concepts. Count results retain occurrence or hierarchy policy; quantities retain
units and net/gross basis. Missing properties and unsupported operations produce
explicit non-answer outcomes instead of fabricated values.

The topology operations distinguish several questions that need different evidence:

| Question | Source-backed behavior |
| --- | --- |
| Where is this object or room? | `containers` follows native containment/aggregation to a requested space, storey, building or site. |
| Which rooms are adjacent? | `boundary_neighbors` uses corresponding native space-boundary pairs when available. Rooms sharing a boundary element are explicitly partial candidates when paired boundaries are unavailable; a long shared wall does not prove exact adjacency. |
| Which rooms are directly connected? | `door_connections` requires a shared physical boundary door, or a shared boundary opening filled by a door. Sharing a wall alone does not establish a connection. |
| Which rooms have direct outdoor access? | `outdoor_access` returns room occurrences with a native PHYSICAL, EXTERNAL door boundary. A subsequent count counts those rooms once, rather than counting doors or boundary records. This does not identify certified fire exits. |

Source, intermediate and result objects must all belong to the captured scope.
If topology needed for an answer lies outside the current view, the result is
`incomplete_coverage`; the query never includes hidden objects silently. Missing
required topology produces `missing_information`, rather than a claim that no
connection or access exists. Native system and zone membership is also retained
for relationship queries; membership alone does not prove that equipment serves
every room in that system or zone.

Descriptive questions can return a natural-language `QueryResult.explanation`
assembled deterministically from executed source values. Project metadata,
literal file-schema declarations, authoring application information and native
site/building addresses are extracted where present. Site latitude/longitude
retain the original IFC degrees/minutes/seconds tuple, and elevation retains its
length unit. Choose **Entire IFC model** for file/project metadata outside the
drawable view inventory; a view-scoped request asks for that scope change.
The summary requires no
second language-model request and no reference-answer lookup. It accompanies
the source facts, object identities and calculation evidence; prose alone does
not establish an answer. Missing metadata remains explicit.

This integration does not add geometry measurement, route finding, nearest-object
distance, facade orientation or north-facade classification, regulatory checking
or every IFC-Bench capability. A valid plan establishes syntax and
references, not correct natural-language interpretation. Check the displayed
interpretation, scope, element set and source facts. The dataset's known families
remain the acceptance target; this feature does not claim complete coverage.

## Supplied question families

The [exhaustive question classification](QUESTION_CLASSIFICATION.md#exhaustive-wording-and-template-catalog)
contains 3,062 quantitative IFC-model rows and 820 IFC-Bench rows (701 distinct
IFC-Bench question texts). IFC-model rows include IFC-derived drawings as well
as IFC paths; these are dataset-source cohorts, not a count of uploaded files.
The table below highlights the relevant families. The IFC-Bench rows shown are
subsets; other inventories, quantities, properties and derived questions remain
in the catalog. Line numbers refer to the full dataset's original `questions.jsonl`.

| Source/family | Rows | Supplied example or scope | First full-dataset line |
| --- | ---: | --- | ---: |
| IFC models: counts and stored quantities | 3,062 | Doors on `Level 1`; a named room's net floor area; level wall length and net slab/wall volume. Preserve literal room/floor names and explicit model-versus-view scope. | 86341 (floor door count), 86345 (room area) |
| IFC-Bench: room/space inventories | 85 | Names/functions by level (9 rows), plus areas and optional heights/function groups (76 rows). | 85610, 85844 |
| IFC-Bench: spatial questions | 19 | Equipment locations, room connections/adjacency, outdoor access, exits, routes, systems serving rooms and town-scale locations. | 85633 (connections), 85634 (adjacency), 85620 (server room) |
| IFC-Bench: overview questions | 32 | Project/location/function (13), structural system (8), combined metrics (5), residential/level layout (5), town defensive layout (1). | 85649 (building/location), 86199 (space organization) |
| IFC-Bench: model software and IFC standards | 14 | Which software tools and modeling standards were applied? | 85651 |

Outdoor access also appears as a count question (line 85759), and room counts
with locations appear as a compound question (line 85907). These show why
question wording, operation and counting grain matter more than the stored
answer-format label: all 820 IFC-Bench rows are labeled `text`, including numeric
questions. Native topology and metadata support cover bounded parts of these
families; they do not establish complete family coverage or benchmark accuracy.

See the [verification record](VERIFICATION.md) for checks actually performed and
the [viewer guide](IFC_VIEWER.md) for rendering and property-inspection limits.

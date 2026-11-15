# Questions about IFC models

Implemented 14 November 2026. The IFC workbench connects an independently selected
Nemotron or Gemini Hydrogen planner to the CPU [IFC query engine](IFC_ENGINE.md).
An exact, conservative grammar compiles supported count and stored-quantity
questions locally with zero inference. Other questions use the configured
planner to propose a structured query; the engine executes it against the uploaded source. The language model
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
and bounded source metadata are sent to the configured IFC planner provider.
Credentials stay on the backend. Uploaded files and extracted model sessions are
temporary and bounded; they are removed when the backend shuts down. Browser
imports remain in memory until refresh.

## Choose the IFC planner

Set the independent IFC option in the existing backend `.env` or process environment:

```dotenv
IFC_API_PROVIDER=gemini
IFC_GEMINI_THINKING_LEVEL=high
```

Gemini uses the existing `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-4-hydrogen` and
network timeout. Its IFC reasoning level is independent of image analysis's low
thinking setting. Keep `GEMINI_THINKING_LEVEL=low` for the image client. Default
IFC planning remains `nemotron`, using `VERDA_*`. Restart the backend after changing
settings. `IMAGE_API_PROVIDER` continues to control image candidates separately;
there is no automatic provider fallback.

| Setting | Default / supported range |
| --- | --- |
| `IFC_API_PROVIDER` | `nemotron`; `nemotron` or `gemini` |
| `IFC_API_FAST_PLANS` | `true`; compile unambiguous supported grammar locally before using the model |
| `IFC_API_COMPACT_CONTEXT` | `true`; compact model-only entity references and metadata locators; public proof IDs remain unchanged |
| `IFC_GEMINI_THINKING_LEVEL` | `high`; `low`, `medium`, `high`, `xhigh` |
| `IFC_GEMINI_MAX_OUTPUT_TOKENS` | `65536`; 1–65536, including thinking |
| `IFC_API_MAX_TOKENS` | `6000`; 1–65536, Nemotron planning output |
| `IFC_API_DEADLINE_SECONDS` | `180`; greater than zero, at most 600 |
| `IFC_API_MAX_MODEL_REQUESTS` | `3`; 1–3 planning/discovery requests total |
| `IFC_API_MAX_INSPECTIONS` | `6`; 0–6 source actions total |

Missing or invalid IFC configuration produces a safe IFC error while independent
image analysis remains available. Each result exports actual planner/model,
reasoning configuration, request/inspection counts and reported token usage in
`planning`; unreported usage stays null. The panel shows these in secondary
diagnostics. Transport retries are disabled. These settings enable comparison;
they do not establish that either provider is more accurate on supplied questions.
Hydrogen constrains a compact native JSON envelope. Its select filters travel
as JSON strings, avoiding recursive decoder unions and opaque empty objects;
only those declared filter slots are decoded back into data. The complete typed plan schema is supplied in instructions and
validated locally before execution; the native envelope alone does not validate
every operation field or establish source truth.

A finite nested predicate decoder was rejected in live checks. Google documents
that schema depth and branching can exceed its grammar limits, and recommends
simplifying native constraints while retaining application validation
([structured-output limitations](https://aistudio.google.com/docs/structured-output#limitations)).
The generic provider error does not identify the exact rejected constraint.

Planner context uses question/revision-scoped `e#` aliases in declared entity
reference slots, and native source locators instead of repeated metadata proof
UUIDs. Only exposed aliases can resolve. Literal source names, property values,
program-step IDs and property keys remain intact. Discovery observations and
exported facts, anchors, source hashes and canonical IDs stay unchanged. Set
`IFC_API_COMPACT_CONTEXT=false` for a controlled context comparison.

Locally compiled questions report `provider=deterministic`, zero model requests
and zero token usage. They still pass the same plan validation, captured-scope
gate, native executor and evidence export. Complete grammar matches and unique
source identifiers are required; extra conditions, ambiguous names/categories
and unsupported wording go to the bounded planner. The compiler reads no
challenge questions or reference answers at runtime. Missing provider credentials
do not prevent a question that can be safely compiled locally.

## Scope and verification

The default **Current view** scope uses the objects enabled by storey and
visibility controls. It includes objects occluded by other geometry or outside
the camera viewport; orbiting and zooming do not change its inventory. **Whole
model** must be selected deliberately to query the complete extracted model,
including objects unavailable in the renderer. Horizontal clipping is a visual
cut, not an exact object inventory; reset it before asking about the current
view. A request that needs a wider scope must not silently include hidden floors.

Answer elements receive a persistent highlight independently of the selected
object, with a slow four-second pulse between blue and light blue. Selecting a
match gives it the green selection pulse; clearing selection restores its blue
answer highlight. Reduced-motion preferences keep both styles steady. Use the
evidence list to inspect an original STEP ID, GUID, name,
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
  excluded element identities, separately unresolved element identities, source facts, anchors, units, source revision
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
`spatial_query` operations, typed scalar/table arithmetic, source measurements
and native distribution-network queries. `related_entities` extracts a reference column from
a relationship table and deduplicates canonical objects, so a query can find
connected rooms, return those rooms' properties, or count the rooms once. Doors,
starting objects and boundary elements remain calculation evidence rather than
being accidentally counted as related rooms.
Its catalog contains literal source labels and identifiers alongside normalized
concepts. Count results retain occurrence or hierarchy policy; quantities retain
units and net/gross basis. Missing properties and unsupported operations produce
explicit non-answer outcomes instead of fabricated values.

For compound questions, the planner can return executable outputs for the
supported requested parts and explicitly list `unanswered_parts`. The API marks
the combined response `partial` while preserving each executed claim's own units,
quality, scope and evidence. Each omitted part appears as an issue. An unanswered
part does not establish source absence, and the planner cannot replace a missing
requested part with an unasked inventory. When no requested part can execute,
the response remains a non-answer.

`arithmetic` combines earlier scalar values with checked units and quantity
bases. `table_calculate` supports row products/ratios/differences, within-group
percentages and consecutive ordered differences. For example, storey elevations
can produce floor-to-floor differences without asking a model to calculate the
heights. Native building identities keep unnamed buildings and repeated names
distinct. Ratios retain denominator evidence and reject zero denominators.

`SourceContext` occurrence fields retain native type/storey/building identifiers
and labels with relationship anchors. They allow type and floor breakdowns while
counting the original occurrences. An exhaustive breakdown can request
`missing_groups=unclassified`; absent, null and ambiguous classifications remain
separate bins with exact occurrence cardinalities and a partial outcome.
`SourceMaterial` retains ordered material-layer records and source thicknesses,
including occurrence overrides and type inheritance. It does not equate a
whole wall's volume with its insulation or concrete volume. Native selected
enumeration/list properties are also retained within bounded size limits.

Area bases need particular care. Revit documents its room `Area` as the author's
net area under the project's room-boundary settings. The guarded
`SourceQuantity.AuthoredRoomNetArea` field preserves that interpretation and its
native authoring/property evidence. It is separate from the exported IFC space
footprint, and the two can disagree. For a modeled room's net footprint when no
explicit standard `NetFloorArea` quantity exists, the engine measures the
represented space footprint and keeps its estimated quality. The stored authored
value remains available for comparison; neither is adjusted to a reference answer.
See Autodesk's [room property definitions](https://help.autodesk.com/cloudhelp/2025/ENU/Revit-ArchDesign/files/GUID-21326970-0037-41C6-A996-980C24EE019F.htm)
and [room-area computation description](https://help.autodesk.com/cloudhelp/2025/ENU/RevitLT-ArchDes/files/GUID-9348929C-18CA-40AC-BB64-71D01CC52F2B.htm).

`measure` distinguishes projected footprints, triangulated surface area,
closed-solid volume, native axis length, world-Z extent/base and explicit
distance methods. These are qualified estimates of source geometry with method,
frame, units and native input records in `measurement_evidence`. World-Z extent
of a long wall over sloping terrain is not its standing wall height. Geometric
separation is not a traversable escape route or regulatory clearance.

`network_query` inspects recorded distribution-port connections and ownership.
It reports defined port and component graph metrics with native relationship
proof in `network_evidence`. Port graph components differ from components of the
owning equipment graph. An optional explicit equipment selection controls the
integration denominator, including portless equipment. No ports means an empty
recorded inventory and an undefined connectivity ratio, rather than zero percent.

Sources of at least 32 MiB, or at least 15,000 native products on a cache miss,
use a lean native object/relationship index and a
deferred property catalog. Requested values are checked against the retained
original IFC before being called present, null or absent. Property work is
bounded per question; a budget failure is an explicit outcome, not a zero or a
claim that uninspected values do not exist. Captured response evidence survives
release of the previous question's hydrated fact cache. See the
[large-model findings](IFC_LARGE_MODEL_FINDINGS.md) for measured limits.
Large idle native sessions are retired before another model is parsed to avoid
holding two native models at peak extraction memory. The browser can reupload
an expired source when needed. Large HTTP responses use lossless gzip when the
client supports it; source evidence and memberships are retained.

The planner starts with a bounded, scope-specific catalog containing spatial
prerequisites, literal source identifiers, metadata search matches and value
facets. It can request validated `search`, `properties`, `facets` and `inspect`
actions before producing a plan, within the shared request/action/deadline caps.
Search uses Unicode normalization and case folding; executable filters preserve
the original source spelling. Matches retain their fields, literal values, fact
and anchor references. Inspections and relationship endpoints stay within the
captured scope. Explicitly truncated samples are discovery candidates, not
complete object inventories; the executor evaluates final predicates over the
authorized source objects.

A compiled question uses zero planning calls; other questions can use one.
Invalid JSON, source references or
step shapes get at most one repair against the same captured source and scope,
within the shared request/deadline caps. Exhausted repair returns a structured
clarification outcome. Missing source facts and genuinely unsupported operations
are not retried. See the [discovery investigation](IFC_OBJECT_DISCOVERY.md) for
remaining proposed extensions such as exhaustive-selection handles. Discovery
provides metadata actions; the planner cannot run arbitrary code, SQL or geometry
tools. Bounded supported geometry runs in the executor after plan validation.

The topology operations distinguish several questions that need different evidence:

| Question | Source-backed behavior |
| --- | --- |
| Where is this object or room? | `containers` follows native containment/aggregation to a requested space, storey, building or site. Room containment can use bounded geometry when usable native room containment is absent. |
| Which rooms are adjacent? | `boundary_neighbors` uses corresponding native space-boundary pairs or geometry-checked boundary patches. Rooms sharing a boundary element remain partial candidates when a patch check is unavailable; a long shared wall does not prove exact adjacency. |
| Which rooms are directly connected? | `door_connections` requires a shared physical boundary door, or a shared boundary opening filled by a door. Sharing a wall alone does not establish a connection. |
| Which rooms have direct outdoor access? | `outdoor_access` returns room occurrences with a native PHYSICAL, EXTERNAL door boundary. A subsequent count counts those rooms once, rather than counting doors or boundary records. This does not identify certified fire exits. |
| How many doors lead outside? | Select door occurrences, then `exterior_doors`, then count. Distinct doors remain separate from room/boundary counts; unknown classifications produce a lower bound or missing-information outcome. |

`exterior_doors` accepts `exterior_basis`:

- `combined` (default): recorded `Pset_DoorCommon.IsExternal` classification plus
  explicit PHYSICAL EXTERNAL door/door-filled-opening paths. Type inheritance and
  occurrence overrides apply. A positive path can resolve a missing flag; a missing
  path alone cannot classify a door as interior. Contradictory evidence produces
  `conflicting_evidence`.
- `classification`: evaluate only the recorded boolean property.
- `boundary`: enumerate recorded external-boundary door paths, explicitly qualified
  as source relationships. Missing source topology cannot establish zero outdoor
  doors. Boundary paths can describe fewer doors than exterior classifications.

Partial classifications preserve a `lower_bound` claim and partial coverage. The
answer panel says **At least**, and unresolved doors are listed separately from
excluded doors. Counts retain one occurrence per doorway, including a double-leaf
door modeled as one occurrence. Properties, boundary/fill relationships and
negative classifications remain inspectable source inputs. Source classification
does not independently verify physical access, traversability or fire-exit rules.

Source, intermediate and result objects must all belong to the captured scope.
If topology needed for an answer lies outside the current view, the result is
`incomplete_coverage`; the query never includes hidden objects silently. Missing
required topology or usable geometry produces `missing_information`, rather than
a claim that no connection or access exists. Mixed supported and unresolved
objects can return verified rows as `partial`, with per-object spatial evidence
and relation-specific coverage. Candidate or unresolved selections cannot feed
an exact aggregate total. Native system and zone membership is also retained
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

Geometry runs lazily against the retained original model in a bounded worker.
Its evidence records the method, source records, coordinate frame, metre units
and tolerance. Session deletion, expiry, eviction and shutdown remove retained
sources after active work finishes. Bounding-box candidates alone do not establish
containment or adjacency. `method=native` disables geometry fallback; the default
`auto` uses supported geometry where appropriate. Presence of a source representation
or a boundary record does not establish complete usable geometry. The containment
fallback currently accepts convex, closed room solids; unsupported room shapes
and boundary surface constructions remain unknown.

This integration does not establish general route finding, facade orientation
or north-facade classification, regulatory checking or every IFC-Bench capability.
Its explicit geometric distance methods do not establish route distances or
every possible meaning of "closest". A valid plan establishes syntax and
references, not correct natural-language interpretation. Check the displayed
interpretation, scope, element set and source facts. The dataset's known families
remain the acceptance target; this feature does not claim complete coverage.

The [IFC coverage inventory](IFC_QUESTION_COVERAGE.md) lists every supplied family
and distinguishes 1,188 direct IFC rows from paired PDF questions. The
[real-dataset evaluator](../experiments/ifc_dataset/README.md) exercises production
upload/question routes with cumulative call budgets, durable predictions and
source/code-bound resume. Numeric reference agreement, free-text review and
independent object-membership correctness remain distinct checks. Unsupported
known families remain work to complete rather than optional extensions.

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
The [paired planner evaluator](../experiments/ifc_planners/README.md) provides a
24-question, six-model synthetic replay with zero inference by default and an
explicit optional live provider comparison. Replay checks do not measure language
interpretation accuracy. [Hydrogen assessment](GEMINI_IFC_ASSESSMENT.md) records
the source-data investigation and remaining model-quality comparison.

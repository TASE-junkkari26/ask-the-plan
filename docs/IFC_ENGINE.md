# Local IFC query engine

The initial implementation reads an IFC into the shared `KnowledgeBundle`,
executes validated `QueryPlan` operations, and returns a `QueryResult` with
materialized entity sets, source anchors, facts, and calculation nodes. It runs
locally on a CPU. The [IFC question API](IFC_QUESTIONS.md) uses a Nemotron or Hydrogen planner to
produce validated plans and returns the engine's answer with source evidence.

The `exterior_doors` spatial operation selects door occurrences using recorded
exterior classifications and/or physical external door/filled-opening boundaries.
It preserves unknown membership, lower bounds and source proofs, separately from
the room-valued `outdoor_access` operation. See [the query guide](IFC_QUESTIONS.md#supported-behavior-and-limits)
for basis selection, scope and physical-completeness limits.

The [project scope](PROJECT_SCOPE.md) is the supplied dataset's known question
families. Extend this executor for uncovered supplied IFC questions, not for
hypothetical unknown evaluation classes. The limitations below describe current
implementation boundaries; they do not make every possible IFC operation a
hackathon requirement.

## Install and run

From the repository root, using Python 3.10 or newer and a compatible
IfcOpenShell wheel. Create a separate environment per OS.

Windows PowerShell (activation is not required):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m ifc_engine --help
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m unittest discover -s tests -v
```

On Debian/Ubuntu, creating a pip-enabled virtual environment may require the
matching `python3-venv` package. Network access is needed to install dependencies;
model extraction and query execution run offline afterward.

The initial Linux checks used Python 3.12.3, IfcOpenShell 0.9.0.post1, and
Pydantic 2.14.3. The latest Windows commands, versions, and results are in the
[verification record](VERIFICATION.md); the real preview-model test passed on
14 November. Earlier full-dataset CLI examples below separately returned the
documented door counts and area sum. These are selected checks, not a complete
question-family benchmark. Current integration checks are recorded separately in
the [verification record](VERIFICATION.md).
The implementation follows the
[frontend evidence requirements](FRONTEND_EVIDENCE_REQUIREMENTS.md)
for source identity and trace data. The IFC question API now returns source
element identities, facts, anchors and units for browser inspection.

In the remaining commands, replace `python` with the virtual environment's
executable above. Commands run from the repository root; one line is one command.
Output parent directories must exist before using `--output`, `--plan-out`, or
`--bundle-out`. `build/` is ignored by Git.

The dataset is optional and is not included in the Python package. These examples
use the full extraction at `dataset/junction-dataset/`. For this checkout's
preview, replace that prefix with `dataset/junction-dataset-preview/`. Both
example roots contain `questions.jsonl` and `data/`; adjust the prefix if your
archive tool adds a directory level. The model and storey counts below are
actual selected checks.

```sh
python -c "from pathlib import Path; Path('build/ifc-examples').mkdir(parents=True, exist_ok=True)"

python -m ifc_engine inspect dataset/junction-dataset/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc --output build/ifc-examples/esplanades-catalog.json

python -m ifc_engine count dataset/junction-dataset/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc door --cache-dir .ifc-cache

python -m ifc_engine count dataset/junction-dataset/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc door --storey 4.korrus --cache-dir .ifc-cache --plan-out build/ifc-examples/doors.plan.json --bundle-out build/ifc-examples/doors.bundle.json --output build/ifc-examples/doors.result.json
```

The model-wide answer is 211; the fourth-storey answer is 42. The result's scope
distinguishes them. Successful commands and query outcomes write JSON. Exit
codes are 0 for an
answered query or successful catalog/bundle export, 1 for a structured non-answer
outcome, and 2 for invalid input or a loading/CLI error. Help and argparse/path
validation errors are text; other caught loading/CLI errors are JSON on stderr.
Input paths cannot be reused as outputs; output paths must also be distinct.

## Operations and catalogs

`inspect` lists schema, extracted entity-class counts, resolved storeys, native
property paths, supported operations, and extraction warnings. Its class counts
cover extracted project/products/types/systems/zones/materials, not every STEP record in
the file. `ingest` exports the knowledge bundle. Query shortcuts are `count`, `sum`, `mean`, `min`, `max`,
`lookup`, and `rank`; `execute --plan PATH` accepts a shared-contract plan.

The following are templates: replace `building.ifc`, the storey/entity values,
and property paths with entries discovered by `inspect` for your chosen model.

```sh
python -m ifc_engine sum building.ifc space --property Qto_SpaceBaseQuantities.NetFloorArea --unit m2

python -m ifc_engine rank building.ifc door --property OverallWidth --storey Ground --limit 5

python -m ifc_engine lookup building.ifc door --entity 'door-guid-from-the-catalog' --property Pset_DoorCommon.FireRating

python -m ifc_engine count building.ifc stair --hierarchy topmost_matches
```

Property paths and storey names are examples and must exist in the chosen file.
An exported plan is bound to its source revision. To execute the real door plan
created above against the same Esplanades file:

```text
python -m ifc_engine execute dataset/junction-dataset/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc --plan build/ifc-examples/doors.plan.json --bundle-out build/ifc-examples/execution.bundle.json --output build/ifc-examples/execution.result.json
```

Fully qualified property keys remove ambiguity; `property_key(pset, name)` and
`attribute_key(name)` construct them. Display paths such as
`Pset_DoorCommon.FireRating` also resolve when unique. Properties with null
values remain explicit nulls, and unsupported property structures are marked
`not_extracted` rather than silently dropped from an answer.

Targets can be native IFC classes, such as `IfcWall`, or the occurrence concepts
in `ifc_engine/catalog.py`, such as `wall`, `space`, and `sanitary_terminal`.
Native class selection includes schema subtypes. Occurrence concepts also use
the assigned IFC type, so an IFC2X3 `IfcFlowTerminal` assigned to an
`IfcSanitaryTerminalType` can be found as `sanitary_terminal`.

Python integration uses the same entry point:

```python
from ifc_engine.engine import IfcQueryEngine

engine = IfcQueryEngine.open("building.ifc", cache_dir=".ifc-cache")
plan = engine.plan("door", storey="Ground", operation="count")
result = engine.execute(plan)
print(result.model_dump_json(indent=2))

# The convenience wrapper also converts unresolved names into structured outcomes.
missing = engine.query("door", operation="lookup", property="UnknownProperty")
assert missing.status == "missing_information"
```

Custom plans can combine selection, typed predicates, bounded relationship
traversal, native-topology spatial queries, grouped aggregation, projection, and ranking of derived table
columns. All IDs are resolved before execution. Unknown operations and count
rules are rejected; plans contain no SQL, Python, or function-evaluation strings.

`rank` preserves stable source order for equal values. By default it returns the
requested `limit` and notes additional rows tied at the cutoff.
`include_ties=true` retains every row with the same cutoff value, including
canonical source objects and source-derived table rows. Quantity equality uses
the resolved units and the same quantity meaning/basis. Exact native source
values remain exact. Estimated derived quantities without a native value type
allow at most 64 double-precision ULPs at the normalized SI cutoff to absorb
computation round-off; the result records this numerical allowance and fixed
`ifc.rank.cutoff_ties.v1` rule. It does not apply a physical measurement tolerance.
This mode returns at most 100 rows/objects. If retaining
all ties would exceed that bound, the result asks for a narrower selection or
limit without silently removing tied results. Included sets, table-cell evidence
and later counts retain every selected tie inside the captured scope.

### Native spatial queries

The `spatial_query` plan operation answers bounded spatial questions using
extracted IFC relationships and, where supported, source geometry. It accepts
`input_step_id`, `method` (`auto`, `native` or `geometry`), a bounded
`tolerance_m` (default 0.01 metres), and one of these relations:

| Relation | Result and evidence |
| --- | --- |
| `containers` | Native containment/aggregation ancestors of the requested `container_kind`: `space`, `storey`, `building` or `site`. When native room containment is unavailable, supported space geometry can establish room containment. |
| `boundary_neighbors` | Rooms linked by corresponding native space boundaries or geometry-checked overlapping boundary patches. When only a shared boundary element is available, the output is explicitly partial candidate neighbors; a shared wall can span separated rooms. |
| `door_connections` | Rooms sharing physical boundary doors, including boundary openings filled by doors. A shared wall is insufficient. |
| `outdoor_access` | Selected room occurrences with PHYSICAL, EXTERNAL door-boundary evidence. Counting the result counts rooms, rather than doors or boundaries. |
| `exterior_doors` | Distinct door occurrences resolved from recorded exterior flags and/or PHYSICAL EXTERNAL door/filled-opening boundary paths. `exterior_basis` selects combined, classification or boundary evidence; unknown membership stays unresolved. |

Native space boundaries retain individual structured records, physical/virtual
and internal/external classifications, corresponding/parent boundary identity,
connection-geometry locators and original source anchors. Openings/fillings and
corresponding-boundary links also retain anchors. Native system and zone membership is
also retained for relationship traversal. These relationships describe the
authoring model; they do not establish a navigable route, equipment service
coverage or fire-exit compliance.

Every input, intermediate and returned object remains inside the executable
scope, including `Scope.exact_entity_ids` for captured browser views. Required
objects outside the scope produce `incomplete_coverage`, without broadening the
view. Missing required topology and unusable geometry produce `missing_information`,
distinct from a supported zero result. Mixed known and unresolved inputs can
return verified rows as `partial`. Calculation nodes expose per-object
`spatial_evidence`; coverage records distinguish the spatial relation, evaluated
objects, unresolved inputs and candidates. Source-record enumeration does not
establish physical absence of a connection.

Most spatial relations return tables. Follow them with `related_entities` to
extract a chosen reference column (default `related`) as a distinct occurrence
set before property projection, traversal or counting. This preserves the
relationship calculation inputs while counting only the requested related
objects. Exact aggregates reject candidate or unresolved spatial selections.

Exterior-door membership retains a separate bounded-count behavior: a known
positive subset with unresolved classifications produces a `lower_bound` count
and partial coverage, never an exact total. Unknown-only and contradictory cases
produce non-answers. `exterior_basis=boundary` qualifies its result as recorded
source paths rather than verified physical access. Unresolved doors are separate
from definite exclusions and retain source evidence.

Geometry is lazy and bounded, with a source-revision/settings cache and isolated
worker failures. Evidence retains source STEP IDs, method, metre coordinate frame
and tolerance. Boundary-patch comparison refines shared-element adjacency;
supported convex, closed room containment requires a closed manifold object
representation and checks all its vertices. The object itself can be nonconvex.
Boundary overlap must exceed both the area and length-tolerance checks; thin
slivers remain unknown. Bounding boxes only prune candidates.
Unsupported nonconvex/invalid room solids and boundary patches with unsupported
surface constructions remain unknown; this is not a generic solid-modeling engine.
Missing or invalid geometry remains unknown. Browser sessions retain their
original source until deletion, expiry, eviction or shutdown; CLI geometry uses
the supplied source path. General spatial predicates remain unsupported; the
measurements and modeled walking routes below have explicit, narrower meanings.

The [IFC question-family audit](IFC_QUESTIONS.md#supplied-question-families)
traces these operations to supplied location, connectivity and outdoor-access
questions. Modeled walking routes now cover the supplied route family with
source qualifications; facade orientation and unrestricted spatial predicates
remain separate required gaps.

### Native geometry measurements

`measure` takes a selected native object set and an explicit geometric `basis`.
It emits a table with `subject`, `reference` and `value` columns; a later rank or
aggregate can use `value`. `union_area` instead emits one scalar union quantity.
Stored source quantities remain preferable when the question asks for a specific
net/gross quantity: mesh area does not silently replace a missing net floor area.

| Metric | Supported basis and precise meaning |
| --- | --- |
| `height` | `world_z_extent`: maximum minus minimum world Z of the represented source mesh. A long wall following sloping terrain can have a much greater vertical extent than its local standing height. `validated_vertical_spans` separately requires complete paired vertical side patches and consistent full-mesh top/base tags before returning one local modeled height; ground contact remains unestablished. |
| `base_elevation` | `world_min_z`: minimum world Z of the represented mesh. This does not substitute for native `ElevationOfTerrain`, `ElevationOfRefHeight` or a storey's `Elevation`. |
| `area` | `surface`: sum of triangulated modeled surface areas; `footprint`: area of the union of XY triangle projections. `net_opaque_face`: one verified cap normal to a horizontal native layer axis, preserving holes and edge-opening cuts. The caller must independently establish the exterior facade selection; none of these bases implies gross facade area, glazing coverage or complete paint scope. |
| `union_area` | `footprint`: union of all selected projected mesh footprints, removing overlap. It does not measure the town enclosed by an inner wall merely by measuring that wall's narrow footprint. |
| `enclosed_area` | `bounded_regions`: union of projected bounded regions supported by the selected subject boundary, jointly adding explicit source closure references. Closure-only courtyards and tolerance-scale slivers are excluded; no hulls or artificial gap closing. |
| `volume` | `solid`: signed tetrahedron integration over a closed, consistently wound mesh. Open, invalid or ambiguous overlapping compound shells remain unavailable. Bounding-box volume is never substituted. |
| `length` | `axis`: total length of explicit straight native Axis/FootPrint polylines. Mesh edges and bounding-box dimensions are not substitutes for a wall's modeled axis. |
| `perimeter` | `footprint`: boundary length, including holes, of the union of XY mesh projections. |
| `horizontal_distance` | `minimum_projected_separation`: minimum separation between projected source meshes, with nearest XY points in evidence. Concave footprints remain concave. |
| `distance` | `surface_centroids`: 3D distance between area-weighted modeled surface centroids. It is distinct from minimum clearance, gate-center distance and a walkable route. |

Measurements use one bounded subprocess batch, physical metre coordinates,
source-hash verification and revision/settings caching. Spatial parents can use
their authorized represented descendants; every required object remains inside
the exact captured scope. Missing geometry, exhausted work limits and hidden
required descendants remain explicit. Evidence records methods, source and
representation STEP IDs, coordinate frame, tolerance, mesh/work counts and numeric
inputs. Tessellated results and downstream arithmetic retain `estimated` quality.
Standing-height proof retains complete side-patch checks and unresolved column /
triangle locators; an observed span range is not a verified uniform height.
One-face area retains the actual-body prism, placement, unit and material-axis
inputs. Authored thickness/offset agreement is reported independently; material
allocation retains its separate strict layer-dimension verification. A gross-one-face basis is deliberately absent: filling cap holes does
not restore bottom-touching doorway cuts. Literal typed native `GrossSideArea`
can still be queried as its stored source quantity.
Partial measurements cannot become exact complete totals. Successful numeric records
share a 2,048-record / 16 MiB cache bounded by a conservative Python-object size
estimate; source/version/basis/units/tolerance, native groups, explicit roots and
scope completeness are part of their identity. No meshes are retained. A first
room-footprint query can prefetch at most 512 authorized spaces in a three-second
batch; this never includes hidden rooms or adds unrelated objects to the answer.

An explicit scalar `aggregate` with `method=sum` and `missing_values=partial`
can total the original `material_quantity.volume` cells or `measure` area `value`
cells. It verifies a complete source batch, per-cell record identity, nonnegative
quantities, compatible units/bases and unavailable-record lineage. Known cells
and unresolved cells retain separate calculation inputs. When quantities remain
unknown, the result is a partial `lower_bound` known subtotal of recorded/model
estimates, rather than a complete total or certified physical minimum. A known
zero subtotal leaves the unresolved inputs visible; an all-unavailable batch
returns `missing_information` without a number. The default `missing_values=fail`
still rejects incomplete totals. Grouped partial sums, arbitrary properties,
length/elevation measurements and partial mean/min/max are unsupported. Bound
results cannot enter scalar arithmetic.

#### Wall measurements and selected source checks

`height` with `basis=validated_vertical_spans` measures local modeled wall-side
height while allowing the bottom and top elevations to vary along the wall. It
checks paired horizontal columns, complete triangulated ruled side patches, and
consistent top/base surface vertices within the physical tolerance. It retains
every patch's source triangle indices, physical endpoints, residuals and the mesh
hash. Open-bottom surface models can qualify: this operation does not require a
closed solid or claim that the bottom boundary is verified ground contact.
Unpaired vertices, incomplete patches and inconsistent local spans retain their
observations but produce no uniform numeric height. The current proof also
conservatively requires cap vertices to have paired columns; unresolved geometry
means the proof is incomplete, rather than a missing physical wall or zero height.

A selected native-source check on 15 November 2026 used the three literal wall
proxies in `ettenheim_gis_city.ifc`. `Mauer-Mitte` (`#50008`) verified at an
estimated **3.0 m**: 492 paired columns, 486 complete side patches and 486 top
triangles. Its global elevation interval spans 21 m, which describes terrain and
wall elevation together. `Mauer-Innen` and `Mauer-Aussen` remain unresolved: the
proof found 246 and 26 unpaired columns respectively, together with unsupported
side patches. The inner wall has observed paired spans of approximately 2–3 m;
those observations do not establish one uniform height. All inner unpaired
vertices lie on open source boundaries, and the outer mesh also has unpaired
boundary/side vertices, so these gaps cannot all be dismissed as harmless
interior tessellation. The validated three-row engine result is partial.

`area` with `basis=net_opaque_face` requires a complete actual-body prism along a
horizontal native layer normal. It returns one congruent vertical cap's area,
preserving window holes and bottom-touching doorway cuts. Closed-body integration,
congruent cap unions, complete side coverage and volume = cap area × actual
thickness are still required. Authored total-layer thickness and offset can
disagree with the actual body: both values and their residuals remain in proof,
while the separate strict material-allocation verification still rejects that
disagreement. The distinct `uniform_layer_axis_body_prism.v1` proof explicitly
has `material_allocation_eligible=false`. Material usage, native placement,
units, source representation and prism checks remain in
the measurement evidence. It requires a source-backed exterior occurrence
selection before it can contribute to a facade query; source exterior flags
alone do not certify physical exposure. This area excludes glazing and does not
establish a complete gross facade or paint quantity.

Selected engine checks using recorded `IsExternal=true` gave:

| Source | Selected walls | Verified faces | Unresolved walls | Known one-face subset |
| --- | ---: | ---: | ---: | ---: |
| `duplex_arc.ifc` | 23 | 17 | 6 | 255.852803 m² |
| `4351_arc.ifc` | 33 | 26 | 7 | 988.90495997 m² |

Neither subset is a complete facade total. Duplex's unresolved inputs comprise
four unequal opposite caps, one nonuniform axis shape and one unusable source
shape. The two former thickness-only failures (`#121` and `#122`) now verify
actual-body faces of 11.741795 m² each; strict material allocation remains
unavailable. The seven 4351 failures are all nonuniform axis shapes. Its two
former thickness failures (`#59871` and `#107834`) contain 150 and 164 vertices
off the proposed two endplanes, by up to 2.641 and 2.926 m respectively; removing
a material-thickness check cannot establish a body prism. Those failures mean
the uniform-prism method did not establish the requested area; another source
quantity or independently validated geometric method may still be usable.
Queries took approximately 0.95 and 1.43 seconds respectively after model load.
These selected Linux checks used Python 3.14 and IfcOpenShell 0.9.0.post1, without
external inference. Saved local proof artifacts are under
`build/ifc-wall-measurements/`; they are separate from the synthetic geometry
regressions and dataset-wide acceptance.

### Modeled walking routes

`route_query` starts from selected `IfcSpace` origins, optionally targets a prior
native door selection, and uses the captured scope's room, opening, door and stair
inventory. `shortest` starts at an explicitly exported modeled interior point or
one supplied physical point. `farthest` requires `start_basis=farthest_sampled`
and returns the maximum of sampled shortest paths across the selected room
regions. It is an estimated sampled maximum, not an exact continuous-domain
maximum; unreachable selected rooms remain unresolved.

The isolated CPU worker projects validated room bodies with holes, connects only
native door/opening paths and matched VIRTUAL open boundaries, and uses one
polygon visibility graph per room plus weighted shortest-path search. Opening
bridges must lie in the actual room/opening union. VIRTUAL patches require
coincident support, opposite room interiors, and a frame interpretation verified
against the room body. Straight native stair walking lines use source rise data
checked against the stair body and endpoint room floors; the reported stair
length is a pitch-line approximation. A double-height room never supplies an
invented vertical connector.

Output includes ordered rooms, traversed doors/stairs, the recorded outdoor
target, estimated physical path distance, nominal door bottleneck, modeled gross
opening-contact bottleneck, unavailable actual clear width, and qualification.
`RouteEvaluation` retains 3D metre path points, per-segment lengths, source and
placement/representation/rise/units anchors, portal/connector checks, source hash,
scope/settings fingerprint, sampling scale and unresolved inputs. Highlight
members describe the chosen path; the full graph inventory remains in calculation
proof. Every returned distance is recomputed from the exported points.

Recorded outdoor boundaries do not certify emergency exits. Literal `IsFireExit`
labels are not booleans. Door operability, hardware clearance and movable
obstructions are unknown, so current paths remain partial potential-route
estimates and cannot establish egress compliance. A positive `clearance_m` request
retains that missing verification. Hidden required portals, missing room bodies,
unsupported connectors and work/deadline exhaustion remain distinct from zero.

Current limits are 500 rooms, 1,000 doors, 64 stair flights, 2,000 portal samples,
8,000 total visibility nodes, 50,000 edges, 128 reflex/hole vertices per room,
3,000 farthest-point samples and a ten-second native worker deadline. Successful
source/scope/settings-bound path proofs share the bounded numeric-record cache;
failed requests do not create persistent absent-connectivity facts. See the
[route implementation findings](IFC_ROUTE_PLAN.md) for actual source checks and
remaining qualifications.

### Recorded distribution networks

`network_query` starts from selected `IfcDistributionPort` occurrences and can
also reference a separately selected physical component set using
`component_step_id`. It uses anchored native `has_port` and `port_connected_to`
relationships. IFC2X3 port-to-element relationships and IFC4 port nesting are
preserved; duplicate/reverse connection records count as one undirected edge.

Results contain selected, connected and isolated ports; unique edges;
connectivity percentage; port-graph connected components and largest component;
component counts, owner coverage, ports per component and component integration
percentage. The separate component graph links two selected owner occurrences
only when a native port pair connects them. It does not invent internal flow
through every port of a component.

The connectivity denominator is the selected native port inventory. An edge to
an in-scope port excluded by the network filter is reported as a cut connection
and does not count in that induced graph. Required owners or connection endpoints
outside the captured view produce `incomplete_coverage`. With no recorded ports,
port counts are zero and the connectivity ratio is undefined, represented by a
missing cell rather than zero percent. A supplied component set includes portless
components in its denominator; otherwise the component inventory is the distinct
recorded owners of the selected ports. The result records graph counts, definitions,
a graph-content hash, source objects and native relationship anchors. This is an
analysis of modeled source topology, without claims about physical completeness,
commissioning, capacity or operational flow.

### Arithmetic and derived tables

`arithmetic` combines two to 32 earlier numeric scalar results with `add`,
`subtract`, `multiply` or `divide`. It never accepts executable expressions or
model-invented operands. The input calculation nodes, source facts, units and
object sets remain in the result. Additions/differences require matching quantity
meanings and net/gross bases. Products and ratios derive dimensions explicitly;
net/gross area ratios are allowed without relabeling either source quantity.
Zero denominators, unresolved units and incompatible meanings produce explicit
non-answers. Estimated operands retain estimated result quality; unresolved
membership and exterior-door lower bounds cannot become exact arithmetic.
The standard `unit:%` represents a dimensionless ratio with SI multiplier 0.01,
so a divided result can be returned as a percentage without a fabricated constant.

`table_calculate` applies the same arithmetic to two to eight numeric
`result_column` fields in each row. It preserves the source columns and adds a
new `value_key`. Its `percent_of_total` variant accepts one numeric column and
optional `group_by` columns, adding each row's share of the source-derived group
sum. It defaults to `unit:%`; each percentage retains numerator, denominator,
sum and division calculation nodes. A distribution with a zero denominator
remains unknown, rather than zero percent.

`consecutive_difference` accepts one numeric value field and a numeric `order_by`
field, optionally grouped by a containing building or other source column. It
sorts within each group and returns successive pairs: the original row, a
`following` record containing the next row, and the difference. This supports
floor-to-floor heights from native storey elevations with both level identities
and elevation facts. Duplicate ordering values require clarification; the last
level does not acquire an invented height. Table calculation inputs are bounded
to 2,000 rows and internal sums have at most 32 operands per calculation node.

## Scope, quantities, and evidence

- Default scope is the supplied model revision's `modeled_objects`. Source
  record scope is also supported. Floor names resolve to entity roots, whose
  containment/assembly descendants are included. Missing or ambiguous names
  produce `needs_clarification`; they never broaden scope to the whole model.
- Traversal stays inside scope, including traversal to types and materials.
  For cross-floor/type/system exploration, use model-wide scope with a filtered
  starting selection. Inherited scalar properties are already retained on
  occurrences with anchors pointing to their original type property records.
- The default policy counts distinct occurrences. `topmost_matches` counts
  matching parent assemblies; `leaves` selects matching objects with no
  decomposition children. These are explicit model policies, not a universal
  interpretation of a construction trade's counting rules.
- A known class can have a complete zero count in the supplied model. That is
  a statement about modeled objects, not proof that the physical building has
  no rooms, doors, or systems. `physical_building` scope is unsupported.
- Each scalar is evaluated once per selected entity. Repeated identical native
  values retain their evidence and do not inflate totals. Conflicting values
  yield `conflicting_evidence`. Occurrence properties override matching type
  properties, including explicit null overrides.
- Length, area, and volume units resolve independently. Explicit quantity units
  override project defaults; square/cubic prefixes use squared/cubed scaling.
  Supported units use decimal arithmetic, preserving the numeric values supplied
  by IfcOpenShell. Unknown or unsupported units cannot be used in aggregation.
  Quantities with different meanings/bases cannot be combined solely because
  their dimensions match.
- Missing aggregate inputs fail the whole query. Missing predicate fields use
  three-valued logic: negating an unknown comparison remains unknown.
  Grouping defaults to the same failure rule. An explicit
  `missing_groups=unclassified` retains absent, null and ambiguous group labels
  as distinct unavailable bins, with exact occurrence counts and a partial
  result explaining the missing classification. These objects are included in
  the inventory; unknown group labels never become a fabricated source string,
  an exclusion or a numeric zero.
- Each returned claim references a matching coverage declaration in
  `engine.bundle`. These declare complete evaluation of the queried source
  records; they do not validate the authoring model against physical reality.
  Export `--bundle-out` together with a result when sharing/verifying references.
  Table cells have individual evidence bindings. Selection records excluded
  candidates; native traversals cite relationship records; aggregation records
  unit-conversion nodes alongside source quantities.
  Native STEP and GUID selectors are ready for a viewer integration; this
  implementation does not render or highlight geometry itself.

Bundle, plan, and result validation reuse `contracts/validation.py`. The
executor independently calculates answers; the validators check reference,
scope, unit, policy, and evidence consistency. Neither layer formally validates
the source IFC against every EXPRESS rule or establishes as-built accuracy.

## Caching and boundaries

Models of 32 MiB or larger use deferred native property hydration. Initial
extraction retains object identity, labels, class facts, relationships and the
available field vocabulary. Before a predicate, projection, grouping or aggregate
uses a field, the engine consults the original native source for those selected
objects. An unchecked property is never interpreted as absent. Type inheritance,
occurrence overrides, explicit nulls, source units and original evidence IDs
have the same semantics as eager extraction. Native port-network metrics need
no per-occurrence property hydration.

Each question has a bounded budget of 200,000 inspected entity/field pairs and
200,000 emitted property facts. Exceeding that budget produces an explicit
non-answer. The HTTP session clears request facts before the next complete
question, after capturing the previous response's proof; discovery and plan
execution share one budget. Native anchors and units remain stable. Deferred
models require their retained original source and do not use the standalone
JSON extraction cache. Small sources continue to use eager extraction.

An optional JSON extraction cache is keyed by source content, resolved source
URI, extractor version, IfcOpenShell version, and attribution configuration.
Cache writes are atomic. Editing a source produces a new asset/document revision
and cache entry. Queries use in-memory indexes; SQLite is a future persistence
adapter, not required for this version. Source files and supplied QA are never
modified or used as an answer lookup.

The extractor handles one `IfcProject` per file, `IfcProduct`
occurrences, type definitions, systems, zones, materials, common scalar
attributes, single-value properties, bounded native enumeration/list properties,
and simple quantities. Lists preserve selected values, source order, duplicates
and original strings. Empty lists, nulls and unextracted complex records remain
distinct. Per-value IFC measure types resolve matching explicit or project units;
an untyped real value does not acquire a guessed currency or dimensionless unit.
Collections are bounded to 256 entries and 65,536 text characters per property;
unsupported nested/reference values retain a `not_extracted` fact with their
original source locator. It preserves
containment, aggregation/nesting, typing, material, system/zone membership and
the native topology described above. Project metadata includes the actual
`FILE_SCHEMA` declaration, native authoring-application information and
site/building address fields where present. Original strings and source anchors
are retained; a legacy standard label in application metadata does not override
the file's schema declaration.
`NativeFilename` preserves literal `FILE_NAME.name` independently of the upload
title. `ApplicationIdentifiers` inventories up to 256 native `IfcApplication`
records in STEP order, retaining each STEP locator, identifier or explicit-null
status, and source anchors. It is separate from the owning application's scalar
`ApplicationIdentifier`. An empty source inventory remains an empty list; an
exhausted inventory budget is `not_extracted`. These metadata fields support
source identity and discovery; they do not map question titles to model answers.
Opaque entity IDs are stable within a source revision. Cross-file identity
reconciliation and multi-model federation are not implemented.

The question API supplies deterministic natural-language result summaries in
`QueryResult.explanation` using executed source values. This adds no second
inference call and does not replace claims, facts, anchors or calculation inputs.
The engine remains a structured executor rather than a natural-language planner.

General geometry predicates, clash detection, unrestricted route finding and orientation predicates,
general partial aggregates beyond the restricted source-quantity sums and exterior-door lower
bounds, arbitrary nested/reference/table IFC
properties, estimated-value propagation, natural-language planning, and
SVG/3D rendering remain explicit extension points. Ranked outputs are bounded
and use deterministic tie order; they do not imply a unique maximum.

The regression suite creates tiny IFC fixtures for scope, overrides, assemblies,
unit conversion, duplicates, missing inputs, predicates, grouping, traversal,
cache invalidation, and CLI exports. An additional real-model test verifies
the Esplanades counts at
`dataset/junction-dataset-preview/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc`.
A full-only or nested extraction can skip that test even when another copy exists;
run the real-file commands above to check that copy explicitly.

Additional manual checks on the preview found 119 sanitary fixtures through
IFC2X3 type relationships in the clinic model, and 579 stair occurrences versus
15 topmost stair assemblies in Molio. These are selected integration checks,
not a dataset-wide accuracy measurement. Small fixtures also cover IFC4X3_ADD2.

The real `ifc_bench/ac20_arc.ifc` model also supports a quantity example:

```sh
python -m ifc_engine sum dataset/junction-dataset/data/ifc_bench/ac20_arc.ifc space --property BaseQuantities.NetFloorArea --unit m2
```

This returns the stored-quantity sum 1939.3839474444 m2 (1939.38 m2 rounded).
Ranking the same property identifies room `006` with 128.2728 m2. Its two widest
doors are `Tür-019` and `Tür-018`, with stored widths of 2.0 m and 1.8 m.

Implementation references: [IfcOpenShell examples](https://docs.ifcopenshell.org/ifcopenshell-python/code_examples.html),
[unit utilities](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/unit/index.html),
and the project's [shared contracts](SCHEMA.md).

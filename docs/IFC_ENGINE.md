# Local IFC query engine

The initial implementation reads an IFC into the shared `KnowledgeBundle`,
executes validated `QueryPlan` operations, and returns a `QueryResult` with
materialized entity sets, source anchors, facts, and calculation nodes. It runs
locally on a CPU. The [IFC question API](IFC_QUESTIONS.md) now uses Nemotron to
produce validated plans and returns the engine's answer with source evidence.

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

### Native spatial queries

The `spatial_query` plan operation answers bounded topology questions using
extracted IFC relationships. It accepts `input_step_id` and one of these relations:

| Relation | Result and evidence |
| --- | --- |
| `containers` | Native containment/aggregation ancestors of the requested `container_kind`: `space`, `storey`, `building` or `site`. |
| `boundary_neighbors` | Rooms linked by corresponding native space boundaries. When only a shared boundary element is available, the output is explicitly partial candidate neighbors; a shared wall can span separated rooms. |
| `door_connections` | Rooms sharing physical boundary doors, including boundary openings filled by doors. A shared wall is insufficient. |
| `outdoor_access` | Selected room occurrences with PHYSICAL, EXTERNAL door-boundary evidence. Counting the result counts rooms, rather than doors or boundaries. |

Native space boundaries, openings/fillings and corresponding-boundary links
retain anchors to their original records. Native system and zone membership is
also retained for relationship traversal. These relationships describe the
authoring model; they do not establish a navigable route, equipment service
coverage or fire-exit compliance.

Every input, intermediate and returned object remains inside the executable
scope, including `Scope.exact_entity_ids` for captured browser views. Required
objects outside the scope produce `incomplete_coverage`, without broadening the
view. Missing required topology produces `missing_information`, distinct from a
supported zero result. Spatial summaries identify native evidence and partial
inferences explicitly.

The [IFC question-family audit](IFC_QUESTIONS.md#supplied-question-families)
traces these operations to supplied location, connectivity and outdoor-access
questions. Geometry-derived distances, routes and orientation remain uncovered
requirements within the wider IFC-Bench catalog, rather than implied support.

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

An optional JSON extraction cache is keyed by source content, resolved source
URI, extractor version, IfcOpenShell version, and attribution configuration.
Cache writes are atomic. Editing a source produces a new asset/document revision
and cache entry. Queries use in-memory indexes; SQLite is a future persistence
adapter, not required for this version. Source files and supplied QA are never
modified or used as an answer lookup.

The extractor handles one `IfcProject` per file, `IfcProduct`
occurrences, type definitions, systems, zones, materials, common scalar
attributes, single-value properties, and simple quantities. It preserves
containment, aggregation/nesting, typing, material, system/zone membership and
the native topology described above. Project metadata includes the actual
`FILE_SCHEMA` declaration, native authoring-application information and
site/building address fields where present. Original strings and source anchors
are retained; a legacy standard label in application metadata does not override
the file's schema declaration.
Opaque entity IDs are stable within a source revision. Cross-file identity
reconciliation and multi-model federation are not implemented.

The question API supplies deterministic natural-language result summaries in
`QueryResult.explanation` using executed source values. This adds no second
inference call and does not replace claims, facts, anchors or calculation inputs.
The engine remains a structured executor rather than a natural-language planner.

Geometry measurements, clash detection, route finding, nearest-distance and
orientation predicates,
arithmetic plan steps, partial aggregates, arbitrary nested/list/table IFC
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

# Shared contracts: drawings, building facts, queries, and evidence

Contract version: **0.1.0**. The source of truth is [contracts/models.py](../contracts/models.py); [contracts/validation.py](../contracts/validation.py) supplies cross-record validation. These contracts represent the observed IFC, CAD, PDF, raster, schedule, quantity, property, and missing-information tasks. They do not claim that every represented operation already has an executor.

Current consumers are the standalone [IFC executor](IFC_ENGINE.md) and generated
types used by the [mock frontend](../frontend/README.md). They are not integrated
through an API yet. Use the executor's capability manifest for supported
operations; the frontend's prepared evidence is not extracted source truth.

The [project scope](PROJECT_SCOPE.md) is bounded by the supplied dataset's question
families. The schema can represent extensions beyond that set; representability
does not make them hackathon requirements. No unknown evaluation class needs to
be anticipated. Keep validators and evidence checks for the tasks actually used.

The core distinction is **source evidence → canonical entities and facts → a resolved query → calculated claims**. A printed door symbol, a DXF arc, a schedule row, an IFC object, and a physical door are different things. The schema connects them without assuming they are identical.

## Public root contracts

| Root | What crosses this boundary | Generated JSON Schema |
|---|---|---|
| `KnowledgeBundle` | Immutable source metadata, extraction provenance, catalogs, geometry, canonical facts, and coverage | [KnowledgeBundle](../contracts/jsonschema/KnowledgeBundle.schema.json) |
| `QuestionRequest` | Original multilingual question and attached asset/view IDs; previous request IDs are context | [QuestionRequest](../contracts/jsonschema/QuestionRequest.schema.json) |
| `QueryPlan` | Resolved scope and an allowlisted operation DAG with named outputs | [QueryPlan](../contracts/jsonschema/QueryPlan.schema.json) |
| `QueryResult` | Typed claims, exact memberships, calculation DAG, evidence bindings, issues, and metrics | [QueryResult](../contracts/jsonschema/QueryResult.schema.json) |
| `CapabilityManifest` | What this executor version can actually handle | [CapabilityManifest](../contracts/jsonschema/CapabilityManifest.schema.json) |
| `BenchmarkCase` | Reference answer, source JSONL location, split/leakage group, tolerance, and adjudication | [BenchmarkCase](../contracts/jsonschema/BenchmarkCase.schema.json) |

Generate the JSON Schemas from the repository root with `python -m contracts.export`. Check that they are current with `python -m contracts.export --check`. Do not edit the generated files. Draft 2020-12 schemas use internal `$defs` and stable versioned URN IDs; they require no network resolution.

Install contract dependencies with `python -m pip install -r contracts/requirements.txt`; run the contract suite with `python -m unittest tests.test_contracts -v` or `python -m pytest tests/test_contracts.py`. Pydantic is the runtime dependency; JSON Schema and pytest support conformance/testing. These instructions operate from the repository root using the configured Python environment. An unqualified `python -m pytest` also discovers IFC tests and requires the full dependencies described in [README](../README.md#install-and-use-the-ifc-engine).

All models forbid unknown fields. Internal IDs are opaque nonempty strings. `schema_version` is the wire contract version, separate from source revisions and extractor/model versions. Consumers must reject unsupported versions rather than silently reinterpret data. Adding a new union variant or changing count semantics requires an explicit compatibility decision and regenerated schemas.

## Knowledge collections and their relationships

| Collections | Meaning |
|---|---|
| `projects` | Dataset/project boundaries used for source resolution and access to related documents. |
| `documents` | Logical document **at a specific revision**, with a project, logical key, discipline, localized title, and optional superseded revision. |
| `assets`, `asset_links` | Immutable files/representations with URI, SHA-256, format, attribution, and license. Links explicitly record equivalent representations, render/conversion origins, or byte duplicates. Same filename stems alone do not prove correspondence or revision equality. |
| `runs` | Extractor/tool/model revision, configuration hash, input assets, output schema version, and start time. Re-extraction creates a new run; do not overwrite historical facts. |
| `concepts`, `properties`, `units` | Extensible canonical catalogs with original-language labels and precise definitions. Concept hierarchies support shared terms; property definitions state value kind, quantity kind, and dimensions. |
| `frames`, `transforms`, `geometries` | Explicit coordinate spaces, mappings, and shapes: point, polyline, multipolygon with holes, box, or content-addressed mesh. |
| `views`, `calibrations` | Pages, plans, details, site maps, schedules, legends, and tiles; each is tied to an asset and frame. Calibration applies to one view. |
| `anchors`, `features` | Exact source locators and extracted source content, including text/OCR, primitives, detections, segmentation, tables, rows, and cells. |
| `entities`, `representations` | Canonical building/site objects and their potentially many source depictions. A representation connects an entity to asset/view, feature, geometry, and anchor IDs. |
| `facts`, `relations` | Provenanced property assertions and entity relationships. Multiple competing assertions remain separate. |
| `coverage` | What concepts/properties were exhaustively extracted or modeled for a precise scope and counting policy. |

### Source identity and canonical identity

`NativeSelector` preserves identifiers such as an IFC GUID, STEP ID, DXF handle, SVG ID, PDF span, or table cell. CAD `instance_path` distinguishes repeated block INSERT instances that share a source handle. `property_path` preserves localized property-set/attribute names. Selectors are asset scoped; an IFC GUID is not a globally authoritative physical-object identity across revisions.

`SourceFeature` describes something actually extracted. It does not automatically become one countable object. A window can have three CAD polylines, a double-leaf door one logical opening, and a double-bowl sink one fixture. `Entity` is the canonical counting unit within its document/project context. `Representation` can connect that entity to several source features and file formats. Cross-document identity is an explicit, provenanced `same_as` relation, not a filename or GUID heuristic silently applied during counting.

Relations preserve `contains`, `aggregates`, `typed_by`, `assigned_to_system`, `has_material`, `belongs_to_unit`, `adjacent_to`, `connected_to`, `hosted_by`, `depicts`, and `same_as`. Unmapped source relations can use `custom` plus `native_predicate`; executors must advertise supported meanings before querying them. Spatial containment and assembly aggregation are separate graphs.

### Facts, language, and absence

Every `Fact` has a canonical `property_key`, the original property path, status, and provenance. Only `present` facts carry a typed value. Other statuses are `explicit_null`, `not_in_source`, `not_extracted`, `unknown`, and `ambiguous`. An absent fact is not evidence of a null value or a zero.

`LocalizedText` retains text and language when known; null language means undetermined. Labels and source text remain available even after canonicalization. Room ID `7.16` and door ID `121.A` are exact strings; do not turn them into numbers or translate them. A French literal room label and a canonical bedroom class may differ. Keep those assertions separate.

`Provenance` records the extraction run, anchors, and method (`native`, `computed`, `ocr`, `detected`, `inferred`, or `human`). An optional score requires an understood score name and is not automatically a calibrated probability. Confidence in detection does not establish complete inventory coverage.

Extraction timestamps must be offset-aware ISO-8601 values. Record UTC or an explicit offset; a naive local timestamp cannot establish ordering across workers.

## Geometry and measurement

A `CoordinateFrame` names the asset, 2D/3D axes, presentation versus physical space, optional unit, and optional CRS. Choose and document axis conventions explicitly, including PDF/image Y direction. `Geometry` always references a frame. There are no implicit pixels, millimetres, or world coordinates.

The semantic validator requires a resolved length unit for physical frames. Keep uncalibrated drawing coordinates in presentation space until their physical meaning is established.

Transforms specify `from_frame_id`, `to_frame_id`, kind, matrix, and provenance. They map column vectors in homogeneous coordinates: the target is `M × source`, followed by homogeneous division when required. An affine 2D mapping is 3×3; 3D is 4×4; a 3D-to-2D projection is 3×4. An inverse map must be explicitly computed and validated; a projection is not invertible by assumption. Matrix shape and frame dimensionality must agree. Do not infer an object-to-view mapping from a label or shared filename.

Polygon shells and holes are closed rings. A room can contain column holes or disconnected components; these must survive through measurement and evidence rendering. Ring closure alone does not prove topology. The semantic validator additionally rejects zero-area/self-intersecting simple 2D rings, holes outside or touching their shell, and overlapping/nested holes. It does not validate intersections between separate multipolygon parts, arbitrary 3D topology/planarity, or measurement correctness. Geometry processing still owns those checks. Meshes and large rendered assets are stored externally by URI and content hash.

A page may contain a floor plan, a site inset, and a legend at different scales. Use separate views and calibration IDs; never establish one metres-per-pixel conversion for the whole page unless that fact is supported. `Calibration` links its view, a transformation, method, and supporting provenance. Cropped/rotated tiles keep their own frames and mappings back to the original view. A drawing marked not to scale can still support symbol counts while metric measurement remains unsupported.

Unit dimensions use SI exponent order **(length, mass, time, electric current, temperature, amount of substance, luminous intensity)**. SI conversion is `SI = magnitude × si_multiplier + si_offset`. Presentation units such as pixels or PDF points do not establish building dimensions. Dimensionless physical quantities use an explicit unit such as `unit:1`; unknown units use null.

`QuantityValue` keeps the original decimal magnitude, unit resolution, quantity kind, basis, source value type, original text, and optional normalized value. Decimal strings avoid silently changing source precision. Preserve a width such as `5'-10 3/8"` in `source_text` while storing its parsed magnitude/unit separately. Preserve IFC typed millimetre lengths and project-default unit evidence before normalizing to metres. Area/volume units may be explicit and must not be inferred by blindly squaring/cubing the project's length-unit setting.

`unit_resolution` distinguishes `explicit`, `project_default`, `calibrated`, `derived`, and `unknown`. Unknown units cannot have normalized values. `basis` distinguishes net/gross/centerline/specified/modeled/calculated meanings; common dimensions alone do not make two quantities semantically interchangeable. `quality` states exact, estimated, lower-bound, or upper-bound status. Arithmetic must propagate both dimensional and quality constraints.

## Scope, counting grain, and completeness

`Scope` is explicit: one project, document revision IDs, optional entity roots, optional views, and a universe. Within an entity/view list, IDs are alternatives; all populated restriction families **intersect**. Entity roots include descendants. Empty entity/view lists add no restriction. `document_ids` cannot be empty. A question attachment locates available context and does not automatically impose the query's scope.

The universe changes what a count means:

| Universe | Meaning |
|---|---|
| `source_records` | Records present in the selected files, regardless of whether they map one-to-one to objects. |
| `modeled_objects` | Building/site entities represented by the model. |
| `depicted_objects` | Objects in the selected drawing views. |
| `schedule_entries` | Specified rows/entries, not necessarily installed physical objects. |
| `physical_building` | A claim about the building itself; this requires evidence beyond merely having extracted a file. |

For a model-wide question attached to a floor PDF, resolve the associated model/document scope and leave floor `view_ids` empty. A floor-only result uses its resolved storey/view restriction. Do not use the same coverage assertion for these two questions.

`CountPolicy` states grain (`logical_object`, `occurrence`, `assembly`, `part`, or `schedule_row`), hierarchy (`all_matches`, `topmost_matches`, or `leaves`), distinct canonical identity, and a versioned `rule_key`. Counting door openings fitted with leaves is a rule; counting leaf panels is another. Fifteen top-level stair assemblies must not become 579 stair parts. Canonical identity and these policies determine membership before arithmetic.

`Coverage` applies to an exact scope, concept/property set, and optional counting policy. States are `complete`, `partial`, `not_modeled`, `not_extracted`, and `unknown`. Missing `IfcSpace` records do not establish zero rooms; a model containing only heating systems cannot establish the absence of doors in the building. A complete zero-count claim requires complete relevant coverage and an explicitly empty counted set.

## Query contract

`QuestionRequest` is unresolved user input. A `QueryPlan` is executable intent: all IDs must already resolve to catalog/scope objects. A request requiring clarification yields a non-answer result rather than a plan with guessed IDs.

`QueryPlan.steps` are a topologically ordered DAG with unique step IDs; inputs can refer only to earlier steps. `outputs` maps stable output keys to step IDs, allowing multipart responses. A result claim's `output_key` references exactly one of these keys, independently of its human-readable `name`. The initial schema uses one shared scope per plan. Questions requiring independently scoped model revisions should be split into plans or expressed with explicit filters/traversals within the common resolved scope.

| Operation | Meaning |
|---|---|
| `select` | Select canonical concepts/entity kinds with typed `where`/`exclude` predicates and explicit count policy. |
| `traverse` | Follow an allowlisted relation in a direction, optionally recursively with a bounded depth. |
| `aggregate` | Count/sum/mean/min/max, optional grouping, declared missing-value handling, and requested output unit. Numeric aggregates require a field; count does not. A grouped result's measure column uses `value_key` (default `value`); group columns use their field keys. |
| `project` | Retrieve catalog fields such as dimensions, materials, or localized descriptions. |
| `rank` | Sort by a field and retain a bounded number of rows/entities. |
| `measure` | Compute area/union area/length/perimeter/volume/distance/angle from geometry, with basis, unit, optional reference entities, and calibrations. |
| `arithmetic` | Add/subtract/multiply/divide earlier scalar outputs, with dimension checking. |

Arithmetic inputs are ordered. Subtraction and division fold from left to right; an executor must check compatible dimensions for addition/subtraction and derive the dimensions for multiplication/division. The current validator checks scalar input shapes and declared unit references; it does not implement full dimensional type inference or recompute arithmetic.

`FieldRef` identifies a property, label, concept, native identifier, entity ID, or `result_column`. Source/catalog fields apply to entity-set inputs; `result_column` resolves only against columns produced by an earlier rowset step. Group keys and the aggregate `value_key` must be distinct. This prevents treating a calculated count column as if it were a stored building property. `project` retrieves a rowset; it does not silently unwrap a singleton as a scalar. Use a scalar aggregate after an explicit singleton selection when a numeric scalar is needed.

Typed predicates support compare, field presence, related entities, spatial predicates, and recursive all/any/not. `near` requires a distance quantity. Missing values and incompatible dimensions cannot be silently compared or added. Property aliases resolve to canonical catalog keys before execution; arbitrary SQL, Python, and unregistered function strings are not query operations.

Traversal stays within the explicit scope. To query a floor's doors through model-wide type/material definitions, use model-wide scope and an explicit floor selection before traversal, or extract inherited properties onto occurrences while preserving the original type/property anchors. The plan validator checks conservative candidate sets without executing filters, so an extractor/executor remains responsible for the final selected membership and geometry suitability.

`required_capabilities` and the executor's `CapabilityManifest` make representability distinct from implementation support. `operations` contains specific capability IDs such as `select`, `aggregate.count`, `aggregate.sum`, `measure.union_area`, and `arithmetic.divide`. Both declared requirements and the operations actually used must be supported. Relation/property/concept names must also be allowlisted against the manifest and catalog. A parsed `measure.volume` request does not prove a volume engine is installed. Report `unsupported_operation` when its executor is unavailable, and `insufficient_calibration` when measurement lacks the necessary physical mapping.

### Illustrative request-to-evidence flow

This schema example is not an executable IFC-engine recipe: its IDs and
`door.opening_with_leaf.v1` rule are illustrative. The IFC engine accepts only its
[registered occurrence/assembly/leaf rules](../ifc_engine/catalog.py).

After ingestion has established `project:demo`, `document:demo:r1`, `storey:ground`, `concept:door`, their source anchors, and complete door coverage, this request can be resolved:

```json
{
  "schema_version": "0.1.0",
  "id": "request:doors",
  "question": {"text": "How many doors are on the ground floor?", "language": "en"},
  "project_id": "project:demo"
}
```

```json
{
  "schema_version": "0.1.0",
  "id": "plan:doors",
  "request_id": "request:doors",
  "scope": {
    "project_id": "project:demo",
    "document_ids": ["document:demo:r1"],
    "entity_ids": ["storey:ground"],
    "universe": "modeled_objects"
  },
  "steps": [
    {
      "id": "doors",
      "operation": {
        "kind": "select",
        "concept_ids": ["concept:door"],
        "count_policy": {
          "grain": "logical_object",
          "hierarchy": "topmost_matches",
          "rule_key": "door.opening_with_leaf.v1"
        }
      }
    },
    {"id": "total", "operation": {"kind": "aggregate", "input_step_id": "doors", "method": "count"}}
  ],
  "outputs": {"door_count": "total"},
  "required_capabilities": ["select", "aggregate.count"]
}
```

The executor materializes the unique door IDs into an `EntitySet`, calculates the count, and returns a `Claim` with that count, matching scope/count policy, a complete coverage reference, and an `EvidenceBinding` to the set/calculation. The viewer resolves each entity's representations to the original drawing anchors. If the user asks the same question in Finnish, only the request text changes; the resolved scope, count policy, and calculation remain equivalent.

For a separately resolved whole-building query that ranks floors by door count, first select doors across the building (not within only `storey:ground`). With a registered `property:storey_id` grouping field, these steps produce and consume an explicit derived column:

```json
[
  {
    "id": "by_floor",
    "operation": {
      "kind": "aggregate",
      "input_step_id": "doors",
      "method": "count",
      "group_by": [{"kind": "property", "key": "property:storey_id"}],
      "value_key": "door_count"
    }
  },
  {
    "id": "ranked_floors",
    "operation": {
      "kind": "rank",
      "input_step_id": "by_floor",
      "field": {"kind": "result_column", "key": "door_count"},
      "direction": "descending",
      "limit": 3
    }
  }
]
```

The plan can bind `outputs` to `ranked_floors`; its claim returns a typed table rather than a scalar. Input-step types and available result columns must be validated. Ranking returns a bounded rowset; an executor must not silently reinterpret a top-k result as proof of a unique maximum when ties exist.

## Results, calculations, and evidence

Values are discriminated unions: count, quantity, localized text, boolean, entity references, unavailable, list, record, or table. Lists/records/tables recursively contain typed values. Table row keys must exactly match its unique column keys. This supports grouped quantities, material breakdowns, property answers, and multipart summaries without collapsing everything into text.

`UnavailableValue` preserves a missing cell or field in a partial result, with reason (`explicit_null`, `not_in_source`, `not_extracted`, `unknown`, or `ambiguous`) and explanation. It is not a successful source fact: source absence uses `Fact.status`, and a present fact cannot hide unavailable nested values. An `answered` result cannot contain unavailable values; use `partial` with a corresponding issue. Do not replace missing cells with zero or an invented empty string.

An `EntitySet` states membership, scope, count policy, and count. Small sets carry unique `entity_ids`; large sets use `members_uri` plus SHA-256. Do not provide both. An empty inline set is a valid explicit empty set; absence of a set is not.

A `Claim` contains its typed value, scope, relevant concepts/properties, quality, coverage IDs, and evidence. Claims containing a count anywhere in their value require a counting policy; use separate claims when different fields need different grains. An exact claim cannot contain estimated quantities. `EvidenceBinding.value_path` is a JSON Pointer inside that claim's value (`""` means root), making a specific table cell or record field individually verifiable. Every binding references a calculation node and can cite anchors, facts, and entity sets. Its pointer must exist, and the addressed value must match that calculation's output.

Every claim requires a root binding. The root calculation's `plan_step_id` must equal `plan.outputs[claim.output_key]`, and its output must equal the complete claim value. Additional cell/field bindings can reference supporting scalar calculations; for example `/rows/0/door_count` points to the first row's typed count value. This ties a visible answer to the requested operation instead of merely attaching unrelated evidence to a valid plan. The UI should show selected/excluded objects and direct property/table-cell evidence rather than treating an entire page as sufficient proof.

`CalculationNode` describes explicit computation, optional associated `plan_step_id`, inputs, included/excluded sets, relevant facts/anchors/calibrations, output, quality, and counting/calculation rule. Calculation dependencies form a DAG. Internal conversion/filter/deduplication nodes may have no plan step; claimed output roots must have one. Unit conversion and duplicate-removal steps remain visible. These are operations and source inputs, not private model reasoning. A calculation trace makes its result inspectable; it does not independently prove that the extraction or geometry was correct.

Result statuses are `answered`, `partial`, `needs_clarification`, `missing_source`, `missing_information`, `incomplete_coverage`, `unsupported_operation`, `conflicting_evidence`, `insufficient_calibration`, and `execution_error`. Answered/partial results require a plan and claims; partial/non-answer outcomes require issues. A non-answer outcome requires an issue with its matching code. An `answered` result cannot carry a blocking issue; non-answer outcomes do not carry successful claims. Do not call a partly extracted quantity an exact complete total; return an appropriately qualified partial claim or no answer.

Issues preserve localized messages, entity/fact/anchor references, and clarification choices. Explanation text is presentation; the structured claim remains authoritative. Execution metrics separate latency, model token usage, caching, and cost amount/currency/basis so marginal compute is not confused with amortized ingestion cost.

## Storage mapping

The intended adapters can use the same contract. Only IFC extraction is
implemented; this table describes proposed mappings for the other sources:

| Source category | Primary contract records |
|---|---|
| Swiss Dwellings | CAD features and room/entity representations; polygon holes; multilingual labels; quantity facts. |
| IFC models | Native GUID/property anchors; entities and type/assembly/system/material relations; quantities and storey scope. |
| IFC-Bench | The same IFC records with multipart/grouped/spatial queries, missing facts, and benchmark adjudication. |
| CubiCasa | Raster views, OCR/detection features, canonical instances, transforms, and class-specific coverage. |
| Opening Design | Native PDF text/table/cell features, schedule-row entities, dimension facts, and diagram references. |
| Finna, HABS, Europeana, Wikimedia | Document/view classification, OCR/handwriting features, per-view calibration, source attribution, and explicit partial/unsupported outcomes. |

The JSON is a transfer/validation contract, not a SQL migration. A practical SQLite implementation maps each knowledge collection to a table, using `id` as a primary key (`properties.key` is its key), foreign keys for references, and join tables for many-to-many IDs. Persist revisioned assets, runs, facts, and provenance rather than rewriting previous observations. `asset_links` needs an explicit composite key or storage-only ID.

Use `relations(subject_id, predicate, object_id)` for relationship traversal; `representations(entity_id, asset_id, view_id)` for evidence; `facts(subject_id, property_key, run_id)` for competing property observations. Index these access paths. Keep geometry/mesh payloads in JSON or content-addressed files initially; spatial indexes can be added when measured workloads justify them. Use FTS5 for source/localized labels and text while retaining exact identifiers separately.

Persist request/plan/result envelopes and benchmark cases as separate tables or JSON documents. A benchmark reference is evaluation data, not an inference fact or an answer lookup. Group translations, alternate formats, project floors, revisions, and duplicate assets into leakage partitions before model selection; keep disputed references and source-backed adjudication separately.

## Validation boundaries and limitations

1. **JSON Schema** checks wire shape, discriminated variants, required fields, enums, scalar bounds, and forbidden extra keys. It cannot express all Python validators or cross-record meaning.
2. **Pydantic models** additionally check local invariants such as ring closure, fact presence/value consistency, unknown-unit normalization, table keys, count/set membership, DAG order, and result outcome shape.
3. **Semantic validation** checks references, ownership/revision consistency, coordinate dimensions, unit compatibility/conversions, scope/coverage relationships, query capabilities, and evidence/calculation links. Validate against the actual bundle/catalog before executing or displaying claims. See [validation.py](../contracts/validation.py) for the implemented checks.
4. **Extractors and executors** still establish real completeness, source semantics, geometry validity/topology, calibrated measurements, query selection correctness, calculation correctness, and reference-answer adjudication. Passing a schema cannot prove those facts.

This version is intentionally a contract layer. It is not a general CAD converter, an IFC geometry engine, a multilingual ontology, a unit parser, an image model, an SQL database, or a complete query executor. New concept/property definitions can extend catalogs without inventing new object tables; new operation/value variants need versioned implementation and validation.

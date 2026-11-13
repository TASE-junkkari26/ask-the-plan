"""Source-of-truth contracts. Export JSON Schema with python -m contracts.export.

IDs are opaque internal strings. Source IDs (IFC GUIDs, STEP IDs, CAD handles)
are asset-scoped locators, never substitutes for canonical entity identity.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(min_length=1)]
DecimalString = Annotated[str, Field(pattern=r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")]
NonnegativeInt = Annotated[int, Field(ge=0, strict=True)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
# SI exponents: length, mass, time, current, temperature, amount, luminous intensity.
Dimension = tuple[int, int, int, int, int, int, int]
Point = Annotated[list[float], Field(min_length=2, max_length=3)]
EntityKind = Literal["site", "building", "storey", "unit", "space", "element", "assembly", "part", "type", "system", "material", "zone", "site_feature", "schedule_row"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Contract(Model):
    schema_version: Literal["0.1.0"] = "0.1.0"


class LocalizedText(Model):
    text: str
    language: str | None = None  # BCP-47 when known; null means undetermined.


class Provenance(Model):
    run_id: Id
    anchor_ids: list[Id] = Field(default_factory=list)
    method: Literal["native", "computed", "ocr", "detected", "inferred", "human"]
    score: float | None = Field(default=None, ge=0, le=1)
    score_name: str | None = None  # Not assumed to be a calibrated probability.


class Project(Model):
    id: Id
    name: str


class Document(Model):
    id: Id
    project_id: Id
    logical_key: Id
    revision: Id
    title: list[LocalizedText] = Field(default_factory=list)
    discipline: str | None = None
    supersedes_document_id: Id | None = None


class Asset(Model):
    id: Id
    document_id: Id
    uri: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    format: Literal["ifc", "dxf", "dwg", "pdf", "svg", "png", "jpeg", "other"]
    media_type: str
    source_collection: str
    attribution: str
    license: str


class AssetLink(Model):
    source_asset_id: Id
    target_asset_id: Id
    kind: Literal["equivalent_representation", "rendered_from", "converted_from", "byte_duplicate"]
    provenance: Provenance


class ExtractionRun(Model):
    id: Id
    tool: str
    version: str
    model_revision: str | None = None
    config_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    input_asset_ids: list[Id] = Field(min_length=1)
    output_schema_version: Literal["0.1.0"] = "0.1.0"
    started_at: datetime  # Offset-aware ISO-8601; assets supply input hashes.

    @model_validator(mode="after")
    def check_time(self):
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("extraction timestamps must have a UTC offset")
        return self


class Concept(Model):
    id: Id
    labels: list[LocalizedText]
    parent_ids: list[Id] = Field(default_factory=list)
    definition: str


class PropertyDefinition(Model):
    key: Id
    labels: list[LocalizedText]
    value_kind: Literal["text", "count", "quantity", "boolean", "references", "list", "record", "table"]
    quantity_kind: str | None = None
    dimension: Dimension | None = None
    definition: str


class Unit(Model):
    id: Id
    symbol: str
    kind: Literal["physical", "presentation"]
    dimension: Dimension | None = None
    si_multiplier: DecimalString | None = None
    si_offset: DecimalString = "0"

    @model_validator(mode="after")
    def check_definition(self):
        if self.kind == "physical":
            if self.dimension is None or self.si_multiplier is None:
                raise ValueError("physical units need dimensions and an SI conversion")
            if Decimal(self.si_multiplier) <= 0:
                raise ValueError("unit multiplier must be positive")
        elif self.dimension is not None or self.si_multiplier is not None:
            raise ValueError("presentation units do not establish building dimensions")
        return self


class CoordinateFrame(Model):
    id: Id
    asset_id: Id
    dimension: Literal[2, 3]
    space: Literal["presentation", "physical"]
    unit_id: Id | None = None
    axes: list[str] = Field(min_length=2, max_length=3)
    crs: str | None = None

    @model_validator(mode="after")
    def check_axes(self):
        if len(self.axes) != self.dimension:
            raise ValueError("axis count must match frame dimension")
        return self


class Transform(Model):
    id: Id
    from_frame_id: Id
    to_frame_id: Id
    kind: Literal["affine", "homography", "projection"]
    matrix: list[list[float]]
    provenance: Provenance


class PointShape(Model):
    kind: Literal["point"]
    coordinates: Point


class PolylineShape(Model):
    kind: Literal["polyline"]
    coordinates: list[Point] = Field(min_length=2)
    closed: bool = False


class PolygonPart(Model):
    shell: list[Point] = Field(min_length=4)
    holes: list[Annotated[list[Point], Field(min_length=4)]] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_rings(self):
        for ring in [self.shell, *self.holes]:
            if ring[0] != ring[-1] or len({tuple(p) for p in ring[:-1]}) < 3:
                raise ValueError("polygon rings must be closed with three distinct vertices")
        return self


class MultiPolygonShape(Model):
    kind: Literal["multipolygon"]
    polygons: list[PolygonPart] = Field(min_length=1)


class BoxShape(Model):
    kind: Literal["box"]
    minimum: Point
    maximum: Point

    @model_validator(mode="after")
    def check_bounds(self):
        if len(self.minimum) != len(self.maximum) or any(a > b for a, b in zip(self.minimum, self.maximum)):
            raise ValueError("invalid box bounds")
        return self


class MeshShape(Model):
    kind: Literal["mesh"]
    uri: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    format: Literal["glb", "gltf", "obj", "other"]


Shape = Annotated[Union[PointShape, PolylineShape, MultiPolygonShape, BoxShape, MeshShape], Field(discriminator="kind")]


class Geometry(Model):
    id: Id
    frame_id: Id
    shape: Shape


class View(Model):
    id: Id
    asset_id: Id
    frame_id: Id
    kind: Literal["page", "floor_plan", "section", "elevation", "detail", "site", "schedule", "legend", "tile", "unknown"]
    page_index: NonnegativeInt | None = None  # Zero-based.
    parent_view_id: Id | None = None
    boundary_geometry_id: Id | None = None
    depicts_entity_ids: list[Id] = Field(default_factory=list)
    labels: list[LocalizedText] = Field(default_factory=list)


class NativeSelector(Model):
    kind: Literal["ifc_guid", "step_id", "dxf_handle", "svg_id", "pdf_span", "table_cell", "image_region", "file_metadata"]
    value: str
    instance_path: list[str] = Field(default_factory=list)  # CAD INSERT ancestry.
    property_path: list[str] = Field(default_factory=list)
    row_index: NonnegativeInt | None = None
    column_index: NonnegativeInt | None = None


class EvidenceAnchor(Model):
    id: Id
    asset_id: Id  # Exact immutable revision/representation, not a filename alias.
    view_id: Id | None = None
    selector: NativeSelector
    geometry_id: Id | None = None  # IFC properties need not have a visible shape.
    quote: LocalizedText | None = None


class Calibration(Model):
    id: Id
    view_id: Id
    transform_id: Id
    method: Literal["native_units", "dimension", "scale_bar", "human"]
    provenance: Provenance  # Evidence required; applies only to this view.


class SourceFeature(Model):
    id: Id
    asset_id: Id
    view_id: Id | None = None
    kind: Literal["cad_primitive", "text_span", "detection", "segmentation", "table", "table_row", "table_cell", "other"]
    anchor_ids: list[Id] = Field(min_length=1)
    text: LocalizedText | None = None
    table_id: Id | None = None
    row_index: NonnegativeInt | None = None
    column_index: NonnegativeInt | None = None
    row_span: PositiveInt = 1
    column_span: PositiveInt = 1
    header_feature_ids: list[Id] = Field(default_factory=list)
    provenance: Provenance


class Entity(Model):
    id: Id
    project_id: Id
    document_id: Id
    kind: EntityKind
    concept_ids: list[Id]
    labels: list[LocalizedText] = Field(default_factory=list)
    provenance: Provenance


class Representation(Model):
    id: Id
    entity_id: Id
    asset_id: Id
    view_id: Id | None = None
    feature_ids: list[Id] = Field(default_factory=list)
    anchor_ids: list[Id] = Field(default_factory=list)
    geometry_ids: list[Id] = Field(default_factory=list)
    provenance: Provenance


class NormalizedQuantity(Model):
    magnitude: DecimalString
    unit_id: Id


class QuantityValue(Model):
    kind: Literal["quantity"]
    magnitude: DecimalString
    unit_id: Id | None  # Unknown is null; dimensionless uses an explicit unit:1.
    quantity_kind: str  # length, area, volume, mass, temperature, angle, ratio...
    basis: str  # net, gross, centerline, modeled, calculated, specified...
    unit_resolution: Literal["explicit", "project_default", "calibrated", "derived", "unknown"]
    unit_anchor_ids: list[Id] = Field(default_factory=list)
    source_value_type: str | None = None  # e.g. IfcLengthMeasure
    source_text: str | None = None  # Preserve e.g. 5'-10 3/8\".
    normalized: NormalizedQuantity | None = None
    quality: Literal["exact", "estimated", "lower_bound", "upper_bound"] = "exact"

    @model_validator(mode="after")
    def check_unit_resolution(self):
        if (self.unit_id is None) != (self.unit_resolution == "unknown"):
            raise ValueError("unknown unit requires null unit_id and unknown resolution")
        if self.normalized is not None and self.unit_id is None:
            raise ValueError("cannot normalize an unresolved unit")
        return self


class CountValue(Model):
    kind: Literal["count"]
    value: NonnegativeInt


class TextValue(Model):
    kind: Literal["text"]
    value: LocalizedText


class BooleanValue(Model):
    kind: Literal["boolean"]
    value: bool


class ReferencesValue(Model):
    kind: Literal["references"]
    entity_ids: list[Id]


class UnavailableValue(Model):
    """A missing cell in a partial list/record/table; never a numeric zero."""
    kind: Literal["unavailable"]
    reason: Literal["explicit_null", "not_in_source", "not_extracted", "unknown", "ambiguous"]
    explanation: str


class ListValue(Model):
    kind: Literal["list"]
    items: list["Value"]


class RecordValue(Model):
    kind: Literal["record"]
    fields: dict[str, "Value"]


class TableColumn(Model):
    key: Id
    label: LocalizedText


class TableValue(Model):
    kind: Literal["table"]
    columns: list[TableColumn] = Field(min_length=1)
    rows: list[dict[str, "Value"]]

    @model_validator(mode="after")
    def check_columns(self):
        keys = [c.key for c in self.columns]
        if len(set(keys)) != len(keys) or any(set(row) != set(keys) for row in self.rows):
            raise ValueError("table keys must be unique and each row must match columns")
        return self


Value = Annotated[Union[QuantityValue, CountValue, TextValue, BooleanValue, ReferencesValue, UnavailableValue, ListValue, RecordValue, TableValue], Field(discriminator="kind")]


class Fact(Model):
    id: Id
    subject_id: Id
    property_key: Id
    original_property_path: list[str] = Field(default_factory=list)
    status: Literal["present", "explicit_null", "not_in_source", "not_extracted", "unknown", "ambiguous"]
    value: Value | None = None
    provenance: Provenance
    supersedes_fact_id: Id | None = None

    @model_validator(mode="after")
    def check_value(self):
        if (self.status == "present") != (self.value is not None):
            raise ValueError("only present facts carry a value; absence is explicit")
        if self.value is not None and any(isinstance(v, UnavailableValue) for v in walk_values(self.value)):
            raise ValueError("use fact status for missing facts, not an unavailable value")
        return self


class Relation(Model):
    id: Id
    subject_id: Id
    predicate: Literal["contains", "aggregates", "typed_by", "assigned_to_system", "has_material", "belongs_to_unit", "adjacent_to", "connected_to", "hosted_by", "depicts", "same_as", "custom"]
    object_id: Id
    native_predicate: str | None = None
    provenance: Provenance


class Scope(Model):
    project_id: Id
    document_ids: list[Id] = Field(min_length=1)  # Explicit revision set.
    entity_ids: list[Id] = Field(default_factory=list)  # Descendants included.
    view_ids: list[Id] = Field(default_factory=list)
    universe: Literal["source_records", "modeled_objects", "depicted_objects", "schedule_entries", "physical_building"]
    # All populated restrictions intersect. Empty entity/view lists mean no
    # additional restriction, not an empty scope. Attachments do not imply scope.


class CountPolicy(Model):
    grain: Literal["logical_object", "occurrence", "assembly", "part", "schedule_row"]
    hierarchy: Literal["all_matches", "topmost_matches", "leaves"]
    distinct_by: Literal["canonical_entity_id"] = "canonical_entity_id"
    rule_key: Id  # e.g. door.opening_with_leaf.v1 or sink.fixture.v1


class Coverage(Model):
    id: Id
    scope: Scope
    concept_ids: list[Id]
    property_keys: list[Id] = Field(default_factory=list)
    count_policy: CountPolicy | None = None
    completeness: Literal["complete", "partial", "not_modeled", "not_extracted", "unknown"]
    explanation: str
    provenance: Provenance


class KnowledgeBundle(Contract):
    projects: list[Project]
    documents: list[Document]
    assets: list[Asset]
    asset_links: list[AssetLink] = Field(default_factory=list)
    runs: list[ExtractionRun]
    concepts: list[Concept]
    properties: list[PropertyDefinition]
    units: list[Unit]
    frames: list[CoordinateFrame] = Field(default_factory=list)
    transforms: list[Transform] = Field(default_factory=list)
    views: list[View] = Field(default_factory=list)
    geometries: list[Geometry] = Field(default_factory=list)
    anchors: list[EvidenceAnchor] = Field(default_factory=list)
    calibrations: list[Calibration] = Field(default_factory=list)
    features: list[SourceFeature] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    representations: list[Representation] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    coverage: list[Coverage] = Field(default_factory=list)


class QuestionRequest(Contract):
    id: Id
    question: LocalizedText
    attachment_asset_ids: list[Id] = Field(default_factory=list)
    attachment_view_ids: list[Id] = Field(default_factory=list)
    project_id: Id | None = None
    previous_request_ids: list[Id] = Field(default_factory=list)


class FieldRef(Model):
    kind: Literal["property", "label", "concept", "native_identifier", "entity_id", "result_column"]
    key: Id


class ComparePredicate(Model):
    kind: Literal["compare"]
    field: FieldRef
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte", "in", "contains"]
    value: Value


class PresentPredicate(Model):
    kind: Literal["field_present"]
    field: FieldRef


class RelationPredicate(Model):
    kind: Literal["related_to"]
    predicate: str  # Must be in the executor's capability allowlist.
    direction: Literal["outgoing", "incoming"]
    entity_ids: list[Id] = Field(min_length=1)


class SpatialPredicate(Model):
    kind: Literal["spatial"]
    operator: Literal["intersects", "within", "contains", "touches", "disjoint", "near"]
    geometry_id: Id
    distance: QuantityValue | None = None

    @model_validator(mode="after")
    def check_near(self):
        if (self.operator == "near") != (self.distance is not None):
            raise ValueError("near requires a distance; other predicates do not")
        return self


class BooleanPredicate(Model):
    kind: Literal["all", "any", "not"]
    operands: list["Predicate"] = Field(min_length=1)

    @model_validator(mode="after")
    def check_not(self):
        if self.kind == "not" and len(self.operands) != 1:
            raise ValueError("not requires exactly one operand")
        return self


Predicate = Annotated[Union[ComparePredicate, PresentPredicate, RelationPredicate, SpatialPredicate, BooleanPredicate], Field(discriminator="kind")]


class SelectOperation(Model):
    kind: Literal["select"]
    concept_ids: list[Id]
    entity_kinds: list[EntityKind] = Field(default_factory=list)
    where: Predicate | None = None
    exclude: Predicate | None = None
    count_policy: CountPolicy


class TraverseOperation(Model):
    kind: Literal["traverse"]
    input_step_id: Id
    predicate: str
    direction: Literal["outgoing", "incoming"]
    recursive: bool = False
    max_depth: PositiveInt = 32


class AggregateOperation(Model):
    kind: Literal["aggregate"]
    input_step_id: Id
    method: Literal["count", "sum", "mean", "min", "max"]
    field: FieldRef | None = None
    group_by: list[FieldRef] = Field(default_factory=list)
    value_key: Id = "value"  # Derived result column; group columns use field.key.
    output_unit_id: Id | None = None
    missing_values: Literal["fail", "partial"] = "fail"

    @model_validator(mode="after")
    def check_field(self):
        if (self.method != "count") != (self.field is not None):
            raise ValueError("numeric aggregation needs a field; count has none")
        if self.method == "count" and self.output_unit_id is not None:
            raise ValueError("count is not a physical quantity")
        group_keys = [field.key for field in self.group_by]
        if len(set(group_keys)) != len(group_keys) or self.value_key in group_keys:
            raise ValueError("group and aggregate result column keys must be distinct")
        return self


class ProjectOperation(Model):
    kind: Literal["project"]
    input_step_id: Id
    fields: list[FieldRef] = Field(min_length=1)


class RankOperation(Model):
    kind: Literal["rank"]
    input_step_id: Id
    field: FieldRef
    direction: Literal["ascending", "descending"]
    limit: PositiveInt


class MeasureOperation(Model):
    kind: Literal["measure"]
    input_step_id: Id
    metric: Literal["area", "union_area", "length", "perimeter", "volume", "distance", "angle"]
    reference_entity_ids: list[Id] = Field(default_factory=list)
    output_unit_id: Id
    basis: str
    calibration_ids: list[Id] = Field(default_factory=list)


class ArithmeticOperation(Model):
    kind: Literal["arithmetic"]
    input_step_ids: list[Id] = Field(min_length=2)
    operator: Literal["add", "subtract", "multiply", "divide"]
    output_unit_id: Id | None = None


Operation = Annotated[Union[SelectOperation, TraverseOperation, AggregateOperation, ProjectOperation, RankOperation, MeasureOperation, ArithmeticOperation], Field(discriminator="kind")]


class PlanStep(Model):
    id: Id
    operation: Operation


class QueryPlan(Contract):
    id: Id
    request_id: Id
    scope: Scope
    steps: list[PlanStep] = Field(min_length=1)
    outputs: dict[str, Id] = Field(min_length=1)
    required_capabilities: list[Id] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_dag(self):
        prior = set()
        for step in self.steps:
            if step.id in prior:
                raise ValueError("duplicate step ID")
            op = step.operation
            inputs = getattr(op, "input_step_ids", [])
            if hasattr(op, "input_step_id"):
                inputs = [op.input_step_id]
            if not set(inputs) <= prior:
                raise ValueError("step inputs must refer to earlier steps")
            prior.add(step.id)
        if not set(self.outputs.values()) <= prior:
            raise ValueError("output refers to unknown step")
        return self


class EntitySet(Model):
    id: Id
    scope: Scope
    count_policy: CountPolicy
    count: NonnegativeInt
    entity_ids: list[Id] | None = None
    members_uri: str | None = None
    members_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None

    @model_validator(mode="after")
    def check_members(self):
        if self.entity_ids is not None:
            if len(set(self.entity_ids)) != len(self.entity_ids) or self.count != len(self.entity_ids):
                raise ValueError("materialized set count must match unique entity IDs")
            if self.members_uri is not None or self.members_sha256 is not None:
                raise ValueError("use inline or persisted members, not both")
        elif self.members_uri is None or self.members_sha256 is None:
            raise ValueError("large sets require persisted members and content hash")
        return self


class CalculationNode(Model):
    id: Id
    plan_step_id: Id | None = None  # Internal calculation nodes may have no plan step.
    operation: Literal["select", "traverse", "project", "rank", "count", "sum", "mean", "min", "max", "lookup", "convert_unit", "add", "subtract", "multiply", "divide", "measure", "group_by", "filter", "deduplicate"]
    input_node_ids: list[Id] = Field(default_factory=list)
    fact_ids: list[Id] = Field(default_factory=list)
    included_set_id: Id | None = None
    excluded_set_id: Id | None = None
    anchor_ids: list[Id] = Field(default_factory=list)
    calibration_ids: list[Id] = Field(default_factory=list)
    output: Value
    quality: Literal["exact", "estimated", "lower_bound", "upper_bound"]
    rule_key: str | None = None


class EvidenceBinding(Model):
    value_path: Annotated[str, Field(pattern=r"^(?:/(?:[^~/]|~[01])*)*$")] = ""
    # JSON Pointer to a typed Value within this claim; empty=root.
    anchor_ids: list[Id] = Field(default_factory=list)
    fact_ids: list[Id] = Field(default_factory=list)
    entity_set_ids: list[Id] = Field(default_factory=list)
    calculation_id: Id


class Claim(Model):
    id: Id
    output_key: Id  # Exact key in QueryPlan.outputs, separate from display name.
    name: str
    scope: Scope
    concept_ids: list[Id]
    property_keys: list[Id] = Field(default_factory=list)
    value: Value
    quality: Literal["exact", "estimated", "lower_bound", "upper_bound"]
    coverage_ids: list[Id] = Field(min_length=1)
    evidence: list[EvidenceBinding] = Field(min_length=1)
    count_policy: CountPolicy | None = None

    @model_validator(mode="after")
    def check_claim_value(self):
        values = list(walk_values(self.value))
        if any(isinstance(v, CountValue) for v in values) and self.count_policy is None:
            raise ValueError("count claims require an explicit counting policy")
        if self.quality == "exact" and any(
            isinstance(v, QuantityValue) and v.quality != "exact" for v in values
        ):
            raise ValueError("an exact claim cannot contain estimated or bounded quantities")
        return self


class Issue(Model):
    code: Literal["needs_clarification", "missing_source", "missing_information", "incomplete_coverage", "unsupported_operation", "conflicting_evidence", "insufficient_calibration", "execution_error"]
    message: LocalizedText
    entity_ids: list[Id] = Field(default_factory=list)
    fact_ids: list[Id] = Field(default_factory=list)
    anchor_ids: list[Id] = Field(default_factory=list)
    options: list[LocalizedText] = Field(default_factory=list)


class ExecutionMetrics(Model):
    latency_ms: float = Field(ge=0)
    model_input_tokens: NonnegativeInt = 0
    model_output_tokens: NonnegativeInt = 0
    cache_hit: bool = False
    cost_amount: DecimalString | None = None
    cost_currency: str | None = None
    cost_basis: Literal["marginal", "amortized", "estimated"] | None = None

    @model_validator(mode="after")
    def check_cost(self):
        parts = (self.cost_amount, self.cost_currency, self.cost_basis)
        if any(x is not None for x in parts) and not all(x is not None for x in parts):
            raise ValueError("cost requires amount, currency, and accounting basis")
        if self.cost_amount is not None and Decimal(self.cost_amount) < 0:
            raise ValueError("cost cannot be negative")
        return self


class QueryResult(Contract):
    id: Id
    request_id: Id
    plan_id: Id | None = None  # Missing for unresolved requests.
    status: Literal["answered", "partial", "needs_clarification", "missing_source", "missing_information", "incomplete_coverage", "unsupported_operation", "conflicting_evidence", "insufficient_calibration", "execution_error"]
    claims: list[Claim] = Field(default_factory=list)
    entity_sets: list[EntitySet] = Field(default_factory=list)
    calculations: list[CalculationNode] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    explanation: LocalizedText | None = None
    executor_version: str
    metrics: ExecutionMetrics | None = None

    @model_validator(mode="after")
    def check_outcome(self):
        if self.status in {"answered", "partial"}:
            if not self.claims or self.plan_id is None:
                raise ValueError("answered/partial results require claims and a plan")
        elif self.claims:
            raise ValueError("non-answer outcomes do not carry successful claims")
        if self.status != "answered" and not self.issues:
            raise ValueError("non-answered outcomes require issues")
        if self.status == "answered" and self.issues:
            raise ValueError("blocking issues require a partial or non-answer outcome")
        if self.status == "answered" and any(
            isinstance(value, UnavailableValue)
            for claim in self.claims for value in walk_values(claim.value)
        ):
            raise ValueError("missing result cells require a partial outcome")
        if self.status not in {"answered", "partial"} and not any(
            issue.code == self.status for issue in self.issues
        ):
            raise ValueError("a non-answer outcome requires a matching issue code")
        return self


class CapabilityManifest(Contract):
    executor_version: str
    operations: list[str]
    relation_predicates: list[str]
    property_keys: list[Id]
    concept_ids: list[Id]
    supported_formats: list[str]
    limitations: list[str]


class BenchmarkCase(Contract):
    id: Id
    request: QuestionRequest
    reference_value: Value
    dataset_path: str
    dataset_line: PositiveInt
    original_answer_type: str
    original_unit: str | None
    split: Literal["train", "development", "test"]
    leakage_group: Id  # Project + duplicates/alternate formats/translations.
    relative_tolerance: float = Field(ge=0, le=1)
    adjudication: Literal["unreviewed", "confirmed", "disputed", "corrected"] = "unreviewed"
    adjudication_anchor_ids: list[Id] = Field(default_factory=list)
    note: str | None = None


def walk_values(value: Value):
    """Visit nested typed values (including tables) without losing their types."""
    yield value
    if isinstance(value, ListValue):
        children = value.items
    elif isinstance(value, RecordValue):
        children = value.fields.values()
    elif isinstance(value, TableValue):
        children = [cell for row in value.rows for cell in row.values()]
    else:
        children = []
    for child in children:
        yield from walk_values(child)


for _model in (ListValue, RecordValue, TableValue, BooleanPredicate):
    _model.model_rebuild()

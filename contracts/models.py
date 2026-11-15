"""Source-of-truth contracts. Export JSON Schema with python -m contracts.export.

IDs are opaque internal strings. Source IDs (IFC GUIDs, STEP IDs, CAD handles)
are asset-scoped locators, never substitutes for canonical entity identity.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from math import isclose
from typing import Annotated, Any, Literal, Union

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
    predicate: Literal["contains", "aggregates", "typed_by", "assigned_to_system", "has_material", "belongs_to_unit", "adjacent_to", "connected_to", "hosted_by", "depicts", "same_as", "custom", "bounded_by", "has_opening", "filled_by", "assigned_to_zone", "corresponding_boundary", "external_boundary", "has_port", "port_connected_to"]
    object_id: Id
    native_predicate: str | None = None
    provenance: Provenance


class Scope(Model):
    project_id: Id
    document_ids: list[Id] = Field(min_length=1)  # Explicit revision set.
    entity_ids: list[Id] = Field(default_factory=list)  # Descendants included.
    exact_entity_ids: list[Id] | None = None  # Exact membership; [] is an empty scope.
    view_ids: list[Id] = Field(default_factory=list)
    universe: Literal["source_records", "modeled_objects", "depicted_objects", "schedule_entries", "physical_building"]
    # All populated restrictions intersect. Empty entity/view lists mean no
    # additional restriction, not an empty scope. exact_entity_ids=None means no
    # exact restriction; an empty exact list means no members. Attachments do not imply scope.


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
    operation_keys: list[str] = Field(default_factory=list)
    examined_entity_ids: list[Id] = Field(default_factory=list)
    unresolved_entity_ids: list[Id] = Field(default_factory=list)
    candidate_entity_ids: list[Id] = Field(default_factory=list)


class IfcSpaceBoundary(Model):
    """A source boundary record, including unusable and virtual boundaries."""

    id: Id
    native_step_id: PositiveInt
    space_id: Id
    element_id: Id | None = None
    corresponding_boundary_id: Id | None = None
    parent_boundary_id: Id | None = None
    physical_or_virtual: str | None
    internal_or_external: str | None
    connection_geometry_step_id: PositiveInt | None = None
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
    space_boundaries: list[IfcSpaceBoundary] = Field(default_factory=list)
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
    missing_groups: Literal["fail", "unclassified"] = "fail"

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


class SpatialQueryOperation(Model):
    """Bounded IFC topology and supported source-geometry checks."""

    kind: Literal["spatial_query"]
    input_step_id: Id
    relation: Literal["containers", "boundary_neighbors", "door_connections", "outdoor_access", "exterior_doors"]
    container_kind: Literal["space", "storey", "building", "site"] = "storey"
    exterior_basis: Literal["combined", "classification", "boundary"] = "combined"
    method: Literal["native", "geometry", "auto"] = "auto"
    tolerance_m: float = Field(default=0.01, ge=0.000001, le=0.1)

    @model_validator(mode="after")
    def check_exterior_basis(self):
        if self.relation != "exterior_doors" and self.exterior_basis != "combined":
            raise ValueError("exterior_basis applies only to exterior_doors")
        return self


class RelatedEntitiesOperation(Model):
    """Deduplicate references from one table column at occurrence grain."""

    kind: Literal["related_entities"]
    input_step_id: Id
    column: Id = "related"


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
    include_ties: bool = False


class MeasureOperation(Model):
    kind: Literal["measure"]
    input_step_id: Id
    metric: Literal["area", "union_area", "enclosed_area", "length", "perimeter", "volume", "distance", "angle", "height", "base_elevation", "horizontal_distance"]
    reference_entity_ids: list[Id] = Field(default_factory=list)
    output_unit_id: Id
    basis: str
    calibration_ids: list[Id] = Field(default_factory=list)


class ArithmeticOperation(Model):
    kind: Literal["arithmetic"]
    input_step_ids: list[Id] = Field(min_length=2)
    operator: Literal["add", "subtract", "multiply", "divide"]
    output_unit_id: Id | None = None


class TableCalculateOperation(Model):
    """Bounded arithmetic over source-derived table cells, never expressions."""

    kind: Literal["table_calculate"]
    input_step_id: Id
    operator: Literal["add", "subtract", "multiply", "divide", "percent_of_total", "consecutive_difference"]
    fields: list[FieldRef] = Field(min_length=1, max_length=8)
    value_key: Id = "calculated"
    output_unit_id: Id | None = None
    group_by: list[FieldRef] = Field(default_factory=list, max_length=8)
    order_by: FieldRef | None = None
    next_key: Id = "following"

    @model_validator(mode="after")
    def check_fields(self):
        refs = [*self.fields, *self.group_by, *([self.order_by] if self.order_by else [])]
        if any(ref.kind != "result_column" for ref in refs):
            raise ValueError("table calculations require result-column fields")
        if self.operator in {"percent_of_total", "consecutive_difference"}:
            if len(self.fields) != 1:
                raise ValueError("shares and consecutive differences require one numeric field")
        elif len(self.fields) < 2:
            raise ValueError("row arithmetic requires at least two numeric fields")
        if (self.operator == "consecutive_difference") != (self.order_by is not None):
            raise ValueError("only consecutive differences require an order field")
        if self.value_key == self.next_key:
            raise ValueError("the result and following-row column keys must differ")
        return self


class NetworkQueryOperation(Model):
    """Metrics of an explicitly selected native distribution-port graph."""

    kind: Literal["network_query"]
    input_step_id: Id
    component_step_id: Id | None = None


class MaterialQuantityOperation(Model):
    """Recorded homogeneous net volumes or source-verified material estimates."""

    kind: Literal["material_quantity"]
    input_step_id: Id
    material_names: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(default_factory=list, max_length=32)
    method: Literal["auto", "recorded_net", "geometry"] = "auto"
    output_unit_id: Id = "unit:m3"
    tolerance_m: float = Field(default=0.001, ge=0.000001, le=0.05, allow_inf_nan=False)

    @model_validator(mode="after")
    def unique_materials(self):
        if len(set(self.material_names)) != len(self.material_names):
            raise ValueError("material names must be distinct literal source values")
        return self


RouteCoordinate = Annotated[float, Field(allow_inf_nan=False)]
RoutePoint = tuple[RouteCoordinate, RouteCoordinate, RouteCoordinate]


class RouteQueryOperation(Model):
    """A bounded modeled walking route, separate from straight-line distance."""

    kind: Literal["route_query"]
    input_step_id: Id
    target_step_id: Id | None = None
    mode: Literal["shortest", "farthest"] = "shortest"
    start_basis: Literal["modeled_interior_point", "explicit_point", "farthest_sampled"] = "modeled_interior_point"
    start_point_m: RoutePoint | None = None
    target_basis: Literal["recorded_external_boundary", "certified_fire_exit"] = "recorded_external_boundary"
    include_stairs: bool = True
    clearance_m: float = Field(default=0, ge=0, le=2, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_start(self):
        if (self.start_basis == "explicit_point") != (self.start_point_m is not None):
            raise ValueError("an explicit route start requires exactly one physical point")
        if self.mode == "farthest" and self.start_basis != "farthest_sampled":
            raise ValueError("farthest routes require the bounded sampled start basis")
        if self.mode != "farthest" and self.start_basis == "farthest_sampled":
            raise ValueError("a farthest sampled start requires farthest mode")
        return self


Operation = Annotated[Union[SelectOperation, TraverseOperation, AggregateOperation, SpatialQueryOperation, RelatedEntitiesOperation, ProjectOperation, RankOperation, MeasureOperation, ArithmeticOperation, TableCalculateOperation, NetworkQueryOperation, MaterialQuantityOperation, RouteQueryOperation], Field(discriminator="kind")]


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
            if getattr(op, "component_step_id", None) is not None:
                inputs = [*inputs, op.component_step_id]
            if getattr(op, "target_step_id", None) is not None:
                inputs = [*inputs, op.target_step_id]
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


class SpatialEvaluation(Model):
    """Machine-readable support and unresolved inputs for one spatial subject."""

    relation: Literal["containers", "boundary_neighbors", "door_connections", "outdoor_access", "exterior_doors"]
    subject_id: Id
    status: Literal["verified", "candidate", "unavailable", "recorded_empty"]
    method: str
    related_ids: list[Id] = Field(default_factory=list)
    anchor_ids: list[Id] = Field(default_factory=list)
    tolerance_m: float | None = Field(default=None, ge=0.000001, le=0.1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MeasurementEvaluation(Model):
    """Inspectably bounded evidence from a retained IFC geometry source."""

    metric: Literal["area", "union_area", "enclosed_area", "length", "perimeter", "volume", "distance", "angle", "height", "base_elevation", "horizontal_distance"]
    subject_id: Id
    reference_entity_ids: list[Id] = Field(default_factory=list, max_length=2000)
    method: Annotated[str, Field(min_length=1, max_length=200)]
    frame: Literal["ifc_world"]
    unit: Literal["m", "m2", "m3", "rad"]
    tolerance_m: float = Field(gt=0, le=0.1, allow_inf_nan=False)
    source_step_ids: list[PositiveInt] = Field(default_factory=list, max_length=2000)
    representation_step_ids: list[PositiveInt] = Field(default_factory=list, max_length=2000)
    status: Literal["verified", "unavailable"]
    value: float | None = Field(default=None, allow_inf_nan=False)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetworkEvaluation(Model):
    method: Literal["native_distribution_port_graph.v1"]
    counting_basis: Annotated[str, Field(min_length=1, max_length=1000)]
    selected_port_count: NonnegativeInt
    selected_component_count: NonnegativeInt
    connected_port_count: NonnegativeInt
    isolated_port_count: NonnegativeInt
    unique_connection_count: NonnegativeInt
    port_component_count: NonnegativeInt
    largest_component_port_count: NonnegativeInt
    components_with_ports_count: NonnegativeInt
    components_with_connected_ports_count: NonnegativeInt
    connection_graph_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    cut_edge_count: NonnegativeInt = 0
    component_network_count: NonnegativeInt = 0
    largest_component_network_count: NonnegativeInt = 0

    @model_validator(mode="after")
    def check_cardinalities(self):
        if self.connected_port_count + self.isolated_port_count != self.selected_port_count:
            raise ValueError("connected and isolated port counts must partition selected ports")
        if self.largest_component_port_count > self.selected_port_count or self.port_component_count > self.selected_port_count:
            raise ValueError("port graph components exceed selected vertices")
        if not self.components_with_connected_ports_count <= self.components_with_ports_count <= self.selected_component_count:
            raise ValueError("component port memberships exceed selected components")
        if self.largest_component_network_count > self.selected_component_count or self.component_network_count > self.selected_component_count:
            raise ValueError("owner graph components exceed selected components")
        return self


class MaterialLayerInput(Model):
    index: PositiveInt
    layer_step_id: PositiveInt
    material_step_id: PositiveInt | None = None
    material_name: str | None = None
    thickness: QuantityValue | None = None


class MaterialEvaluation(Model):
    subject_id: Id
    material_name: str | None = None
    material_step_ids: list[PositiveInt] = Field(default_factory=list, max_length=256)
    layer_step_ids: list[PositiveInt] = Field(default_factory=list, max_length=256)
    assignment_step_ids: list[PositiveInt] = Field(default_factory=list, max_length=256)
    source_step_ids: list[PositiveInt] = Field(default_factory=list, max_length=2000)
    method: Literal["recorded_net_homogeneous", "closed_mesh_homogeneous", "verified_uniform_layers", "recorded_not_used", "unavailable"]
    status: Literal["verified", "recorded_not_used", "unavailable"]
    frame: Literal["ifc_world", "native_quantity"]
    unit: Literal["m3"] = "m3"
    volume_m3: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    host_volume_m3: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    selected_thickness_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    total_thickness_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    tolerance_m: float = Field(gt=0, le=0.05, allow_inf_nan=False)
    recorded_quantity: QuantityValue | None = None
    specified_layers: list[MaterialLayerInput] = Field(default_factory=list, max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_value(self):
        if self.status != "unavailable" and self.volume_m3 is None:
            raise ValueError("verified material quantities need a numeric value")
        if self.status == "unavailable" and self.volume_m3 is not None:
            raise ValueError("unavailable material quantities cannot carry a numeric volume")
        if self.method == "verified_uniform_layers" and self.status == "verified" and (
                self.host_volume_m3 is None or self.selected_thickness_m is None or self.total_thickness_m is None):
            raise ValueError("layer allocation requires verified host volume and layer thicknesses")
        return self


class RouteEvaluation(Model):
    subject_id: Id
    target_id: Id | None = None
    method: Annotated[str, Field(min_length=1, max_length=200)]
    frame: Literal["ifc_world"]
    unit: Literal["m"] = "m"
    tolerance_m: float = Field(gt=0, le=0.1, allow_inf_nan=False)
    quality: Literal["estimated"] = "estimated"
    status: Literal["verified", "partial", "unavailable"]
    path_points_m: list[RoutePoint] = Field(default_factory=list, max_length=2048)
    room_ids: list[Id] = Field(default_factory=list, max_length=500)
    door_ids: list[Id] = Field(default_factory=list, max_length=1000)
    stair_ids: list[Id] = Field(default_factory=list, max_length=64)
    source_step_ids: list[PositiveInt] = Field(default_factory=list, max_length=2000)
    anchor_ids: list[Id] = Field(default_factory=list, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_path(self):
        if self.status == "verified" and len(self.path_points_m) < 2:
            raise ValueError("verified routes require at least two physical path points")
        if self.status == "unavailable" and self.path_points_m:
            raise ValueError("unavailable routes cannot carry a verified physical path")
        return self


class CalculationNode(Model):
    id: Id
    plan_step_id: Id | None = None  # Internal calculation nodes may have no plan step.
    operation: Literal["select", "traverse", "spatial_query", "related_entities", "network_query", "material_quantity", "route_query", "project", "rank", "count", "sum", "mean", "min", "max", "lookup", "convert_unit", "add", "subtract", "multiply", "divide", "measure", "group_by", "filter", "deduplicate"]
    input_node_ids: list[Id] = Field(default_factory=list)
    fact_ids: list[Id] = Field(default_factory=list)
    included_set_id: Id | None = None
    excluded_set_id: Id | None = None
    anchor_ids: list[Id] = Field(default_factory=list)
    calibration_ids: list[Id] = Field(default_factory=list)
    output: Value
    quality: Literal["exact", "estimated", "lower_bound", "upper_bound"]
    rule_key: str | None = None
    spatial_evidence: list[SpatialEvaluation] = Field(default_factory=list)
    measurement_evidence: list[MeasurementEvaluation] = Field(default_factory=list)
    network_evidence: list[NetworkEvaluation] = Field(default_factory=list)
    material_evidence: list[MaterialEvaluation] = Field(default_factory=list)
    route_evidence: list[RouteEvaluation] = Field(default_factory=list)


class EvidenceBinding(Model):
    value_path: Annotated[str, Field(pattern=r"^(?:/(?:[^~/]|~[01])*)*$")] = ""
    # JSON Pointer to a typed Value within this claim; empty=root.
    anchor_ids: list[Id] = Field(default_factory=list)
    fact_ids: list[Id] = Field(default_factory=list)
    entity_set_ids: list[Id] = Field(default_factory=list)
    calculation_id: Id
    evidence_kind: Literal["verified", "candidate", "unavailable"] = "verified"


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
    model_input_tokens: NonnegativeInt | None = 0
    model_output_tokens: NonnegativeInt | None = 0
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


class IfcElement(Model):
    """Canonical entity and its original product locators for viewer verification."""

    entity_id: Id
    step_id: PositiveInt | None = None
    guid: str | None = None
    ifc_class: str
    name: str


class IfcModelResponse(Contract):
    model_id: Id
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    ifc_schema: str
    entity_count: NonnegativeInt
    warnings: list[str] = Field(default_factory=list)


class IfcQuestionRequest(Contract):
    model_id: Annotated[str, Field(min_length=1, max_length=100)]
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    question: Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
    scope: Literal["view", "model"] = "view"
    visible_step_ids: list[PositiveInt] | None = Field(default=None, max_length=200000)
    view_label: Annotated[str, Field(max_length=300)] | None = None

    @model_validator(mode="after")
    def check_view(self):
        if self.scope == "view" and self.visible_step_ids is None:
            raise ValueError("view scope requires an explicit list of visible STEP IDs")
        if self.visible_step_ids is not None and len(set(self.visible_step_ids)) != len(self.visible_step_ids):
            raise ValueError("visible STEP IDs must be unique")
        return self


class IfcPlanningProvenance(Model):
    provider: str
    requested_model: str
    returned_model: str
    thinking_level: str | None = None
    prompt_version: str
    discovery_version: str
    model_requests: NonnegativeInt
    inspection_count: NonnegativeInt
    prompt_tokens: NonnegativeInt | None = None
    completion_tokens: NonnegativeInt | None = None
    thought_tokens: NonnegativeInt | None = None


class IfcQuestionResponse(Contract):
    request_id: Id
    model_id: Id
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    question: str
    scope: Literal["view", "model"]
    scope_label: str
    interpretation: str
    result: QueryResult
    plan: QueryPlan | None = None
    included_elements: list[IfcElement] = Field(default_factory=list)
    excluded_elements: list[IfcElement] = Field(default_factory=list)
    unresolved_elements: list[IfcElement] = Field(default_factory=list)
    planning: IfcPlanningProvenance | None = None
    facts: list[Fact] = Field(default_factory=list)
    anchors: list[EvidenceAnchor] = Field(default_factory=list)
    units: list[Unit] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    properties: list[PropertyDefinition] = Field(default_factory=list)
    coverage: list[Coverage] = Field(default_factory=list)
    extraction_runs: list[ExtractionRun] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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


class CandidateImage(Model):
    """The exact submitted source and oriented inference/display frame."""

    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    inference_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    width: PositiveInt
    height: PositiveInt
    coordinate_system: Literal["display_pixels_top_left"] = "display_pixels_top_left"


class ImageCandidate(Model):
    """An unreviewed detection, not a canonical building entity or final claim."""

    id: Id
    category: Annotated[str, Field(min_length=1, max_length=120, pattern=r"\S")]
    source_label: Annotated[str, Field(max_length=1000)] | None = None
    geometry: BoxShape
    uncertain: bool
    uncertainty_reason: Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S")] | None = None
    visual_cue: Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S")]

    @model_validator(mode="after")
    def check_candidate(self):
        minimum, maximum = self.geometry.minimum, self.geometry.maximum
        if len(minimum) != 2 or len(maximum) != 2:
            raise ValueError("candidate boxes require two-dimensional display coordinates")
        if any(a < 0 or a >= b for a, b in zip(minimum, maximum)):
            raise ValueError("candidate boxes require nonnegative coordinates and positive area")
        if self.uncertain != (self.uncertainty_reason is not None):
            raise ValueError("uncertain candidates require a reason; certain candidates use null")
        return self


class CandidatePreparation(Model):
    """Actual model image size, distinct from the unchanged display frame."""

    mode: Literal["off", "original", "overview"]
    pipeline_version: str | None = None
    prepared_id: Id | None = None
    input_width: PositiveInt
    input_height: PositiveInt


class CandidateProvenance(Model):
    requested_model: Id
    returned_model: Id
    prompt_version: Id
    preprocessing: CandidatePreparation | None = None


class CandidateMetrics(Model):
    elapsed_ms: float = Field(ge=0)
    prompt_tokens: NonnegativeInt | None = None
    completion_tokens: NonnegativeInt | None = None
    preparation_ms: float | None = Field(default=None, ge=0)
    preparation_cache_hit: bool | None = None


class AnalysisDecisionNode(Model):
    id: Id
    parent_id: Id | None = None
    criterion: Literal["capability", "route", "preparation", "analysis", "evidence"]
    state: Literal["evaluated", "selected", "skipped", "reused", "completed", "failed", "unavailable"]
    reason_code: Annotated[str, Field(min_length=1, max_length=120)]
    value: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    threshold: float | None = Field(default=None, ge=0, le=1)
    call_id: Id | None = None


class AnalysisCall(Model):
    id: Id
    purpose: Literal["routing", "analysis", "region_proposal", "candidate_verification", "reinspection"]
    requested_model: Id
    returned_model: Id | None = None
    completed_at: Annotated[str, Field(max_length=40)]
    outcome: Literal["completed", "failed", "cancelled"]
    elapsed_ms: float = Field(ge=0)
    input_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    input_width: PositiveInt
    input_height: PositiveInt
    source_box: Annotated[list[Annotated[float, Field(allow_inf_nan=False)]], Field(min_length=4, max_length=4)] | None = None
    prompt_tokens: NonnegativeInt | None = None
    completion_tokens: NonnegativeInt | None = None

    @model_validator(mode="after")
    def check_timestamp(self):
        value = datetime.fromisoformat(self.completed_at.replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError("call timestamp must include its timezone")
        return self


class ImageDecisionTrace(Model):
    """Host-recorded routing path, never a model's hidden reasoning."""

    request_id: Id
    question_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    image: CandidateImage
    mode: Literal["off", "shadow", "auto"]
    policy_version: Id
    capability_version: Id
    selected_profile: Literal["normal", "strong", "manual", "pending"]
    recommended_profile: Literal["normal", "strong"] | None = None
    assessments: dict[Id, Annotated[str, Field(min_length=1, max_length=120)]] = Field(default_factory=dict, max_length=8)
    assessment_probabilities: dict[Id, Annotated[float, Field(ge=0, le=1)]] = Field(default_factory=dict, max_length=8)
    nodes: list[AnalysisDecisionNode] = Field(default_factory=list, max_length=20)
    calls: list[AnalysisCall] = Field(default_factory=list, max_length=13)

    @model_validator(mode="after")
    def check_trace(self):
        if not set(self.assessment_probabilities).issubset(self.assessments):
            raise ValueError("assessment probabilities must reference recorded choices")
        call_ids = [call.id for call in self.calls]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("trace call IDs must be unique")
        for call in self.calls:
            if call.source_box is None:
                if call.input_sha256 != self.image.inference_sha256:
                    raise ValueError("single-image calls must reference the inference image")
            else:
                x0, y0, x1, y1 = call.source_box
                if not (0 <= x0 < x1 <= self.image.width and 0 <= y0 < y1 <= self.image.height):
                    raise ValueError("call source bounds must lie within the submitted image")
                # Overview rounding can change aspect by at most one pixel.
                expected_height = call.input_width * (y1-y0) / (x1-x0)
                if abs(call.input_height - expected_height) > 1.01:
                    raise ValueError("call dimensions must preserve the source region aspect")
                if call.purpose == "routing":
                    raise ValueError("routing must reference the full submitted inference image")
        seen = set()
        for node in self.nodes:
            if node.id in seen or (node.parent_id is not None and node.parent_id not in seen):
                raise ValueError("trace nodes need unique IDs and preceding parents")
            if node.call_id is not None and node.call_id not in call_ids:
                raise ValueError("trace node references an unknown call")
            seen.add(node.id)
        return self

DetailPixelBox = Annotated[list[Annotated[int, Field(strict=True)]], Field(min_length=4, max_length=4)]


class DetailRegion(Model):
    id: Id
    source_box: DetailPixelBox
    inference_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    status: Literal["ok", "partial", "unreadable", "unsupported", "failed"]
    candidate_count: NonnegativeInt


class DetailObservation(Model):
    candidate_id: Id
    observation_ids: list[Id] = Field(min_length=1, max_length=64)
    region_ids: list[Id] = Field(min_length=1, max_length=64)
    clipped: bool
    source_labels: list[str | None] = Field(default_factory=list, max_length=64)


class DeferredDetailObservation(Model):
    observation_id: Id
    region_id: Id
    category: str
    source_box: Annotated[list[float], Field(min_length=4, max_length=4)]
    reason: str


class DetailMembershipCheck(Model):
    observation_ids: list[Id] = Field(min_length=1, max_length=64)
    category: str
    source_box: Annotated[list[float], Field(min_length=4, max_length=4)]
    region_id: Id
    verdict: Literal["supported", "rejected", "ambiguous", "failed"]
    reason: str


class CandidateDetailTrace(Model):
    mode: Literal["auto", "regions", "tiles"]
    selection: Literal["automatic", "explicit"]
    selected_regions: list[DetailPixelBox] = Field(min_length=1, max_length=4)
    regions: list[DetailRegion] = Field(max_length=12)
    observations: list[DetailObservation] = Field(max_length=100)
    provider_calls: NonnegativeInt
    selection_limitations: list[str] = Field(default_factory=list, max_length=20)
    superseded_observation_ids: list[Id] = Field(default_factory=list, max_length=1200)
    reinspection_regions: list[DetailPixelBox] = Field(default_factory=list, max_length=12)
    deferred_observations: list[DeferredDetailObservation] = Field(default_factory=list, max_length=1200)
    target_kind: str = "other"
    reused_crops: NonnegativeInt = 0
    membership_checks: list[DetailMembershipCheck] = Field(default_factory=list, max_length=12)


class ImageCandidateResponse(Contract):
    """Image-bound proposals; an empty list does not establish a zero count."""

    request_id: Id
    scope: Literal["submitted_image"] = "submitted_image"
    image: CandidateImage
    status: Literal["ok", "partial", "unreadable", "unsupported"]
    inventory_completeness: Literal["unverified"] = "unverified"
    candidates: list[ImageCandidate] = Field(default_factory=list, max_length=100)
    limitations: list[Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]] = Field(default_factory=list, max_length=100)
    provenance: CandidateProvenance
    metrics: CandidateMetrics
    decision_trace: ImageDecisionTrace | None = None
    detail: CandidateDetailTrace | None = None

    @model_validator(mode="after")
    def check_candidate_response(self):
        if self.decision_trace is not None and (
                self.decision_trace.request_id != self.request_id
                or self.decision_trace.image != self.image):
            raise ValueError("decision trace must match response request and source")
        if self.detail is not None:
            regions = {region.id: region for region in self.detail.regions}
            if len(regions) != len(self.detail.regions):
                raise ValueError("detail region IDs must be unique")
            for box in [*self.detail.selected_regions, *(r.source_box for r in regions.values())]:
                x0, y0, x1, y1 = box
                if not (0 <= x0 < x1 <= self.image.width and 0 <= y0 < y1 <= self.image.height):
                    raise ValueError("detail regions must lie within the submitted image")
            for box in self.detail.reinspection_regions:
                x0, y0, x1, y1 = box
                if not (0 <= x0 < x1 <= self.image.width and 0 <= y0 < y1 <= self.image.height):
                    raise ValueError("reinspection regions must lie within the submitted image")
            for observation in self.detail.deferred_observations:
                if observation.region_id not in regions:
                    raise ValueError("deferred observations reference unknown regions")
                x0, y0, x1, y1 = observation.source_box
                a, b, c, d = regions[observation.region_id].source_box
                if not (a <= x0 < x1 <= c and b <= y0 < y1 <= d):
                    raise ValueError("deferred observations must lie inside their source region")
            for check in self.detail.membership_checks:
                if check.region_id not in regions:
                    raise ValueError("membership checks reference unknown regions")
                x0, y0, x1, y1 = check.source_box
                a, b, c, d = regions[check.region_id].source_box
                if not (a <= x0 < x1 <= c and b <= y0 < y1 <= d):
                    raise ValueError("membership checks must lie inside their review region")
            candidate_ids = {candidate.id for candidate in self.candidates}
            if len(self.detail.observations) != len(candidate_ids) or {o.candidate_id for o in self.detail.observations} != candidate_ids:
                raise ValueError("detail provenance must cover every surviving candidate")
            for observation in self.detail.observations:
                if not set(observation.region_ids) <= regions.keys():
                    raise ValueError("detail observations reference unknown regions")
        if self.status != "ok" and not self.limitations:
            raise ValueError("non-ok candidate outcomes require an explanation")
        if self.status in {"unreadable", "unsupported"} and self.candidates:
            raise ValueError("unreadable/unsupported outcomes cannot carry candidates")
        if len(self.candidates) == 100 and self.status != "partial":
            raise ValueError("reaching the candidate limit requires a partial outcome")
        seen_ids = set()
        seen_boxes = set()
        for candidate in self.candidates:
            if candidate.id in seen_ids:
                raise ValueError("candidate IDs must be unique within a response")
            seen_ids.add(candidate.id)
            minimum, maximum = candidate.geometry.minimum, candidate.geometry.maximum
            if maximum[0] > self.image.width or maximum[1] > self.image.height:
                raise ValueError("candidate boxes must lie inside the declared display image")
            key = (candidate.category, tuple(minimum), tuple(maximum))
            if key in seen_boxes:
                raise ValueError("duplicate category/geometry candidate records are invalid")
            seen_boxes.add(key)
        return self


class ImageRegionSelection(Model):
    id: Id
    source_box: DetailPixelBox
    reason: str


class ImageRegionResponse(Contract):
    request_id: Id
    image: CandidateImage
    status: Literal["selected", "full_source"]
    regions: list[ImageRegionSelection] = Field(min_length=1, max_length=4)
    limitations: list[str] = Field(default_factory=list)
    provenance: CandidateProvenance
    metrics: CandidateMetrics
    target_kind: str = "other"

    @model_validator(mode="after")
    def check_regions(self):
        for region in self.regions:
            x0, y0, x1, y1 = region.source_box
            if not (0 <= x0 < x1 <= self.image.width and 0 <= y0 < y1 <= self.image.height):
                raise ValueError("selected region must lie within the submitted image")
        return self


class ImageCandidateError(Contract):
    request_id: Id
    code: Id
    message: Annotated[str, Field(min_length=1, pattern=r"\S")]
    retryable: bool
    decision_trace: ImageDecisionTrace | None = None

    @model_validator(mode="after")
    def check_error_trace(self):
        if self.decision_trace is not None and self.decision_trace.request_id != self.request_id:
            raise ValueError("decision trace must match error request")
        return self


class ImageCandidateProgress(Contract):
    """Actual analyzer dispatch, sent before waiting for candidate output."""

    request_id: Id
    question_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    image: CandidateImage
    requested_model: Annotated[str, Field(min_length=1, max_length=200)]


class ImageCandidateStreamEvent(Contract):
    type: Literal["handoff", "result", "error"]
    progress: ImageCandidateProgress | None = None
    result: ImageCandidateResponse | None = None
    error: ImageCandidateError | None = None

    @model_validator(mode="after")
    def check_payload(self):
        selected = {"handoff": "progress", "result": "result", "error": "error"}[self.type]
        if any((getattr(self, field) is not None) != (field == selected)
               for field in ("progress", "result", "error")):
            raise ValueError("stream event requires exactly its matching payload")
        return self


class DxfPreviewResponse(Contract):
    """One rendered layout, not a CAD inventory or a calibrated measurement."""

    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    svg: Annotated[str, Field(min_length=1, max_length=8 * 1024 * 1024)]
    width: Annotated[int, Field(gt=0, le=4096, strict=True)]
    height: Annotated[int, Field(gt=0, le=4096, strict=True)]
    page: PositiveInt
    layouts: list[Annotated[str, Field(min_length=1, max_length=255)]] = Field(min_length=1, max_length=128)
    insunits: NonnegativeInt | None = None  # Literal $INSUNITS; not raster calibration.
    status: Literal["rendered", "partial"]
    warnings: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(max_length=40)

    @model_validator(mode="after")
    def check_preview(self):
        if self.page > len(self.layouts) or len(set(self.layouts)) != len(self.layouts):
            raise ValueError("DXF preview must identify one unique source layout")
        if self.width * self.height > 8_000_000:
            raise ValueError("DXF preview exceeds its pixel budget")
        if self.status == "partial" and not self.warnings:
            raise ValueError("partial DXF previews require an explanation")
        return self


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


# Raster preparation artifacts. Coordinates are presentation pixels, never a
# physical calibration or a claim about complete drawing/object extraction.
PixelBounds = tuple[NonnegativeInt, NonnegativeInt, NonnegativeInt, NonnegativeInt]


def _artifact_uri(value: str) -> None:
    """Artifact paths are portable and resolved below one artifact directory."""
    if not value or "\\" in value or ":" in value or value.startswith("/") or any(
        part in {"", ".", ".."} for part in value.split("/")
    ):
        raise ValueError("artifact URI must be a relative portable path without traversal")


def _pixel_matrix(actual: list[list[float]], expected: list[list[float]]) -> None:
    if len(actual) != 3 or any(len(row) != 3 for row in actual) or any(
        not isclose(value, expected[i][j], rel_tol=1e-9, abs_tol=1e-7)
        for i, row in enumerate(actual) for j, value in enumerate(row)
    ):
        raise ValueError("pixel transform must agree with crop bounds and image dimensions")


class OCRTextSpan(Model):
    id: Id
    text: str
    frame_id: Id
    bbox: tuple[float, float, float, float]
    confidence: float | None = Field(default=None, ge=0, le=1)
    engine: Id

    @model_validator(mode="after")
    def check_bounds(self):
        left, top, right, bottom = self.bbox
        if left < 0 or top < 0 or right <= left or bottom <= top:
            raise ValueError("OCR boxes need positive area in nonnegative source pixels")
        return self


class InspectRegionArgs(Model):
    view_id: Id
    bbox: tuple[float, float, float, float]
    coordinate_space: Literal["view", "overview"] = "view"
    output_long_edge: Annotated[int, Field(ge=64, le=8192, strict=True)] | None = None

    @model_validator(mode="after")
    def check_bounds(self):
        left, top, right, bottom = self.bbox
        if left < 0 or top < 0 or right <= left or bottom <= top:
            raise ValueError("inspection box needs positive area in nonnegative pixels")
        return self


class OCRResult(Model):
    status: Literal["not_requested", "unavailable", "complete", "partial", "failed"]
    engine: str | None = None
    version: str | None = None
    languages: list[str] = Field(default_factory=list)
    spans: list[OCRTextSpan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_status(self):
        if self.status in {"not_requested", "unavailable", "failed"} and self.spans:
            raise ValueError("unperformed or failed OCR cannot carry successful spans")
        if self.status in {"complete", "partial"} and not self.engine:
            raise ValueError("performed OCR needs an engine identifier")
        if len({span.id for span in self.spans}) != len(self.spans):
            raise ValueError("OCR span IDs must be unique")
        return self


class PreparedRegion(Model):
    id: Id
    role: Literal["full_source", "drawing_candidate", "context_candidate", "unknown"]
    source_bbox: PixelBounds  # Half-open [left, top, right, bottom].
    frame_id: Id
    image_uri: str
    width: PositiveInt
    height: PositiveInt
    overview_uri: str
    overview_width: PositiveInt
    overview_height: PositiveInt
    overview_frame_id: Id
    to_source: list[list[float]]
    overview_to_source: list[list[float]]
    reason: str

    @model_validator(mode="after")
    def check_region(self):
        left, top, right, bottom = self.source_bbox
        if right <= left or bottom <= top or (right - left, bottom - top) != (self.width, self.height):
            raise ValueError("crop dimensions must match positive-area source bounds")
        if self.overview_width > self.width or self.overview_height > self.height:
            raise ValueError("an overview cannot enlarge its source region")
        if self.frame_id == self.overview_frame_id:
            raise ValueError("crop and overview frames must have separate IDs")
        _artifact_uri(self.image_uri)
        _artifact_uri(self.overview_uri)
        _pixel_matrix(self.to_source, [[1., 0., float(left)], [0., 1., float(top)], [0., 0., 1.]])
        _pixel_matrix(self.overview_to_source, [
            [self.width / self.overview_width, 0., float(left)],
            [0., self.height / self.overview_height, float(top)], [0., 0., 1.],
        ])
        return self


class PreparedDrawing(Contract):
    id: Id
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    config_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    pipeline_version: Id
    source_uri: str
    original_uri: str
    source_image_uri: str
    source_width: PositiveInt
    source_height: PositiveInt
    source_frame_id: Id
    regions: list[PreparedRegion] = Field(min_length=1)
    ocr: OCRResult
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_artifacts(self):
        _artifact_uri(self.original_uri)
        _artifact_uri(self.source_image_uri)
        full_sources = [region for region in self.regions if region.role == "full_source"]
        if len(full_sources) != 1:
            raise ValueError("prepared drawing must retain exactly one full_source region")
        if full_sources[0].image_uri != self.source_image_uri:
            raise ValueError("full_source region must reference the canonical source image")
        if len({region.id for region in self.regions}) != len(self.regions):
            raise ValueError("prepared region IDs must be unique")
        frames = [self.source_frame_id]
        for region in self.regions:
            left, top, right, bottom = region.source_bbox
            if right > self.source_width or bottom > self.source_height:
                raise ValueError("region bounds exceed the source image")
            if region.role == "full_source" and region.source_bbox != (0, 0, self.source_width, self.source_height):
                raise ValueError("full_source region must cover the entire source image")
            frames.extend((region.frame_id, region.overview_frame_id))
        if len(set(frames)) != len(frames):
            raise ValueError("source, crop and overview frame IDs must be unique")
        for span in self.ocr.spans:
            if span.frame_id != self.source_frame_id or span.bbox[2] > self.source_width or span.bbox[3] > self.source_height:
                raise ValueError("OCR spans must be bounded source-frame pixels")
        return self


# Additive answer contracts. The candidate and IFC APIs retain their original
# wire formats; this envelope binds their executed evidence to presentation.
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
AnswerStatus = Literal["answered", "partial", "needs_clarification", "missing_source", "missing_information", "incomplete_coverage", "unsupported_operation", "conflicting_evidence", "insufficient_calibration", "execution_error", "blocked"]


class AnswerSnapshot(Model):
    source_sha256: Sha256
    source_revision: Id
    display_sha256: Sha256 | None = None
    page_index: NonnegativeInt | None = None
    layout_name: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    rotation: Literal[0, 90, 180, 270] = 0
    display_width: PositiveInt | None = None
    display_height: PositiveInt | None = None
    viewport_transform: Annotated[list[float], Field(min_length=6, max_length=6)] | None = None
    source_bounds: Annotated[list[float], Field(min_length=4, max_length=4)] | None = None

    @model_validator(mode="after")
    def check_frame(self):
        if (self.display_width is None) != (self.display_height is None):
            raise ValueError("display dimensions must be supplied together")
        if self.display_sha256 is not None and self.display_width is None:
            raise ValueError("a displayed raster needs explicit pixel dimensions")
        if self.source_bounds is not None:
            x0, y0, x1, y1 = self.source_bounds
            if x1 <= x0 or y1 <= y0:
                raise ValueError("source bounds must have positive area")
        if self.viewport_transform is not None:
            a, b, c, d, _, _ = self.viewport_transform
            if abs(a * d - b * c) < 1e-15:
                raise ValueError("viewport transform must be invertible")
        return self


class AnswerSourceBinding(AnswerSnapshot):
    source_id: Id
    kind: Literal["image", "pdf", "svg", "dxf", "ifc"]
    scope_label: Annotated[str, Field(min_length=1, max_length=1000)]


class AnswerRequestedPart(Model):
    key: Annotated[str, Field(min_length=1, max_length=100)]
    question: Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
    operation: Annotated[str, Field(min_length=1, max_length=100)] = "auto"
    target: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    literal_identifiers: list[str] = Field(default_factory=list, max_length=100)
    filters: list[str] = Field(default_factory=list, max_length=100)
    exclusions: list[str] = Field(default_factory=list, max_length=100)
    depends_on: list[Id] = Field(default_factory=list, max_length=16)


class AnswerIntent(Model):
    language: Annotated[str, Field(min_length=2, max_length=35)] = "en"
    scope_label: Annotated[str, Field(min_length=1, max_length=1000)]
    requested_parts: list[AnswerRequestedPart] = Field(min_length=1, max_length=16)
    ambiguities: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def check_parts(self):
        prior = set()
        for part in self.requested_parts:
            if part.key in prior or not set(part.depends_on) <= prior:
                raise ValueError("requested parts need unique keys and earlier dependencies")
            prior.add(part.key)
        return self


class AnswerRequest(Contract):
    source_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    model_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    source_sha256: Sha256
    question: Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
    language: Annotated[str, Field(min_length=2, max_length=35)] | None = None
    snapshot: AnswerSnapshot | None = None
    detail: bool = False
    parts: list[AnswerRequestedPart] | None = Field(default=None, min_length=1, max_length=16)
    plans: dict[Id, QueryPlan] = Field(default_factory=dict, max_length=16)

    @model_validator(mode="after")
    def check_source(self):
        if (self.source_id is None) == (self.model_id is None):
            raise ValueError("supply exactly one registered source or IFC model handle")
        if self.snapshot is not None and self.snapshot.source_sha256 != self.source_sha256:
            raise ValueError("snapshot original hash must match the requested source")
        if self.parts is not None:
            AnswerIntent(scope_label="validated request", requested_parts=self.parts)
            if not self.plans.keys() <= {part.key for part in self.parts}:
                raise ValueError("plans must identify requested part keys")
        elif self.plans:
            raise ValueError("direct plans require explicit requested parts")
        return self


class AnswerPart(Model):
    key: Id
    status: AnswerStatus
    result: QueryResult | None = None
    plan: QueryPlan | None = None
    evidence_context_id: Id | None = None
    message: LocalizedText | None = None
    depends_on: list[Id] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def check_part(self):
        if self.result is not None and self.result.status != self.status:
            raise ValueError("answer part status must preserve the executed result status")
        if self.status in {"answered", "partial"}:
            if self.result is None or self.plan is None or self.evidence_context_id is None:
                raise ValueError("successful answer parts require result, plan and evidence context")
        elif self.result is None and self.message is None:
            raise ValueError("unavailable answer parts need an explicit reason")
        if self.status == "blocked" and not self.depends_on:
            raise ValueError("blocked parts must identify their dependencies")
        return self


class AnswerEvidenceContext(Model):
    id: Id
    bundle: KnowledgeBundle
    source_snapshot: AnswerSnapshot | None = None


class AnswerSentence(Model):
    id: Id
    part_key: Id
    kind: Literal["claim", "issue"]
    text: Annotated[str, Field(min_length=1)]
    claim_ids: list[Id] = Field(default_factory=list)
    value_paths: list[str] = Field(default_factory=list)
    anchor_ids: list[Id] = Field(default_factory=list)
    qualification: Literal["exact", "estimated", "lower_bound", "upper_bound", "unavailable"]


class AnswerCall(Model):
    id: Id
    purpose: Literal["planning", "routing", "analysis", "region_proposal", "candidate_verification", "reinspection", "wording"]
    requested_model: Id
    returned_model: Id | None = None
    outcome: Literal["completed", "failed", "cancelled"]
    elapsed_ms: float = Field(default=0, ge=0)
    completed_at: str | None = None
    prompt_tokens: NonnegativeInt | None = None
    completion_tokens: NonnegativeInt | None = None
    thought_tokens: NonnegativeInt | None = None
    input_sha256: Sha256 | None = None


class AnswerMetrics(Model):
    elapsed_ms: float = Field(ge=0)
    external_attempts: Annotated[int, Field(strict=True, ge=0, le=15)] = 0
    calls: list[AnswerCall] = Field(default_factory=list, max_length=15)
    model_input_tokens: NonnegativeInt | None = None
    model_output_tokens: NonnegativeInt | None = None
    cache_hit: bool = False
    cost_amount: DecimalString | None = None
    cost_currency: str | None = None
    cost_basis: Literal["marginal", "amortized", "estimated"] | None = None

    @model_validator(mode="after")
    def check_ledger(self):
        if len(self.calls) != len({call.id for call in self.calls}):
            raise ValueError("answer call IDs must be unique")
        if len(self.calls) > self.external_attempts:
            raise ValueError("recorded calls cannot exceed total external attempts")
        ExecutionMetrics(latency_ms=self.elapsed_ms, cost_amount=self.cost_amount,
                         cost_currency=self.cost_currency, cost_basis=self.cost_basis)
        return self


class AnswerResponse(Contract):
    request_id: Id
    question: Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
    question_sha256: Sha256
    source: AnswerSourceBinding
    interpretation: AnswerIntent
    parts: list[AnswerPart] = Field(min_length=1, max_length=16)
    narrative: list[AnswerSentence] = Field(default_factory=list)
    evidence_contexts: list[AnswerEvidenceContext] = Field(default_factory=list, max_length=16)
    metrics: AnswerMetrics
    candidate_response: ImageCandidateResponse | None = None
    ifc_response: IfcQuestionResponse | None = None

    @model_validator(mode="after")
    def check_accounting(self):
        import hashlib
        if hashlib.sha256(self.question.encode("utf-8")).hexdigest() != self.question_sha256:
            raise ValueError("answer question hash does not match the captured question")
        requested = [part.key for part in self.interpretation.requested_parts]
        actual = [part.key for part in self.parts]
        if len(set(actual)) != len(actual) or set(actual) != set(requested):
            raise ValueError("every requested part must appear exactly once")
        contexts = [context.id for context in self.evidence_contexts]
        if len(set(contexts)) != len(contexts):
            raise ValueError("evidence context IDs must be unique")
        for part in self.parts:
            if part.evidence_context_id is not None and part.evidence_context_id not in contexts:
                raise ValueError("answer part references an unknown evidence context")
            if part.result is not None and part.result.request_id != self.request_id:
                raise ValueError("answer result must belong to the captured request")
            expected = next(item for item in self.interpretation.requested_parts if item.key == part.key)
            if part.depends_on != expected.depends_on:
                raise ValueError("answer part dependencies must preserve the requested dependency graph")
        if len({sentence.id for sentence in self.narrative}) != len(self.narrative):
            raise ValueError("narrative sentence IDs must be unique")
        if any(sentence.part_key not in actual for sentence in self.narrative):
            raise ValueError("narrative sentence references an unknown requested part")
        if self.candidate_response is not None:
            candidate = self.candidate_response
            if candidate.request_id != self.request_id or candidate.image.sha256 != self.source.display_sha256:
                raise ValueError("candidate response must match the answer request and displayed raster")
            if (candidate.image.width, candidate.image.height) != (self.source.display_width, self.source.display_height):
                raise ValueError("candidate response frame differs from the captured display")
            if candidate.decision_trace is not None and candidate.decision_trace.question_sha256 != self.question_sha256:
                raise ValueError("candidate routing trace belongs to another question")
        if self.ifc_response is not None:
            if (self.ifc_response.request_id != self.request_id or self.ifc_response.question != self.question
                    or self.ifc_response.source_sha256 != self.source.source_sha256
                    or self.ifc_response.model_id != self.source.source_id or self.source.kind != "ifc"):
                raise ValueError("IFC response must match the captured source and question")
        return self


class AnswerStreamEvent(Contract):
    type: Literal["handoff", "result", "error"]
    progress: ImageCandidateProgress | None = None
    result: AnswerResponse | None = None
    error: ImageCandidateError | None = None

    @model_validator(mode="after")
    def check_payload(self):
        selected = {"handoff": "progress", "result": "result", "error": "error"}[self.type]
        if any((getattr(self, field) is not None) != (field == selected)
               for field in ("progress", "result", "error")):
            raise ValueError("answer stream event requires exactly its matching payload")
        return self

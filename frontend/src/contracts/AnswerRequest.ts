/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type Detail = boolean;
export type Language = string | null;
export type ModelId = string | null;
export type Parts =
  | [AnswerRequestedPart]
  | [AnswerRequestedPart, AnswerRequestedPart]
  | [AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart]
  | [AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart]
  | [AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | null;
/**
 * @maxItems 16
 */
export type DependsOn =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ];
/**
 * @maxItems 100
 */
export type Exclusions = string[];
/**
 * @maxItems 100
 */
export type Filters = string[];
export type Key = string;
/**
 * @maxItems 100
 */
export type LiteralIdentifiers = string[];
export type Operation = string;
export type Question = string;
export type Target = string | null;
export type Id = string;
export type RequestId = string;
export type RequiredCapabilities = string[];
export type SchemaVersion = '0.1.0';
/**
 * @minItems 1
 */
export type DocumentIds = [string, ...string[]];
export type EntityIds = string[];
export type ExactEntityIds = string[] | null;
export type ProjectId = string;
export type Universe =
  'source_records' | 'modeled_objects' | 'depicted_objects' | 'schedule_entries' | 'physical_building';
export type ViewIds = string[];
/**
 * @minItems 1
 */
export type Steps = [PlanStep, ...PlanStep[]];
export type Id1 = string;
export type Operation1 =
  | SelectOperation
  | TraverseOperation
  | AggregateOperation
  | SpatialQueryOperation
  | RelatedEntitiesOperation
  | ProjectOperation
  | RankOperation
  | MeasureOperation
  | ArithmeticOperation
  | TableCalculateOperation
  | NetworkQueryOperation
  | MaterialQuantityOperation
  | RouteQueryOperation;
export type ConceptIds = string[];
export type DistinctBy = 'canonical_entity_id';
export type Grain = 'logical_object' | 'occurrence' | 'assembly' | 'part' | 'schedule_row';
export type Hierarchy = 'all_matches' | 'topmost_matches' | 'leaves';
export type RuleKey = string;
export type EntityKinds = (
  | 'site'
  | 'building'
  | 'storey'
  | 'unit'
  | 'space'
  | 'element'
  | 'assembly'
  | 'part'
  | 'type'
  | 'system'
  | 'material'
  | 'zone'
  | 'site_feature'
  | 'schedule_row'
)[];
export type Exclude =
  (ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate) | null;
export type Key1 = string;
export type Kind = 'property' | 'label' | 'concept' | 'native_identifier' | 'entity_id' | 'result_column';
export type Kind1 = 'compare';
export type Operator = 'eq' | 'ne' | 'lt' | 'lte' | 'gt' | 'gte' | 'in' | 'contains';
export type Value =
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue;
export type Basis = string;
export type Kind2 = 'quantity';
export type Magnitude = string;
export type Magnitude1 = string;
export type UnitId = string;
export type Quality = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
export type QuantityKind = string;
export type SourceText = string | null;
export type SourceValueType = string | null;
export type UnitAnchorIds = string[];
export type UnitId1 = string | null;
export type UnitResolution = 'explicit' | 'project_default' | 'calibrated' | 'derived' | 'unknown';
export type Kind3 = 'count';
export type Value1 = number;
export type Kind4 = 'text';
export type Language1 = string | null;
export type Text = string;
export type Kind5 = 'boolean';
export type Value2 = boolean;
export type EntityIds1 = string[];
export type Kind6 = 'references';
export type Explanation = string;
export type Kind7 = 'unavailable';
export type Reason = 'explicit_null' | 'not_in_source' | 'not_extracted' | 'unknown' | 'ambiguous';
/**
 * @minItems 1
 */
export type Columns = [TableColumn, ...TableColumn[]];
export type Key2 = string;
export type Kind8 = 'table';
export type Rows = {
  [k: string]:
    | QuantityValue
    | CountValue
    | TextValue
    | BooleanValue
    | ReferencesValue
    | UnavailableValue
    | ListValue
    | RecordValue
    | TableValue;
}[];
export type Kind9 = 'record';
export type Items = (
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue
)[];
export type Kind10 = 'list';
export type Kind11 = 'field_present';
export type Direction = 'outgoing' | 'incoming';
/**
 * @minItems 1
 */
export type EntityIds2 = [string, ...string[]];
export type Kind12 = 'related_to';
export type Predicate = string;
export type GeometryId = string;
export type Kind13 = 'spatial';
export type Operator1 = 'intersects' | 'within' | 'contains' | 'touches' | 'disjoint' | 'near';
export type Kind14 = 'all' | 'any' | 'not';
/**
 * @minItems 1
 */
export type Operands = [
  ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate,
  ...(ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate)[]
];
export type Kind15 = 'select';
export type Where =
  (ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate) | null;
export type Direction1 = 'outgoing' | 'incoming';
export type InputStepId = string;
export type Kind16 = 'traverse';
export type MaxDepth = number;
export type Predicate1 = string;
export type Recursive = boolean;
export type GroupBy = FieldRef[];
export type InputStepId1 = string;
export type Kind17 = 'aggregate';
export type Method = 'count' | 'sum' | 'mean' | 'min' | 'max';
export type MissingGroups = 'fail' | 'unclassified';
export type MissingValues = 'fail' | 'partial';
export type OutputUnitId = string | null;
export type ValueKey = string;
export type ContainerKind = 'space' | 'storey' | 'building' | 'site';
export type ExteriorBasis = 'combined' | 'classification' | 'boundary';
export type InputStepId2 = string;
export type Kind18 = 'spatial_query';
export type Method1 = 'native' | 'geometry' | 'auto';
export type Relation = 'containers' | 'boundary_neighbors' | 'door_connections' | 'outdoor_access' | 'exterior_doors';
export type ToleranceM = number;
export type Column = string;
export type InputStepId3 = string;
export type Kind19 = 'related_entities';
/**
 * @minItems 1
 */
export type Fields1 = [FieldRef, ...FieldRef[]];
export type InputStepId4 = string;
export type Kind20 = 'project';
export type Direction2 = 'ascending' | 'descending';
export type IncludeTies = boolean;
export type InputStepId5 = string;
export type Kind21 = 'rank';
export type Limit = number;
export type Basis1 = string;
export type CalibrationIds = string[];
export type InputStepId6 = string;
export type Kind22 = 'measure';
export type Metric =
  | 'area'
  | 'union_area'
  | 'enclosed_area'
  | 'length'
  | 'perimeter'
  | 'volume'
  | 'distance'
  | 'angle'
  | 'height'
  | 'base_elevation'
  | 'horizontal_distance';
export type OutputUnitId1 = string;
export type ReferenceEntityIds = string[];
/**
 * @minItems 2
 */
export type InputStepIds = [string, string, ...string[]];
export type Kind23 = 'arithmetic';
export type Operator2 = 'add' | 'subtract' | 'multiply' | 'divide';
export type OutputUnitId2 = string | null;
/**
 * @minItems 1
 * @maxItems 8
 */
export type Fields2 =
  | [FieldRef]
  | [FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef];
/**
 * @maxItems 8
 */
export type GroupBy1 =
  | []
  | [FieldRef]
  | [FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef]
  | [FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef, FieldRef];
export type InputStepId7 = string;
export type Kind24 = 'table_calculate';
export type NextKey = string;
export type Operator3 = 'add' | 'subtract' | 'multiply' | 'divide' | 'percent_of_total' | 'consecutive_difference';
export type OutputUnitId3 = string | null;
export type ValueKey1 = string;
export type ComponentStepId = string | null;
export type InputStepId8 = string;
export type Kind25 = 'network_query';
export type InputStepId9 = string;
export type Kind26 = 'material_quantity';
/**
 * @maxItems 32
 */
export type MaterialNames = string[];
export type Method2 = 'auto' | 'recorded_net' | 'geometry';
export type OutputUnitId4 = string;
export type ToleranceM1 = number;
export type ClearanceM = number;
export type IncludeStairs = boolean;
export type InputStepId10 = string;
export type Kind27 = 'route_query';
export type Mode = 'shortest' | 'farthest';
export type StartBasis = 'modeled_interior_point' | 'explicit_point' | 'farthest_sampled';
export type StartPointM = [unknown, unknown, unknown] | null;
export type TargetBasis = 'recorded_external_boundary' | 'certified_fire_exit';
export type TargetStepId = string | null;
export type Question1 = string;
export type SchemaVersion1 = '0.1.0';
export type DisplayHeight = number | null;
export type DisplaySha256 = string | null;
export type DisplayWidth = number | null;
export type LayoutName = string | null;
export type PageIndex = number | null;
export type Rotation = 0 | 90 | 180 | 270;
export type SourceBounds = [number, number, number, number] | null;
export type SourceRevision = string;
export type SourceSha256 = string;
export type ViewportTransform = [number, number, number, number, number, number] | null;
export type SourceId = string | null;
export type SourceSha2561 = string;

export interface AnswerRequest {
  detail?: Detail;
  language?: Language;
  model_id?: ModelId;
  parts?: Parts;
  plans?: Plans;
  question: Question1;
  schema_version?: SchemaVersion1;
  snapshot?: AnswerSnapshot | null;
  source_id?: SourceId;
  source_sha256: SourceSha2561;
}
export interface AnswerRequestedPart {
  depends_on?: DependsOn;
  exclusions?: Exclusions;
  filters?: Filters;
  key: Key;
  literal_identifiers?: LiteralIdentifiers;
  operation?: Operation;
  question: Question;
  target?: Target;
}
export interface Plans {
  [k: string]: QueryPlan;
}
export interface QueryPlan {
  id: Id;
  outputs: Outputs;
  request_id: RequestId;
  required_capabilities?: RequiredCapabilities;
  schema_version?: SchemaVersion;
  scope: Scope;
  steps: Steps;
}
export interface Outputs {
  [k: string]: string;
}
export interface Scope {
  document_ids: DocumentIds;
  entity_ids?: EntityIds;
  exact_entity_ids?: ExactEntityIds;
  project_id: ProjectId;
  universe: Universe;
  view_ids?: ViewIds;
}
export interface PlanStep {
  id: Id1;
  operation: Operation1;
}
export interface SelectOperation {
  concept_ids: ConceptIds;
  count_policy: CountPolicy;
  entity_kinds?: EntityKinds;
  exclude?: Exclude;
  kind: Kind15;
  where?: Where;
}
export interface CountPolicy {
  distinct_by?: DistinctBy;
  grain: Grain;
  hierarchy: Hierarchy;
  rule_key: RuleKey;
}
export interface ComparePredicate {
  field: FieldRef;
  kind: Kind1;
  operator: Operator;
  value: Value;
}
export interface FieldRef {
  key: Key1;
  kind: Kind;
}
export interface QuantityValue {
  basis: Basis;
  kind: Kind2;
  magnitude: Magnitude;
  normalized?: NormalizedQuantity | null;
  quality?: Quality;
  quantity_kind: QuantityKind;
  source_text?: SourceText;
  source_value_type?: SourceValueType;
  unit_anchor_ids?: UnitAnchorIds;
  unit_id: UnitId1;
  unit_resolution: UnitResolution;
}
export interface NormalizedQuantity {
  magnitude: Magnitude1;
  unit_id: UnitId;
}
export interface CountValue {
  kind: Kind3;
  value: Value1;
}
export interface TextValue {
  kind: Kind4;
  value: LocalizedText;
}
export interface LocalizedText {
  language?: Language1;
  text: Text;
}
export interface BooleanValue {
  kind: Kind5;
  value: Value2;
}
export interface ReferencesValue {
  entity_ids: EntityIds1;
  kind: Kind6;
}
/**
 * A missing cell in a partial list/record/table; never a numeric zero.
 */
export interface UnavailableValue {
  explanation: Explanation;
  kind: Kind7;
  reason: Reason;
}
export interface ListValue {
  items: Items;
  kind: Kind10;
}
export interface RecordValue {
  fields: Fields;
  kind: Kind9;
}
export interface Fields {
  [k: string]:
    | QuantityValue
    | CountValue
    | TextValue
    | BooleanValue
    | ReferencesValue
    | UnavailableValue
    | ListValue
    | RecordValue
    | TableValue;
}
export interface TableValue {
  columns: Columns;
  kind: Kind8;
  rows: Rows;
}
export interface TableColumn {
  key: Key2;
  label: LocalizedText;
}
export interface PresentPredicate {
  field: FieldRef;
  kind: Kind11;
}
export interface RelationPredicate {
  direction: Direction;
  entity_ids: EntityIds2;
  kind: Kind12;
  predicate: Predicate;
}
export interface SpatialPredicate {
  distance?: QuantityValue | null;
  geometry_id: GeometryId;
  kind: Kind13;
  operator: Operator1;
}
export interface BooleanPredicate {
  kind: Kind14;
  operands: Operands;
}
export interface TraverseOperation {
  direction: Direction1;
  input_step_id: InputStepId;
  kind: Kind16;
  max_depth?: MaxDepth;
  predicate: Predicate1;
  recursive?: Recursive;
}
export interface AggregateOperation {
  field?: FieldRef | null;
  group_by?: GroupBy;
  input_step_id: InputStepId1;
  kind: Kind17;
  method: Method;
  missing_groups?: MissingGroups;
  missing_values?: MissingValues;
  output_unit_id?: OutputUnitId;
  value_key?: ValueKey;
}
/**
 * Bounded IFC topology and supported source-geometry checks.
 */
export interface SpatialQueryOperation {
  container_kind?: ContainerKind;
  exterior_basis?: ExteriorBasis;
  input_step_id: InputStepId2;
  kind: Kind18;
  method?: Method1;
  relation: Relation;
  tolerance_m?: ToleranceM;
}
/**
 * Deduplicate references from one table column at occurrence grain.
 */
export interface RelatedEntitiesOperation {
  column?: Column;
  input_step_id: InputStepId3;
  kind: Kind19;
}
export interface ProjectOperation {
  fields: Fields1;
  input_step_id: InputStepId4;
  kind: Kind20;
}
export interface RankOperation {
  direction: Direction2;
  field: FieldRef;
  include_ties?: IncludeTies;
  input_step_id: InputStepId5;
  kind: Kind21;
  limit: Limit;
}
export interface MeasureOperation {
  basis: Basis1;
  calibration_ids?: CalibrationIds;
  input_step_id: InputStepId6;
  kind: Kind22;
  metric: Metric;
  output_unit_id: OutputUnitId1;
  reference_entity_ids?: ReferenceEntityIds;
}
export interface ArithmeticOperation {
  input_step_ids: InputStepIds;
  kind: Kind23;
  operator: Operator2;
  output_unit_id?: OutputUnitId2;
}
/**
 * Bounded arithmetic over source-derived table cells, never expressions.
 */
export interface TableCalculateOperation {
  fields: Fields2;
  group_by?: GroupBy1;
  input_step_id: InputStepId7;
  kind: Kind24;
  next_key?: NextKey;
  operator: Operator3;
  order_by?: FieldRef | null;
  output_unit_id?: OutputUnitId3;
  value_key?: ValueKey1;
}
/**
 * Metrics of an explicitly selected native distribution-port graph.
 */
export interface NetworkQueryOperation {
  component_step_id?: ComponentStepId;
  input_step_id: InputStepId8;
  kind: Kind25;
}
/**
 * Recorded homogeneous net volumes or source-verified material estimates.
 */
export interface MaterialQuantityOperation {
  input_step_id: InputStepId9;
  kind: Kind26;
  material_names?: MaterialNames;
  method?: Method2;
  output_unit_id?: OutputUnitId4;
  tolerance_m?: ToleranceM1;
}
/**
 * A bounded modeled walking route, separate from straight-line distance.
 */
export interface RouteQueryOperation {
  clearance_m?: ClearanceM;
  include_stairs?: IncludeStairs;
  input_step_id: InputStepId10;
  kind: Kind27;
  mode?: Mode;
  start_basis?: StartBasis;
  start_point_m?: StartPointM;
  target_basis?: TargetBasis;
  target_step_id?: TargetStepId;
}
export interface AnswerSnapshot {
  display_height?: DisplayHeight;
  display_sha256?: DisplaySha256;
  display_width?: DisplayWidth;
  layout_name?: LayoutName;
  page_index?: PageIndex;
  rotation?: Rotation;
  source_bounds?: SourceBounds;
  source_revision: SourceRevision;
  source_sha256: SourceSha256;
  viewport_transform?: ViewportTransform;
}

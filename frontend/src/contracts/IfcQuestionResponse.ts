/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type AssetId = string;
export type GeometryId = string | null;
export type Id = string;
export type Language = string | null;
export type Text = string;
export type ColumnIndex = number | null;
export type InstancePath = string[];
export type Kind =
  'ifc_guid' | 'step_id' | 'dxf_handle' | 'svg_id' | 'pdf_span' | 'table_cell' | 'image_region' | 'file_metadata';
export type PropertyPath = string[];
export type RowIndex = number | null;
export type Value = string;
export type ViewId = string | null;
export type Anchors = EvidenceAnchor[];
export type Attribution = string;
export type DocumentId = string;
export type Format = 'ifc' | 'dxf' | 'dwg' | 'pdf' | 'svg' | 'png' | 'jpeg' | 'other';
export type Id1 = string;
export type License = string;
export type MediaType = string;
export type Sha256 = string;
export type SourceCollection = string;
export type Uri = string;
export type Assets = Asset[];
export type Completeness = 'complete' | 'partial' | 'not_modeled' | 'not_extracted' | 'unknown';
export type ConceptIds = string[];
export type DistinctBy = 'canonical_entity_id';
export type Grain = 'logical_object' | 'occurrence' | 'assembly' | 'part' | 'schedule_row';
export type Hierarchy = 'all_matches' | 'topmost_matches' | 'leaves';
export type RuleKey = string;
export type Explanation = string;
export type Id2 = string;
export type PropertyKeys = string[];
export type AnchorIds = string[];
export type Method = 'native' | 'computed' | 'ocr' | 'detected' | 'inferred' | 'human';
export type RunId = string;
export type Score = number | null;
export type ScoreName = string | null;
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
export type Coverage = Coverage1[];
export type EntityId = string;
export type Guid = string | null;
export type IfcClass = string;
export type Name = string;
export type StepId = number | null;
export type ExcludedElements = IfcElement[];
export type ConfigSha256 = string;
export type Id3 = string;
/**
 * @minItems 1
 */
export type InputAssetIds = [string, ...string[]];
export type ModelRevision = string | null;
export type OutputSchemaVersion = '0.1.0';
export type StartedAt = string;
export type Tool = string;
export type Version = string;
export type ExtractionRuns = ExtractionRun[];
export type Id4 = string;
export type OriginalPropertyPath = string[];
export type PropertyKey = string;
export type Status = 'present' | 'explicit_null' | 'not_in_source' | 'not_extracted' | 'unknown' | 'ambiguous';
export type SubjectId = string;
export type SupersedesFactId = string | null;
export type Value1 =
  | (
      | QuantityValue
      | CountValue
      | TextValue
      | BooleanValue
      | ReferencesValue
      | UnavailableValue
      | ListValue
      | RecordValue
      | TableValue
    )
  | null;
export type Basis = string;
export type Kind1 = 'quantity';
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
export type Kind2 = 'count';
export type Value2 = number;
export type Kind3 = 'text';
export type Kind4 = 'boolean';
export type Value3 = boolean;
export type EntityIds1 = string[];
export type Kind5 = 'references';
export type Explanation1 = string;
export type Kind6 = 'unavailable';
export type Reason = 'explicit_null' | 'not_in_source' | 'not_extracted' | 'unknown' | 'ambiguous';
/**
 * @minItems 1
 */
export type Columns = [TableColumn, ...TableColumn[]];
export type Key = string;
export type Kind7 = 'table';
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
export type Kind8 = 'record';
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
export type Kind9 = 'list';
export type Facts = Fact[];
export type IncludedElements = IfcElement[];
export type Interpretation = string;
export type ModelId = string;
export type Id5 = string;
export type RequestId = string;
export type RequiredCapabilities = string[];
export type SchemaVersion = '0.1.0';
/**
 * @minItems 1
 */
export type Steps = [PlanStep, ...PlanStep[]];
export type Id6 = string;
export type Operation =
  | SelectOperation
  | TraverseOperation
  | AggregateOperation
  | SpatialQueryOperation
  | ProjectOperation
  | RankOperation
  | MeasureOperation
  | ArithmeticOperation;
export type ConceptIds1 = string[];
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
export type Kind10 = 'property' | 'label' | 'concept' | 'native_identifier' | 'entity_id' | 'result_column';
export type Kind11 = 'compare';
export type Operator = 'eq' | 'ne' | 'lt' | 'lte' | 'gt' | 'gte' | 'in' | 'contains';
export type Value4 =
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue;
export type Kind12 = 'field_present';
export type Direction = 'outgoing' | 'incoming';
/**
 * @minItems 1
 */
export type EntityIds2 = [string, ...string[]];
export type Kind13 = 'related_to';
export type Predicate = string;
export type GeometryId1 = string;
export type Kind14 = 'spatial';
export type Operator1 = 'intersects' | 'within' | 'contains' | 'touches' | 'disjoint' | 'near';
export type Kind15 = 'all' | 'any' | 'not';
/**
 * @minItems 1
 */
export type Operands = [
  ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate,
  ...(ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate)[]
];
export type Kind16 = 'select';
export type Where =
  (ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate) | null;
export type Direction1 = 'outgoing' | 'incoming';
export type InputStepId = string;
export type Kind17 = 'traverse';
export type MaxDepth = number;
export type Predicate1 = string;
export type Recursive = boolean;
export type GroupBy = FieldRef[];
export type InputStepId1 = string;
export type Kind18 = 'aggregate';
export type Method1 = 'count' | 'sum' | 'mean' | 'min' | 'max';
export type MissingValues = 'fail' | 'partial';
export type OutputUnitId = string | null;
export type ValueKey = string;
export type ContainerKind = 'space' | 'storey' | 'building' | 'site';
export type InputStepId2 = string;
export type Kind19 = 'spatial_query';
export type Relation = 'containers' | 'boundary_neighbors' | 'door_connections' | 'outdoor_access';
/**
 * @minItems 1
 */
export type Fields1 = [FieldRef, ...FieldRef[]];
export type InputStepId3 = string;
export type Kind20 = 'project';
export type Direction2 = 'ascending' | 'descending';
export type InputStepId4 = string;
export type Kind21 = 'rank';
export type Limit = number;
export type Basis1 = string;
export type CalibrationIds = string[];
export type InputStepId5 = string;
export type Kind22 = 'measure';
export type Metric = 'area' | 'union_area' | 'length' | 'perimeter' | 'volume' | 'distance' | 'angle';
export type OutputUnitId1 = string;
export type ReferenceEntityIds = string[];
/**
 * @minItems 2
 */
export type InputStepIds = [string, string, ...string[]];
export type Kind23 = 'arithmetic';
export type Operator2 = 'add' | 'subtract' | 'multiply' | 'divide';
export type OutputUnitId2 = string | null;
export type Definition = string;
export type Dimension = [unknown, unknown, unknown, unknown, unknown, unknown, unknown] | null;
export type Key2 = string;
export type Labels = LocalizedText[];
export type QuantityKind1 = string | null;
export type ValueKind = 'text' | 'count' | 'quantity' | 'boolean' | 'references' | 'list' | 'record' | 'table';
export type Properties = PropertyDefinition[];
export type Question = string;
export type RequestId1 = string;
export type AnchorIds1 = string[];
export type CalibrationIds1 = string[];
export type ExcludedSetId = string | null;
export type FactIds = string[];
export type Id7 = string;
export type IncludedSetId = string | null;
export type InputNodeIds = string[];
export type Operation1 =
  | 'select'
  | 'traverse'
  | 'spatial_query'
  | 'project'
  | 'rank'
  | 'count'
  | 'sum'
  | 'mean'
  | 'min'
  | 'max'
  | 'lookup'
  | 'convert_unit'
  | 'add'
  | 'subtract'
  | 'multiply'
  | 'divide'
  | 'measure'
  | 'group_by'
  | 'filter'
  | 'deduplicate';
export type Output =
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue;
export type PlanStepId = string | null;
export type Quality1 = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
export type RuleKey1 = string | null;
export type Calculations = CalculationNode[];
export type ConceptIds2 = string[];
/**
 * @minItems 1
 */
export type CoverageIds = [string, ...string[]];
/**
 * @minItems 1
 */
export type Evidence = [EvidenceBinding, ...EvidenceBinding[]];
export type AnchorIds2 = string[];
export type CalculationId = string;
export type EntitySetIds = string[];
export type FactIds1 = string[];
export type ValuePath = string;
export type Id8 = string;
export type Name1 = string;
export type OutputKey = string;
export type PropertyKeys1 = string[];
export type Quality2 = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
export type Value5 =
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue;
export type Claims = Claim[];
export type Count = number;
export type EntityIds3 = string[] | null;
export type Id9 = string;
export type MembersSha256 = string | null;
export type MembersUri = string | null;
export type EntitySets = EntitySet[];
export type ExecutorVersion = string;
export type Id10 = string;
export type AnchorIds3 = string[];
export type Code =
  | 'needs_clarification'
  | 'missing_source'
  | 'missing_information'
  | 'incomplete_coverage'
  | 'unsupported_operation'
  | 'conflicting_evidence'
  | 'insufficient_calibration'
  | 'execution_error';
export type EntityIds4 = string[];
export type FactIds2 = string[];
export type Options = LocalizedText[];
export type Issues = Issue[];
export type CacheHit = boolean;
export type CostAmount = string | null;
export type CostBasis = ('marginal' | 'amortized' | 'estimated') | null;
export type CostCurrency = string | null;
export type LatencyMs = number;
export type ModelInputTokens = number;
export type ModelOutputTokens = number;
export type PlanId = string | null;
export type RequestId2 = string;
export type SchemaVersion1 = '0.1.0';
export type Status1 =
  | 'answered'
  | 'partial'
  | 'needs_clarification'
  | 'missing_source'
  | 'missing_information'
  | 'incomplete_coverage'
  | 'unsupported_operation'
  | 'conflicting_evidence'
  | 'insufficient_calibration'
  | 'execution_error';
export type SchemaVersion2 = '0.1.0';
export type Scope1 = 'view' | 'model';
export type ScopeLabel = string;
export type SourceSha256 = string;
export type Dimension1 = [unknown, unknown, unknown, unknown, unknown, unknown, unknown] | null;
export type Id11 = string;
export type Kind24 = 'physical' | 'presentation';
export type SiMultiplier = string | null;
export type SiOffset = string;
export type Symbol = string;
export type Units = Unit[];
export type Warnings = string[];

export interface IfcQuestionResponse {
  anchors?: Anchors;
  assets?: Assets;
  coverage?: Coverage;
  excluded_elements?: ExcludedElements;
  extraction_runs?: ExtractionRuns;
  facts?: Facts;
  included_elements?: IncludedElements;
  interpretation: Interpretation;
  model_id: ModelId;
  plan?: QueryPlan | null;
  properties?: Properties;
  question: Question;
  request_id: RequestId1;
  result: QueryResult;
  schema_version?: SchemaVersion2;
  scope: Scope1;
  scope_label: ScopeLabel;
  source_sha256: SourceSha256;
  units?: Units;
  warnings?: Warnings;
}
export interface EvidenceAnchor {
  asset_id: AssetId;
  geometry_id?: GeometryId;
  id: Id;
  quote?: LocalizedText | null;
  selector: NativeSelector;
  view_id?: ViewId;
}
export interface LocalizedText {
  language?: Language;
  text: Text;
}
export interface NativeSelector {
  column_index?: ColumnIndex;
  instance_path?: InstancePath;
  kind: Kind;
  property_path?: PropertyPath;
  row_index?: RowIndex;
  value: Value;
}
export interface Asset {
  attribution: Attribution;
  document_id: DocumentId;
  format: Format;
  id: Id1;
  license: License;
  media_type: MediaType;
  sha256: Sha256;
  source_collection: SourceCollection;
  uri: Uri;
}
export interface Coverage1 {
  completeness: Completeness;
  concept_ids: ConceptIds;
  count_policy?: CountPolicy | null;
  explanation: Explanation;
  id: Id2;
  property_keys?: PropertyKeys;
  provenance: Provenance;
  scope: Scope;
}
export interface CountPolicy {
  distinct_by?: DistinctBy;
  grain: Grain;
  hierarchy: Hierarchy;
  rule_key: RuleKey;
}
export interface Provenance {
  anchor_ids?: AnchorIds;
  method: Method;
  run_id: RunId;
  score?: Score;
  score_name?: ScoreName;
}
export interface Scope {
  document_ids: DocumentIds;
  entity_ids?: EntityIds;
  exact_entity_ids?: ExactEntityIds;
  project_id: ProjectId;
  universe: Universe;
  view_ids?: ViewIds;
}
/**
 * Canonical entity and its original product locators for viewer verification.
 */
export interface IfcElement {
  entity_id: EntityId;
  guid?: Guid;
  ifc_class: IfcClass;
  name: Name;
  step_id?: StepId;
}
export interface ExtractionRun {
  config_sha256: ConfigSha256;
  id: Id3;
  input_asset_ids: InputAssetIds;
  model_revision?: ModelRevision;
  output_schema_version?: OutputSchemaVersion;
  started_at: StartedAt;
  tool: Tool;
  version: Version;
}
export interface Fact {
  id: Id4;
  original_property_path?: OriginalPropertyPath;
  property_key: PropertyKey;
  provenance: Provenance;
  status: Status;
  subject_id: SubjectId;
  supersedes_fact_id?: SupersedesFactId;
  value?: Value1;
}
export interface QuantityValue {
  basis: Basis;
  kind: Kind1;
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
  kind: Kind2;
  value: Value2;
}
export interface TextValue {
  kind: Kind3;
  value: LocalizedText;
}
export interface BooleanValue {
  kind: Kind4;
  value: Value3;
}
export interface ReferencesValue {
  entity_ids: EntityIds1;
  kind: Kind5;
}
/**
 * A missing cell in a partial list/record/table; never a numeric zero.
 */
export interface UnavailableValue {
  explanation: Explanation1;
  kind: Kind6;
  reason: Reason;
}
export interface ListValue {
  items: Items;
  kind: Kind9;
}
export interface RecordValue {
  fields: Fields;
  kind: Kind8;
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
  kind: Kind7;
  rows: Rows;
}
export interface TableColumn {
  key: Key;
  label: LocalizedText;
}
export interface QueryPlan {
  id: Id5;
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
export interface PlanStep {
  id: Id6;
  operation: Operation;
}
export interface SelectOperation {
  concept_ids: ConceptIds1;
  count_policy: CountPolicy;
  entity_kinds?: EntityKinds;
  exclude?: Exclude;
  kind: Kind16;
  where?: Where;
}
export interface ComparePredicate {
  field: FieldRef;
  kind: Kind11;
  operator: Operator;
  value: Value4;
}
export interface FieldRef {
  key: Key1;
  kind: Kind10;
}
export interface PresentPredicate {
  field: FieldRef;
  kind: Kind12;
}
export interface RelationPredicate {
  direction: Direction;
  entity_ids: EntityIds2;
  kind: Kind13;
  predicate: Predicate;
}
export interface SpatialPredicate {
  distance?: QuantityValue | null;
  geometry_id: GeometryId1;
  kind: Kind14;
  operator: Operator1;
}
export interface BooleanPredicate {
  kind: Kind15;
  operands: Operands;
}
export interface TraverseOperation {
  direction: Direction1;
  input_step_id: InputStepId;
  kind: Kind17;
  max_depth?: MaxDepth;
  predicate: Predicate1;
  recursive?: Recursive;
}
export interface AggregateOperation {
  field?: FieldRef | null;
  group_by?: GroupBy;
  input_step_id: InputStepId1;
  kind: Kind18;
  method: Method1;
  missing_values?: MissingValues;
  output_unit_id?: OutputUnitId;
  value_key?: ValueKey;
}
/**
 * Bounded native IFC topology, separate from mesh/metric spatial predicates.
 */
export interface SpatialQueryOperation {
  container_kind?: ContainerKind;
  input_step_id: InputStepId2;
  kind: Kind19;
  relation: Relation;
}
export interface ProjectOperation {
  fields: Fields1;
  input_step_id: InputStepId3;
  kind: Kind20;
}
export interface RankOperation {
  direction: Direction2;
  field: FieldRef;
  input_step_id: InputStepId4;
  kind: Kind21;
  limit: Limit;
}
export interface MeasureOperation {
  basis: Basis1;
  calibration_ids?: CalibrationIds;
  input_step_id: InputStepId5;
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
export interface PropertyDefinition {
  definition: Definition;
  dimension?: Dimension;
  key: Key2;
  labels: Labels;
  quantity_kind?: QuantityKind1;
  value_kind: ValueKind;
}
export interface QueryResult {
  calculations?: Calculations;
  claims?: Claims;
  entity_sets?: EntitySets;
  executor_version: ExecutorVersion;
  explanation?: LocalizedText | null;
  id: Id10;
  issues?: Issues;
  metrics?: ExecutionMetrics | null;
  plan_id?: PlanId;
  request_id: RequestId2;
  schema_version?: SchemaVersion1;
  status: Status1;
}
export interface CalculationNode {
  anchor_ids?: AnchorIds1;
  calibration_ids?: CalibrationIds1;
  excluded_set_id?: ExcludedSetId;
  fact_ids?: FactIds;
  id: Id7;
  included_set_id?: IncludedSetId;
  input_node_ids?: InputNodeIds;
  operation: Operation1;
  output: Output;
  plan_step_id?: PlanStepId;
  quality: Quality1;
  rule_key?: RuleKey1;
}
export interface Claim {
  concept_ids: ConceptIds2;
  count_policy?: CountPolicy | null;
  coverage_ids: CoverageIds;
  evidence: Evidence;
  id: Id8;
  name: Name1;
  output_key: OutputKey;
  property_keys?: PropertyKeys1;
  quality: Quality2;
  scope: Scope;
  value: Value5;
}
export interface EvidenceBinding {
  anchor_ids?: AnchorIds2;
  calculation_id: CalculationId;
  entity_set_ids?: EntitySetIds;
  fact_ids?: FactIds1;
  value_path?: ValuePath;
}
export interface EntitySet {
  count: Count;
  count_policy: CountPolicy;
  entity_ids?: EntityIds3;
  id: Id9;
  members_sha256?: MembersSha256;
  members_uri?: MembersUri;
  scope: Scope;
}
export interface Issue {
  anchor_ids?: AnchorIds3;
  code: Code;
  entity_ids?: EntityIds4;
  fact_ids?: FactIds2;
  message: LocalizedText;
  options?: Options;
}
export interface ExecutionMetrics {
  cache_hit?: CacheHit;
  cost_amount?: CostAmount;
  cost_basis?: CostBasis;
  cost_currency?: CostCurrency;
  latency_ms: LatencyMs;
  model_input_tokens?: ModelInputTokens;
  model_output_tokens?: ModelOutputTokens;
}
export interface Unit {
  dimension?: Dimension1;
  id: Id11;
  kind: Kind24;
  si_multiplier?: SiMultiplier;
  si_offset?: SiOffset;
  symbol: Symbol;
}

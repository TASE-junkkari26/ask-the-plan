/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type AnchorIds = string[];
export type CalibrationIds = string[];
export type ExcludedSetId = string | null;
export type FactIds = string[];
export type Id = string;
export type IncludedSetId = string | null;
export type InputNodeIds = string[];
export type Operation =
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
export type Basis = string;
export type Kind = 'quantity';
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
export type Kind1 = 'count';
export type Value = number;
export type Kind2 = 'text';
export type Language = string | null;
export type Text = string;
export type Kind3 = 'boolean';
export type Value1 = boolean;
export type EntityIds = string[];
export type Kind4 = 'references';
export type Explanation = string;
export type Kind5 = 'unavailable';
export type Reason = 'explicit_null' | 'not_in_source' | 'not_extracted' | 'unknown' | 'ambiguous';
/**
 * @minItems 1
 */
export type Columns = [TableColumn, ...TableColumn[]];
export type Key = string;
export type Kind6 = 'table';
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
export type Kind7 = 'record';
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
export type Kind8 = 'list';
export type PlanStepId = string | null;
export type Quality1 = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
export type RuleKey = string | null;
export type Calculations = CalculationNode[];
export type ConceptIds = string[];
export type DistinctBy = 'canonical_entity_id';
export type Grain = 'logical_object' | 'occurrence' | 'assembly' | 'part' | 'schedule_row';
export type Hierarchy = 'all_matches' | 'topmost_matches' | 'leaves';
export type RuleKey1 = string;
/**
 * @minItems 1
 */
export type CoverageIds = [string, ...string[]];
/**
 * @minItems 1
 */
export type Evidence = [EvidenceBinding, ...EvidenceBinding[]];
export type AnchorIds1 = string[];
export type CalculationId = string;
export type EntitySetIds = string[];
export type FactIds1 = string[];
export type ValuePath = string;
export type Id1 = string;
export type Name = string;
export type OutputKey = string;
export type PropertyKeys = string[];
export type Quality2 = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
/**
 * @minItems 1
 */
export type DocumentIds = [string, ...string[]];
export type EntityIds1 = string[];
export type ExactEntityIds = string[] | null;
export type ProjectId = string;
export type Universe =
  'source_records' | 'modeled_objects' | 'depicted_objects' | 'schedule_entries' | 'physical_building';
export type ViewIds = string[];
export type Value2 =
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
export type EntityIds2 = string[] | null;
export type Id2 = string;
export type MembersSha256 = string | null;
export type MembersUri = string | null;
export type EntitySets = EntitySet[];
export type ExecutorVersion = string;
export type Id3 = string;
export type AnchorIds2 = string[];
export type Code =
  | 'needs_clarification'
  | 'missing_source'
  | 'missing_information'
  | 'incomplete_coverage'
  | 'unsupported_operation'
  | 'conflicting_evidence'
  | 'insufficient_calibration'
  | 'execution_error';
export type EntityIds3 = string[];
export type FactIds2 = string[];
export type Options = LocalizedText[];
export type Issues = Issue[];
export type CacheHit = boolean;
export type CostAmount = string | null;
export type CostBasis = ('marginal' | 'amortized' | 'estimated') | null;
export type CostCurrency = string | null;
export type LatencyMs = number;
export type ModelInputTokens = number | null;
export type ModelOutputTokens = number | null;
export type PlanId = string | null;
export type RequestId = string;
export type SchemaVersion = '0.1.0';
export type Status =
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

export interface QueryResult {
  calculations?: Calculations;
  claims?: Claims;
  entity_sets?: EntitySets;
  executor_version: ExecutorVersion;
  explanation?: LocalizedText | null;
  id: Id3;
  issues?: Issues;
  metrics?: ExecutionMetrics | null;
  plan_id?: PlanId;
  request_id: RequestId;
  schema_version?: SchemaVersion;
  status: Status;
}
export interface CalculationNode {
  anchor_ids?: AnchorIds;
  calibration_ids?: CalibrationIds;
  excluded_set_id?: ExcludedSetId;
  fact_ids?: FactIds;
  id: Id;
  included_set_id?: IncludedSetId;
  input_node_ids?: InputNodeIds;
  operation: Operation;
  output: Output;
  plan_step_id?: PlanStepId;
  quality: Quality1;
  rule_key?: RuleKey;
}
export interface QuantityValue {
  basis: Basis;
  kind: Kind;
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
  kind: Kind1;
  value: Value;
}
export interface TextValue {
  kind: Kind2;
  value: LocalizedText;
}
export interface LocalizedText {
  language?: Language;
  text: Text;
}
export interface BooleanValue {
  kind: Kind3;
  value: Value1;
}
export interface ReferencesValue {
  entity_ids: EntityIds;
  kind: Kind4;
}
/**
 * A missing cell in a partial list/record/table; never a numeric zero.
 */
export interface UnavailableValue {
  explanation: Explanation;
  kind: Kind5;
  reason: Reason;
}
export interface ListValue {
  items: Items;
  kind: Kind8;
}
export interface RecordValue {
  fields: Fields;
  kind: Kind7;
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
  kind: Kind6;
  rows: Rows;
}
export interface TableColumn {
  key: Key;
  label: LocalizedText;
}
export interface Claim {
  concept_ids: ConceptIds;
  count_policy?: CountPolicy | null;
  coverage_ids: CoverageIds;
  evidence: Evidence;
  id: Id1;
  name: Name;
  output_key: OutputKey;
  property_keys?: PropertyKeys;
  quality: Quality2;
  scope: Scope;
  value: Value2;
}
export interface CountPolicy {
  distinct_by?: DistinctBy;
  grain: Grain;
  hierarchy: Hierarchy;
  rule_key: RuleKey1;
}
export interface EvidenceBinding {
  anchor_ids?: AnchorIds1;
  calculation_id: CalculationId;
  entity_set_ids?: EntitySetIds;
  fact_ids?: FactIds1;
  value_path?: ValuePath;
}
export interface Scope {
  document_ids: DocumentIds;
  entity_ids?: EntityIds1;
  exact_entity_ids?: ExactEntityIds;
  project_id: ProjectId;
  universe: Universe;
  view_ids?: ViewIds;
}
export interface EntitySet {
  count: Count;
  count_policy: CountPolicy;
  entity_ids?: EntityIds2;
  id: Id2;
  members_sha256?: MembersSha256;
  members_uri?: MembersUri;
  scope: Scope;
}
export interface Issue {
  anchor_ids?: AnchorIds2;
  code: Code;
  entity_ids?: EntityIds3;
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

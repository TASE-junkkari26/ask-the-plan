/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type AnchorIds = string[];
export type CalibrationIds = string[];
export type ExcludedSetId = string | null;
export type FactIds = string[];
export type Id = string;
export type IncludedSetId = string | null;
export type InputNodeIds = string[];
/**
 * @maxItems 256
 */
export type AssignmentStepIds = number[];
export type Frame = 'ifc_world' | 'native_quantity';
export type HostVolumeM3 = number | null;
/**
 * @maxItems 256
 */
export type LayerStepIds = number[];
export type MaterialName = string | null;
/**
 * @maxItems 256
 */
export type MaterialStepIds = number[];
export type Method =
  | 'recorded_net_homogeneous'
  | 'closed_mesh_homogeneous'
  | 'verified_uniform_layers'
  | 'recorded_not_used'
  | 'unavailable';
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
export type SelectedThicknessM = number | null;
/**
 * @maxItems 2000
 */
export type SourceStepIds = number[];
export type Index = number;
export type LayerStepId = number;
export type MaterialName1 = string | null;
export type MaterialStepId = number | null;
/**
 * @maxItems 256
 */
export type SpecifiedLayers = MaterialLayerInput[];
export type Status = 'verified' | 'recorded_not_used' | 'unavailable';
export type SubjectId = string;
export type ToleranceM = number;
export type TotalThicknessM = number | null;
export type Unit = 'm3';
export type VolumeM3 = number | null;
export type MaterialEvidence = MaterialEvaluation[];
export type Frame1 = 'ifc_world';
export type Method1 = string;
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
/**
 * @maxItems 2000
 */
export type ReferenceEntityIds = string[];
/**
 * @maxItems 2000
 */
export type RepresentationStepIds = number[];
/**
 * @maxItems 2000
 */
export type SourceStepIds1 = number[];
export type Status1 = 'verified' | 'unavailable';
export type SubjectId1 = string;
export type ToleranceM1 = number;
export type Unit1 = 'm' | 'm2' | 'm3' | 'rad';
export type Value = number | null;
export type MeasurementEvidence = MeasurementEvaluation[];
export type ComponentNetworkCount = number;
export type ComponentsWithConnectedPortsCount = number;
export type ComponentsWithPortsCount = number;
export type ConnectedPortCount = number;
export type ConnectionGraphSha256 = string;
export type CountingBasis = string;
export type CutEdgeCount = number;
export type IsolatedPortCount = number;
export type LargestComponentNetworkCount = number;
export type LargestComponentPortCount = number;
export type Method2 = 'native_distribution_port_graph.v1';
export type PortComponentCount = number;
export type SelectedComponentCount = number;
export type SelectedPortCount = number;
export type UniqueConnectionCount = number;
export type NetworkEvidence = NetworkEvaluation[];
export type Operation =
  | 'select'
  | 'traverse'
  | 'spatial_query'
  | 'related_entities'
  | 'network_query'
  | 'material_quantity'
  | 'route_query'
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
export type Kind1 = 'count';
export type Value1 = number;
export type Kind2 = 'text';
export type Language = string | null;
export type Text = string;
export type Kind3 = 'boolean';
export type Value2 = boolean;
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
/**
 * @maxItems 10000
 */
export type AnchorIds1 = string[];
/**
 * @maxItems 1000
 */
export type DoorIds = string[];
export type Frame2 = 'ifc_world';
export type Method3 = string;
/**
 * @maxItems 2048
 */
export type PathPointsM = [unknown, unknown, unknown][];
export type Quality2 = 'estimated';
/**
 * @maxItems 500
 */
export type RoomIds = string[];
/**
 * @maxItems 2000
 */
export type SourceStepIds2 = number[];
/**
 * @maxItems 64
 */
export type StairIds = string[];
export type Status2 = 'verified' | 'partial' | 'unavailable';
export type SubjectId2 = string;
export type TargetId = string | null;
export type ToleranceM2 = number;
export type Unit2 = 'm';
export type RouteEvidence = RouteEvaluation[];
export type RuleKey = string | null;
export type AnchorIds2 = string[];
export type Method4 = string;
export type RelatedIds = string[];
export type Relation = 'containers' | 'boundary_neighbors' | 'door_connections' | 'outdoor_access' | 'exterior_doors';
export type Status3 = 'verified' | 'candidate' | 'unavailable' | 'recorded_empty';
export type SubjectId3 = string;
export type ToleranceM3 = number | null;
export type SpatialEvidence = SpatialEvaluation[];
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
export type AnchorIds3 = string[];
export type CalculationId = string;
export type EntitySetIds = string[];
export type EvidenceKind = 'verified' | 'candidate' | 'unavailable';
export type FactIds1 = string[];
export type ValuePath = string;
export type Id1 = string;
export type Name = string;
export type OutputKey = string;
export type PropertyKeys = string[];
export type Quality3 = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
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
export type Value3 =
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
export type AnchorIds4 = string[];
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
export type Status4 =
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
  status: Status4;
}
export interface CalculationNode {
  anchor_ids?: AnchorIds;
  calibration_ids?: CalibrationIds;
  excluded_set_id?: ExcludedSetId;
  fact_ids?: FactIds;
  id: Id;
  included_set_id?: IncludedSetId;
  input_node_ids?: InputNodeIds;
  material_evidence?: MaterialEvidence;
  measurement_evidence?: MeasurementEvidence;
  network_evidence?: NetworkEvidence;
  operation: Operation;
  output: Output;
  plan_step_id?: PlanStepId;
  quality: Quality1;
  route_evidence?: RouteEvidence;
  rule_key?: RuleKey;
  spatial_evidence?: SpatialEvidence;
}
export interface MaterialEvaluation {
  assignment_step_ids?: AssignmentStepIds;
  frame: Frame;
  host_volume_m3?: HostVolumeM3;
  layer_step_ids?: LayerStepIds;
  material_name?: MaterialName;
  material_step_ids?: MaterialStepIds;
  metadata?: Metadata;
  method: Method;
  recorded_quantity?: QuantityValue | null;
  selected_thickness_m?: SelectedThicknessM;
  source_step_ids?: SourceStepIds;
  specified_layers?: SpecifiedLayers;
  status: Status;
  subject_id: SubjectId;
  tolerance_m: ToleranceM;
  total_thickness_m?: TotalThicknessM;
  unit?: Unit;
  volume_m3?: VolumeM3;
}
export interface Metadata {
  [k: string]: unknown;
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
export interface MaterialLayerInput {
  index: Index;
  layer_step_id: LayerStepId;
  material_name?: MaterialName1;
  material_step_id?: MaterialStepId;
  thickness?: QuantityValue | null;
}
/**
 * Inspectably bounded evidence from a retained IFC geometry source.
 */
export interface MeasurementEvaluation {
  frame: Frame1;
  metadata?: Metadata1;
  method: Method1;
  metric: Metric;
  reference_entity_ids?: ReferenceEntityIds;
  representation_step_ids?: RepresentationStepIds;
  source_step_ids?: SourceStepIds1;
  status: Status1;
  subject_id: SubjectId1;
  tolerance_m: ToleranceM1;
  unit: Unit1;
  value?: Value;
}
export interface Metadata1 {
  [k: string]: unknown;
}
export interface NetworkEvaluation {
  component_network_count?: ComponentNetworkCount;
  components_with_connected_ports_count: ComponentsWithConnectedPortsCount;
  components_with_ports_count: ComponentsWithPortsCount;
  connected_port_count: ConnectedPortCount;
  connection_graph_sha256: ConnectionGraphSha256;
  counting_basis: CountingBasis;
  cut_edge_count?: CutEdgeCount;
  isolated_port_count: IsolatedPortCount;
  largest_component_network_count?: LargestComponentNetworkCount;
  largest_component_port_count: LargestComponentPortCount;
  method: Method2;
  port_component_count: PortComponentCount;
  selected_component_count: SelectedComponentCount;
  selected_port_count: SelectedPortCount;
  unique_connection_count: UniqueConnectionCount;
}
export interface CountValue {
  kind: Kind1;
  value: Value1;
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
  value: Value2;
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
export interface RouteEvaluation {
  anchor_ids?: AnchorIds1;
  door_ids?: DoorIds;
  frame: Frame2;
  metadata?: Metadata2;
  method: Method3;
  path_points_m?: PathPointsM;
  quality?: Quality2;
  room_ids?: RoomIds;
  source_step_ids?: SourceStepIds2;
  stair_ids?: StairIds;
  status: Status2;
  subject_id: SubjectId2;
  target_id?: TargetId;
  tolerance_m: ToleranceM2;
  unit?: Unit2;
}
export interface Metadata2 {
  [k: string]: unknown;
}
/**
 * Machine-readable support and unresolved inputs for one spatial subject.
 */
export interface SpatialEvaluation {
  anchor_ids?: AnchorIds2;
  metadata?: Metadata3;
  method: Method4;
  related_ids?: RelatedIds;
  relation: Relation;
  status: Status3;
  subject_id: SubjectId3;
  tolerance_m?: ToleranceM3;
}
export interface Metadata3 {
  [k: string]: unknown;
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
  quality: Quality3;
  scope: Scope;
  value: Value3;
}
export interface CountPolicy {
  distinct_by?: DistinctBy;
  grain: Grain;
  hierarchy: Hierarchy;
  rule_key: RuleKey1;
}
export interface EvidenceBinding {
  anchor_ids?: AnchorIds3;
  calculation_id: CalculationId;
  entity_set_ids?: EntitySetIds;
  evidence_kind?: EvidenceKind;
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
  anchor_ids?: AnchorIds4;
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

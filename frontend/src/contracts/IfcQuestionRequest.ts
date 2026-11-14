/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type ModelId = string;
export type Question = string;
export type SchemaVersion = '0.1.0';
export type Scope = 'view' | 'model';
export type SourceSha256 = string;
export type ViewLabel = string | null;
export type VisibleStepIds = number[] | null;

export interface IfcQuestionRequest {
  model_id: ModelId;
  question: Question;
  schema_version?: SchemaVersion;
  scope?: Scope;
  source_sha256: SourceSha256;
  view_label?: ViewLabel;
  visible_step_ids?: VisibleStepIds;
}

/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type CoordinateSystem = 'display_pixels_top_left';
export type Height = number;
export type InferenceSha256 = string;
export type Sha256 = string;
export type Width = number;
export type Limitations = string[];
export type CompletionTokens = number | null;
export type ElapsedMs = number;
export type PreparationCacheHit = boolean | null;
export type PreparationMs = number | null;
export type PromptTokens = number | null;
export type InputHeight = number;
export type InputWidth = number;
export type Mode = 'off' | 'original' | 'overview';
export type PipelineVersion = string | null;
export type PreparedId = string | null;
export type PromptVersion = string;
export type RequestedModel = string;
export type ReturnedModel = string;
/**
 * @minItems 1
 * @maxItems 4
 */
export type Regions =
  | [ImageRegionSelection]
  | [ImageRegionSelection, ImageRegionSelection]
  | [ImageRegionSelection, ImageRegionSelection, ImageRegionSelection]
  | [ImageRegionSelection, ImageRegionSelection, ImageRegionSelection, ImageRegionSelection];
export type Id = string;
export type Reason = string;
/**
 * @minItems 4
 * @maxItems 4
 */
export type SourceBox = [number, number, number, number];
export type RequestId = string;
export type SchemaVersion = '0.1.0';
export type Status = 'selected' | 'full_source';
export type TargetKind = string;

export interface ImageRegionResponse {
  image: CandidateImage;
  limitations?: Limitations;
  metrics: CandidateMetrics;
  provenance: CandidateProvenance;
  regions: Regions;
  request_id: RequestId;
  schema_version?: SchemaVersion;
  status: Status;
  target_kind?: TargetKind;
}
/**
 * The exact submitted source and oriented inference/display frame.
 */
export interface CandidateImage {
  coordinate_system?: CoordinateSystem;
  height: Height;
  inference_sha256: InferenceSha256;
  sha256: Sha256;
  width: Width;
}
export interface CandidateMetrics {
  completion_tokens?: CompletionTokens;
  elapsed_ms: ElapsedMs;
  preparation_cache_hit?: PreparationCacheHit;
  preparation_ms?: PreparationMs;
  prompt_tokens?: PromptTokens;
}
export interface CandidateProvenance {
  preprocessing?: CandidatePreparation | null;
  prompt_version: PromptVersion;
  requested_model: RequestedModel;
  returned_model: ReturnedModel;
}
/**
 * Actual model image size, distinct from the unchanged display frame.
 */
export interface CandidatePreparation {
  input_height: InputHeight;
  input_width: InputWidth;
  mode: Mode;
  pipeline_version?: PipelineVersion;
  prepared_id?: PreparedId;
}
export interface ImageRegionSelection {
  id: Id;
  reason: Reason;
  source_box: SourceBox;
}

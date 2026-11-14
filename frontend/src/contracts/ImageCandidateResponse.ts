/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type Category = string;
export type Kind = 'box';
/**
 * @minItems 2
 * @maxItems 3
 */
export type Maximum = [number, number] | [number, number, number];
/**
 * @minItems 2
 * @maxItems 3
 */
export type Minimum = [number, number] | [number, number, number];
export type Id = string;
export type SourceLabel = string | null;
export type Uncertain = boolean;
export type UncertaintyReason = string | null;
export type VisualCue = string;
/**
 * @maxItems 100
 */
export type Candidates = ImageCandidate[];
export type CoordinateSystem = 'display_pixels_top_left';
export type Height = number;
export type InferenceSha256 = string;
export type Sha256 = string;
export type Width = number;
export type InventoryCompleteness = 'unverified';
/**
 * @maxItems 100
 */
export type Limitations = string[];
export type CompletionTokens = number | null;
export type ElapsedMs = number;
export type PromptTokens = number | null;
export type PromptVersion = string;
export type RequestedModel = string;
export type ReturnedModel = string;
export type RequestId = string;
export type SchemaVersion = '0.1.0';
export type Scope = 'submitted_image';
export type Status = 'ok' | 'partial' | 'unreadable' | 'unsupported';

/**
 * Image-bound proposals; an empty list does not establish a zero count.
 */
export interface ImageCandidateResponse {
  candidates?: Candidates;
  image: CandidateImage;
  inventory_completeness?: InventoryCompleteness;
  limitations?: Limitations;
  metrics: CandidateMetrics;
  provenance: CandidateProvenance;
  request_id: RequestId;
  schema_version?: SchemaVersion;
  scope?: Scope;
  status: Status;
}
/**
 * An unreviewed detection, not a canonical building entity or final claim.
 */
export interface ImageCandidate {
  category: Category;
  geometry: BoxShape;
  id: Id;
  source_label?: SourceLabel;
  uncertain: Uncertain;
  uncertainty_reason?: UncertaintyReason;
  visual_cue: VisualCue;
}
export interface BoxShape {
  kind: Kind;
  maximum: Maximum;
  minimum: Minimum;
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
  prompt_tokens?: PromptTokens;
}
export interface CandidateProvenance {
  prompt_version: PromptVersion;
  requested_model: RequestedModel;
  returned_model: ReturnedModel;
}

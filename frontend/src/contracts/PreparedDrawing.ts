/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type ConfigSha256 = string;
export type Id = string;
export type Engine = string | null;
export type Languages = string[];
/**
 * @minItems 4
 * @maxItems 4
 */
export type Bbox = [unknown, unknown, unknown, unknown];
export type Confidence = number | null;
export type Engine1 = string;
export type FrameId = string;
export type Id1 = string;
export type Text = string;
export type Spans = OCRTextSpan[];
export type Status = 'not_requested' | 'unavailable' | 'complete' | 'partial' | 'failed';
export type Version = string | null;
export type Warnings = string[];
export type OriginalUri = string;
export type PipelineVersion = string;
/**
 * @minItems 1
 */
export type Regions = [PreparedRegion, ...PreparedRegion[]];
export type FrameId1 = string;
export type Height = number;
export type Id2 = string;
export type ImageUri = string;
export type OverviewFrameId = string;
export type OverviewHeight = number;
export type OverviewToSource = number[][];
export type OverviewUri = string;
export type OverviewWidth = number;
export type Reason = string;
export type Role = 'full_source' | 'drawing_candidate' | 'context_candidate' | 'unknown';
/**
 * @minItems 4
 * @maxItems 4
 */
export type SourceBbox = [unknown, unknown, unknown, unknown];
export type ToSource = number[][];
export type Width = number;
export type SchemaVersion = '0.1.0';
export type SourceFrameId = string;
export type SourceHeight = number;
export type SourceImageUri = string;
export type SourceSha256 = string;
export type SourceUri = string;
export type SourceWidth = number;
export type Warnings1 = string[];

export interface PreparedDrawing {
  config_sha256: ConfigSha256;
  id: Id;
  ocr: OCRResult;
  original_uri: OriginalUri;
  pipeline_version: PipelineVersion;
  regions: Regions;
  schema_version?: SchemaVersion;
  source_frame_id: SourceFrameId;
  source_height: SourceHeight;
  source_image_uri: SourceImageUri;
  source_sha256: SourceSha256;
  source_uri: SourceUri;
  source_width: SourceWidth;
  warnings?: Warnings1;
}
export interface OCRResult {
  engine?: Engine;
  languages?: Languages;
  spans?: Spans;
  status: Status;
  version?: Version;
  warnings?: Warnings;
}
export interface OCRTextSpan {
  bbox: Bbox;
  confidence?: Confidence;
  engine: Engine1;
  frame_id: FrameId;
  id: Id1;
  text: Text;
}
export interface PreparedRegion {
  frame_id: FrameId1;
  height: Height;
  id: Id2;
  image_uri: ImageUri;
  overview_frame_id: OverviewFrameId;
  overview_height: OverviewHeight;
  overview_to_source: OverviewToSource;
  overview_uri: OverviewUri;
  overview_width: OverviewWidth;
  reason: Reason;
  role: Role;
  source_bbox: SourceBbox;
  to_source: ToSource;
  width: Width;
}

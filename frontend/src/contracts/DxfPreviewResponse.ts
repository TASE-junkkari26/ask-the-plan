/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type Height = number;
export type Insunits = number | null;
/**
 * @minItems 1
 * @maxItems 128
 */
export type Layouts = [string, ...string[]];
export type Page = number;
export type SchemaVersion = '0.1.0';
export type SourceSha256 = string;
export type Status = 'rendered' | 'partial';
export type Svg = string;
/**
 * @maxItems 40
 */
export type Warnings = string[];
export type Width = number;

/**
 * One rendered layout, not a CAD inventory or a calibrated measurement.
 */
export interface DxfPreviewResponse {
  height: Height;
  insunits?: Insunits;
  layouts: Layouts;
  page: Page;
  schema_version?: SchemaVersion;
  source_sha256: SourceSha256;
  status: Status;
  svg: Svg;
  warnings: Warnings;
  width: Width;
}

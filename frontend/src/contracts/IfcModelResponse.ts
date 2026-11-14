/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type EntityCount = number;
export type IfcSchema = string;
export type ModelId = string;
export type SchemaVersion = '0.1.0';
export type SourceSha256 = string;
export type Warnings = string[];

export interface IfcModelResponse {
  entity_count: EntityCount;
  ifc_schema: IfcSchema;
  model_id: ModelId;
  schema_version?: SchemaVersion;
  source_sha256: SourceSha256;
  warnings?: Warnings;
}

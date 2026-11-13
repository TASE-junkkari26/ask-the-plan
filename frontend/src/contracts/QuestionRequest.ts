/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type AttachmentAssetIds = string[];
export type AttachmentViewIds = string[];
export type Id = string;
export type PreviousRequestIds = string[];
export type ProjectId = string | null;
export type Language = string | null;
export type Text = string;
export type SchemaVersion = '0.1.0';

export interface QuestionRequest {
  attachment_asset_ids?: AttachmentAssetIds;
  attachment_view_ids?: AttachmentViewIds;
  id: Id;
  previous_request_ids?: PreviousRequestIds;
  project_id?: ProjectId;
  question: LocalizedText;
  schema_version?: SchemaVersion;
}
export interface LocalizedText {
  language?: Language;
  text: Text;
}

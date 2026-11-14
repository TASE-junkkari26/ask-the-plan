/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type Code = string;
export type Message = string;
export type RequestId = string;
export type Retryable = boolean;
export type SchemaVersion = '0.1.0';

export interface ImageCandidateError {
  code: Code;
  message: Message;
  request_id: RequestId;
  retryable: Retryable;
  schema_version?: SchemaVersion;
}

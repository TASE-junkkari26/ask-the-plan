/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type Code = string;
/**
 * @maxItems 2
 */
export type Calls = [] | [AnalysisCall] | [AnalysisCall, AnalysisCall];
export type CompletedAt = string;
export type CompletionTokens = number | null;
export type ElapsedMs = number;
export type Id = string;
export type InputHeight = number;
export type InputSha256 = string;
export type InputWidth = number;
export type Outcome = 'completed' | 'failed' | 'cancelled';
export type PromptTokens = number | null;
export type Purpose = 'routing' | 'analysis';
export type RequestedModel = string;
export type ReturnedModel = string | null;
export type CapabilityVersion = string;
export type CoordinateSystem = 'display_pixels_top_left';
export type Height = number;
export type InferenceSha256 = string;
export type Sha256 = string;
export type Width = number;
export type Mode = 'off' | 'shadow' | 'auto';
/**
 * @maxItems 20
 */
export type Nodes =
  | []
  | [AnalysisDecisionNode]
  | [AnalysisDecisionNode, AnalysisDecisionNode]
  | [AnalysisDecisionNode, AnalysisDecisionNode, AnalysisDecisionNode]
  | [AnalysisDecisionNode, AnalysisDecisionNode, AnalysisDecisionNode, AnalysisDecisionNode]
  | [AnalysisDecisionNode, AnalysisDecisionNode, AnalysisDecisionNode, AnalysisDecisionNode, AnalysisDecisionNode]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ]
  | [
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode,
      AnalysisDecisionNode
    ];
export type CallId = string | null;
export type Criterion = 'capability' | 'route' | 'preparation' | 'analysis' | 'evidence';
export type Id1 = string;
export type ParentId = string | null;
export type Probability = number | null;
export type ReasonCode = string;
export type State = 'evaluated' | 'selected' | 'skipped' | 'reused' | 'completed' | 'failed' | 'unavailable';
export type Threshold = number | null;
export type Value = string | null;
export type PolicyVersion = string;
export type QuestionSha256 = string;
export type RecommendedProfile = ('normal' | 'strong') | null;
export type RequestId = string;
export type SelectedProfile = 'normal' | 'strong' | 'manual' | 'pending';
export type Message = string;
export type RequestId1 = string;
export type Retryable = boolean;
export type SchemaVersion = '0.1.0';

export interface ImageCandidateError {
  code: Code;
  decision_trace?: ImageDecisionTrace | null;
  message: Message;
  request_id: RequestId1;
  retryable: Retryable;
  schema_version?: SchemaVersion;
}
/**
 * Host-recorded routing path, never a model's hidden reasoning.
 */
export interface ImageDecisionTrace {
  assessment_probabilities?: AssessmentProbabilities;
  assessments?: Assessments;
  calls?: Calls;
  capability_version: CapabilityVersion;
  image: CandidateImage;
  mode: Mode;
  nodes?: Nodes;
  policy_version: PolicyVersion;
  question_sha256: QuestionSha256;
  recommended_profile?: RecommendedProfile;
  request_id: RequestId;
  selected_profile: SelectedProfile;
}
export interface AssessmentProbabilities {
  [k: string]: number;
}
export interface Assessments {
  [k: string]: string;
}
export interface AnalysisCall {
  completed_at: CompletedAt;
  completion_tokens?: CompletionTokens;
  elapsed_ms: ElapsedMs;
  id: Id;
  input_height: InputHeight;
  input_sha256: InputSha256;
  input_width: InputWidth;
  outcome: Outcome;
  prompt_tokens?: PromptTokens;
  purpose: Purpose;
  requested_model: RequestedModel;
  returned_model?: ReturnedModel;
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
export interface AnalysisDecisionNode {
  call_id?: CallId;
  criterion: Criterion;
  id: Id1;
  parent_id?: ParentId;
  probability?: Probability;
  reason_code: ReasonCode;
  state: State;
  threshold?: Threshold;
  value?: Value;
}

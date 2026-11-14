/* Generated from the shared Python contracts. Run npm run generate:contracts. */

export type Code = string;
/**
 * @maxItems 13
 */
export type Calls =
  | []
  | [AnalysisCall]
  | [AnalysisCall, AnalysisCall]
  | [AnalysisCall, AnalysisCall, AnalysisCall]
  | [AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall]
  | [AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall]
  | [AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall]
  | [AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall]
  | [AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall, AnalysisCall]
  | [
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall
    ]
  | [
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall
    ]
  | [
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall
    ]
  | [
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall
    ]
  | [
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall,
      AnalysisCall
    ];
export type CompletedAt = string;
export type CompletionTokens = number | null;
export type ElapsedMs = number;
export type Id = string;
export type InputHeight = number;
export type InputSha256 = string;
export type InputWidth = number;
export type Outcome = 'completed' | 'failed' | 'cancelled';
export type PromptTokens = number | null;
export type Purpose = 'routing' | 'analysis' | 'region_proposal' | 'candidate_verification' | 'reinspection';
export type RequestedModel = string;
export type ReturnedModel = string | null;
export type SourceBox = [number, number, number, number] | null;
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
export type QuestionSha2561 = string;
export type RequestId2 = string;
export type RequestedModel1 = string;
export type SchemaVersion1 = '0.1.0';
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
export type Id2 = string;
export type SourceLabel = string | null;
export type Uncertain = boolean;
export type UncertaintyReason = string | null;
export type VisualCue = string;
/**
 * @maxItems 100
 */
export type Candidates = ImageCandidate[];
export type Category1 = string;
export type ObservationId = string;
export type Reason = string;
export type RegionId = string;
/**
 * @minItems 4
 * @maxItems 4
 */
export type SourceBox1 = [number, number, number, number];
/**
 * @maxItems 1200
 */
export type DeferredObservations = DeferredDetailObservation[];
/**
 * @maxItems 12
 */
export type MembershipChecks =
  | []
  | [DetailMembershipCheck]
  | [DetailMembershipCheck, DetailMembershipCheck]
  | [DetailMembershipCheck, DetailMembershipCheck, DetailMembershipCheck]
  | [DetailMembershipCheck, DetailMembershipCheck, DetailMembershipCheck, DetailMembershipCheck]
  | [DetailMembershipCheck, DetailMembershipCheck, DetailMembershipCheck, DetailMembershipCheck, DetailMembershipCheck]
  | [
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck
    ]
  | [
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck
    ]
  | [
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck
    ]
  | [
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck
    ]
  | [
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck
    ]
  | [
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck
    ]
  | [
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck,
      DetailMembershipCheck
    ];
export type Category2 = string;
/**
 * @minItems 1
 * @maxItems 64
 */
export type ObservationIds = [string, ...string[]];
export type Reason1 = string;
export type RegionId1 = string;
/**
 * @minItems 4
 * @maxItems 4
 */
export type SourceBox2 = [number, number, number, number];
export type Verdict = 'supported' | 'rejected' | 'ambiguous' | 'failed';
export type Mode1 = 'auto' | 'regions' | 'tiles';
export type CandidateId = string;
export type Clipped = boolean;
/**
 * @minItems 1
 * @maxItems 64
 */
export type ObservationIds1 = [string, ...string[]];
/**
 * @minItems 1
 * @maxItems 64
 */
export type RegionIds = [string, ...string[]];
/**
 * @maxItems 64
 */
export type SourceLabels = (string | null)[];
/**
 * @maxItems 100
 */
export type Observations = DetailObservation[];
export type ProviderCalls = number;
/**
 * @maxItems 12
 */
export type Regions =
  | []
  | [DetailRegion]
  | [DetailRegion, DetailRegion]
  | [DetailRegion, DetailRegion, DetailRegion]
  | [DetailRegion, DetailRegion, DetailRegion, DetailRegion]
  | [DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion]
  | [DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion]
  | [DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion]
  | [DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion, DetailRegion]
  | [
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion
    ]
  | [
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion
    ]
  | [
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion
    ]
  | [
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion,
      DetailRegion
    ];
export type CandidateCount = number;
export type Id3 = string;
export type InferenceSha2561 = string;
/**
 * @minItems 4
 * @maxItems 4
 */
export type SourceBox3 = [number, number, number, number];
export type Status = 'ok' | 'partial' | 'unreadable' | 'unsupported' | 'failed';
/**
 * @maxItems 12
 */
export type ReinspectionRegions =
  | []
  | [[number, number, number, number]]
  | [[number, number, number, number], [number, number, number, number]]
  | [[number, number, number, number], [number, number, number, number], [number, number, number, number]]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ];
export type ReusedCrops = number;
/**
 * @minItems 1
 * @maxItems 4
 */
export type SelectedRegions =
  | [[number, number, number, number]]
  | [[number, number, number, number], [number, number, number, number]]
  | [[number, number, number, number], [number, number, number, number], [number, number, number, number]]
  | [
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number],
      [number, number, number, number]
    ];
export type Selection = 'automatic' | 'explicit';
/**
 * @maxItems 20
 */
export type SelectionLimitations =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ];
/**
 * @maxItems 1200
 */
export type SupersededObservationIds = string[];
export type TargetKind = string;
export type InventoryCompleteness = 'unverified';
/**
 * @maxItems 100
 */
export type Limitations = string[];
export type CompletionTokens1 = number | null;
export type ElapsedMs1 = number;
export type PreparationCacheHit = boolean | null;
export type PreparationMs = number | null;
export type PromptTokens1 = number | null;
export type InputHeight1 = number;
export type InputWidth1 = number;
export type Mode2 = 'off' | 'original' | 'overview';
export type PipelineVersion = string | null;
export type PreparedId = string | null;
export type PromptVersion = string;
export type RequestedModel2 = string;
export type ReturnedModel1 = string;
export type RequestId3 = string;
export type SchemaVersion2 = '0.1.0';
export type Scope = 'submitted_image';
export type Status1 = 'ok' | 'partial' | 'unreadable' | 'unsupported';
export type SchemaVersion3 = '0.1.0';
export type Type = 'handoff' | 'result' | 'error';

export interface ImageCandidateStreamEvent {
  error?: ImageCandidateError | null;
  progress?: ImageCandidateProgress | null;
  result?: ImageCandidateResponse | null;
  schema_version?: SchemaVersion3;
  type: Type;
}
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
  source_box?: SourceBox;
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
/**
 * Actual analyzer dispatch, sent before waiting for candidate output.
 */
export interface ImageCandidateProgress {
  image: CandidateImage;
  question_sha256: QuestionSha2561;
  request_id: RequestId2;
  requested_model: RequestedModel1;
  schema_version?: SchemaVersion1;
}
/**
 * Image-bound proposals; an empty list does not establish a zero count.
 */
export interface ImageCandidateResponse {
  candidates?: Candidates;
  decision_trace?: ImageDecisionTrace | null;
  detail?: CandidateDetailTrace | null;
  image: CandidateImage;
  inventory_completeness?: InventoryCompleteness;
  limitations?: Limitations;
  metrics: CandidateMetrics;
  provenance: CandidateProvenance;
  request_id: RequestId3;
  schema_version?: SchemaVersion2;
  scope?: Scope;
  status: Status1;
}
/**
 * An unreviewed detection, not a canonical building entity or final claim.
 */
export interface ImageCandidate {
  category: Category;
  geometry: BoxShape;
  id: Id2;
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
export interface CandidateDetailTrace {
  deferred_observations?: DeferredObservations;
  membership_checks?: MembershipChecks;
  mode: Mode1;
  observations: Observations;
  provider_calls: ProviderCalls;
  regions: Regions;
  reinspection_regions?: ReinspectionRegions;
  reused_crops?: ReusedCrops;
  selected_regions: SelectedRegions;
  selection: Selection;
  selection_limitations?: SelectionLimitations;
  superseded_observation_ids?: SupersededObservationIds;
  target_kind?: TargetKind;
}
export interface DeferredDetailObservation {
  category: Category1;
  observation_id: ObservationId;
  reason: Reason;
  region_id: RegionId;
  source_box: SourceBox1;
}
export interface DetailMembershipCheck {
  category: Category2;
  observation_ids: ObservationIds;
  reason: Reason1;
  region_id: RegionId1;
  source_box: SourceBox2;
  verdict: Verdict;
}
export interface DetailObservation {
  candidate_id: CandidateId;
  clipped: Clipped;
  observation_ids: ObservationIds1;
  region_ids: RegionIds;
  source_labels?: SourceLabels;
}
export interface DetailRegion {
  candidate_count: CandidateCount;
  id: Id3;
  inference_sha256: InferenceSha2561;
  source_box: SourceBox3;
  status: Status;
}
export interface CandidateMetrics {
  completion_tokens?: CompletionTokens1;
  elapsed_ms: ElapsedMs1;
  preparation_cache_hit?: PreparationCacheHit;
  preparation_ms?: PreparationMs;
  prompt_tokens?: PromptTokens1;
}
export interface CandidateProvenance {
  preprocessing?: CandidatePreparation | null;
  prompt_version: PromptVersion;
  requested_model: RequestedModel2;
  returned_model: ReturnedModel1;
}
/**
 * Actual model image size, distinct from the unchanged display frame.
 */
export interface CandidatePreparation {
  input_height: InputHeight1;
  input_width: InputWidth1;
  mode: Mode2;
  pipeline_version?: PipelineVersion;
  prepared_id?: PreparedId;
}

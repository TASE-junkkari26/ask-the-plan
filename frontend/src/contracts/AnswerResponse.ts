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
export type Id1 = string;
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
export type Id2 = string;
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
export type RequestedModel1 = string;
export type ReturnedModel1 = string;
export type RequestId1 = string;
export type SchemaVersion = '0.1.0';
export type Scope = 'submitted_image';
export type Status1 = 'ok' | 'partial' | 'unreadable' | 'unsupported';
/**
 * @maxItems 16
 */
export type EvidenceContexts =
  | []
  | [AnswerEvidenceContext]
  | [AnswerEvidenceContext, AnswerEvidenceContext]
  | [AnswerEvidenceContext, AnswerEvidenceContext, AnswerEvidenceContext]
  | [AnswerEvidenceContext, AnswerEvidenceContext, AnswerEvidenceContext, AnswerEvidenceContext]
  | [AnswerEvidenceContext, AnswerEvidenceContext, AnswerEvidenceContext, AnswerEvidenceContext, AnswerEvidenceContext]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ]
  | [
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext,
      AnswerEvidenceContext
    ];
export type AssetId = string;
export type GeometryId = string | null;
export type Id4 = string;
export type Language = string | null;
export type Text = string;
export type ColumnIndex = number | null;
export type InstancePath = string[];
export type Kind1 =
  'ifc_guid' | 'step_id' | 'dxf_handle' | 'svg_id' | 'pdf_span' | 'table_cell' | 'image_region' | 'file_metadata';
export type PropertyPath = string[];
export type RowIndex = number | null;
export type Value1 = string;
export type ViewId = string | null;
export type Anchors = EvidenceAnchor[];
export type Kind2 = 'equivalent_representation' | 'rendered_from' | 'converted_from' | 'byte_duplicate';
export type AnchorIds = string[];
export type Method = 'native' | 'computed' | 'ocr' | 'detected' | 'inferred' | 'human';
export type RunId = string;
export type Score = number | null;
export type ScoreName = string | null;
export type SourceAssetId = string;
export type TargetAssetId = string;
export type AssetLinks = AssetLink[];
export type Attribution = string;
export type DocumentId = string;
export type Format = 'ifc' | 'dxf' | 'dwg' | 'pdf' | 'svg' | 'png' | 'jpeg' | 'other';
export type Id5 = string;
export type License = string;
export type MediaType = string;
export type Sha2561 = string;
export type SourceCollection = string;
export type Uri = string;
export type Assets = Asset[];
export type Id6 = string;
export type Method1 = 'native_units' | 'dimension' | 'scale_bar' | 'human';
export type TransformId = string;
export type ViewId1 = string;
export type Calibrations = Calibration[];
export type Definition = string;
export type Id7 = string;
export type Labels = LocalizedText[];
export type ParentIds = string[];
export type Concepts = Concept[];
export type CandidateEntityIds = string[];
export type Completeness = 'complete' | 'partial' | 'not_modeled' | 'not_extracted' | 'unknown';
export type ConceptIds = string[];
export type DistinctBy = 'canonical_entity_id';
export type Grain = 'logical_object' | 'occurrence' | 'assembly' | 'part' | 'schedule_row';
export type Hierarchy = 'all_matches' | 'topmost_matches' | 'leaves';
export type RuleKey = string;
export type ExaminedEntityIds = string[];
export type Explanation = string;
export type Id8 = string;
export type OperationKeys = string[];
export type PropertyKeys = string[];
/**
 * @minItems 1
 */
export type DocumentIds = [string, ...string[]];
export type EntityIds = string[];
export type ExactEntityIds = string[] | null;
export type ProjectId = string;
export type Universe =
  'source_records' | 'modeled_objects' | 'depicted_objects' | 'schedule_entries' | 'physical_building';
export type ViewIds = string[];
export type UnresolvedEntityIds = string[];
export type Coverage = Coverage1[];
export type Discipline = string | null;
export type Id9 = string;
export type LogicalKey = string;
export type ProjectId1 = string;
export type Revision = string;
export type SupersedesDocumentId = string | null;
export type Title = LocalizedText[];
export type Documents = Document[];
export type ConceptIds1 = string[];
export type DocumentId1 = string;
export type Id10 = string;
export type Kind3 =
  | 'site'
  | 'building'
  | 'storey'
  | 'unit'
  | 'space'
  | 'element'
  | 'assembly'
  | 'part'
  | 'type'
  | 'system'
  | 'material'
  | 'zone'
  | 'site_feature'
  | 'schedule_row';
export type Labels1 = LocalizedText[];
export type ProjectId2 = string;
export type Entities = Entity[];
export type Id11 = string;
export type OriginalPropertyPath = string[];
export type PropertyKey = string;
export type Status2 = 'present' | 'explicit_null' | 'not_in_source' | 'not_extracted' | 'unknown' | 'ambiguous';
export type SubjectId = string;
export type SupersedesFactId = string | null;
export type Value2 =
  | (
      | QuantityValue
      | CountValue
      | TextValue
      | BooleanValue
      | ReferencesValue
      | UnavailableValue
      | ListValue
      | RecordValue
      | TableValue
    )
  | null;
export type Basis = string;
export type Kind4 = 'quantity';
export type Magnitude = string;
export type Magnitude1 = string;
export type UnitId = string;
export type Quality = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
export type QuantityKind = string;
export type SourceText = string | null;
export type SourceValueType = string | null;
export type UnitAnchorIds = string[];
export type UnitId1 = string | null;
export type UnitResolution = 'explicit' | 'project_default' | 'calibrated' | 'derived' | 'unknown';
export type Kind5 = 'count';
export type Value3 = number;
export type Kind6 = 'text';
export type Kind7 = 'boolean';
export type Value4 = boolean;
export type EntityIds1 = string[];
export type Kind8 = 'references';
export type Explanation1 = string;
export type Kind9 = 'unavailable';
export type Reason2 = 'explicit_null' | 'not_in_source' | 'not_extracted' | 'unknown' | 'ambiguous';
/**
 * @minItems 1
 */
export type Columns = [TableColumn, ...TableColumn[]];
export type Key = string;
export type Kind10 = 'table';
export type Rows = {
  [k: string]:
    | QuantityValue
    | CountValue
    | TextValue
    | BooleanValue
    | ReferencesValue
    | UnavailableValue
    | ListValue
    | RecordValue
    | TableValue;
}[];
export type Kind11 = 'record';
export type Items = (
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue
)[];
export type Kind12 = 'list';
export type Facts = Fact[];
/**
 * @minItems 1
 */
export type AnchorIds1 = [string, ...string[]];
export type AssetId1 = string;
export type ColumnIndex1 = number | null;
export type ColumnSpan = number;
export type HeaderFeatureIds = string[];
export type Id12 = string;
export type Kind13 =
  'cad_primitive' | 'text_span' | 'detection' | 'segmentation' | 'table' | 'table_row' | 'table_cell' | 'other';
export type RowIndex1 = number | null;
export type RowSpan = number;
export type TableId = string | null;
export type ViewId2 = string | null;
export type Features = SourceFeature[];
export type AssetId2 = string;
/**
 * @minItems 2
 * @maxItems 3
 */
export type Axes = [string, string] | [string, string, string];
export type Crs = string | null;
export type Dimension = 2 | 3;
export type Id13 = string;
export type Space = 'presentation' | 'physical';
export type UnitId2 = string | null;
export type Frames = CoordinateFrame[];
export type FrameId = string;
export type Id14 = string;
export type Shape = PointShape | PolylineShape | MultiPolygonShape | BoxShape | MeshShape;
/**
 * @minItems 2
 * @maxItems 3
 */
export type Coordinates = [number, number] | [number, number, number];
export type Kind14 = 'point';
export type Closed = boolean;
/**
 * @minItems 2
 */
export type Coordinates1 = [
  [number, number] | [number, number, number],
  [number, number] | [number, number, number],
  ...([number, number] | [number, number, number])[]
];
export type Kind15 = 'polyline';
export type Kind16 = 'multipolygon';
/**
 * @minItems 1
 */
export type Polygons = [PolygonPart, ...PolygonPart[]];
export type Holes = [
  [number, number] | [number, number, number],
  [number, number] | [number, number, number],
  [number, number] | [number, number, number],
  [number, number] | [number, number, number],
  ...([number, number] | [number, number, number])[]
][];
/**
 * @minItems 4
 */
export type Shell = [
  [number, number] | [number, number, number],
  [number, number] | [number, number, number],
  [number, number] | [number, number, number],
  [number, number] | [number, number, number],
  ...([number, number] | [number, number, number])[]
];
export type Format1 = 'glb' | 'gltf' | 'obj' | 'other';
export type Kind17 = 'mesh';
export type Sha2562 = string;
export type Uri1 = string;
export type Geometries = Geometry[];
export type Id15 = string;
export type Name = string;
export type Projects = Project[];
export type Definition1 = string;
export type Dimension1 = [unknown, unknown, unknown, unknown, unknown, unknown, unknown] | null;
export type Key1 = string;
export type Labels2 = LocalizedText[];
export type QuantityKind1 = string | null;
export type ValueKind = 'text' | 'count' | 'quantity' | 'boolean' | 'references' | 'list' | 'record' | 'table';
export type Properties = PropertyDefinition[];
export type Id16 = string;
export type NativePredicate = string | null;
export type ObjectId = string;
export type Predicate =
  | 'contains'
  | 'aggregates'
  | 'typed_by'
  | 'assigned_to_system'
  | 'has_material'
  | 'belongs_to_unit'
  | 'adjacent_to'
  | 'connected_to'
  | 'hosted_by'
  | 'depicts'
  | 'same_as'
  | 'custom'
  | 'bounded_by'
  | 'has_opening'
  | 'filled_by'
  | 'assigned_to_zone'
  | 'corresponding_boundary'
  | 'external_boundary';
export type SubjectId1 = string;
export type Relations = Relation[];
export type AnchorIds2 = string[];
export type AssetId3 = string;
export type EntityId = string;
export type FeatureIds = string[];
export type GeometryIds = string[];
export type Id17 = string;
export type ViewId3 = string | null;
export type Representations = Representation[];
export type ConfigSha256 = string;
export type Id18 = string;
/**
 * @minItems 1
 */
export type InputAssetIds = [string, ...string[]];
export type ModelRevision = string | null;
export type OutputSchemaVersion = '0.1.0';
export type StartedAt = string;
export type Tool = string;
export type Version = string;
export type Runs = ExtractionRun[];
export type SchemaVersion1 = '0.1.0';
export type ConnectionGeometryStepId = number | null;
export type CorrespondingBoundaryId = string | null;
export type ElementId = string | null;
export type Id19 = string;
export type InternalOrExternal = string | null;
export type NativeStepId = number;
export type ParentBoundaryId = string | null;
export type PhysicalOrVirtual = string | null;
export type SpaceId = string;
export type SpaceBoundaries = IfcSpaceBoundary[];
export type FromFrameId = string;
export type Id20 = string;
export type Kind18 = 'affine' | 'homography' | 'projection';
export type Matrix = number[][];
export type ToFrameId = string;
export type Transforms = Transform[];
export type Dimension2 = [unknown, unknown, unknown, unknown, unknown, unknown, unknown] | null;
export type Id21 = string;
export type Kind19 = 'physical' | 'presentation';
export type SiMultiplier = string | null;
export type SiOffset = string;
export type Symbol = string;
export type Units = Unit[];
export type AssetId4 = string;
export type BoundaryGeometryId = string | null;
export type DepictsEntityIds = string[];
export type FrameId1 = string;
export type Id22 = string;
export type Kind20 =
  'page' | 'floor_plan' | 'section' | 'elevation' | 'detail' | 'site' | 'schedule' | 'legend' | 'tile' | 'unknown';
export type Labels3 = LocalizedText[];
export type PageIndex = number | null;
export type ParentViewId = string | null;
export type Views = View[];
export type Id23 = string;
export type DisplayHeight = number | null;
export type DisplaySha256 = string | null;
export type DisplayWidth = number | null;
export type LayoutName = string | null;
export type PageIndex1 = number | null;
export type Rotation = 0 | 90 | 180 | 270;
export type SourceBounds = [number, number, number, number] | null;
export type SourceRevision = string;
export type SourceSha256 = string;
export type ViewportTransform = [number, number, number, number, number, number] | null;
export type Anchors1 = EvidenceAnchor[];
export type Assets1 = Asset[];
export type Coverage2 = Coverage1[];
export type EntityId1 = string;
export type Guid = string | null;
export type IfcClass = string;
export type Name1 = string;
export type StepId = number | null;
export type ExcludedElements = IfcElement[];
export type ExtractionRuns = ExtractionRun[];
export type Facts1 = Fact[];
export type IncludedElements = IfcElement[];
export type Interpretation = string;
export type ModelId = string;
export type Id24 = string;
export type RequestId2 = string;
export type RequiredCapabilities = string[];
export type SchemaVersion2 = '0.1.0';
/**
 * @minItems 1
 */
export type Steps = [PlanStep, ...PlanStep[]];
export type Id25 = string;
export type Operation =
  | SelectOperation
  | TraverseOperation
  | AggregateOperation
  | SpatialQueryOperation
  | RelatedEntitiesOperation
  | ProjectOperation
  | RankOperation
  | MeasureOperation
  | ArithmeticOperation;
export type ConceptIds2 = string[];
export type EntityKinds = (
  | 'site'
  | 'building'
  | 'storey'
  | 'unit'
  | 'space'
  | 'element'
  | 'assembly'
  | 'part'
  | 'type'
  | 'system'
  | 'material'
  | 'zone'
  | 'site_feature'
  | 'schedule_row'
)[];
export type Exclude =
  (ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate) | null;
export type Key2 = string;
export type Kind21 = 'property' | 'label' | 'concept' | 'native_identifier' | 'entity_id' | 'result_column';
export type Kind22 = 'compare';
export type Operator = 'eq' | 'ne' | 'lt' | 'lte' | 'gt' | 'gte' | 'in' | 'contains';
export type Value5 =
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue;
export type Kind23 = 'field_present';
export type Direction = 'outgoing' | 'incoming';
/**
 * @minItems 1
 */
export type EntityIds2 = [string, ...string[]];
export type Kind24 = 'related_to';
export type Predicate1 = string;
export type GeometryId1 = string;
export type Kind25 = 'spatial';
export type Operator1 = 'intersects' | 'within' | 'contains' | 'touches' | 'disjoint' | 'near';
export type Kind26 = 'all' | 'any' | 'not';
/**
 * @minItems 1
 */
export type Operands = [
  ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate,
  ...(ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate)[]
];
export type Kind27 = 'select';
export type Where =
  (ComparePredicate | PresentPredicate | RelationPredicate | SpatialPredicate | BooleanPredicate) | null;
export type Direction1 = 'outgoing' | 'incoming';
export type InputStepId = string;
export type Kind28 = 'traverse';
export type MaxDepth = number;
export type Predicate2 = string;
export type Recursive = boolean;
export type GroupBy = FieldRef[];
export type InputStepId1 = string;
export type Kind29 = 'aggregate';
export type Method2 = 'count' | 'sum' | 'mean' | 'min' | 'max';
export type MissingValues = 'fail' | 'partial';
export type OutputUnitId = string | null;
export type ValueKey = string;
export type ContainerKind = 'space' | 'storey' | 'building' | 'site';
export type ExteriorBasis = 'combined' | 'classification' | 'boundary';
export type InputStepId2 = string;
export type Kind30 = 'spatial_query';
export type Method3 = 'native' | 'geometry' | 'auto';
export type Relation1 = 'containers' | 'boundary_neighbors' | 'door_connections' | 'outdoor_access' | 'exterior_doors';
export type ToleranceM = number;
export type Column = string;
export type InputStepId3 = string;
export type Kind31 = 'related_entities';
/**
 * @minItems 1
 */
export type Fields1 = [FieldRef, ...FieldRef[]];
export type InputStepId4 = string;
export type Kind32 = 'project';
export type Direction2 = 'ascending' | 'descending';
export type InputStepId5 = string;
export type Kind33 = 'rank';
export type Limit = number;
export type Basis1 = string;
export type CalibrationIds = string[];
export type InputStepId6 = string;
export type Kind34 = 'measure';
export type Metric = 'area' | 'union_area' | 'length' | 'perimeter' | 'volume' | 'distance' | 'angle';
export type OutputUnitId1 = string;
export type ReferenceEntityIds = string[];
/**
 * @minItems 2
 */
export type InputStepIds = [string, string, ...string[]];
export type Kind35 = 'arithmetic';
export type Operator2 = 'add' | 'subtract' | 'multiply' | 'divide';
export type OutputUnitId2 = string | null;
export type CompletionTokens2 = number | null;
export type DiscoveryVersion = string;
export type InspectionCount = number;
export type ModelRequests = number;
export type PromptTokens2 = number | null;
export type PromptVersion1 = string;
export type Provider = string;
export type RequestedModel2 = string;
export type ReturnedModel2 = string;
export type ThinkingLevel = string | null;
export type ThoughtTokens = number | null;
export type Properties1 = PropertyDefinition[];
export type Question = string;
export type RequestId3 = string;
export type AnchorIds3 = string[];
export type CalibrationIds1 = string[];
export type ExcludedSetId = string | null;
export type FactIds = string[];
export type Id26 = string;
export type IncludedSetId = string | null;
export type InputNodeIds = string[];
export type Operation1 =
  | 'select'
  | 'traverse'
  | 'spatial_query'
  | 'related_entities'
  | 'project'
  | 'rank'
  | 'count'
  | 'sum'
  | 'mean'
  | 'min'
  | 'max'
  | 'lookup'
  | 'convert_unit'
  | 'add'
  | 'subtract'
  | 'multiply'
  | 'divide'
  | 'measure'
  | 'group_by'
  | 'filter'
  | 'deduplicate';
export type Output =
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue;
export type PlanStepId = string | null;
export type Quality1 = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
export type RuleKey1 = string | null;
export type AnchorIds4 = string[];
export type Method4 = string;
export type RelatedIds = string[];
export type Relation2 = 'containers' | 'boundary_neighbors' | 'door_connections' | 'outdoor_access' | 'exterior_doors';
export type Status3 = 'verified' | 'candidate' | 'unavailable' | 'recorded_empty';
export type SubjectId2 = string;
export type ToleranceM1 = number | null;
export type SpatialEvidence = SpatialEvaluation[];
export type Calculations = CalculationNode[];
export type ConceptIds3 = string[];
/**
 * @minItems 1
 */
export type CoverageIds = [string, ...string[]];
/**
 * @minItems 1
 */
export type Evidence = [EvidenceBinding, ...EvidenceBinding[]];
export type AnchorIds5 = string[];
export type CalculationId = string;
export type EntitySetIds = string[];
export type EvidenceKind = 'verified' | 'candidate' | 'unavailable';
export type FactIds1 = string[];
export type ValuePath = string;
export type Id27 = string;
export type Name2 = string;
export type OutputKey = string;
export type PropertyKeys1 = string[];
export type Quality2 = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound';
export type Value6 =
  | QuantityValue
  | CountValue
  | TextValue
  | BooleanValue
  | ReferencesValue
  | UnavailableValue
  | ListValue
  | RecordValue
  | TableValue;
export type Claims = Claim[];
export type Count = number;
export type EntityIds3 = string[] | null;
export type Id28 = string;
export type MembersSha256 = string | null;
export type MembersUri = string | null;
export type EntitySets = EntitySet[];
export type ExecutorVersion = string;
export type Id29 = string;
export type AnchorIds6 = string[];
export type Code =
  | 'needs_clarification'
  | 'missing_source'
  | 'missing_information'
  | 'incomplete_coverage'
  | 'unsupported_operation'
  | 'conflicting_evidence'
  | 'insufficient_calibration'
  | 'execution_error';
export type EntityIds4 = string[];
export type FactIds2 = string[];
export type Options = LocalizedText[];
export type Issues = Issue[];
export type CacheHit = boolean;
export type CostAmount = string | null;
export type CostBasis = ('marginal' | 'amortized' | 'estimated') | null;
export type CostCurrency = string | null;
export type LatencyMs = number;
export type ModelInputTokens = number | null;
export type ModelOutputTokens = number | null;
export type PlanId = string | null;
export type RequestId4 = string;
export type SchemaVersion3 = '0.1.0';
export type Status4 =
  | 'answered'
  | 'partial'
  | 'needs_clarification'
  | 'missing_source'
  | 'missing_information'
  | 'incomplete_coverage'
  | 'unsupported_operation'
  | 'conflicting_evidence'
  | 'insufficient_calibration'
  | 'execution_error';
export type SchemaVersion4 = '0.1.0';
export type Scope2 = 'view' | 'model';
export type ScopeLabel = string;
export type SourceSha2561 = string;
export type Units1 = Unit[];
export type UnresolvedElements = IfcElement[];
export type Warnings = string[];
/**
 * @maxItems 100
 */
export type Ambiguities = string[];
export type Language1 = string;
/**
 * @minItems 1
 * @maxItems 16
 */
export type RequestedParts =
  | [AnswerRequestedPart]
  | [AnswerRequestedPart, AnswerRequestedPart]
  | [AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart]
  | [AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart]
  | [AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart, AnswerRequestedPart]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ]
  | [
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart,
      AnswerRequestedPart
    ];
/**
 * @maxItems 16
 */
export type DependsOn =
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
    ];
/**
 * @maxItems 100
 */
export type Exclusions = string[];
/**
 * @maxItems 100
 */
export type Filters = string[];
export type Key3 = string;
/**
 * @maxItems 100
 */
export type LiteralIdentifiers = string[];
export type Operation2 = string;
export type Question1 = string;
export type Target = string | null;
export type ScopeLabel1 = string;
export type CacheHit1 = boolean;
/**
 * @maxItems 15
 */
export type Calls1 =
  | []
  | [AnswerCall]
  | [AnswerCall, AnswerCall]
  | [AnswerCall, AnswerCall, AnswerCall]
  | [AnswerCall, AnswerCall, AnswerCall, AnswerCall]
  | [AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall]
  | [AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall]
  | [AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall]
  | [AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall]
  | [AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall, AnswerCall]
  | [
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall
    ]
  | [
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall
    ]
  | [
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall
    ]
  | [
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall
    ]
  | [
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall
    ]
  | [
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall,
      AnswerCall
    ];
export type CompletedAt1 = string | null;
export type CompletionTokens3 = number | null;
export type ElapsedMs2 = number;
export type Id30 = string;
export type InputSha2561 = string | null;
export type Outcome1 = 'completed' | 'failed' | 'cancelled';
export type PromptTokens3 = number | null;
export type Purpose1 =
  'planning' | 'routing' | 'analysis' | 'region_proposal' | 'candidate_verification' | 'reinspection' | 'wording';
export type RequestedModel3 = string;
export type ReturnedModel3 = string | null;
export type ThoughtTokens1 = number | null;
export type CostAmount1 = string | null;
export type CostBasis1 = ('marginal' | 'amortized' | 'estimated') | null;
export type CostCurrency1 = string | null;
export type ElapsedMs3 = number;
export type ExternalAttempts = number;
export type ModelInputTokens1 = number | null;
export type ModelOutputTokens1 = number | null;
export type AnchorIds7 = string[];
export type ClaimIds = string[];
export type Id31 = string;
export type Kind36 = 'claim' | 'issue';
export type PartKey = string;
export type Qualification = 'exact' | 'estimated' | 'lower_bound' | 'upper_bound' | 'unavailable';
export type Text1 = string;
export type ValuePaths = string[];
export type Narrative = AnswerSentence[];
/**
 * @minItems 1
 * @maxItems 16
 */
export type Parts =
  | [AnswerPart]
  | [AnswerPart, AnswerPart]
  | [AnswerPart, AnswerPart, AnswerPart]
  | [AnswerPart, AnswerPart, AnswerPart, AnswerPart]
  | [AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart]
  | [AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart]
  | [AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart]
  | [AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart]
  | [AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart, AnswerPart]
  | [
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart
    ]
  | [
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart
    ]
  | [
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart
    ]
  | [
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart
    ]
  | [
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart
    ]
  | [
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart
    ]
  | [
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart,
      AnswerPart
    ];
/**
 * @maxItems 16
 */
export type DependsOn1 =
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
    ];
export type EvidenceContextId = string | null;
export type Key4 = string;
export type Status5 =
  | 'answered'
  | 'partial'
  | 'needs_clarification'
  | 'missing_source'
  | 'missing_information'
  | 'incomplete_coverage'
  | 'unsupported_operation'
  | 'conflicting_evidence'
  | 'insufficient_calibration'
  | 'execution_error'
  | 'blocked';
export type Question2 = string;
export type QuestionSha2561 = string;
export type RequestId5 = string;
export type SchemaVersion5 = '0.1.0';
export type DisplayHeight1 = number | null;
export type DisplaySha2561 = string | null;
export type DisplayWidth1 = number | null;
export type Kind37 = 'image' | 'pdf' | 'svg' | 'dxf' | 'ifc';
export type LayoutName1 = string | null;
export type PageIndex2 = number | null;
export type Rotation1 = 0 | 90 | 180 | 270;
export type ScopeLabel2 = string;
export type SourceBounds1 = [number, number, number, number] | null;
export type SourceId = string;
export type SourceRevision1 = string;
export type SourceSha2562 = string;
export type ViewportTransform1 = [number, number, number, number, number, number] | null;

export interface AnswerResponse {
  candidate_response?: ImageCandidateResponse | null;
  evidence_contexts?: EvidenceContexts;
  ifc_response?: IfcQuestionResponse | null;
  interpretation: AnswerIntent;
  metrics: AnswerMetrics;
  narrative?: Narrative;
  parts: Parts;
  question: Question2;
  question_sha256: QuestionSha2561;
  request_id: RequestId5;
  schema_version?: SchemaVersion5;
  source: AnswerSourceBinding;
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
  request_id: RequestId1;
  schema_version?: SchemaVersion;
  scope?: Scope;
  status: Status1;
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
  id: Id1;
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
  id: Id2;
  parent_id?: ParentId;
  probability?: Probability;
  reason_code: ReasonCode;
  state: State;
  threshold?: Threshold;
  value?: Value;
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
  requested_model: RequestedModel1;
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
export interface AnswerEvidenceContext {
  bundle: KnowledgeBundle;
  id: Id23;
  source_snapshot?: AnswerSnapshot | null;
}
export interface KnowledgeBundle {
  anchors?: Anchors;
  asset_links?: AssetLinks;
  assets: Assets;
  calibrations?: Calibrations;
  concepts: Concepts;
  coverage?: Coverage;
  documents: Documents;
  entities?: Entities;
  facts?: Facts;
  features?: Features;
  frames?: Frames;
  geometries?: Geometries;
  projects: Projects;
  properties: Properties;
  relations?: Relations;
  representations?: Representations;
  runs: Runs;
  schema_version?: SchemaVersion1;
  space_boundaries?: SpaceBoundaries;
  transforms?: Transforms;
  units: Units;
  views?: Views;
}
export interface EvidenceAnchor {
  asset_id: AssetId;
  geometry_id?: GeometryId;
  id: Id4;
  quote?: LocalizedText | null;
  selector: NativeSelector;
  view_id?: ViewId;
}
export interface LocalizedText {
  language?: Language;
  text: Text;
}
export interface NativeSelector {
  column_index?: ColumnIndex;
  instance_path?: InstancePath;
  kind: Kind1;
  property_path?: PropertyPath;
  row_index?: RowIndex;
  value: Value1;
}
export interface AssetLink {
  kind: Kind2;
  provenance: Provenance;
  source_asset_id: SourceAssetId;
  target_asset_id: TargetAssetId;
}
export interface Provenance {
  anchor_ids?: AnchorIds;
  method: Method;
  run_id: RunId;
  score?: Score;
  score_name?: ScoreName;
}
export interface Asset {
  attribution: Attribution;
  document_id: DocumentId;
  format: Format;
  id: Id5;
  license: License;
  media_type: MediaType;
  sha256: Sha2561;
  source_collection: SourceCollection;
  uri: Uri;
}
export interface Calibration {
  id: Id6;
  method: Method1;
  provenance: Provenance;
  transform_id: TransformId;
  view_id: ViewId1;
}
export interface Concept {
  definition: Definition;
  id: Id7;
  labels: Labels;
  parent_ids?: ParentIds;
}
export interface Coverage1 {
  candidate_entity_ids?: CandidateEntityIds;
  completeness: Completeness;
  concept_ids: ConceptIds;
  count_policy?: CountPolicy | null;
  examined_entity_ids?: ExaminedEntityIds;
  explanation: Explanation;
  id: Id8;
  operation_keys?: OperationKeys;
  property_keys?: PropertyKeys;
  provenance: Provenance;
  scope: Scope1;
  unresolved_entity_ids?: UnresolvedEntityIds;
}
export interface CountPolicy {
  distinct_by?: DistinctBy;
  grain: Grain;
  hierarchy: Hierarchy;
  rule_key: RuleKey;
}
export interface Scope1 {
  document_ids: DocumentIds;
  entity_ids?: EntityIds;
  exact_entity_ids?: ExactEntityIds;
  project_id: ProjectId;
  universe: Universe;
  view_ids?: ViewIds;
}
export interface Document {
  discipline?: Discipline;
  id: Id9;
  logical_key: LogicalKey;
  project_id: ProjectId1;
  revision: Revision;
  supersedes_document_id?: SupersedesDocumentId;
  title?: Title;
}
export interface Entity {
  concept_ids: ConceptIds1;
  document_id: DocumentId1;
  id: Id10;
  kind: Kind3;
  labels?: Labels1;
  project_id: ProjectId2;
  provenance: Provenance;
}
export interface Fact {
  id: Id11;
  original_property_path?: OriginalPropertyPath;
  property_key: PropertyKey;
  provenance: Provenance;
  status: Status2;
  subject_id: SubjectId;
  supersedes_fact_id?: SupersedesFactId;
  value?: Value2;
}
export interface QuantityValue {
  basis: Basis;
  kind: Kind4;
  magnitude: Magnitude;
  normalized?: NormalizedQuantity | null;
  quality?: Quality;
  quantity_kind: QuantityKind;
  source_text?: SourceText;
  source_value_type?: SourceValueType;
  unit_anchor_ids?: UnitAnchorIds;
  unit_id: UnitId1;
  unit_resolution: UnitResolution;
}
export interface NormalizedQuantity {
  magnitude: Magnitude1;
  unit_id: UnitId;
}
export interface CountValue {
  kind: Kind5;
  value: Value3;
}
export interface TextValue {
  kind: Kind6;
  value: LocalizedText;
}
export interface BooleanValue {
  kind: Kind7;
  value: Value4;
}
export interface ReferencesValue {
  entity_ids: EntityIds1;
  kind: Kind8;
}
/**
 * A missing cell in a partial list/record/table; never a numeric zero.
 */
export interface UnavailableValue {
  explanation: Explanation1;
  kind: Kind9;
  reason: Reason2;
}
export interface ListValue {
  items: Items;
  kind: Kind12;
}
export interface RecordValue {
  fields: Fields;
  kind: Kind11;
}
export interface Fields {
  [k: string]:
    | QuantityValue
    | CountValue
    | TextValue
    | BooleanValue
    | ReferencesValue
    | UnavailableValue
    | ListValue
    | RecordValue
    | TableValue;
}
export interface TableValue {
  columns: Columns;
  kind: Kind10;
  rows: Rows;
}
export interface TableColumn {
  key: Key;
  label: LocalizedText;
}
export interface SourceFeature {
  anchor_ids: AnchorIds1;
  asset_id: AssetId1;
  column_index?: ColumnIndex1;
  column_span?: ColumnSpan;
  header_feature_ids?: HeaderFeatureIds;
  id: Id12;
  kind: Kind13;
  provenance: Provenance;
  row_index?: RowIndex1;
  row_span?: RowSpan;
  table_id?: TableId;
  text?: LocalizedText | null;
  view_id?: ViewId2;
}
export interface CoordinateFrame {
  asset_id: AssetId2;
  axes: Axes;
  crs?: Crs;
  dimension: Dimension;
  id: Id13;
  space: Space;
  unit_id?: UnitId2;
}
export interface Geometry {
  frame_id: FrameId;
  id: Id14;
  shape: Shape;
}
export interface PointShape {
  coordinates: Coordinates;
  kind: Kind14;
}
export interface PolylineShape {
  closed?: Closed;
  coordinates: Coordinates1;
  kind: Kind15;
}
export interface MultiPolygonShape {
  kind: Kind16;
  polygons: Polygons;
}
export interface PolygonPart {
  holes?: Holes;
  shell: Shell;
}
export interface MeshShape {
  format: Format1;
  kind: Kind17;
  sha256: Sha2562;
  uri: Uri1;
}
export interface Project {
  id: Id15;
  name: Name;
}
export interface PropertyDefinition {
  definition: Definition1;
  dimension?: Dimension1;
  key: Key1;
  labels: Labels2;
  quantity_kind?: QuantityKind1;
  value_kind: ValueKind;
}
export interface Relation {
  id: Id16;
  native_predicate?: NativePredicate;
  object_id: ObjectId;
  predicate: Predicate;
  provenance: Provenance;
  subject_id: SubjectId1;
}
export interface Representation {
  anchor_ids?: AnchorIds2;
  asset_id: AssetId3;
  entity_id: EntityId;
  feature_ids?: FeatureIds;
  geometry_ids?: GeometryIds;
  id: Id17;
  provenance: Provenance;
  view_id?: ViewId3;
}
export interface ExtractionRun {
  config_sha256: ConfigSha256;
  id: Id18;
  input_asset_ids: InputAssetIds;
  model_revision?: ModelRevision;
  output_schema_version?: OutputSchemaVersion;
  started_at: StartedAt;
  tool: Tool;
  version: Version;
}
/**
 * A source boundary record, including unusable and virtual boundaries.
 */
export interface IfcSpaceBoundary {
  connection_geometry_step_id?: ConnectionGeometryStepId;
  corresponding_boundary_id?: CorrespondingBoundaryId;
  element_id?: ElementId;
  id: Id19;
  internal_or_external: InternalOrExternal;
  native_step_id: NativeStepId;
  parent_boundary_id?: ParentBoundaryId;
  physical_or_virtual: PhysicalOrVirtual;
  provenance: Provenance;
  space_id: SpaceId;
}
export interface Transform {
  from_frame_id: FromFrameId;
  id: Id20;
  kind: Kind18;
  matrix: Matrix;
  provenance: Provenance;
  to_frame_id: ToFrameId;
}
export interface Unit {
  dimension?: Dimension2;
  id: Id21;
  kind: Kind19;
  si_multiplier?: SiMultiplier;
  si_offset?: SiOffset;
  symbol: Symbol;
}
export interface View {
  asset_id: AssetId4;
  boundary_geometry_id?: BoundaryGeometryId;
  depicts_entity_ids?: DepictsEntityIds;
  frame_id: FrameId1;
  id: Id22;
  kind: Kind20;
  labels?: Labels3;
  page_index?: PageIndex;
  parent_view_id?: ParentViewId;
}
export interface AnswerSnapshot {
  display_height?: DisplayHeight;
  display_sha256?: DisplaySha256;
  display_width?: DisplayWidth;
  layout_name?: LayoutName;
  page_index?: PageIndex1;
  rotation?: Rotation;
  source_bounds?: SourceBounds;
  source_revision: SourceRevision;
  source_sha256: SourceSha256;
  viewport_transform?: ViewportTransform;
}
export interface IfcQuestionResponse {
  anchors?: Anchors1;
  assets?: Assets1;
  coverage?: Coverage2;
  excluded_elements?: ExcludedElements;
  extraction_runs?: ExtractionRuns;
  facts?: Facts1;
  included_elements?: IncludedElements;
  interpretation: Interpretation;
  model_id: ModelId;
  plan?: QueryPlan | null;
  planning?: IfcPlanningProvenance | null;
  properties?: Properties1;
  question: Question;
  request_id: RequestId3;
  result: QueryResult;
  schema_version?: SchemaVersion4;
  scope: Scope2;
  scope_label: ScopeLabel;
  source_sha256: SourceSha2561;
  units?: Units1;
  unresolved_elements?: UnresolvedElements;
  warnings?: Warnings;
}
/**
 * Canonical entity and its original product locators for viewer verification.
 */
export interface IfcElement {
  entity_id: EntityId1;
  guid?: Guid;
  ifc_class: IfcClass;
  name: Name1;
  step_id?: StepId;
}
export interface QueryPlan {
  id: Id24;
  outputs: Outputs;
  request_id: RequestId2;
  required_capabilities?: RequiredCapabilities;
  schema_version?: SchemaVersion2;
  scope: Scope1;
  steps: Steps;
}
export interface Outputs {
  [k: string]: string;
}
export interface PlanStep {
  id: Id25;
  operation: Operation;
}
export interface SelectOperation {
  concept_ids: ConceptIds2;
  count_policy: CountPolicy;
  entity_kinds?: EntityKinds;
  exclude?: Exclude;
  kind: Kind27;
  where?: Where;
}
export interface ComparePredicate {
  field: FieldRef;
  kind: Kind22;
  operator: Operator;
  value: Value5;
}
export interface FieldRef {
  key: Key2;
  kind: Kind21;
}
export interface PresentPredicate {
  field: FieldRef;
  kind: Kind23;
}
export interface RelationPredicate {
  direction: Direction;
  entity_ids: EntityIds2;
  kind: Kind24;
  predicate: Predicate1;
}
export interface SpatialPredicate {
  distance?: QuantityValue | null;
  geometry_id: GeometryId1;
  kind: Kind25;
  operator: Operator1;
}
export interface BooleanPredicate {
  kind: Kind26;
  operands: Operands;
}
export interface TraverseOperation {
  direction: Direction1;
  input_step_id: InputStepId;
  kind: Kind28;
  max_depth?: MaxDepth;
  predicate: Predicate2;
  recursive?: Recursive;
}
export interface AggregateOperation {
  field?: FieldRef | null;
  group_by?: GroupBy;
  input_step_id: InputStepId1;
  kind: Kind29;
  method: Method2;
  missing_values?: MissingValues;
  output_unit_id?: OutputUnitId;
  value_key?: ValueKey;
}
/**
 * Bounded IFC topology and supported source-geometry checks.
 */
export interface SpatialQueryOperation {
  container_kind?: ContainerKind;
  exterior_basis?: ExteriorBasis;
  input_step_id: InputStepId2;
  kind: Kind30;
  method?: Method3;
  relation: Relation1;
  tolerance_m?: ToleranceM;
}
/**
 * Deduplicate references from one table column at occurrence grain.
 */
export interface RelatedEntitiesOperation {
  column?: Column;
  input_step_id: InputStepId3;
  kind: Kind31;
}
export interface ProjectOperation {
  fields: Fields1;
  input_step_id: InputStepId4;
  kind: Kind32;
}
export interface RankOperation {
  direction: Direction2;
  field: FieldRef;
  input_step_id: InputStepId5;
  kind: Kind33;
  limit: Limit;
}
export interface MeasureOperation {
  basis: Basis1;
  calibration_ids?: CalibrationIds;
  input_step_id: InputStepId6;
  kind: Kind34;
  metric: Metric;
  output_unit_id: OutputUnitId1;
  reference_entity_ids?: ReferenceEntityIds;
}
export interface ArithmeticOperation {
  input_step_ids: InputStepIds;
  kind: Kind35;
  operator: Operator2;
  output_unit_id?: OutputUnitId2;
}
export interface IfcPlanningProvenance {
  completion_tokens?: CompletionTokens2;
  discovery_version: DiscoveryVersion;
  inspection_count: InspectionCount;
  model_requests: ModelRequests;
  prompt_tokens?: PromptTokens2;
  prompt_version: PromptVersion1;
  provider: Provider;
  requested_model: RequestedModel2;
  returned_model: ReturnedModel2;
  thinking_level?: ThinkingLevel;
  thought_tokens?: ThoughtTokens;
}
export interface QueryResult {
  calculations?: Calculations;
  claims?: Claims;
  entity_sets?: EntitySets;
  executor_version: ExecutorVersion;
  explanation?: LocalizedText | null;
  id: Id29;
  issues?: Issues;
  metrics?: ExecutionMetrics | null;
  plan_id?: PlanId;
  request_id: RequestId4;
  schema_version?: SchemaVersion3;
  status: Status4;
}
export interface CalculationNode {
  anchor_ids?: AnchorIds3;
  calibration_ids?: CalibrationIds1;
  excluded_set_id?: ExcludedSetId;
  fact_ids?: FactIds;
  id: Id26;
  included_set_id?: IncludedSetId;
  input_node_ids?: InputNodeIds;
  operation: Operation1;
  output: Output;
  plan_step_id?: PlanStepId;
  quality: Quality1;
  rule_key?: RuleKey1;
  spatial_evidence?: SpatialEvidence;
}
/**
 * Machine-readable support and unresolved inputs for one spatial subject.
 */
export interface SpatialEvaluation {
  anchor_ids?: AnchorIds4;
  metadata?: Metadata;
  method: Method4;
  related_ids?: RelatedIds;
  relation: Relation2;
  status: Status3;
  subject_id: SubjectId2;
  tolerance_m?: ToleranceM1;
}
export interface Metadata {
  [k: string]: unknown;
}
export interface Claim {
  concept_ids: ConceptIds3;
  count_policy?: CountPolicy | null;
  coverage_ids: CoverageIds;
  evidence: Evidence;
  id: Id27;
  name: Name2;
  output_key: OutputKey;
  property_keys?: PropertyKeys1;
  quality: Quality2;
  scope: Scope1;
  value: Value6;
}
export interface EvidenceBinding {
  anchor_ids?: AnchorIds5;
  calculation_id: CalculationId;
  entity_set_ids?: EntitySetIds;
  evidence_kind?: EvidenceKind;
  fact_ids?: FactIds1;
  value_path?: ValuePath;
}
export interface EntitySet {
  count: Count;
  count_policy: CountPolicy;
  entity_ids?: EntityIds3;
  id: Id28;
  members_sha256?: MembersSha256;
  members_uri?: MembersUri;
  scope: Scope1;
}
export interface Issue {
  anchor_ids?: AnchorIds6;
  code: Code;
  entity_ids?: EntityIds4;
  fact_ids?: FactIds2;
  message: LocalizedText;
  options?: Options;
}
export interface ExecutionMetrics {
  cache_hit?: CacheHit;
  cost_amount?: CostAmount;
  cost_basis?: CostBasis;
  cost_currency?: CostCurrency;
  latency_ms: LatencyMs;
  model_input_tokens?: ModelInputTokens;
  model_output_tokens?: ModelOutputTokens;
}
export interface AnswerIntent {
  ambiguities?: Ambiguities;
  language?: Language1;
  requested_parts: RequestedParts;
  scope_label: ScopeLabel1;
}
export interface AnswerRequestedPart {
  depends_on?: DependsOn;
  exclusions?: Exclusions;
  filters?: Filters;
  key: Key3;
  literal_identifiers?: LiteralIdentifiers;
  operation?: Operation2;
  question: Question1;
  target?: Target;
}
export interface AnswerMetrics {
  cache_hit?: CacheHit1;
  calls?: Calls1;
  cost_amount?: CostAmount1;
  cost_basis?: CostBasis1;
  cost_currency?: CostCurrency1;
  elapsed_ms: ElapsedMs3;
  external_attempts?: ExternalAttempts;
  model_input_tokens?: ModelInputTokens1;
  model_output_tokens?: ModelOutputTokens1;
}
export interface AnswerCall {
  completed_at?: CompletedAt1;
  completion_tokens?: CompletionTokens3;
  elapsed_ms?: ElapsedMs2;
  id: Id30;
  input_sha256?: InputSha2561;
  outcome: Outcome1;
  prompt_tokens?: PromptTokens3;
  purpose: Purpose1;
  requested_model: RequestedModel3;
  returned_model?: ReturnedModel3;
  thought_tokens?: ThoughtTokens1;
}
export interface AnswerSentence {
  anchor_ids?: AnchorIds7;
  claim_ids?: ClaimIds;
  id: Id31;
  kind: Kind36;
  part_key: PartKey;
  qualification: Qualification;
  text: Text1;
  value_paths?: ValuePaths;
}
export interface AnswerPart {
  depends_on?: DependsOn1;
  evidence_context_id?: EvidenceContextId;
  key: Key4;
  message?: LocalizedText | null;
  plan?: QueryPlan | null;
  result?: QueryResult | null;
  status: Status5;
}
export interface AnswerSourceBinding {
  display_height?: DisplayHeight1;
  display_sha256?: DisplaySha2561;
  display_width?: DisplayWidth1;
  kind: Kind37;
  layout_name?: LayoutName1;
  page_index?: PageIndex2;
  rotation?: Rotation1;
  scope_label: ScopeLabel2;
  source_bounds?: SourceBounds1;
  source_id: SourceId;
  source_revision: SourceRevision1;
  source_sha256: SourceSha2562;
  viewport_transform?: ViewportTransform1;
}

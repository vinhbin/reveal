export type ReviewStatus = 'pending' | 'analyzing' | 'completed' | 'failed';
export type DecisionStatus = 'unreviewed' | 'accepted' | 'dismissed' | 'intentional';
export type EvidenceOrigin = 'model_inference' | 'dialogue' | 'filmmaker_intent' | 'human_verification';
export type UncertaintyLevel = 'low' | 'medium' | 'high';

export interface SeekRequest {
  time: number;
  nonce: number;
}

export interface Cue {
  id: string;
  review_id: string;
  index: number;
  start_time: string;
  end_time: string;
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface Finding {
  id: string;
  review_id: string;
  cue_id: string;
  cue_index: number;
  candidate_name: string;
  issue_description: string;
  proposed_text: string;
  edited_proposal: string;
  previous_accepted_text?: string;
  needs_re_review?: boolean;
  evidence_origin: EvidenceOrigin;
  interval_start: number;
  interval_end: number;
  uncertainty: UncertaintyLevel;
  status: DecisionStatus;
  created_at: string;
  updated_at: string;
}

export interface Review {
  id: string;
  title: string;
  video_filename: string;
  srt_filename: string;
  intent_notes?: string;
  status: ReviewStatus;
  error_message?: string;
  model_used?: string;
  created_at: string;
  updated_at: string;
  cues: Cue[];
  findings: Finding[];
}

export interface ReviewSummary {
  id: string;
  title: string;
  video_filename: string;
  srt_filename: string;
  status: ReviewStatus;
  cue_count: number;
  finding_count: number;
  unreviewed_count: number;
  created_at: string;
  updated_at: string;
}

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, field_validator
from backend.models import ReviewStatus, DecisionStatus, EvidenceOrigin, UncertaintyLevel

class CueSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    index: int
    start_time: str
    end_time: str
    start_seconds: float
    end_seconds: float
    text: str

class FindingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    cue_id: str
    cue_index: int
    candidate_name: str
    issue_description: str
    proposed_text: str
    edited_proposal: Optional[str] = ""
    previous_accepted_text: Optional[str] = None
    needs_re_review: bool = False
    evidence_origin: EvidenceOrigin
    interval_start: float
    interval_end: float
    uncertainty: UncertaintyLevel
    status: DecisionStatus
    created_at: datetime
    updated_at: datetime

    @field_validator("needs_re_review", mode="before")
    @classmethod
    def coerce_needs_re_review(cls, v: Any) -> bool:
        return bool(v) if v is not None else False

class FindingUpdateSchema(BaseModel):
    status: Optional[DecisionStatus] = None
    edited_proposal: Optional[str] = None

class ReviewSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    video_filename: str
    srt_filename: str
    intent_notes: Optional[str] = ""
    status: ReviewStatus
    error_message: Optional[str] = ""
    model_used: Optional[str] = ""
    created_at: datetime
    updated_at: datetime
    cues: List[CueSchema] = []
    findings: List[FindingSchema] = []

class ReviewSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    video_filename: str
    srt_filename: str
    status: ReviewStatus
    cue_count: int
    finding_count: int
    unreviewed_count: int
    created_at: datetime
    updated_at: datetime

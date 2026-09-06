import enum
from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Integer, Float, Text, Enum as SQLEnum, ForeignKey, DateTime, LargeBinary, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"

class DecisionStatus(str, enum.Enum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    INTENTIONAL = "intentional"

class EvidenceOrigin(str, enum.Enum):
    MODEL_INFERENCE = "model_inference"
    DIALOGUE = "dialogue"
    FILMMAKER_INTENT = "filmmaker_intent"
    HUMAN_VERIFICATION = "human_verification"

class UncertaintyLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    video_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    video_path: Mapped[str] = mapped_column(String(512), nullable=False)
    srt_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    srt_content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_srt_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    media_duration: Mapped[float] = mapped_column(Float, nullable=True, default=None)
    intent_notes: Mapped[str] = mapped_column(Text, nullable=True, default="")
    status: Mapped[ReviewStatus] = mapped_column(SQLEnum(ReviewStatus), default=ReviewStatus.PENDING)
    error_message: Mapped[str] = mapped_column(Text, nullable=True, default="")
    model_used: Mapped[str] = mapped_column(String(100), nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    cues: Mapped[list["Cue"]] = relationship("Cue", back_populates="review", cascade="all, delete-orphan", order_by="Cue.index")
    findings: Mapped[list["Finding"]] = relationship("Finding", back_populates="review", cascade="all, delete-orphan")

class Cue(Base):
    __tablename__ = "cues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(20), nullable=False)
    end_time: Mapped[str] = mapped_column(String(20), nullable=False)
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_block: Mapped[str] = mapped_column(Text, nullable=True, default="")
    start_byte: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    end_byte: Mapped[int] = mapped_column(Integer, nullable=True, default=0)

    review: Mapped["Review"] = relationship("Review", back_populates="cues")
    findings: Mapped[list["Finding"]] = relationship("Finding", back_populates="cue", cascade="all, delete-orphan")

class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    cue_id: Mapped[str] = mapped_column(String(36), ForeignKey("cues.id", ondelete="CASCADE"), nullable=False)
    cue_index: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issue_description: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_proposal: Mapped[str] = mapped_column(Text, nullable=True, default="")
    previous_accepted_text: Mapped[str] = mapped_column(Text, nullable=True, default=None)
    needs_re_review: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_origin: Mapped[EvidenceOrigin] = mapped_column(SQLEnum(EvidenceOrigin), default=EvidenceOrigin.MODEL_INFERENCE)
    interval_start: Mapped[float] = mapped_column(Float, nullable=False)
    interval_end: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty: Mapped[UncertaintyLevel] = mapped_column(SQLEnum(UncertaintyLevel), default=UncertaintyLevel.MEDIUM)
    status: Mapped[DecisionStatus] = mapped_column(SQLEnum(DecisionStatus), default=DecisionStatus.UNREVIEWED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    review: Mapped["Review"] = relationship("Review", back_populates="findings")
    cue: Mapped["Cue"] = relationship("Cue", back_populates="findings")

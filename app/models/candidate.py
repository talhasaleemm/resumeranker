"""
app/models/candidate.py — ORM models for Candidate and CandidateSkill.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    ARRAY,
    JSON,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Original extracted text — stored for auditability
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full structured profile: skills, education, experience, projects, certifications
    structured_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Auto-tags: e.g. ["backend", "AI/ML"]
    profile_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True, default=list
    )

    # Source file metadata
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_filetype: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "pdf" | "docx"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    candidate_skills: Mapped[list["CandidateSkill"]] = relationship(
        "CandidateSkill", back_populates="candidate", cascade="all, delete-orphan"
    )
    match_results: Mapped[list["MatchResult"]] = relationship(  # type: ignore[name-defined]
        "MatchResult", back_populates="candidate", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} name={self.name!r}>"


class CandidateSkill(Base):
    """
    Join table between Candidate and Skill with extraction metadata.
    Stores confidence and the source sentence so every skill claim is traceable.
    """
    __tablename__ = "candidate_skills"
    __table_args__ = (
        UniqueConstraint("candidate_id", "skill_id", name="uq_candidate_skill"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    # The sentence/phrase from which this skill was extracted
    source_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="candidate_skills")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="candidate_skills")  # type: ignore[name-defined]

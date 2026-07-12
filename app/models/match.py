"""
app/models/match.py — ORM model for MatchResult (candidate ↔ job ranking).

Every score is fully explainable via explanation_log (JSONB).
Example explanation_log structure:
{
  "tfidf_score": 0.72,
  "bm25_score": 0.68,
  "skill_overlap_score": 0.80,
  "final_score": 0.724,
  "weights": {"tfidf": 0.4, "bm25": 0.4, "skill": 0.2},
  "matched_required_skills": ["Python", "FastAPI", "PostgreSQL"],
  "matched_preferred_skills": ["Docker", "Redis"],
  "missing_required_skills": ["Kubernetes"],
  "candidate_profile_tags": ["backend", "AI/ML"],
  "top_tfidf_terms": ["python", "api", "database"],
  "explanation_text": "Candidate matched 3/4 required skills and 2/3 preferred skills..."
}
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Individual component scores (stored for auditability)
    tfidf_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bm25_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    skill_overlap_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Weighted composite score
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)

    # Full explanation: which fields, weights, matched skills produced this score
    explanation_log: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Human-readable summary of the match
    explanation_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    candidate: Mapped["Candidate"] = relationship(  # type: ignore[name-defined]
        "Candidate", back_populates="match_results"
    )
    job: Mapped["Job"] = relationship(  # type: ignore[name-defined]
        "Job", back_populates="match_results"
    )

    def __repr__(self) -> str:
        return f"<MatchResult candidate={self.candidate_id} job={self.job_id} score={self.final_score:.3f}>"

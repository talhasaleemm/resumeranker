"""
app/models/match.py — ORM model for MatchResult (candidate ↔ job ranking).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Append-only history uses RESTRICT delete
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Individual component scores (stored for auditability)
    tfidf_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bm25_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    skill_overlap_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Weighted composite score
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Immutable snapshot data
    weights_used: Mapped[dict] = mapped_column(JSONB, nullable=False)
    explanation_log: Mapped[dict] = mapped_column(JSONB, nullable=False)

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

    __table_args__ = (
        CheckConstraint(
            "final_score >= 0.0 AND final_score <= 100.0", name="chk_final_score_bounds"
        ),
        CheckConstraint(
            "tfidf_score >= 0.0 AND tfidf_score <= 1.0", name="chk_tfidf_score_bounds"
        ),
        CheckConstraint(
            "bm25_score >= 0.0 AND bm25_score <= 1.0", name="chk_bm25_score_bounds"
        ),
        CheckConstraint(
            "skill_overlap_score >= 0.0 AND skill_overlap_score <= 1.0",
            name="chk_skill_overlap_score_bounds",
        ),
    )

    def __repr__(self) -> str:
        return f"<MatchResult candidate={self.candidate_id} job={self.job_id} score={self.final_score:.3f}>"

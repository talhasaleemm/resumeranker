"""
app/models/candidate.py — ORM models for Candidate.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    raw_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Original extracted text — stored for auditability
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full structured profile
    parsed_skills: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True, default=list
    )
    parsed_experience: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    parsed_projects: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)

    # Auto-tags: e.g. ["backend", "AI/ML"]
    assigned_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True, default=list
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    match_results: Mapped[list["MatchResult"]] = relationship(  # type: ignore[name-defined]
        "MatchResult", back_populates="candidate"
    )

    __table_args__ = (
        Index(
            "ix_candidate_email_unique",
            "email",
            unique=True,
            postgresql_where=email.isnot(None),
        ),
        Index(
            "ix_candidate_hash_unique",
            "raw_text_hash",
            unique=True,
            postgresql_where=raw_text_hash.isnot(None),
        ),
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} email={self.email!r}>"

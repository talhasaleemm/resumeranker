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
from sqlalchemy import ForeignKey

from app.database import Base
from app.services.encryption import decrypt_text, decrypt_json


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=False
    )
    email_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Original extracted text — stored securely
    raw_text_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full structured profile
    parsed_skills: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True, default=list
    )
    parsed_experience_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_projects_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    recruiter: Mapped["Recruiter"] = relationship(  # type: ignore[name-defined]
        "Recruiter", back_populates="candidates"
    )
    match_results: Mapped[list["MatchResult"]] = relationship(  # type: ignore[name-defined]
        "MatchResult", back_populates="candidate", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ix_candidate_email_unique",
            "recruiter_id",
            "email_hash",
            unique=True,
            postgresql_where=email_hash.isnot(None),
        ),
        Index(
            "ix_candidate_hash_unique",
            "recruiter_id",
            "raw_text_hash",
            unique=True,
            postgresql_where=raw_text_hash.isnot(None),
        ),
    )

    @property
    def email(self) -> str | None:
        return decrypt_text(self.email_encrypted)

    @property
    def phone(self) -> str | None:
        return decrypt_text(self.phone_encrypted)

    @property
    def name(self) -> str | None:
        return decrypt_text(self.full_name_encrypted)

    @property
    def raw_text(self) -> str | None:
        return decrypt_text(self.raw_text_encrypted)

    @property
    def parsed_experience(self) -> dict | list | None:
        return decrypt_json(self.parsed_experience_encrypted)

    @property
    def parsed_projects(self) -> dict | list | None:
        return decrypt_json(self.parsed_projects_encrypted)

    def __repr__(self) -> str:
        return f"<Candidate id={self.id}>"

"""
app/models/job.py — ORM model for Job Descriptions.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import ARRAY, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Skills parsed from the job description — stored as canonical names
    required_skills: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True, default=list
    )
    preferred_skills: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True, default=list
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    match_results: Mapped[list["MatchResult"]] = relationship(  # type: ignore[name-defined]
        "MatchResult", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title!r}>"

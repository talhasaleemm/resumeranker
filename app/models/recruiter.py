"""
app/models/recruiter.py — ORM model for Recruiter.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Recruiter(Base):
    __tablename__ = "recruiters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # Relationships
    jobs: Mapped[list["Job"]] = relationship(  # type: ignore[name-defined]
        "Job", back_populates="recruiter", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["Candidate"]] = relationship(  # type: ignore[name-defined]
        "Candidate", back_populates="recruiter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Recruiter id={self.id} email={self.email!r}>"

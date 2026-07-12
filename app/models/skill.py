"""
app/models/skill.py — Normalized skill taxonomy model.
"""
import uuid

from sqlalchemy import ARRAY, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Skill(Base):
    """
    A canonical skill node. Aliases map to this canonical name.
    Example: canonical_name="JavaScript", aliases=["JS", "javascript", "js", "node"]
    """
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("canonical_name", name="uq_skill_canonical_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    # All known aliases (lowercase preferred for matching)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True, default=list)
    # Broad category: "language", "framework", "tool", "platform", "soft-skill", etc.
    category: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    candidate_skills: Mapped[list["CandidateSkill"]] = relationship(  # type: ignore[name-defined]
        "CandidateSkill", back_populates="skill"
    )

    def __repr__(self) -> str:
        return f"<Skill canonical={self.canonical_name!r}>"

"""
app/schemas/candidate.py — Pydantic schemas for Candidate API I/O.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class StructuredProfile(BaseModel):
    """The parsed profile extracted by the NER pipeline."""
    skills: list[str] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class CandidateSkillOut(BaseModel):
    skill_id: uuid.UUID
    canonical_name: str
    confidence: float
    source_context: str | None = None

    model_config = {"from_attributes": True}


class CandidateOut(BaseModel):
    id: uuid.UUID
    name: str | None
    email: str | None
    phone: str | None
    profile_tags: list[str] | None = None
    source_filename: str | None = None
    source_filetype: str | None = None
    structured_json: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateDetailOut(CandidateOut):
    """Full detail including extracted skills with confidence."""
    candidate_skills: list[CandidateSkillOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    """Response returned after a resume is uploaded and parsed."""
    candidate_id: uuid.UUID
    message: str
    name: str | None
    email: str | None
    skills_extracted: int
    profile_tags: list[str]
    structured_profile: StructuredProfile

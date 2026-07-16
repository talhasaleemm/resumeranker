"""
app/schemas/job.py — Pydantic schemas for Job API I/O.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: str = Field(..., min_length=10, max_length=50000)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

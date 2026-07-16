"""
app/schemas/responses.py — Pydantic response models for API endpoints.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResumeUploadResponse(BaseModel):
    """Response for POST /api/v1/resumes/"""
    status: str
    candidate_id: uuid.UUID


class JobCreateResponse(BaseModel):
    """Response for POST /api/v1/jobs/"""
    status: str
    job_id: uuid.UUID


class MatchCandidate(BaseModel):
    """Individual match result for a candidate"""
    candidate_id: uuid.UUID
    candidate_name: str | None
    candidate_email: str | None
    tfidf_score: float
    bm25_score: float
    skill_score: float
    final_score: float
    explanation_log: dict[str, Any]

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    """Response for POST /api/v1/matches/"""
    status: str
    matches: list[MatchCandidate]


class TaskResponse(BaseModel):
    """Response for task status endpoint."""
    task_id: str
    status: str
    result: Any | None = None

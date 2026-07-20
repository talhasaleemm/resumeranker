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
    vector_score: float
    final_score: float
    explanation_log: dict[str, Any]

    model_config = {"from_attributes": True}


class AsyncAcceptedResponse(BaseModel):
    status: str
    task_id: str
    message: str


class MessageResponse(BaseModel):
    message: str


class MatchResponse(BaseModel):
    """Response for POST /api/v1/matches/"""
    status: str
    matches: list[MatchCandidate]


class TaskResponse(BaseModel):
    """Response for task status endpoint."""
    task_id: str
    status: str
    result: Any | None = None


class CandidateSummary(BaseModel):
    """Lightweight candidate view for listing."""
    id: uuid.UUID
    name: str | None = None
    email: str | None = None
    skills: list[str] = []
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CandidateListResponse(BaseModel):
    count: int
    candidates: list[CandidateSummary]


class JobSummary(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    count: int
    jobs: list[JobSummary]


class MatchHistoryItem(BaseModel):
    job_id: uuid.UUID
    job_title: str | None = None
    candidate_id: uuid.UUID
    candidate_name: str | None = None
    final_score: float
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MatchHistoryResponse(BaseModel):
    count: int
    matches: list[MatchHistoryItem]

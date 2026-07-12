"""
app/schemas/match.py — Pydantic schemas for MatchResult API I/O.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel


class MatchResultOut(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    tfidf_score: float
    bm25_score: float
    skill_overlap_score: float
    final_score: float
    explanation_text: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchExplanationOut(MatchResultOut):
    """Full explanation detail — includes the complete JSON log."""
    explanation_log: dict | None = None

    model_config = {"from_attributes": True}


class RankedCandidateOut(BaseModel):
    """One entry in a ranked list of candidates for a job."""
    rank: int
    match_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str | None
    candidate_email: str | None
    profile_tags: list[str] | None = None
    final_score: float
    tfidf_score: float
    bm25_score: float
    skill_overlap_score: float
    explanation_text: str | None = None

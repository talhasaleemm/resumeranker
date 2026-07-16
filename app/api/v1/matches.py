"""
app/api/v1/matches.py — Match/ranking endpoint (Phase 2).
Phase 6B-2b: Rate limiting added.
Phase 8: Strict response typing added.
Phase 9: Async task queue via Celery.
"""
from typing import List, Dict, Any, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, model_validator, Field

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import Job
from app.services.matching.scorer import score_candidates
from app.services.encryption import decrypt_text, decrypt_json
from app.config import get_settings
from app.rate_limiter import limiter
from app.schemas.responses import MatchResponse, MatchCandidate
from app.worker import score_candidates_task
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/matches", tags=["matches"])

import math

class MatchWeights(BaseModel):
    tfidf: float
    bm25: float
    skills: float

    @model_validator(mode="after")
    def check_weights_sum(self) -> "MatchWeights":
        if self.tfidf < 0 or self.bm25 < 0 or self.skills < 0:
            raise ValueError("Weights cannot be negative.")
            
        total = self.tfidf + self.bm25 + self.skills
        if not math.isclose(total, 1.0, rel_tol=1e-5):
            raise ValueError(f"Weights must sum to exactly 1.0. Got {total:.2f}")
        return self


class MatchRequest(BaseModel):
    job_id: uuid.UUID
    candidate_ids: List[uuid.UUID] = Field(..., min_length=1, max_length=100)
    weights: Optional[MatchWeights] = None


@router.post("/", response_model=MatchResponse)
@limiter.limit("60/minute")
async def match_candidates(request: Request, match_request: MatchRequest, db: AsyncSession = Depends(get_db)):
    """
    Submit candidates for asynchronous matching against a job.
    Returns 202 Accepted with a task_id for polling.
    """
    job = await db.get(Job, match_request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stmt = select(Candidate).where(Candidate.id.in_(match_request.candidate_ids))
    res = await db.execute(stmt)
    candidates_db = res.scalars().all()
    if not candidates_db:
        raise HTTPException(status_code=404, detail="No candidates found")

    candidate_ids_str = [str(cid) for cid in match_request.candidate_ids]
    task = score_candidates_task.delay(
        job_id=str(match_request.job_id),
        candidate_ids=candidate_ids_str,
    )

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "task_id": task.id,
            "message": "Matching is being processed. Use GET /api/v1/tasks/{task_id} to check status.",
        },
    )

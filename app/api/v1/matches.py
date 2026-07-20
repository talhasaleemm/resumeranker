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
from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import Job
from app.services.matching.scorer import score_candidates
from app.services.encryption import decrypt_text, decrypt_json
from app.config import get_settings
from app.rate_limiter import limiter
from app.schemas.responses import MatchResponse, MatchCandidate, AsyncAcceptedResponse, MatchHistoryResponse, MatchHistoryItem
from app.worker import score_candidates_task
from fastapi.responses import JSONResponse
from app.models.user import User
from app.services.auth_service import get_current_active_user

router = APIRouter(prefix="/matches", tags=["matches"])

import math

class MatchWeights(BaseModel):
    tfidf: float
    bm25: float
    skills: float
    vector: float

    @model_validator(mode="after")
    def check_weights_sum(self) -> "MatchWeights":
        if self.tfidf < 0 or self.bm25 < 0 or self.skills < 0 or self.vector < 0:
            raise ValueError("Weights cannot be negative.")
            
        total = self.tfidf + self.bm25 + self.skills + self.vector
        if not math.isclose(total, 1.0, rel_tol=1e-5):
            raise ValueError(f"Weights must sum to exactly 1.0. Got {total:.2f}")
        return self


class MatchRequest(BaseModel):
    job_id: uuid.UUID
    candidate_ids: List[uuid.UUID] = Field(..., min_length=1, max_length=100)
    weights: Optional[MatchWeights] = None


@router.post("/", response_model=AsyncAcceptedResponse, status_code=202)
@limiter.limit("60/minute")
async def match_candidates(
    request: Request, 
    match_request: MatchRequest, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Submit candidates for asynchronous matching against a job.
    Returns 202 Accepted with a task_id for polling.
    """
    job = await db.get(Job, match_request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")

    stmt = select(Candidate).where(Candidate.id.in_(match_request.candidate_ids))
    res = await db.execute(stmt)
    candidates_db = res.scalars().all()
    if not candidates_db:
        raise HTTPException(status_code=404, detail="No candidates found")
        
    authorized = []
    unauthorized = []
    for c in candidates_db:
        if c.owner_id == current_user.id:
            authorized.append(c)
        else:
            unauthorized.append(str(c.id))
    
    if unauthorized and not authorized:
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized to access any of the requested candidates",
        )
    
    if unauthorized:
        candidate_ids_str = [str(c.id) for c in authorized]
    else:
        candidate_ids_str = [str(cid) for cid in match_request.candidate_ids]
    task = score_candidates_task.delay(
        job_id=str(match_request.job_id),
        candidate_ids=candidate_ids_str,
        weights=match_request.weights.model_dump() if match_request.weights else None,
        owner_id=str(current_user.id),
    )

    return AsyncAcceptedResponse(
        status="accepted",
        task_id=task.id,
        message="Matching is being processed. Use GET /api/v1/tasks/{task_id} to check status.",
    )


@router.get("/history", summary="List your match history", response_model=MatchHistoryResponse)
@limiter.limit("60/minute")
async def match_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List past match results for jobs owned by the authenticated user.
    Returns one row per MatchResult, decorated with job title and candidate name.
    """
    from app.models.match import MatchResult

    # Only include results whose job belongs to the current user (isolation).
    stmt = (
        select(MatchResult)
        .join(Job, MatchResult.job_id == Job.id)
        .where(Job.owner_id == current_user.id)
        .order_by(MatchResult.created_at.desc())
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()

    items = []
    for m in rows:
        job = await db.get(Job, m.job_id)
        candidate = await db.get(Candidate, m.candidate_id)
        items.append(
            MatchHistoryItem(
                job_id=m.job_id,
                job_title=job.title if job else None,
                candidate_id=m.candidate_id,
                candidate_name=candidate.name if candidate else None,
                final_score=m.final_score,
                created_at=m.created_at,
            )
        )

    return MatchHistoryResponse(count=len(items), matches=items)

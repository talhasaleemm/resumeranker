"""
app/api/v1/matches.py — Match/ranking endpoint (Phase 2).
"""
from typing import List, Dict, Any, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, model_validator

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.match import MatchResult
from app.services.matching.scorer import score_candidates
from app.config import get_settings

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
    candidate_ids: List[uuid.UUID]
    weights: Optional[MatchWeights] = None


@router.post("/")
async def match_candidates(request: MatchRequest, db: AsyncSession = Depends(get_db)):
    """
    Computes match scores between a job and candidates, loading from DB and persisting results.
    """
    settings = get_settings()

    # Load job
    job = await db.get(Job, request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Load candidates
    stmt = select(Candidate).where(Candidate.id.in_(request.candidate_ids))
    res = await db.execute(stmt)
    candidates_db = res.scalars().all()
    if not candidates_db:
        raise HTTPException(status_code=404, detail="No candidates found")

    candidates_payload = []
    for c in candidates_db:
        candidates_payload.append({
            "id": str(c.id),
            "raw_text": c.raw_text or "",
            "skills": c.parsed_skills or [],
            "experience": c.parsed_experience or [],
            "projects": c.parsed_projects or []
        })

    original_tfidf = settings.tfidf_weight
    original_bm25 = settings.bm25_weight
    original_skills = settings.skill_weight

    weights_used = {
        "tfidf": original_tfidf,
        "bm25": original_bm25,
        "skills": original_skills
    }

    try:
        if request.weights:
            settings.tfidf_weight = request.weights.tfidf
            settings.bm25_weight = request.weights.bm25
            settings.skill_weight = request.weights.skills
            weights_used = {
                "tfidf": request.weights.tfidf,
                "bm25": request.weights.bm25,
                "skills": request.weights.skills
            }

        results = score_candidates(
            job_description=job.description,
            job_required_skills=job.required_skills or [],
            candidates=candidates_payload
        )

        matches_out = []
        for r in results:
            mr = MatchResult(
                candidate_id=uuid.UUID(r["candidate_id"]),
                job_id=job.id,
                tfidf_score=r["tfidf_score"],
                bm25_score=r["bm25_score"],
                skill_overlap_score=r["skill_score"],
                final_score=r["final_score"],
                weights_used=weights_used,
                explanation_log=r["explanation_log"]
            )
            db.add(mr)
            matches_out.append(r)

        await db.commit()
        return {"status": "success", "matches": matches_out}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Restore original settings
        settings.tfidf_weight = original_tfidf
        settings.bm25_weight = original_bm25
        settings.skill_weight = original_skills

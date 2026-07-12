"""
app/api/v1/matches.py — Match/ranking endpoint (Phase 2).
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.services.matching.scorer import score_candidates
from app.config import get_settings

router = APIRouter(prefix="/matches", tags=["matches"])


class MatchWeights(BaseModel):
    tfidf: Optional[float] = 0.4
    bm25: Optional[float] = 0.4
    skills: Optional[float] = 0.2


class MatchRequest(BaseModel):
    job_description: str
    required_skills: List[str]
    candidates: List[Dict[str, Any]]
    weights: Optional[MatchWeights] = None


@router.post("/")
async def match_candidates(request: MatchRequest):
    """
    Computes match scores between a job description and a list of candidates.
    Overrides default matching weights if provided.
    """
    settings = get_settings()

    # Temporarily override weights for this request if provided
    original_tfidf = settings.tfidf_weight
    original_bm25 = settings.bm25_weight
    original_skills = settings.skill_weight

    try:
        if request.weights:
            settings.tfidf_weight = request.weights.tfidf
            settings.bm25_weight = request.weights.bm25
            settings.skill_weight = request.weights.skills

        results = score_candidates(
            job_description=request.job_description,
            job_required_skills=request.required_skills,
            candidates=request.candidates
        )
        return {"status": "success", "matches": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Restore original settings
        settings.tfidf_weight = original_tfidf
        settings.bm25_weight = original_bm25
        settings.skill_weight = original_skills

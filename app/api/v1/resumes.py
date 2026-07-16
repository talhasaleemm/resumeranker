"""
app/api/v1/resumes.py — Resume upload endpoint (placeholder for Phase 4).
Wired up in Phase 0 so FastAPI router registration works.
Real parsing logic added in Phase 1.
Phase 6B-2b: Rate limiting added.
Phase 8: Strict response typing added.
"""
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from app.database import get_db
from app.services.candidate_service import ingest_candidate
from app.rate_limiter import limiter
from app.schemas.responses import ResumeUploadResponse

router = APIRouter(prefix="/resumes", tags=["resumes"])

class ResumeUpload(BaseModel):
    raw_text: str = Field(..., max_length=100000)
    filename: str = Field("unknown", max_length=255)

@router.post("/", summary="Ingest a candidate resume", response_model=ResumeUploadResponse)
@limiter.limit("10/minute")
async def upload_resume(request: Request, upload: ResumeUpload, db: AsyncSession = Depends(get_db)):
    """Ingest a candidate resume with dedup logic."""
    candidate = await ingest_candidate(db, raw_text=upload.raw_text, filename=upload.filename)
    return ResumeUploadResponse(status="success", candidate_id=candidate.id)

@router.get("/", summary="List all candidates")
@limiter.limit("60/minute")
async def list_candidates(request: Request):
    """List candidates — not yet implemented."""
    return {"message": "Candidate listing not yet implemented."}

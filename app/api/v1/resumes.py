"""
app/api/v1/resumes.py — Resume upload endpoint (placeholder for Phase 4).
Wired up in Phase 0 so FastAPI router registration works.
Real parsing logic added in Phase 1.
"""
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.database import get_db
from app.services.candidate_service import ingest_candidate

router = APIRouter(prefix="/resumes", tags=["resumes"])

class ResumeUpload(BaseModel):
    raw_text: str
    filename: str = "unknown"

@router.post("/", summary="Ingest a candidate resume")
async def upload_resume(upload: ResumeUpload, db: AsyncSession = Depends(get_db)):
    """Ingest a candidate resume with dedup logic."""
    candidate = await ingest_candidate(db, raw_text=upload.raw_text, filename=upload.filename)
    return {"status": "success", "candidate_id": str(candidate.id)}

@router.get("/", summary="List all candidates")
async def list_candidates():
    """List candidates — not yet implemented."""
    return {"message": "Candidate listing not yet implemented."}

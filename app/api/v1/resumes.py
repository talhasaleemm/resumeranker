"""
app/api/v1/resumes.py — Resume upload endpoint (placeholder for Phase 4).
Wired up in Phase 0 so FastAPI router registration works.
Real parsing logic added in Phase 1.
Phase 6B-2b: Rate limiting added.
Phase 8: Strict response typing added.
Phase 9: Async task queue via Celery.
"""
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from app.database import get_db
from app.rate_limiter import limiter
from app.schemas.responses import ResumeUploadResponse
from app.worker import ingest_candidate_task

router = APIRouter(prefix="/resumes", tags=["resumes"])

class ResumeUpload(BaseModel):
    raw_text: str = Field(..., max_length=100000)
    filename: str = Field("unknown", max_length=255)

@router.post("/", summary="Ingest a candidate resume", response_model=ResumeUploadResponse)
@limiter.limit("10/minute")
async def upload_resume(request: Request, upload: ResumeUpload, db: AsyncSession = Depends(get_db)):
    """
    Submit a resume for asynchronous parsing and ingestion.
    Returns 202 Accepted with a task_id for polling.
    """
    task = ingest_candidate_task.delay(raw_text=upload.raw_text, filename=upload.filename)
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "task_id": task.id,
            "message": "Resume is being processed. Use GET /api/v1/tasks/{task_id} to check status.",
        },
    )

@router.get("/", summary="List all candidates")
@limiter.limit("60/minute")
async def list_candidates(request: Request):
    """List candidates — not yet implemented."""
    return {"message": "Candidate listing not yet implemented."}

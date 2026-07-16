"""
app/api/v1/jobs.py — Job description endpoint (placeholder for Phase 4).
# Bind mount test comment
Phase 6B-2b: Rate limiting added.
Phase 8: Strict response typing added.
"""
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobCreate
from app.rate_limiter import limiter
from app.schemas.responses import JobCreateResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/", summary="Create a new job", response_model=JobCreateResponse)
@limiter.limit("10/minute")
async def create_job(request: Request, job_in: JobCreate, db: AsyncSession = Depends(get_db)):
    job = Job(
        title=job_in.title,
        description=job_in.description,
        required_skills=job_in.required_skills,
        preferred_skills=job_in.preferred_skills,
        is_active=True
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return JobCreateResponse(status="success", job_id=job.id)

@router.get("/", summary="List all jobs")
@limiter.limit("60/minute")
async def list_jobs(request: Request):
    """List jobs — not yet implemented."""
    return {"message": "Job listing not yet implemented."}

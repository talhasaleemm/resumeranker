"""
app/api/v1/jobs.py — Job description endpoint (placeholder for Phase 4).
# Bind mount test comment
Phase 6B-2b: Rate limiting added.
"""
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from app.database import get_db
from app.models.job import Job
from app.rate_limiter import limiter

router = APIRouter(prefix="/jobs", tags=["jobs"])

class JobCreate(BaseModel):
    title: str
    description: str
    required_skills: List[str] = []
    preferred_skills: List[str] = []

@router.post("/", summary="Create a new job")
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
    return {"status": "success", "job_id": str(job.id)}

@router.get("/", summary="List all jobs")
@limiter.limit("60/minute")
async def list_jobs(request: Request):
    """List jobs — not yet implemented."""
    return {"message": "Job listing not yet implemented."}

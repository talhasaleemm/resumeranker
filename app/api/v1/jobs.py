"""
app/api/v1/jobs.py — Job description endpoint (placeholder for Phase 4).
# Bind mount test comment
"""
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.database import get_db
from app.models.job import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])

class JobCreate(BaseModel):
    title: str
    description: str
    required_skills: List[str] = []
    preferred_skills: List[str] = []

@router.post("/", summary="Create a new job")
async def create_job(job_in: JobCreate, db: AsyncSession = Depends(get_db)):
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
async def list_jobs():
    """List jobs — not yet implemented."""
    return {"message": "Job listing not yet implemented."}

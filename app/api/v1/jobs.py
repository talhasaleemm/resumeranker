"""
app/api/v1/jobs.py — Job description endpoint (placeholder for Phase 4).
# Bind mount test comment
Phase 6B-2b: Rate limiting added.
Phase 8: Strict response typing added.
"""
from pydantic import BaseModel
from typing import List
import uuid
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobCreate
from app.rate_limiter import limiter
from app.schemas.responses import JobCreateResponse, JobListResponse, JobSummary
from app.models.user import User
from app.models.recruiter import Recruiter
from app.services.auth_service import get_current_active_user

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/", summary="Create a new job", response_model=JobCreateResponse)
@limiter.limit("10/minute")
async def create_job(
    request: Request, 
    job_in: JobCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    import asyncio
    from app.services.embedding import get_embedding_service
    embedding_service = get_embedding_service()
    embedding_vector = await asyncio.to_thread(embedding_service.get_embedding, job_in.description)

    # Resolve the recruiter tenant. The authenticated principal is a User, but
    # jobs.recruiter_id is an FK to the recruiters table, so we map by email
    # (recruiters are uniquely indexed on email) and fall back to the system
    # recruiter if no matching recruiter row exists.
    SYSTEM_RECRUITER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
    recruiter = await db.scalar(
        sqlalchemy.select(Recruiter).where(Recruiter.email == current_user.email)
    )
    recruiter_id = recruiter.id if recruiter is not None else SYSTEM_RECRUITER_ID

    job = Job(
        title=job_in.title,
        description=job_in.description,
        required_skills=job_in.required_skills,
        preferred_skills=job_in.preferred_skills,
        embedding=embedding_vector,
        is_active=True,
        owner_id=current_user.id,
        recruiter_id=recruiter_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return JobCreateResponse(status="success", job_id=job.id)

from app.schemas.responses import JobCreateResponse, MessageResponse

@router.get("/", summary="List your jobs", response_model=JobListResponse)
@limiter.limit("60/minute")
async def list_jobs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List jobs owned by the authenticated user."""
    from sqlalchemy import select

    stmt = (
        select(Job)
        .where(Job.owner_id == current_user.id)
        .order_by(Job.created_at.desc())
    )
    res = await db.execute(stmt)
    jobs = res.scalars().all()
    return JobListResponse(
        count=len(jobs),
        jobs=[
            JobSummary(id=j.id, title=j.title, description=j.description, created_at=j.created_at)
            for j in jobs
        ],
    )

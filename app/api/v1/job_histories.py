"""
app/api/v1/job_histories.py — JobHistory saved sessions endpoints.
"""
from typing import List
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from app.database import get_db
from app.models.job import JobHistory
from app.schemas.job import JobHistoryCreate, JobHistoryResponse
from app.rate_limiter import limiter
from app.models.user import User
from app.services.auth_service import get_current_active_user


router = APIRouter(prefix="/job-histories", tags=["job-histories"])


@router.post("/", response_model=JobHistoryResponse, status_code=201)
@limiter.limit("10/minute")
async def create_job_history(
    request: Request,
    payload: JobHistoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new job history entry for the authenticated user.
    The owner_id is securely extracted from the JWT session.
    """
    job_history = JobHistory(
        title=payload.title,
        description=payload.description,
        required_skills=payload.required_skills,
        owner_id=current_user.id,
        is_active=True,
    )
    db.add(job_history)
    await db.commit()
    await db.refresh(job_history)
    return job_history


@router.get("/", response_model=List[JobHistoryResponse])
@limiter.limit("60/minute")
async def list_job_histories(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List all job history entries owned by the authenticated user.
    """
    stmt = (
        select(JobHistory)
        .where(JobHistory.owner_id == current_user.id)
        .order_by(JobHistory.created_at.desc())
    )
    res = await db.execute(stmt)
    job_histories = res.scalars().all()
    return job_histories

"""
app/api/v1/jobs.py — Job description endpoint (placeholder for Phase 4).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", summary="List all jobs")
async def list_jobs():
    """Placeholder — full implementation in Phase 4."""
    return {"message": "Job endpoints coming in Phase 4"}

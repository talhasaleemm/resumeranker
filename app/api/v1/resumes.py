"""
app/api/v1/resumes.py — Resume upload endpoint (placeholder for Phase 4).
Wired up in Phase 0 so FastAPI router registration works.
Real parsing logic added in Phase 1.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("/", summary="List all candidates")
async def list_candidates():
    """Placeholder — full implementation in Phase 4."""
    return {"message": "Resume endpoints coming in Phase 1/4"}

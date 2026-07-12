"""
app/api/v1/matches.py — Match/ranking endpoint (placeholder for Phase 4).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/", summary="List match results")
async def list_matches():
    """Placeholder — full implementation in Phase 4."""
    return {"message": "Match endpoints coming in Phase 4"}

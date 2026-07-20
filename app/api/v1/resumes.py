"""
app/api/v1/resumes.py — Resume upload endpoint.
Phase 11: Switched to multipart/form-data UploadFile with security constraints.
"""
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.rate_limiter import limiter
from app.schemas.responses import (
    ResumeUploadResponse,
    AsyncAcceptedResponse,
    MessageResponse,
    CandidateListResponse,
    CandidateSummary,
)
from app.models.candidate import Candidate
from app.worker import ingest_candidate_task
from app.models.user import User
from app.services.auth_service import get_current_active_user

router = APIRouter(prefix="/resumes", tags=["resumes"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_MIMETYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@router.post("/", summary="Ingest a candidate resume", response_model=AsyncAcceptedResponse, status_code=202)
@limiter.limit("10/minute")
async def upload_resume(
    request: Request, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Submit a resume binary file for asynchronous parsing and ingestion.
    Returns 202 Accepted with a task_id for polling.
    """
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    
    if file.content_type not in ALLOWED_MIMETYPES:
        raise HTTPException(status_code=415, detail="Unsupported media type (must be PDF or DOCX)")
        
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file extension '{ext or 'none'}' (must be .pdf or .docx)",
        )

    file_id = uuid.uuid4().hex
    safe_filename = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / safe_filename

    # Manually check size if file.size isn't accurately populated.
    # Wrap disk I/O so permission/IO errors return an explicit payload
    # instead of an uncaught 500.
    try:
        real_size = 0
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):
                real_size += len(chunk)
                if real_size > MAX_FILE_SIZE:
                    buffer.close()
                    file_path.unlink()
                    raise HTTPException(status_code=413, detail="File too large (max 10MB)")
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        # Clean up any partial file and return a structured error.
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {exc}",
        )

    # Pass the actual file path and the original filename (for logging/metadata, not path traversal)
    task = ingest_candidate_task.delay(
        file_path=str(file_path),
        original_filename=file.filename,
        owner_id=str(current_user.id)
    )
    
    return AsyncAcceptedResponse(
        status="accepted",
        task_id=task.id,
        message="Resume is being processed. Use GET /api/v1/tasks/{task_id} to check status.",
    )

@router.get("/", summary="List your candidates", response_model=CandidateListResponse)
@limiter.limit("60/minute")
async def list_candidates(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List candidates owned by the authenticated user."""
    from sqlalchemy import select

    stmt = (
        select(Candidate)
        .where(Candidate.owner_id == current_user.id)
        .order_by(Candidate.created_at.desc())
    )
    res = await db.execute(stmt)
    candidates = res.scalars().all()
    return CandidateListResponse(
        count=len(candidates),
        candidates=[
            CandidateSummary(
                id=c.id,
                name=c.name,
                email=c.email,
                skills=c.parsed_skills or [],
                created_at=c.created_at,
            )
            for c in candidates
        ],
    )

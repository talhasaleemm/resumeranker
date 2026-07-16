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
from app.schemas.responses import ResumeUploadResponse
from app.worker import ingest_candidate_task
from app.models.recruiter import Recruiter
from app.services.auth_service import get_current_active_recruiter

router = APIRouter(prefix="/resumes", tags=["resumes"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_MIMETYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@router.post("/", summary="Ingest a candidate resume", response_model=ResumeUploadResponse)
@limiter.limit("10/minute")
async def upload_resume(
    request: Request, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    current_user: Recruiter = Depends(get_current_active_recruiter)
):
    """
    Submit a resume binary file for asynchronous parsing and ingestion.
    Returns 202 Accepted with a task_id for polling.
    """
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    
    if file.content_type not in ALLOWED_MIMETYPES:
        raise HTTPException(status_code=415, detail="Unsupported media type (must be PDF or DOCX)")
        
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file extension (must be .pdf or .docx)")

    file_id = uuid.uuid4().hex
    safe_filename = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / safe_filename

    # Manually check size if file.size isn't accurately populated
    real_size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(8192):
            real_size += len(chunk)
            if real_size > MAX_FILE_SIZE:
                buffer.close()
                file_path.unlink()
                raise HTTPException(status_code=413, detail="File too large (max 10MB)")
            buffer.write(chunk)

    # Pass the actual file path and the original filename (for logging/metadata, not path traversal)
    task = ingest_candidate_task.delay(
        file_path=str(file_path), 
        original_filename=file.filename,
        recruiter_id=str(current_user.id)
    )
    
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

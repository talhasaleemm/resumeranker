"""
app/worker.py — Celery worker for background NLP/AI inference.

Decouples CPU-bound operations (spaCy NER, TF-IDF/BM25 scoring, OCR)
from the FastAPI request-response cycle.

Tasks:
  - ingest_candidate_task: parse resume, encrypt PII, dedup, persist
  - score_candidates_task: load job/candidates, decrypt, score, persist matches
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from celery import Celery
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.match import MatchResult
from app.services.parser.ner_pipeline import parse_resume
from app.services.tagging.tagger import assign_tags
from app.services.encryption import encrypt_text, encrypt_json, compute_blind_index, decrypt_text, decrypt_json
from app.services.matching.scorer import score_candidates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery app setup
# ---------------------------------------------------------------------------
settings = get_settings()

celery_app = Celery(
    "resumeranker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=290,
)

# ---------------------------------------------------------------------------
# Sync database setup for worker
# ---------------------------------------------------------------------------
# Convert asyncpg URL to psycopg2 URL for sync SQLAlchemy in the worker
_sync_db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
_engine = create_engine(_sync_db_url, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, name="ingest_candidate")
def ingest_candidate_task(self, file_path: str, original_filename: str, recruiter_id: str) -> dict:
    """
    Parse a resume from a file, extract text, encrypt PII, apply dedup logic, and persist to PostgreSQL.
    Runs in the Celery worker to avoid blocking the API event loop.
    Deletes the temporary file after processing.
    """
    db: Session = SessionLocal()
    import os
    
    # 1. Read and extract text
    if not os.path.exists(file_path):
        return {"status": "failure", "error": "File not found", "filename": original_filename}
        
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            
        if original_filename.lower().endswith(".pdf"):
            from app.services.parser.pdf_parser import extract_text_from_pdf
            raw_text = extract_text_from_pdf(file_bytes, original_filename)
        elif original_filename.lower().endswith(".docx"):
            from app.services.parser.docx_parser import extract_text_from_docx
            raw_text = extract_text_from_docx(file_bytes, original_filename)
        else:
            raise ValueError(f"Unsupported file extension: {original_filename}")
            
        if not raw_text or len(raw_text.strip()) < 50:
            raise ValueError("Extracted text is empty or near-empty")
            
    except Exception as exc:
        logger.exception("Worker: failed to extract text from '%s': %s", original_filename, exc)
        return {
            "status": "failure",
            "error": str(exc),
            "filename": original_filename,
        }
    finally:
        # Delete the temp file to ensure no PII sits on disk
        try:
            os.remove(file_path)
        except OSError:
            logger.warning("Worker: failed to delete temp file %s", file_path)

    # 2. Parse and Persist
    try:
        logger.info("Worker: ingesting candidate from '%s' (%d chars)", original_filename, len(raw_text))

        raw_text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        profile = parse_resume(raw_text, filename=original_filename)

        email = profile.get("email")
        phone = profile.get("phone")
        full_name = profile.get("name")
        parsed_skills = profile.get("skills", [])
        parsed_experience = profile.get("experience", [])
        parsed_projects = profile.get("projects", [])

        assigned_tags = assign_tags(profile)

        candidate = None

        # Dedup 1: By Email Hash
        email_hash = compute_blind_index(email) if email else None
        if email_hash:
            candidate = (
                db.query(Candidate)
                .filter(Candidate.email_hash == email_hash, Candidate.recruiter_id == recruiter_id)
                .first()
            )

        # Dedup 2: By raw_text_hash
        if not candidate:
            candidate = (
                db.query(Candidate)
                .filter(Candidate.raw_text_hash == raw_text_hash, Candidate.recruiter_id == recruiter_id)
                .first()
            )

        if candidate:
            # Update existing candidate
            if email_hash:
                candidate.email_hash = email_hash
                candidate.email_encrypted = encrypt_text(email)
            candidate.raw_text_hash = raw_text_hash
            candidate.phone_encrypted = encrypt_text(phone)
            candidate.full_name_encrypted = encrypt_text(full_name)
            candidate.raw_text_encrypted = encrypt_text(raw_text)
            candidate.parsed_skills = parsed_skills
            candidate.parsed_experience_encrypted = encrypt_json(parsed_experience)
            candidate.parsed_projects_encrypted = encrypt_json(parsed_projects)
            candidate.assigned_tags = assigned_tags
            candidate.is_active = True
            candidate.updated_at = _utcnow()
            action = "updated"
        else:
            logger.info("Worker: Creating new candidate profile for '%s'", original_filename)
            # Insert new candidate
            candidate = Candidate(
                recruiter_id=recruiter_id,
                email_hash=email_hash,
                email_encrypted=encrypt_text(email) if email else None,
                raw_text_hash=raw_text_hash,
                phone_encrypted=encrypt_text(phone) if phone else None,
                full_name_encrypted=encrypt_text(full_name) if full_name else None,
                raw_text_encrypted=encrypt_text(raw_text),
                parsed_skills=parsed_skills,
                parsed_experience_encrypted=encrypt_json(parsed_experience),
                parsed_projects_encrypted=encrypt_json(parsed_projects),
                assigned_tags=assigned_tags,
                is_active=True,
            )
            db.add(candidate)
            action = "created"

        db.commit()
        db.refresh(candidate)

        logger.info("Worker: candidate %s (id=%s)", action, candidate.id)

        return {
            "status": "success",
            "action": action,
            "candidate_id": str(candidate.id),
            "email_hash": email_hash,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Worker: failed to ingest candidate from '%s': %s", original_filename, exc)
        return {
            "status": "failure",
            "error": str(exc),
            "filename": original_filename,
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="score_candidates")
def score_candidates_task(self, job_id: str, candidate_ids: list[str]) -> dict:
    """
    Load a job and candidates from PostgreSQL, decrypt PII, run TF-IDF/BM25
    scoring, persist MatchResult records, and return the rankings.
    Runs in the Celery worker to avoid blocking the API event loop.
    """
    db: Session = SessionLocal()
    try:
        logger.info(
            "Worker: scoring candidates for job_id=%s (candidates=%d)",
            job_id,
            len(candidate_ids),
        )

        # Load job
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {
                "status": "failure",
                "error": f"Job not found: {job_id}",
                "job_id": job_id,
            }

        # Load candidates
        candidates_db = (
            db.query(Candidate)
            .filter(Candidate.id.in_(candidate_ids))
            .all()
        )
        if not candidates_db:
            return {
                "status": "failure",
                "error": "No candidates found",
                "job_id": job_id,
                "candidate_ids": candidate_ids,
            }

        candidates_payload = []
        cand_map = {}
        for c in candidates_db:
            cand_map[str(c.id)] = c
            candidates_payload.append({
                "id": str(c.id),
                "raw_text": decrypt_text(c.raw_text_encrypted) or "",
                "skills": c.parsed_skills or [],
                "experience": decrypt_json(c.parsed_experience_encrypted) or [],
                "projects": decrypt_json(c.parsed_projects_encrypted) or [],
            })

        results = score_candidates(
            job_description=job.description,
            job_required_skills=job.required_skills or [],
            candidates=candidates_payload,
        )

        matches_out = []
        for r in results:
            mr = MatchResult(
                candidate_id=r["candidate_id"],
                job_id=job.id,
                tfidf_score=r["tfidf_score"],
                bm25_score=r["bm25_score"],
                skill_overlap_score=r["skill_score"],
                final_score=r["final_score"],
                weights_used={
                    "tfidf": get_settings().tfidf_weight,
                    "bm25": get_settings().bm25_weight,
                    "skills": get_settings().skill_weight,
                },
                explanation_log=r["explanation_log"],
            )
            db.add(mr)

            c = cand_map[r["candidate_id"]]
            matches_out.append({
                "candidate_id": r["candidate_id"],
                "candidate_name": decrypt_text(c.full_name_encrypted),
                "candidate_email": decrypt_text(c.email_encrypted),
                "tfidf_score": r["tfidf_score"],
                "bm25_score": r["bm25_score"],
                "skill_score": r["skill_score"],
                "final_score": r["final_score"],
                "explanation_log": r["explanation_log"],
            })

        db.commit()

        logger.info(
            "Worker: scored %d candidates for job_id=%s",
            len(matches_out),
            job_id,
        )

        return {
            "status": "success",
            "job_id": job_id,
            "matches": matches_out,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Worker: failed to score candidates for job_id=%s: %s", job_id, exc)
        return {
            "status": "failure",
            "error": str(exc),
            "job_id": job_id,
        }
    finally:
        db.close()

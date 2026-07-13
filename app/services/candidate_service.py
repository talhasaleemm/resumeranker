"""
app/services/candidate_service.py — Service layer for candidate ingestion.
"""
import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.services.parser.ner_pipeline import parse_resume
from app.services.tagging.tagger import assign_tags
from app.services.encryption import encrypt_text, encrypt_json, compute_blind_index


async def ingest_candidate(
    db: AsyncSession, raw_text: str, filename: str = "unknown"
) -> Candidate:
    """
    Parses a resume and persists it to the database with dedup logic.
    """
    raw_text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    profile = parse_resume(raw_text, filename=filename)

    email = profile.get("email")
    phone = profile.get("phone")
    full_name = profile.get("name")
    parsed_skills = profile.get("skills", [])
    parsed_experience = profile.get("experience", [])
    parsed_projects = profile.get("projects", [])

    # Tags assignment
    assigned_tags = assign_tags(profile)

    candidate = None

    # Dedup 1: By Email Hash
    email_hash = compute_blind_index(email) if email else None
    if email_hash:
        stmt = select(Candidate).where(Candidate.email_hash == email_hash)
        result = await db.execute(stmt)
        candidate = result.scalar_one_or_none()

    # Dedup 2: By raw_text_hash
    if not candidate:
        stmt = select(Candidate).where(Candidate.raw_text_hash == raw_text_hash)
        result = await db.execute(stmt)
        candidate = result.scalar_one_or_none()

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
    else:
        # Insert new candidate
        candidate = Candidate(
            email_hash=email_hash,
            email_encrypted=encrypt_text(email),
            raw_text_hash=raw_text_hash,
            phone_encrypted=encrypt_text(phone),
            full_name_encrypted=encrypt_text(full_name),
            raw_text_encrypted=encrypt_text(raw_text),
            parsed_skills=parsed_skills,
            parsed_experience_encrypted=encrypt_json(parsed_experience),
            parsed_projects_encrypted=encrypt_json(parsed_projects),
            assigned_tags=assigned_tags,
            is_active=True,
        )
        db.add(candidate)

    await db.flush()
    await db.refresh(candidate)
    return candidate

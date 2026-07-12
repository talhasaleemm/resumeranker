import pytest
import asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.database import AsyncSessionLocal
from app.services.candidate_service import ingest_candidate
from app.models.candidate import Candidate
from app.models.match import MatchResult

pytestmark = pytest.mark.asyncio

async def test_persistence_new_candidate_insert():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c1 = await ingest_candidate(db, raw_text="Developer with new_test1@example.com", filename="res1.pdf")
        assert c1.id is not None
        assert c1.email == "new_test1@example.com"
    await test_engine.dispose()

async def test_persistence_email_match_update():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c1 = await ingest_candidate(db, raw_text="Developer with update_test@example.com", filename="res1.pdf")
        original_id = c1.id
        c2 = await ingest_candidate(db, raw_text="Senior Developer with update_test@example.com", filename="res2.pdf")
        assert c2.id == original_id
        assert c2.raw_text == "Senior Developer with update_test@example.com"
    await test_engine.dispose()

async def test_persistence_raw_text_hash_fallback_match():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c3 = await ingest_candidate(db, raw_text="Identical raw text without email fallback", filename="res3.pdf")
        c3_id = c3.id
        c4 = await ingest_candidate(db, raw_text="Identical raw text without email fallback", filename="res4.pdf")
        assert c4.id == c3_id
    await test_engine.dispose()

async def test_persistence_concurrent_duplicate_rejection():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c1 = await ingest_candidate(db, raw_text="Developer with concurrent_test@example.com", filename="res1.pdf")
        
        c_dup = Candidate(
            email="concurrent_test@example.com",
            raw_text="duplicate",
            raw_text_hash="dummy_hash"
        )
        db.add(c_dup)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()
    await test_engine.dispose()

async def test_match_endpoint_append_only():
    import httpx
    BASE_URL = "http://localhost:8000"
    
    with httpx.Client(base_url=BASE_URL) as client:
        res_cand = client.post("/api/v1/resumes/", json={
            "raw_text": "I am a persistent developer.",
            "filename": "cand_persist.pdf"
        })
        cand_id = res_cand.json()["candidate_id"]

        res_job = client.post("/api/v1/jobs/", json={
            "title": "Persistent Developer",
            "description": "We need a persistent developer.",
            "required_skills": [],
            "preferred_skills": []
        })
        job_id = res_job.json()["job_id"]

        # Call match endpoint first time
        payload = {"job_id": job_id, "candidate_ids": [cand_id]}
        client.post("/api/v1/matches/", json=payload)

        # Call match endpoint second time
        client.post("/api/v1/matches/", json=payload)

    # Check DB
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        stmt = select(MatchResult).where(MatchResult.job_id == job_id, MatchResult.candidate_id == cand_id)
        res = await db.execute(stmt)
        results = res.scalars().all()

        # Assert 2 distinct rows
        assert len(results) == 2
        assert results[0].id != results[1].id
        assert results[0].created_at != results[1].created_at
    await test_engine.dispose()

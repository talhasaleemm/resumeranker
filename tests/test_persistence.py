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
    import uuid
    unique_email = f"new_test1_{uuid.uuid4()}@example.com"
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c1 = await ingest_candidate(db, raw_text=f"Developer with {unique_email}", filename="res1.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        assert c1.id is not None
        assert c1.email == unique_email
    await test_engine.dispose()

async def test_persistence_email_match_update():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    import uuid
    unique_email = f"update_test_{uuid.uuid4()}@example.com"
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c1 = await ingest_candidate(db, raw_text=f"Developer with {unique_email}", filename="res1.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        original_id = c1.id
        c2 = await ingest_candidate(db, raw_text=f"Senior Developer with {unique_email}", filename="res2.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        assert c2.id == original_id
        assert c2.raw_text == f"Senior Developer with {unique_email}"
    await test_engine.dispose()

async def test_persistence_raw_text_hash_fallback_match():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    import uuid
    unique_text = f"Identical raw text without email fallback {uuid.uuid4()}"
    
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c3 = await ingest_candidate(db, raw_text=unique_text, filename="res3.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        c3_id = c3.id
        c4 = await ingest_candidate(db, raw_text=unique_text, filename="res4.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        assert c4.id == c3_id
    await test_engine.dispose()

async def test_persistence_concurrent_duplicate_rejection():
    """
    Test that concurrent insertions of the same candidate are rejected by database constraints.
    Uses a deterministic approach with threading.Barrier to ensure true concurrency.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.exc import IntegrityError
    from app.config import get_settings
    import uuid
    import threading
    import asyncio
    
    test_engine = create_async_engine(get_settings().database_url)
    unique_email = f"concurrent_{uuid.uuid4()}@example.com"
    
    # Barrier ensures both tasks start database operations simultaneously
    barrier = threading.Barrier(2)
    results = []
    
    async def try_ingest_with_barrier():
        """
        Attempt ingestion with synchronization barrier to force race condition.
        """
        try:
            async with AsyncSession(test_engine) as db:
                # Wait for both tasks to reach this point before proceeding
                await asyncio.get_event_loop().run_in_executor(None, barrier.wait)
                
                # Both tasks now attempt the insert simultaneously
                candidate = await ingest_candidate(
                    db, 
                    raw_text=f"Developer with {unique_email}", 
                    filename="res1.pdf",
                    recruiter_id="00000000-0000-0000-0000-000000000000"
                )
                cid = candidate.id
                await db.commit()
                return ("success", cid)
        except IntegrityError as e:
            return ("integrity_error", str(e))
        except Exception as e:
            return ("other_error", str(e))
    
    # Run both tasks concurrently
    task_results = await asyncio.gather(
        try_ingest_with_barrier(),
        try_ingest_with_barrier(),
        return_exceptions=False
    )
    
    # One should succeed, one should fail with IntegrityError
    successes = [r for r in task_results if r[0] == "success"]
    integrity_errors = [r for r in task_results if r[0] == "integrity_error"]
    
    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {task_results}"
    assert len(integrity_errors) == 1, f"Expected 1 IntegrityError, got {len(integrity_errors)}: {task_results}"
    
    await test_engine.dispose()

async def test_match_results_append_only_in_db():
    from app.main import app
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from app.config import get_settings
    from app.database import get_db

    app.state.limiter.enabled = False

    settings = get_settings()
    test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session
            await session.commit()

    from app.models.recruiter import Recruiter
    async def override_get_current_active_recruiter():
        import uuid
        return Recruiter(id=uuid.UUID("00000000-0000-0000-0000-000000000000"), email="test@test.com", is_active=True)

    app.dependency_overrides[get_db] = override_get_db
    from app.services.auth_service import get_current_active_recruiter
    app.dependency_overrides[get_current_active_recruiter] = override_get_current_active_recruiter
    
    # 1. Ingest candidate via Python API directly
    from app.services.candidate_service import ingest_candidate

    import uuid
    unique_text = f"I am a persistent developer. {uuid.uuid4()}"
    async with TestingSessionLocal() as db:
        c = await ingest_candidate(db, raw_text=unique_text, filename="cand_persist.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        await db.commit()
        await db.refresh(c)
        cand_id = str(c.id)

    with TestClient(app) as client:
        res_job = client.post("/api/v1/jobs/", json={
            "title": "Persistent Developer",
            "description": "We need a persistent developer.",
            "required_skills": [],
            "preferred_skills": []
        })
        job_id = res_job.json()["job_id"]

        # Call match endpoint first time
        payload = {"job_id": job_id, "candidate_ids": [cand_id]}
        res1 = client.post("/api/v1/matches/", json=payload)
        assert res1.status_code == 202

        # Call match endpoint second time
        res2 = client.post("/api/v1/matches/", json=payload)
        assert res2.status_code == 202

    # Check DB
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        stmt = select(MatchResult).where(MatchResult.job_id == job_id, MatchResult.candidate_id == cand_id)
        res = await db.execute(stmt)
        results = res.scalars().all()

        assert len(results) == 1, "Expected exactly 1 match result due to ON CONFLICT DO UPDATE"
    await test_engine.dispose()
    app.dependency_overrides.clear()

async def test_ciphertext_at_rest():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    import uuid
    unique_email = f"cipher_test_{uuid.uuid4()}@example.com"
    unique_text = f"Ciphertext raw body with {unique_email}"
    
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c1 = await ingest_candidate(db, raw_text=unique_text, filename="cipher.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        assert c1.id is not None
        
        # Query raw table columns bypassing the ORM properties
        stmt = text("SELECT email_encrypted, raw_text_encrypted FROM candidates WHERE id = :cid")
        result = await db.execute(stmt, {"cid": c1.id})
        row = result.fetchone()
        
        # Assert the database actually contains ciphertext, not plaintext
        raw_email_db = row[0]
        raw_text_db = row[1]
        
        assert raw_email_db is not None
        assert raw_text_db is not None
        assert unique_email not in raw_email_db
        assert unique_text not in raw_text_db
        assert raw_email_db.startswith("gAAAAA") # Fernet tokens start with gAAAAA
        assert raw_text_db.startswith("gAAAAA")
        
    await test_engine.dispose()

async def test_raw_text_hash_stability_across_reencryption():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    import uuid
    
    unique_text = f"Stable hash resume body {uuid.uuid4()}"
    
    test_engine = create_async_engine(get_settings().database_url)
    async with AsyncSession(test_engine) as db:
        c1 = await ingest_candidate(db, raw_text=unique_text, filename="stable1.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        first_hash = c1.raw_text_hash
        
        # Bypassing ORM to get the exact raw_text_encrypted string
        stmt = text("SELECT raw_text_encrypted FROM candidates WHERE id = :cid")
        res1 = await db.execute(stmt, {"cid": c1.id})
        first_ciphertext = res1.scalar()
        
        # Re-ingest exact same candidate to trigger an update/re-encryption
        c2 = await ingest_candidate(db, raw_text=unique_text, filename="stable2.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        assert c2.id == c1.id # Dedup worked
        
        # The hash should be identical because it is computed from plaintext before encryption
        assert c2.raw_text_hash == first_hash
        
        # The new ciphertext must be different because Fernet generates a new IV on every encrypt call
        res2 = await db.execute(stmt, {"cid": c2.id})
        second_ciphertext = res2.scalar()
        
        assert first_ciphertext != second_ciphertext
        
    await test_engine.dispose()

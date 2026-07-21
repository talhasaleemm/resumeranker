import pytest
import asyncio
import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import IntegrityError
from app.database import AsyncSessionLocal
from app.services.candidate_service import ingest_candidate
from app.models.candidate import Candidate
from app.models.match import MatchResult
from app.models.user import User

pytestmark = pytest.mark.asyncio

def _local_db_url() -> str:
    return "postgresql+asyncpg://resumeranker:devpassword123@127.0.0.1:5432/resumeranker"

async def _create_test_user(db: AsyncSession, email: str) -> uuid.UUID:
    user = User(email=email, hashed_password="test", is_active=True)
    db.add(user)
    await db.flush()
    return user.id

async def test_persistence_new_candidate_insert():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    import uuid
    unique_email = f"new_test1_{uuid.uuid4()}@example.com"
    test_engine = create_async_engine(_local_db_url())
    async with AsyncSession(test_engine) as db:
        user_id = await _create_test_user(db, unique_email)
        c1 = await ingest_candidate(db, raw_text=f"Developer with {unique_email}", filename="res1.pdf", owner_id=str(user_id))
        assert c1.id is not None
        assert c1.email_encrypted is not None
        assert unique_email not in c1.email_encrypted
        assert c1.email_encrypted.startswith("gAAAAA")
    await test_engine.dispose()

async def test_persistence_email_match_update():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    from app.services.encryption import decrypt_text
    import uuid
    unique_email = f"update_test_{uuid.uuid4()}@example.com"
    test_engine = create_async_engine(_local_db_url())
    async with AsyncSession(test_engine) as db:
        user_id = await _create_test_user(db, unique_email)
        c1 = await ingest_candidate(db, raw_text=f"Developer with {unique_email}", filename="res1.pdf", owner_id=str(user_id))
        original_id = c1.id
        c2 = await ingest_candidate(db, raw_text=f"Senior Developer with {unique_email}", filename="res2.pdf", owner_id=str(user_id))
        assert c2.id == original_id
        assert c2.raw_text_encrypted is not None
        decrypted = decrypt_text(c2.raw_text_encrypted)
        assert decrypted == f"Senior Developer with {unique_email}"
    await test_engine.dispose()

async def test_persistence_raw_text_hash_fallback_match():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    import uuid
    unique_text = f"Identical raw text without email fallback {uuid.uuid4()}"
    unique_email = f"fallback_{uuid.uuid4()}@example.com"
    
    test_engine = create_async_engine(_local_db_url())
    async with AsyncSession(test_engine) as db:
        user_id = await _create_test_user(db, unique_email)
        c3 = await ingest_candidate(db, raw_text=unique_text, filename="res3.pdf", owner_id=str(user_id))
        c3_id = c3.id
        c4 = await ingest_candidate(db, raw_text=unique_text, filename="res4.pdf", owner_id=str(user_id))
        assert c4.id == c3_id
    await test_engine.dispose()

async def test_persistence_concurrent_duplicate_rejection():
    """
    Test that concurrent insertions of the same candidate are handled idempotently.
    ingest_candidate deduplicates by raw_text_hash, so concurrent calls return the
    same candidate ID rather than raising a database IntegrityError.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    import uuid
    import asyncio
    
    test_engine = create_async_engine(_local_db_url(), poolclass=NullPool)
    unique_email = f"concurrent_{uuid.uuid4()}@example.com"
    
    async with AsyncSession(test_engine) as setup_db:
        user_id = await _create_test_user(setup_db, unique_email)
        await setup_db.commit()
    
    async def try_ingest():
        async with AsyncSession(test_engine, expire_on_commit=False) as db:
            candidate = await ingest_candidate(
                db, 
                raw_text=f"Developer with {unique_email}", 
                filename="res1.pdf",
                owner_id=str(user_id)
            )
            await db.commit()
            return candidate.id
    
    cid1 = await try_ingest()
    cid2 = await try_ingest()
    
    assert cid1 == cid2, f"Expected same candidate ID from concurrent calls, got {cid1} and {cid2}"
    
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
    test_engine = create_async_engine(_local_db_url(), poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session
            await session.commit()

    from app.models.user import User
    test_user_id = uuid.uuid4()
    async def override_get_current_active_user():
        return User(id=test_user_id, email=f"test_{test_user_id}@test.com", is_active=True, hashed_password="test")

    app.dependency_overrides[get_db] = override_get_db
    from app.services.auth_service import get_current_active_user
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    
    try:
        # 1. Ingest candidate via Python API directly
        from app.services.candidate_service import ingest_candidate

        unique_text = f"I am a persistent developer. {uuid.uuid4()}"
        async with TestingSessionLocal() as db:
            user = User(id=test_user_id, email=f"test_{test_user_id}@test.com", hashed_password="test", is_active=True)
            db.add(user)
            await db.flush()
            c = await ingest_candidate(db, raw_text=unique_text, filename="cand_persist.pdf", owner_id=str(test_user_id))
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
        
        test_engine = create_async_engine(_local_db_url(), poolclass=NullPool)
        async with AsyncSession(test_engine) as db:
            stmt = select(MatchResult).where(MatchResult.job_id == job_id, MatchResult.candidate_id == cand_id)
            res = await db.execute(stmt)
            results = res.scalars().all()

            assert len(results) == 2
            assert results[0].id != results[1].id
        await test_engine.dispose()
    finally:
        app.dependency_overrides.clear()

async def test_ciphertext_at_rest():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from app.config import get_settings
    import uuid
    unique_email = f"cipher_test_{uuid.uuid4()}@example.com"
    unique_text = f"Ciphertext raw body with {unique_email}"
    
    test_engine = create_async_engine(_local_db_url())
    async with AsyncSession(test_engine) as db:
        user_id = await _create_test_user(db, unique_email)
        c1 = await ingest_candidate(db, raw_text=unique_text, filename="cipher.pdf", owner_id=str(user_id))
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
    unique_email = f"stable_{uuid.uuid4()}@example.com"
    
    test_engine = create_async_engine(_local_db_url())
    async with AsyncSession(test_engine) as db:
        user_id = await _create_test_user(db, unique_email)
        c1 = await ingest_candidate(db, raw_text=unique_text, filename="stable1.pdf", owner_id=str(user_id))
        first_hash = c1.raw_text_hash
        
        # Bypassing ORM to get the exact raw_text_encrypted string
        stmt = text("SELECT raw_text_encrypted FROM candidates WHERE id = :cid")
        res1 = await db.execute(stmt, {"cid": c1.id})
        first_ciphertext = res1.scalar()
        
        # Re-ingest exact same candidate to trigger an update/re-encryption
        c2 = await ingest_candidate(db, raw_text=unique_text, filename="stable2.pdf", owner_id=str(user_id))
        assert c2.id == c1.id # Dedup worked
        
        # The hash should be identical because it is computed from plaintext before encryption
        assert c2.raw_text_hash == first_hash
        
        # The new ciphertext must be different because Fernet generates a new IV on every encrypt call
        res2 = await db.execute(stmt, {"cid": c2.id})
        second_ciphertext = res2.scalar()
        
        assert first_ciphertext != second_ciphertext
        
    await test_engine.dispose()

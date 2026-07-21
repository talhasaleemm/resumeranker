import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.main import app
from app.config import get_settings
from app.database import get_db
from app.services.candidate_service import ingest_candidate
from app.models.job import Job
from app.models.user import User
from app.services.auth_service import get_current_active_user

# Disable rate limiter for test client
app.state.limiter.enabled = False

def _local_db_url() -> str:
    return "postgresql+asyncpg://resumeranker:devpassword123@127.0.0.1:5432/resumeranker"

async def override_get_db():
    engine = create_async_engine(_local_db_url(), poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    async with TestingSessionLocal() as session:
        yield session
        await session.commit()
    await engine.dispose()

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
async def setup_data():
    engine = create_async_engine(_local_db_url(), poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    async with TestingSessionLocal() as session:
        test_user = User(email=f"test_{uuid.uuid4()}@test.com", hashed_password="test", is_active=True)
        session.add(test_user)
        await session.flush()
        user_id = str(test_user.id)
        
        app.dependency_overrides[get_current_active_user] = lambda: test_user
        
        cand1 = await ingest_candidate(session, raw_text=f"I am a backend developer writing Python and React code for my web apps. I have a B.S. in Computer Science. {uuid.uuid4()}", filename="cand1.pdf", owner_id=user_id, recruiter_id="00000000-0000-0000-0000-000000000000")
        cand2 = await ingest_candidate(session, raw_text=f"I program in Java and Spring Boot. {uuid.uuid4()}", filename="cand2.pdf", owner_id=user_id, recruiter_id="00000000-0000-0000-0000-000000000000")
        
        job = Job(
            title="Python Developer",
            description="We need a Python developer who knows React.",
            required_skills=["python", "react"],
            preferred_skills=[],
            owner_id=test_user.id,
            recruiter_id=uuid.UUID('00000000-0000-0000-0000-000000000000')
        )
        session.add(job)
        await session.commit()
        
        _ = test_user.id
        _ = cand1.id
        _ = cand2.id
        _ = job.id
        
        cand1_id = str(cand1.id)
        cand2_id = str(cand2.id)
        job_id = str(job.id)
        
        ret_val = job_id, [cand1_id, cand2_id]
    await engine.dispose()
    return ret_val

@pytest.mark.asyncio
async def test_match_endpoint_success(setup_data):
    """Test standard valid request returns 202 and matches schema."""
    job_id, candidate_ids = setup_data
    payload = {
        "job_id": job_id,
        "candidate_ids": candidate_ids,
        "weights": {
            "tfidf": 0.5,
            "bm25": 0.3,
            "skills": 0.2,
            "vector": 0.0
        }
    }
    
    with TestClient(app) as client:
        response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert "task_id" in data

@pytest.mark.asyncio
async def test_match_endpoint_weights_not_summing_to_1(setup_data):
    job_id, candidate_ids = setup_data
    payload = {
        "job_id": job_id,
        "candidate_ids": candidate_ids,
        "weights": {
            "tfidf": 0.5,
            "bm25": 0.5,
            "skills": 0.5,
            "vector": 0.0
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_match_endpoint_missing_weight_key(setup_data):
    job_id, candidate_ids = setup_data
    # Deliberately omit 'vector' key — still missing a required field
    payload = {
        "job_id": job_id,
        "candidate_ids": candidate_ids,
        "weights": {
            "tfidf": 0.5,
            "bm25": 0.5
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_match_endpoint_negative_weight(setup_data):
    job_id, candidate_ids = setup_data
    payload = {
        "job_id": job_id,
        "candidate_ids": candidate_ids,
        "weights": {
            "tfidf": -0.5,
            "bm25": 1.5,
            "skills": 0.0,
            "vector": 0.0
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_match_endpoint_too_many_candidates():
    """
    Verifies that providing over 100 candidate IDs is rejected with 422.
    """
    from app.models.user import User
    test_user = User(id=uuid.UUID('00000000-0000-0000-0000-000000000000'), email="test@test.com", hashed_password="test", is_active=True)
    app.dependency_overrides[get_current_active_user] = lambda: test_user
    try:
        payload = {
            "job_id": str(uuid.UUID('00000000-0000-0000-0000-000000000000')),
            "candidate_ids": [str(uuid.UUID('00000000-0000-0000-0000-000000000000')) for _ in range(101)]
        }
        with TestClient(app) as client:
            response = client.post("/api/v1/matches/", json=payload)
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

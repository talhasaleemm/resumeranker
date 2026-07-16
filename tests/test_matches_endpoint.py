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
from app.models.recruiter import Recruiter
from app.services.auth_service import get_current_active_recruiter

# Disable rate limiter for test client
app.state.limiter.enabled = False

# Override get_db to use NullPool to prevent event loop issues across TestClient requests
settings = get_settings()
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session
        await session.commit()

async def override_get_current_active_recruiter():
    return Recruiter(id=uuid.UUID('00000000-0000-0000-0000-000000000000'), email="test@test.com", is_active=True)

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_active_recruiter] = override_get_current_active_recruiter

@pytest.fixture
async def setup_data():
    async with TestingSessionLocal() as session:
        # Get the recruiter_id from the dependency override
        recruiter = await override_get_current_active_recruiter()
        recruiter_id = str(recruiter.id)
        
        cand1 = await ingest_candidate(session, raw_text=f"I am a backend developer writing Python and React code for my web apps. I have a B.S. in Computer Science. {uuid.uuid4()}", filename="cand1.pdf", recruiter_id=recruiter_id)
        cand2 = await ingest_candidate(session, raw_text=f"I program in Java and Spring Boot. {uuid.uuid4()}", filename="cand2.pdf", recruiter_id=recruiter_id)
        
        job = Job(
            title="Python Developer",
            description="We need a Python developer who knows React.",
            required_skills=["python", "react"],
            preferred_skills=[],
            recruiter_id=recruiter.id
        )
        session.add(job)
        await session.flush()
        
        cand1_id = str(cand1.id)
        cand2_id = str(cand2.id)
        job_id = str(job.id)
        await session.commit()
        
        return job_id, [cand1_id, cand2_id]

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
            "skills": 0.2
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
            "skills": 0.5
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_match_endpoint_missing_weight_key(setup_data):
    job_id, candidate_ids = setup_data
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
            "skills": 0.0
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
    payload = {
        "job_id": str(uuid.UUID('00000000-0000-0000-0000-000000000000')),
        "candidate_ids": [str(uuid.UUID('00000000-0000-0000-0000-000000000000')) for _ in range(101)]
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 422

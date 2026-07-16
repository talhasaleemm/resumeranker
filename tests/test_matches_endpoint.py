import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.config import get_settings
from app.database import get_db

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

app.dependency_overrides[get_db] = override_get_db

def setup_data():
    with TestClient(app) as client:
        # Ingest candidates
        res_cand1 = client.post("/api/v1/resumes/", json={
            "raw_text": "I am a backend developer writing Python and React code for my web apps. I have a B.S. in Computer Science.",
            "filename": "cand1.pdf"
        })
        cand1_id = res_cand1.json()["candidate_id"]

        res_cand2 = client.post("/api/v1/resumes/", json={
            "raw_text": "I program in Java and Spring Boot.",
            "filename": "cand2.pdf"
        })
        cand2_id = res_cand2.json()["candidate_id"]

        # Create job
        res_job = client.post("/api/v1/jobs/", json={
            "title": "Python Developer",
            "description": "We need a Python developer who knows React.",
            "required_skills": ["python", "react"],
            "preferred_skills": []
        })
        job_id = res_job.json()["job_id"]

        return job_id, [cand1_id, cand2_id]

def test_match_endpoint_success():
    """Test standard valid request returns 200 and matches schema."""
    job_id, candidate_ids = setup_data()
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
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "matches" in data
    assert len(data["matches"]) == 2
    
    # Check structure
    match = data["matches"][0]
    assert "candidate_id" in match
    assert "final_score" in match
    assert "explanation_log" in match
    
    explanation = match["explanation_log"]
    assert "tags_detected" in explanation
    assert "tag_evidence" in explanation


def test_match_endpoint_weights_not_summing_to_1():
    job_id, candidate_ids = setup_data()
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


def test_match_endpoint_missing_weight_key():
    job_id, candidate_ids = setup_data()
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


def test_match_endpoint_negative_weight():
    job_id, candidate_ids = setup_data()
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


def test_match_endpoint_single_candidate_with_overlap():
    job_id, candidate_ids = setup_data()
    payload = {
        "job_id": job_id,
        "candidate_ids": [candidate_ids[0]],
        "weights": {
            "tfidf": 0.4,
            "bm25": 0.4,
            "skills": 0.2
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 200
    assert response.json()["matches"][0]["bm25_score"] == 1.0


def test_match_endpoint_single_candidate_without_overlap():
    job_id, candidate_ids = setup_data()
    payload = {
        "job_id": job_id,
        "candidate_ids": [candidate_ids[1]],
        "weights": {
            "tfidf": 0.4,
            "bm25": 0.4,
            "skills": 0.2
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 200
    assert response.json()["matches"][0]["bm25_score"] == 0.0


def test_match_endpoint_accepts_repeated_calls():
    job_id, candidate_ids = setup_data()
    payload = {
        "job_id": job_id,
        "candidate_ids": [candidate_ids[0]]
    }
    with TestClient(app) as client:
        res1 = client.post("/api/v1/matches/", json=payload)
        assert res1.status_code == 200
        res2 = client.post("/api/v1/matches/", json=payload)
        assert res2.status_code == 200

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.config import get_settings
from app.database import get_db
from app.main import app

async def override_get_db():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
    async with TestingSessionLocal() as session:
        yield session
    await engine.dispose()

@pytest.fixture(autouse=True)
def setup_db_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

def test_full_e2e_recruiter_workflow():
    # Set rate limiting off for tests
    app.state.limiter.enabled = False

    with TestClient(app) as client:
        # 1. Register Recruiter
        email = f"e2e_pytest_{uuid.uuid4()}@test.com"
        password = "SecurePassword123!"
        reg_resp = client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password
        })
        # Note: register endpoint returns 201 Created on success
        assert reg_resp.status_code == 201

        # 2. Login
        login_resp = client.post("/api/v1/auth/login", data={
            "username": email,
            "password": password
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Upload Resume
        with open("tests/sample_resumes/resume_backend_engineer.pdf", "rb") as f:
            upload_resp = client.post(
                "/api/v1/resumes/",
                files={"file": ("resume_backend_engineer.pdf", f, "application/pdf")},
                headers=headers
            )
        assert upload_resp.status_code == 202
        upload_task_id = upload_resp.json()["task_id"]

        # 4. Poll Upload Task (Eager Celery means it executes immediately)
        task_resp = client.get(f"/api/v1/tasks/{upload_task_id}", headers=headers)
        assert task_resp.status_code == 200
        task_data = task_resp.json()
        assert task_data["status"] == "success"
        candidate_id = task_data["result"]["candidate_id"]

        # 5. Create Job
        job_resp = client.post(
            "/api/v1/jobs/",
            json={
                "title": "Senior Python Backend Engineer",
                "description": "We are looking for a Senior Backend Engineer with experience in Python, FastAPI, Docker, and PostgreSQL.",
                "required_skills": ["python", "fastapi", "docker", "postgresql"],
                "preferred_skills": []
            },
            headers=headers
        )
        assert job_resp.status_code == 200
        job_id = job_resp.json()["job_id"]

        # 6. Run Match
        match_resp = client.post(
            "/api/v1/matches/",
            json={
                "job_id": job_id,
                "candidate_ids": [candidate_id],
                "weights": {
                    "tfidf": 0.4,
                    "bm25": 0.4,
                    "skills": 0.2,
                    "vector": 0.0
                }
            },
            headers=headers
        )
        assert match_resp.status_code == 202
        match_task_id = match_resp.json()["task_id"]

        # 7. Poll Match Task and assert non-zero score
        match_task_resp = client.get(f"/api/v1/tasks/{match_task_id}", headers=headers)
        assert match_task_resp.status_code == 200
        match_data = match_task_resp.json()
        assert match_data["status"] == "success"
        
        matches = match_data["result"]["matches"]
        assert len(matches) == 1
        aisha_match = matches[0]
        assert aisha_match["candidate_name"] == "Aisha Raza"
        
        # Calculate expected final score from all 4 components (vector=0.0 so no change vs Phase 11)
        tfidf_contrib = aisha_match["tfidf_score"] * 40.0
        bm25_contrib = aisha_match["bm25_score"] * 40.0
        skill_contrib = aisha_match["skill_score"] * 20.0
        vector_contrib = aisha_match.get("vector_score", 0.0) * 0.0  # weight=0.0
        expected_final = round(tfidf_contrib + bm25_contrib + skill_contrib + vector_contrib, 2)
        
        assert aisha_match["final_score"] == pytest.approx(expected_final, abs=0.01)
        assert aisha_match["skill_score"] == 1.0
        assert aisha_match["tfidf_score"] > 0.0
        assert aisha_match["bm25_score"] > 0.0

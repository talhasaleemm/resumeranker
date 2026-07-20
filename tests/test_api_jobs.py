import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.models.job import Job
import uuid
from app.models.user import User
from app.services.auth_service import get_current_active_user

async def override_get_current_active_user():
    return User(id=uuid.UUID('00000000-0000-0000-0000-000000000000'), email="test@test.com", is_active=True, hashed_password="test")

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    yield
    app.dependency_overrides.clear()

def test_job_create_description_too_short():
    """
    Verifies that a job description under 10 chars is rejected with 422.
    If the min_length constraint were removed, this would vacantly pass.
    """
    with TestClient(app) as client:
        payload = {
            "title": "Backend Dev",
            "description": "Short",
            "required_skills": ["Python"]
        }
        response = client.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422

def test_job_create_description_too_long():
    """
    Verifies that a job description over 50,000 chars is rejected with 422.
    If the max_length constraint were removed, this would vacantly pass and bloat the DB.
    """
    with TestClient(app) as client:
        payload = {
            "title": "Backend Dev",
            "description": "A" * 50001,
            "required_skills": ["Python"]
        }
        response = client.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422

def test_job_create_too_many_required_skills():
    """
    Verifies that providing over 100 required skills is rejected with 422.
    If the max_length array constraint were removed, this would vacantly pass.
    """
    with TestClient(app) as client:
        payload = {
            "title": "Backend Dev",
            "description": "Valid job description here.",
            "required_skills": ["Skill"] * 101
        }
        response = client.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422

import pytest
from fastapi.testclient import TestClient
from app.main import app

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

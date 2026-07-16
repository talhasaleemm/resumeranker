import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.recruiter import Recruiter
from app.services.auth_service import get_current_active_recruiter
import uuid

async def override_get_current_active_recruiter():
    return Recruiter(id=uuid.UUID('00000000-0000-0000-0000-000000000000'), email="test@test.com", is_active=True)

app.dependency_overrides[get_current_active_recruiter] = override_get_current_active_recruiter

def test_resume_upload_max_length():
    """
    Verifies that a resume payload exceeding the 10MB limit is rejected.
    """
    with TestClient(app) as client:
        # Create a dummy file that exceeds 10MB (10 * 1024 * 1024)
        dummy_content = b"0" * (10 * 1024 * 1024 + 1)
        files = {"file": ("test.pdf", dummy_content, "application/pdf")}
        response = client.post("/api/v1/resumes/", files=files)
        assert response.status_code == 413

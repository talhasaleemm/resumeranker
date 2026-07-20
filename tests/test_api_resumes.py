import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
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

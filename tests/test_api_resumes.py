import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_resume_upload_max_length():
    """
    Verifies that a resume payload exceeding the 100,000 character limit is rejected with 422.
    This protects the NLP pipeline from Out-Of-Memory/DoS attacks. If the max_length constraint
    on ResumeUpload.raw_text were removed, this test would fail because the payload would be accepted.
    """
    with TestClient(app) as client:
        payload = {
            "raw_text": "A" * 100001,
            "filename": "test.txt"
        }
        response = client.post("/api/v1/resumes/", json=payload)
        assert response.status_code == 422

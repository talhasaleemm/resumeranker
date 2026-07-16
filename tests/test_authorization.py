import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_data_isolation_between_recruiters():
    from app.main import app
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        email_a = f"recruiter_a_{uuid.uuid4()}@test.com"
        email_b = f"recruiter_b_{uuid.uuid4()}@test.com"
        
        # Register recruiter A
        await ac.post("/api/v1/auth/register", json={
            "email": email_a,
            "password": "securepassword123"
        })
        resp_a = await ac.post("/api/v1/auth/login", data={
            "username": email_a,
            "password": "securepassword123"
        })
        token_a = resp_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Register recruiter B
        await ac.post("/api/v1/auth/register", json={
            "email": email_b,
            "password": "securepassword123"
        })
        resp_b = await ac.post("/api/v1/auth/login", data={
            "username": email_b,
            "password": "securepassword123"
        })
        token_b = resp_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Recruiter A creates a job
        job_payload_a = {
            "title": "Data Scientist",
            "description": "A very descriptive job description for data science.",
            "required_skills": ["Python", "SQL"]
        }
        create_job_resp = await ac.post("/api/v1/jobs/", json=job_payload_a, headers=headers_a)
        assert create_job_resp.status_code == 200
        job_id_a = create_job_resp.json()["job_id"]

        # Recruiter A uploads a candidate
        dummy_content = b"Candidate A resume content."
        files = {"file": ("cand_a.pdf", dummy_content, "application/pdf")}
        create_cand_resp = await ac.post("/api/v1/resumes/", files=files, headers=headers_a)
        assert create_cand_resp.status_code == 202

        match_payload = {
            "job_id": job_id_a,
            "candidate_ids": [str(uuid.UUID('00000000-0000-0000-0000-000000000000'))]
        }
        
        # Recruiter B tries to access Recruiter A's job
        match_resp_b = await ac.post("/api/v1/matches/", json=match_payload, headers=headers_b)
        assert match_resp_b.status_code == 403, f"Expected 403, got {match_resp_b.status_code}: {match_resp_b.text}"
        assert match_resp_b.json()["detail"] == "Not authorized to access this job"

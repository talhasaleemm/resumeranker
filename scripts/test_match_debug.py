import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.recruiter import Recruiter
from app.services.auth_service import get_current_active_recruiter
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.config import get_settings
from app.services.candidate_service import ingest_candidate
import uuid

async def run():
    app.state.limiter.enabled = False
    
    settings = get_settings()
    test_engine_insert = create_async_engine(settings.database_url)
    async with AsyncSession(test_engine_insert) as db:
        unique_text = f"I am a persistent developer. {uuid.uuid4()}"
        c = await ingest_candidate(db, raw_text=unique_text, filename="cand_persist.pdf", recruiter_id="00000000-0000-0000-0000-000000000000")
        cand_id = str(c.id)
    await test_engine_insert.dispose()

    async def override_get_current_active_recruiter():
        return Recruiter(id=uuid.UUID('00000000-0000-0000-0000-000000000000'), email="test@test.com", is_active=True)

    app.dependency_overrides[get_current_active_recruiter] = override_get_current_active_recruiter

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_job = await client.post("/api/v1/jobs/", json={
            "title": "Persistent Developer",
            "description": "We need a persistent developer.",
            "required_skills": [],
            "preferred_skills": []
        })
        job_id = res_job.json()["job_id"]

        payload = {"job_id": job_id, "candidate_ids": [cand_id]}
        res_match1 = await client.post("/api/v1/matches/", json=payload)
        print("MATCH 1:", res_match1.status_code, res_match1.json())
        res_match2 = await client.post("/api/v1/matches/", json=payload)
        print("MATCH 2:", res_match2.status_code, res_match2.json())

if __name__ == '__main__':
    asyncio.run(run())

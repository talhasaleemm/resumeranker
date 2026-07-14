"""
tests/test_rate_limiting.py — Rate limiting tests (Phase 6B-2b).

These tests run against an isolated FastAPI app instance with rate limiting
enabled, so they don't interfere with or get interfered with by the rest
of the test suite.
"""
import time
import uuid

from fastapi import FastAPI, Request, Body
from fastapi.testclient import TestClient
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings


def _custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    from fastapi.responses import JSONResponse
    response = JSONResponse(
        {"error": f"Rate limit exceeded: {exc.detail}"},
        status_code=429,
    )
    app_limiter = request.app.state.limiter
    try:
        view_limit = getattr(request.state, "view_rate_limit", None)
        if app_limiter and view_limit is not None:
            window_stats = app_limiter.limiter.get_window_stats(view_limit[0], *view_limit[1])
            reset_in = max(1, 1 + window_stats[0])
            response.headers["Retry-After"] = str(int(reset_in - time.time()))
    except Exception:
        pass
    return response


def _create_test_app() -> tuple[FastAPI, Limiter]:
    app = FastAPI()
    settings = get_settings()
    settings.rate_limit_enabled = True

    def _key_func(request: Request) -> str:
        return get_remote_address(request)

    limiter = Limiter(key_func=_key_func, headers_enabled=False)
    limiter._default_limits = ["60/minute"]
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_handler)

    resume_router = FastAPI().router
    job_router = FastAPI().router
    match_router = FastAPI().router

    class ResumeUpload(BaseModel):
        raw_text: str
        filename: str = "unknown"

    @resume_router.post("/", tags=["resumes"])
    @limiter.limit("10/minute")
    async def upload_resume(request: Request, upload: ResumeUpload):
        return {"status": "success", "candidate_id": str(uuid.uuid4())}

    @job_router.post("/", tags=["jobs"])
    @limiter.limit("10/minute")
    async def create_job(request: Request):
        return {"status": "success", "job_id": str(uuid.uuid4())}

    @match_router.post("/", tags=["matches"])
    @limiter.limit("60/minute")
    async def match_candidates(request: Request, job_id: str = Body(...), candidate_ids: list[str] = Body(...)):
        return {"status": "success", "matches": []}

    app.include_router(resume_router, prefix="/api/v1/resumes")
    app.include_router(job_router, prefix="/api/v1/jobs")
    app.include_router(match_router, prefix="/api/v1/matches")

    return app, limiter


def test_upload_rate_limit_triggers_429():
    app, limiter = _create_test_app()
    client = TestClient(app)

    for _ in range(10):
        resp = client.post("/api/v1/resumes/", json={"raw_text": "x", "filename": "t.pdf"})
        assert resp.status_code == 200

    resp = client.post("/api/v1/resumes/", json={"raw_text": "x", "filename": "t.pdf"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_job_creation_rate_limit_triggers_429():
    app, limiter = _create_test_app()
    client = TestClient(app)

    for _ in range(10):
        resp = client.post("/api/v1/jobs/")
        assert resp.status_code == 200

    resp = client.post("/api/v1/jobs/")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_match_rate_limit_triggers_429():
    app, limiter = _create_test_app()
    client = TestClient(app)

    payload = {"job_id": str(uuid.uuid4()), "candidate_ids": [str(uuid.uuid4())]}
    for _ in range(60):
        resp = client.post("/api/v1/matches/", json=payload)
        assert resp.status_code == 200

    resp = client.post("/api/v1/matches/", json=payload)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_resets_after_window():
    app, limiter = _create_test_app()
    limiter.reset()

    client = TestClient(app)

    for _ in range(10):
        resp = client.post("/api/v1/resumes/", json={"raw_text": "x", "filename": "t.pdf"})
        assert resp.status_code == 200

    resp = client.post("/api/v1/resumes/", json={"raw_text": "x", "filename": "t.pdf"})
    assert resp.status_code == 429

    time.sleep(61)

    resp = client.post("/api/v1/resumes/", json={"raw_text": "x", "filename": "t.pdf"})
    assert resp.status_code == 200

"""
app/main.py — ResumeRanker FastAPI application entry point.

Phase 0: Health check + router registration skeleton.
Phase 6B-2b: Rate limiting via slowapi.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1 import resumes, jobs, matches, tasks, auth, job_histories
from app.config import get_settings
from app.rate_limiter import limiter, _custom_rate_limit_handler

settings = get_settings()
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG if not settings.is_production else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown logic."""
    logger.info("=== ResumeRanker starting up (env=%s) ===", settings.app_env)

    # Seed a demo user for local development so the frontend can log in
    # and obtain a real JWT without manual registration. Never runs in prod.
    if not settings.is_production and settings.dev_seed_demo_recruiter:
        from sqlalchemy import select

        from app.database import AsyncSessionLocal
        from app.models.user import User
        from app.services.auth_service import get_password_hash

        try:
            async with AsyncSessionLocal() as session:
                existing = await session.scalar(
                    select(User).where(
                        User.email == settings.dev_demo_recruiter_email
                    )
                )
                if existing is None:
                    session.add(
                        User(
                            email=settings.dev_demo_recruiter_email,
                            hashed_password=get_password_hash(
                                settings.dev_demo_recruiter_password
                            ),
                        )
                    )
                    await session.commit()
                    logger.info(
                        "Seeded demo user %s for local development",
                        settings.dev_demo_recruiter_email,
                    )
        except Exception as exc:  # pragma: no cover - best effort seeding
            logger.warning("Demo user seeding skipped: %s", exc)

    yield
    logger.info("=== ResumeRanker shutting down ===")


app = FastAPI(
    title="ResumeRanker API",
    description=(
        "AI-assisted resume parsing and candidate-matching platform. "
        "Parses PDF/DOCX resumes, extracts structured profiles, "
        "and ranks candidates against job descriptions using NLP-based matching."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.state.limiter = limiter

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_handler)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Log every request with timing."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.debug(
        "%s %s -> %d (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
API_V1_PREFIX = "/api/v1"

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(resumes.router, prefix=API_V1_PREFIX)
app.include_router(jobs.router, prefix=API_V1_PREFIX)
app.include_router(job_histories.router, prefix=API_V1_PREFIX)
app.include_router(matches.router, prefix=API_V1_PREFIX)
app.include_router(tasks.router, prefix=API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Health & root
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"], summary="Health check")
async def health_check():
    """
    Liveness probe — returns 200 if the app is running.
    Docker healthcheck and load balancers use this.
    """
    return {
        "status": "ok",
        "version": "0.1.0",
        "env": settings.app_env,
    }


@app.get("/", tags=["root"], summary="API root")
async def root():
    return {
        "message": "Welcome to ResumeRanker API",
        "docs": "/docs",
        "health": "/health",
        "version": "0.1.0",
    }


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )

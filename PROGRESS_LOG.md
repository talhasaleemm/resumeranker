# PROGRESS_LOG.md — ResumeRanker Build Progress

---

## Phase 0 — Repo Setup, Docker Skeleton, DB Schema, FastAPI Boilerplate

**Status:** ✅ Complete  
**Date:** 2026-07-12

### What was built
- Full project directory structure created
- `.gitignore` — covers `.env`, `__pycache__`, `venv/`, logs
- `.env.example` — all environment variables documented, no real secrets
- `.env` — dev values, gitignored
- `Dockerfile` — multi-stage build (builder + runtime), non-root user
- `docker-compose.yml` — PostgreSQL 16 + FastAPI with healthchecks, Alembic runs on startup
- `requirements.txt` — pinned versions: FastAPI, SQLAlchemy async, spaCy, pdfplumber, PyMuPDF, python-docx, scikit-learn, rank-bm25, slowapi, alembic, asyncpg
- `app/config.py` — pydantic-settings singleton, all env vars typed
- `app/database.py` — async SQLAlchemy engine, per-request session with auto-commit/rollback
- `app/models/` — ORM models: `Candidate`, `CandidateSkill`, `Skill`, `Job`, `MatchResult`
  - Every match score traceable via `explanation_log` JSONB column
  - `CandidateSkill` stores confidence + source_context for auditability
- `app/schemas/` — Pydantic schemas for all models
- `app/api/v1/` — Router stubs for resumes, jobs, matches (real logic added Phase 1/4)
- `app/main.py` — FastAPI app with CORS, request timing middleware, health endpoint, global exception handler
- `alembic.ini` + `app/migrations/env.py` — async Alembic, DB URL from settings (not hardcoded)
- `README.md` — tech stack, quick start, dev setup, project structure

### DB Schema (ERD summary)
- `candidates` — UUID PK, extracted fields, structured_json JSONB, profile_tags TEXT[]
- `skills` — canonical_name + aliases TEXT[], category
- `candidate_skills` — join table with confidence + source_context
- `jobs` — title, description, required_skills TEXT[], preferred_skills TEXT[]
- `match_results` — tfidf/bm25/skill/final scores + full explanation_log JSONB

### What broke / how fixed
- Nothing broke in Phase 0 (scaffolding only)

### Git
- Remote: `https://github.com/talhasaleemm/resumeranker`
- Branch: `main`
- Commit: `phase-0: repo setup, docker skeleton, db schema, fastapi boilerplate`

---

## Phase 1 — spaCy NER Pipeline (UPCOMING)

Parser: PDF/DOCX → structured JSON  
Skills, education, experience, projects, certifications extraction  
Tested on 3 sample resumes  

---

## Phase 2 — Skill Normalization + TF-IDF/BM25 Matching (UPCOMING)

---

## Phase 3 — Auto-tagging + Explainable Match Logging (UPCOMING)

---

## Phase 4 — FastAPI Endpoints + PostgreSQL Persistence (UPCOMING)

---

## Phase 5 — Full Dockerization + README (UPCOMING)

---

## Phase 6 — QA + Security Review (UPCOMING)

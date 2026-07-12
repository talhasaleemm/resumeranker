# PROJECT_CONTEXT.md

## General Rules & Guidelines
- **Git Protocol**: Do not amend commits or force-push to `main` without explicit prior authorization in a prompt.
- **Evidence-Based Reporting**: No self-certification — state findings, paste raw bash/docker/pytest output, and let the reviewer judge completion. Do not use absolute/self-certifying language ("completely verified," "fully closed") without specific raw evidence.
- **Scope Discipline**: No scope expansion beyond an explicitly authorized task list. Do not begin unauthorized tasks.
- **Testing Approach**: Test endpoints inside Docker using `httpx.Client(base_url="http://localhost:8000")` instead of `TestClient` to prevent asyncio loop collisions with global database engine pools. Test DB-backed functions by creating local, isolated `AsyncEngine` instances within tests.

## Current Project State
- **Phase 0**: Boilerplate & Setup (Complete)
- **Phase 1**: Resume Parser (Complete)
- **Phase 2**: TF-IDF & BM25 Match Engines (Complete)
- **Phase 3**: Auto-Tagging & Explainable Match Logs (Complete)
- **Phase 4**: PostgreSQL Persistence (Complete)
  - Candidates and Jobs are mutable entities.
  - MatchResults are immutable, append-only logs.
  - Dedup fallback logic: email match first, `raw_text_hash` fallback. Partial unique indexes handle concurrency.
- **Phase 5**: (Pending)

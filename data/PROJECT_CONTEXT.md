# ResumeRanker Project Context

## Project Overview
ResumeRanker is an intelligent matching engine that evaluates candidate resumes against job descriptions to produce a ranked 0-100 score. The project is designed to extract structured signals (skills, experience, projects) from documents and evaluate semantic overlap, explicit skill matches, and auto-generate specialized role tags.
**Tech Stack**: Python (3.12), FastAPI, spaCy (NER), scikit-learn (TF-IDF), rank_bm25 (BM25 engine), PostgreSQL (Alembic for migrations), and Docker/Docker Compose.

## Architecture Summary
The system is composed of several cleanly decoupled modules:
- **Parser (`app/services/parsing/`)**: Extracts raw text from PDFs/DOCXs and uses a spaCy-based NER pipeline (`ner_pipeline.py`) to extract structured candidate entities like `skills`, `experience`, and `projects`.
- **Normalizer (`app/services/normalization/`)**: Uses a predefined `skill_taxonomy.json` to map raw extracted skills (e.g., "NodeJS") into canonical base forms (e.g., "node.js").
- **Matching Engine (`app/services/matching/`)**: 
  - **TF-IDF**: Computes statistical document similarity between raw job descriptions and candidate text.
  - **BM25**: Computes term-frequency/inverse-document-frequency with a focus on rare keyword matches.
  - **Skill Overlap**: Computes exact literal/canonical skill intersection.
- **Tagger (`app/services/tagging/`)**: Evaluates structured candidate evidence (`skills`, `projects`, `experience`) to auto-assign specialized role tags (e.g., `frontend`, `backend`, `data science`) based on defined heuristics.
- **Scorer (`app/services/matching/scorer.py`)**: The central pipeline orchestrator. Merges TF-IDF, BM25, and Skill Overlap into a unified weighted score and packages an explainability log.
- **API Layer (`app/api/`)**: Exposes FastAPI endpoints (e.g., `/api/v1/matches/`) allowing consumers to dynamically weight components and retrieve scored batches.

## Current Build State
- **Phase 0 (Foundation)**: Complete. Scaffolding, dependency configuration, and Docker containerization.
- **Phase 1 (Parsing & Extraction)**: Complete. PDF/DOCX multi-format parsers and spaCy NER extraction pipeline developed.
- **Phase 2 (Matching Engine)**: Complete. Normalizer, TF-IDF, BM25, and dynamic Scorer pipeline developed. Endpoint added and validated with fallback logic.
- **Phase 3 (Auto-tagging & Explainable Logging)**: Complete. `tagger.py` developed for signal-based categorization, full-stack inference, and explainability injection. Discrepancies between literal input and canonical logs resolved.
- **Phase 4 (PostgreSQL Persistence)**: Complete. Schema designed with `candidates` and `jobs` as mutable entities, and `match_results` as an immutable append-only history. Concurrency dedup logic implemented via `email` and `raw_text_hash` fallback with partial unique indexes. Test infrastructure migrated to direct `httpx` container networking to prevent event loop connection clashes.

## Key Design Decisions
- **Explainability Logging Uses Literal Strings**: Both `tag_evidence` and `matched_skills`/`missing_skills` display the exact literal string submitted by the candidate/job description (e.g., "NodeJS" instead of "node.js"). This ensures traceability back to the source text for human recruiters reading the logs, avoiding confusion over canonical mapping.
- **Weights Must Sum to 1.0**: The endpoint enforces a strict sum-to-1 constraint (`MatchWeights` Pydantic model) for transparency and mathematical stability, rejecting invalid payloads with a 422.
- **BM25 Single-Candidate Fallback**: Due to BM25 returning 0.0 scores natively on single-document batches, min-max normalization falls back to `1.0` if there is ANY keyword overlap, and `0.0` otherwise.
- **Full-Stack Tag Stacking**: When a candidate has sufficient evidence for both `frontend` and `backend` tags, the `full-stack` tag is explicitly appended sequentially. All three tags are intentionally returned in the final output.
- **Targeted Evidence vs Raw Text**: The tagging rules exclusively scan structured fields (`skills`, `projects`, `experience`) and actively exclude the un-sectioned `raw_text` dump. This enforces signal accuracy over generic keyword guessing.
- **Mutable vs Immutable Architecture**: `Candidates` and `Jobs` are treated as mutable entities representing current states. `MatchResults` are strictly immutable, append-only logs documenting a snapshot in time.
- **Deduplication Logic**: When importing candidates, the system attempts deduplication on `email` first. If no email exists, it falls back to a SHA256 hash of the `raw_text`. Partial unique indexes enforce this concurrently at the DB layer.
- **Testing Database Integration**: Tests run against the live FastAPI app via `httpx.Client(base_url="http://localhost:8000")` instead of `TestClient` to prevent asyncio loop collisions with global database engine pools. Standalone database test logic isolates itself by dynamically creating and disposing a local `AsyncEngine` inside each test.

## Known Gaps / Tech Debt
- **No messy/real-world resume tests**: Parsing tests use perfectly formatted dummy documents; real-world multi-column PDFs are not yet tested.
- **BM25 Stopword Filtering**: Tokenization for BM25 relies on basic whitespace splitting and lowercase; formal stopword filtering (e.g., "and", "the") is missing.
- **PII Limiting**: While emails and phones are extracted, the system currently lacks anonymization logic. Since raw texts are stored in the DB alongside full names, proper PII redaction capabilities may be needed for production.

## How to Run the Project
All commands should be executed from the project root (`scratch/resumeranker/`).\
**Prerequisite (Windows):** Docker Desktop must be running before any `docker-compose` command will work. Launch it via `Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"` or from the Start Menu, and wait for the whale icon in the system tray to show "Docker Desktop is running". The `docker-compose` CLI will fail with a pipe-not-found error if the daemon is not up.
- **Start Services (Detached)**: `docker-compose up -d`
- **Rebuild Services**: `docker-compose up -d --build` or `docker-compose build --no-cache`
- **Check Health**: `curl -s http://localhost:8001/health`
- **Run Full Test Suite**: `docker-compose exec -T app pytest tests/ -v --tb=short`
- **View App Logs**: `docker logs resumeranker-app-1`

## Standing Rules for Agents
1. **NO FORCE PUSH OR AMEND ON `MAIN`**: You must never use `git commit --amend` or `git push --force` on the `main` branch under any circumstance unless a prompt explicitly names and authorizes that specific operation.
2. **NO SELF-CERTIFICATION**: Never mark a task as complete without pasting raw terminal output (e.g., from `pytest`, `docker logs`, `curl`) proving it works exactly as required.
3. **NO SCOPE CREEP**: Do not begin, plan for, or anticipate tasks outside of the explicit checklist provided in the active prompt.
4. **DOCUMENT UPDATES**: At the end of every phase, `PROJECT_CONTEXT.md` and `PROGRESS_LOG.md` must be updated to reflect newly added modules, closed phases, and architectural shifts.

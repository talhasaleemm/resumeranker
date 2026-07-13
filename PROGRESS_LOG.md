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

### DB Schema (ERD summary — as originally designed in Phase 0)
- `candidates` — UUID PK, extracted fields, `structured_json` JSONB, `profile_tags` TEXT[]
- `skills` — `canonical_name` + `aliases` TEXT[], `category`
- `candidate_skills` — join table with `confidence` + `source_context`
- `jobs` — title, description, `required_skills` TEXT[], `preferred_skills` TEXT[]
- `match_results` — tfidf/bm25/skill/final scores + full `explanation_log` JSONB

> **Schema evolution note (reconciled during Phase 4 review):** The as-built live schema diverges from the original Phase 0 design in three ways:
> 1. **`skills` + `candidate_skills` tables were never created.** During Phase 4 design review, a normalised join table was judged unnecessary overhead at this project's scale; skills are stored as a flat `parsed_skills TEXT[]` column on `candidates` instead.
> 2. **`structured_json` JSONB column does not exist.** Structured parsed data is stored via two separate columns — `parsed_experience JSONB` and `parsed_projects JSONB` — for clarity and direct query access.
> 3. **`profile_tags TEXT[]` was renamed `assigned_tags TEXT[]`** to better reflect that tags are auto-assigned by the Phase 3 tagger module, not submitted by the user.

### What broke / how fixed
- Nothing broke in Phase 0 (scaffolding only)

### Git
- Remote: `https://github.com/talhasaleemm/resumeranker`
- Branch: `main`
- Commit: `phase-0: repo setup, docker skeleton, db schema, fastapi boilerplate`

---

## Phase 1 — spaCy NER Pipeline

**Status:** ✅ Complete  
**Date:** 2026-07-12

### What was built
- `app/services/parser/pdf_parser.py` — pdfplumber primary + PyMuPDF fallback; raises `ParseError` explicitly on scanned/empty/corrupt PDFs — no fake success
- `app/services/parser/docx_parser.py` — python-docx with table cells + text box extraction; raises `ParseError` on invalid input
- `app/services/parser/ner_pipeline.py` — Full spaCy NER pipeline:
  - Contact extraction: email, phone, URLs via regex (more reliable than NER for these)
  - Name extraction: first PERSON entity in top 500 chars, falls back to first clean line
  - Section detection: regex-based header matching for SKILLS / EXPERIENCE / EDUCATION / PROJECTS / CERTIFICATIONS / SUMMARY
  - Skills parser: comma/bullet/newline delimited; preserves hyphenated tokens (scikit-learn, Next.js)
  - Education parser: degree regex + institution detection + year ranges
  - Experience parser: job title/company splitting + duration regex + bullet descriptions
  - Projects parser: name + description + technology extraction
  - Certifications parser: bullet/line splitting

### Sample resumes generated (3/3)
- `tests/sample_resumes/resume_backend_engineer.pdf` — Aisha Raza, Backend Engineer
- `tests/sample_resumes/resume_data_scientist.docx` — Marcus Chen, Data Scientist  
- `tests/sample_resumes/resume_fullstack_dev.pdf` — Priya Nair, Full-Stack Developer

### Raw test output
```
platform win32 -- Python 3.13.7, pytest-9.1.1
collected 22 items

tests/test_parser.py::TestPDFParser::test_backend_pdf_extracts_text PASSED
tests/test_parser.py::TestPDFParser::test_fullstack_pdf_extracts_text PASSED
tests/test_parser.py::TestPDFParser::test_pdf_parser_raises_on_empty_bytes PASSED
tests/test_parser.py::TestPDFParser::test_pdf_parser_raises_on_empty_file PASSED
tests/test_parser.py::TestDOCXParser::test_data_scientist_docx_extracts_text PASSED
tests/test_parser.py::TestDOCXParser::test_docx_parser_raises_on_invalid_file PASSED
tests/test_parser.py::TestNERPipeline::test_output_has_required_keys PASSED
tests/test_parser.py::TestNERPipeline::test_backend_email_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_backend_phone_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_backend_skills_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_backend_experience_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_backend_certifications_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_backend_projects_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_data_scientist_email_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_data_scientist_skills_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_data_scientist_education_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_fullstack_email_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_fullstack_skills_contain_frontend_and_backend PASSED
tests/test_parser.py::TestNERPipeline::test_fullstack_urls_extracted PASSED
tests/test_parser.py::TestNERPipeline::test_empty_text_returns_empty_profile PASSED
tests/test_parser.py::TestNERPipeline::test_whitespace_only_returns_empty_profile PASSED
tests/test_parser.py::TestNERPipeline::test_json_serializable PASSED

22 passed in 9.97s
```

### What broke / how fixed
1. **spaCy 3.8.2 → 3.8.14 in Docker**: spaCy 3.8.2 has no prebuilt Linux wheel for Python 3.13 (gcc compile failed). Fixed by switching Dockerfile base to `python:3.12-slim` and pinning `spacy==3.8.14`.
2. **`click` missing**: spaCy CLI requires click but it wasn't in requirements. Added explicitly.
3. **Name extraction grabbed email line**: Fallback regex matched `Aisha Raza\naisha.raza@...` as one token. Fixed with stricter line rules: max 4 words, no digits, no `|`/`+`, max 50 chars.
4. **`scikit-learn` split on hyphen**: Skill separator regex was replacing all hyphens. Fixed to only replace em/en dashes surrounded by spaces; preserves internal hyphens.
5. **Year regex matched `20` prefix**: `_YEAR_RE.findall()` was returning just the prefix group. Fixed by filtering to `len(y) == 4`.

### Tech Debt (Flagged for Phase 6 QA)
1. **Realistic / Messy Resumes**: Current sample resumes are perfectly structured. Needs tests for multi-column layouts, resume-as-table, scanned/image-based PDFs, and resumes missing whole sections.
2. **False Positives**: Added 3 tests to ensure company names don't leak into skills, certifications don't leak into projects, and skills aren't full sentences. Should continue expanding negative-content tests.

---

## Phase 2: Matching Engine (Completed)

**Objective**: Define standard taxonomy for skills, implement TF-IDF and BM25 scoring engines, and combine them into a single `score_candidates` pipeline exposed via `POST /api/v1/matches/`.

**What was done**:
1. **Skill Taxonomy & Normalization**: Created `skill_taxonomy.json` mapping common aliases (e.g., `js` -> `javascript`) and implemented `normalizer.py` to clean and canonicalize skills.
2. **TF-IDF Engine**: Implemented `tfidf_engine.py` using `scikit-learn`'s `TfidfVectorizer` to calculate cosine similarity between JD and resumes.
3. **BM25 Engine**: Implemented `bm25_engine.py` using `rank_bm25`'s `BM25Okapi` and added min-max normalization to bound scores between 0.0 and 1.0.
4. **Match Scorer**: Implemented `scorer.py` that computes exact skill overlap (Jaccard-like) and aggregates it with TF-IDF and BM25 scores using configurable weights. Outputs a 0-100 `final_score` and an `explanation_log`.
5. **API Endpoint**: Updated `app/api/v1/matches.py` to expose `POST /api/v1/matches/`, allowing dynamic weight overrides.
6. **Tests**: Added `tests/test_matching.py` providing full coverage for the normalizer, TF-IDF, BM25, and matching pipeline.

### Git
- Branch: `main`
- Commit: `phase-2: TF-IDF, BM25, Match Scorer pipeline, 7 matching tests passing`

---

## Phase 3 — Auto-tagging + Explainable Match Logging

**Status:** ✅ Complete  
**Date:** 2026-07-13

### What was built
- Auto-tagging module (`tagger.py`) parsing structural Phase 1 output (skills, experience).
- Categories: backend, frontend, full-stack, data science, AI/ML, bioinformatics.
- Explainable logging showing exact original candidate/job skill strings that matched.
- Dedicated test coverage added to ensure non-overlap between conflicting domains (e.g., Data Science vs AI/ML).

---

## Phase 4 — FastAPI Endpoints + PostgreSQL Persistence

**Status:** ✅ Complete  
**Date:** 2026-07-13

### What was built
- Designed and implemented relational schema (candidates, jobs, match_results).
- Candidates and Jobs: mutable entities. MatchResults: immutable append-only history.
- Partial unique indexes added to Candidate table on `email` and `raw_text_hash` to handle concurrent duplicate ingestion.
- `MatchResult` constraints added for 0.0-1.0 checks on BM25, TF-IDF, and Skill scores.
- Test infrastructure updated: transitioned to using `httpx.Client` directly against the containerized FastAPI port `8000` to prevent event loop connection pool clashes.
- Dedup fallbacks explicitly tested across four separated tests (`test_persistence_new_candidate_insert`, `test_persistence_email_match_update`, `test_persistence_raw_text_hash_fallback_match`, `test_persistence_concurrent_duplicate_rejection`).


---

## Phase 5 — Full Dockerization + README (UPCOMING)

---

## Phase 6 — QA + Security Review (UPCOMING)

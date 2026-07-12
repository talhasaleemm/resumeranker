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

### Git
- Branch: `main`
- Commit: `phase-1: spaCy NER pipeline, PDF/DOCX parsers, 27 tests passing`

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

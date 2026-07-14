# ResumeRanker

**ResumeRanker** is an AI-assisted resume parsing and candidate-matching platform. It ingests PDF and DOCX resumes, extracts structured signals (skills, experience, projects, contact details) using a spaCy NER pipeline, normalises raw skill strings against a canonical taxonomy, and scores each candidate against a job description using a weighted blend of TF-IDF, BM25, and exact skill-overlap algorithms. Every result is persisted in PostgreSQL with a full **explainability log** — showing exactly which skills matched, which were missing, and which role tags were detected and why — so hiring teams can audit every decision rather than trust a black-box score.

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Web framework | FastAPI | 0.115.0 |
| ASGI server | Uvicorn | 0.32.0 |
| NLP / NER | spaCy (`en_core_web_sm`) | 3.8.14 |
| PDF parsing | pdfplumber + PyMuPDF (fallback) | 0.11.4 / 1.24.14 |
| DOCX parsing | python-docx | 1.1.2 |
| Statistical similarity | scikit-learn (TF-IDF) | 1.5.2 |
| Keyword ranking | rank-bm25 (BM25Okapi) | 0.2.2 |
| Database | PostgreSQL | 16 (Alpine) |
| ORM / migrations | SQLAlchemy async + Alembic | 2.0.36 / 1.14.0 |
| Async DB driver | asyncpg | 0.30.0 |
| Configuration | pydantic-settings | 2.6.1 |
| Rate limiting | slowapi | 0.1.9 |
| Containerisation | Docker + Docker Compose | — |
| Testing | pytest + pytest-asyncio + httpx | 8.3.3 / 0.24.0 / 0.28.0 |

---

## Architecture Overview

Resumes flow through a linear pipeline before scores are persisted:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         POST /api/v1/resumes/                       │
│  raw_text (or future: PDF/DOCX bytes)                               │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Parser Layer   │  pdf_parser.py / docx_parser.py
                    │  (raw text)     │  pdfplumber → PyMuPDF fallback
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  NER Pipeline   │  ner_pipeline.py (spaCy)
                    │                 │  → name, email, phone, URLs
                    │                 │  → skills, experience, education
                    │                 │  → projects, certifications
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Normalizer     │  normalizer.py + skill_taxonomy.json
                    │                 │  "NodeJS" → "node.js"
                    │                 │  "js" → "javascript"
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Tagger         │  tagger.py
                    │                 │  backend / frontend / full-stack /
                    │                 │  data science / AI/ML / bioinformatics
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────────┐
              │         POST /api/v1/matches/    │
              │                                 │
              │  ┌──────────┐ ┌───────────────┐ │
              │  │  TF-IDF  │ │  BM25Okapi    │ │  (configurable weights,
              │  │  cosine  │ │  + min-max    │ │   must sum to 1.0)
              │  │ similarity│ │  normalise    │ │
              │  └────┬─────┘ └──────┬────────┘ │
              │       │              │           │
              │  ┌────▼──────────────▼────────┐  │
              │  │       Scorer               │  │
              │  │  weighted blend → 0-100    │  │
              │  │  + explanation_log JSONB   │  │
              │  └────────────┬───────────────┘  │
              └───────────────│──────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  PostgreSQL 16    │
                    │  match_results    │  immutable append-only history
                    │  candidates       │  mutable, dedup on email/hash
                    │  jobs             │  mutable
                    └───────────────────┘
```

### Module map

| Module | Path | Role |
|---|---|---|
| PDF parser | `app/services/parser/pdf_parser.py` | pdfplumber primary, PyMuPDF fallback |
| DOCX parser | `app/services/parser/docx_parser.py` | python-docx with table + text-box support |
| NER pipeline | `app/services/parser/ner_pipeline.py` | spaCy entity extraction + section detection |
| Normalizer | `app/services/normalization/normalizer.py` | Skill alias → canonical form via taxonomy JSON |
| Skill taxonomy | `app/services/normalization/skill_taxonomy.json` | Alias map (e.g. `js` → `javascript`) |
| TF-IDF engine | `app/services/matching/tfidf_engine.py` | scikit-learn TfidfVectorizer, cosine similarity |
| BM25 engine | `app/services/matching/bm25_engine.py` | rank-bm25 BM25Okapi + min-max normalisation |
| Scorer | `app/services/matching/scorer.py` | Pipeline orchestrator, weighted blend, explainability log |
| Tagger | `app/services/tagging/tagger.py` | Signal-based role tag assignment |
| Candidate service | `app/services/candidate_service.py` | Dedup logic (email → hash fallback) |
| API — resumes | `app/api/v1/resumes.py` | `POST /api/v1/resumes/` |
| API — jobs | `app/api/v1/jobs.py` | `POST /api/v1/jobs/` |
| API — matches | `app/api/v1/matches.py` | `POST /api/v1/matches/` |

---

## Setup & Running Locally

### Prerequisites

- **Docker Desktop** must be running before any `docker-compose` command will work.
  - Windows: launch via Start Menu or `Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"` and wait for the whale icon in the system tray to show *Docker Desktop is running*.
  - The CLI will fail with a pipe-not-found error if the daemon is not up.
- Git

### 1. Clone the repo

```bash
git clone https://github.com/talhasaleemm/resumeranker.git
cd resumeranker
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env if you want non-default passwords — the defaults work for local dev
```

### 3. Start services (app + PostgreSQL)

```bash
docker-compose up -d
```

On first run this builds the image (downloads spaCy model — allow ~2 min). On startup the app container automatically runs Alembic migrations before starting Uvicorn. Both containers expose healthchecks; the app waits for PostgreSQL to be healthy before starting.

### 4. Verify the app is running

```bash
curl http://localhost:8001/health
```

Expected response:
```json
{"status": "ok", "version": "0.1.0", "env": "development"}
```

### 5. Interactive API docs

Open **http://localhost:8001/docs** in your browser (Swagger UI) or **/redoc** for ReDoc.

### 6. Run the test suite

```bash
docker-compose exec -T app pytest tests/ -v
```

Expected: **70 tests, 0 failures** (see [Testing](#testing) section).

### Useful commands

```bash
# Rebuild image after code changes
docker-compose up -d --build

# View app logs
docker logs resumeranker-app-1

# Connect to PostgreSQL directly
docker-compose exec db psql -U resumeranker -d resumeranker

# Stop everything
docker-compose down
```

---

## API Usage Example

Below is a complete worked example showing the three-step workflow. All commands are `curl`-based; you can also use the Swagger UI at `/docs`.

### Step 1 — Ingest a candidate resume

```bash
curl -s -X POST http://localhost:8001/api/v1/resumes/ \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "Aisha Raza\naisha.raza@email.com\n\nSKILLS\nPython, FastAPI, PostgreSQL, Docker, Redis\n\nEXPERIENCE\nBackend Engineer at TechCorp (2021-2023)\n- Built microservices in Python and FastAPI\n- Managed PostgreSQL databases\n\nCERTIFICATIONS\nAWS Certified Developer",
    "filename": "aisha_raza.pdf"
  }'
```

Response:
```json
{"candidate_id": "3e2e6da0-57cf-4aa7-840f-c80fee8bfc2e"}
```

### Step 2 — Create a job

```bash
curl -s -X POST http://localhost:8001/api/v1/jobs/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Backend Engineer",
    "description": "We are looking for a backend engineer with strong Python and FastAPI skills. Experience with PostgreSQL and Docker is required.",
    "required_skills": ["python", "fastapi", "postgresql", "docker"],
    "preferred_skills": ["redis", "aws"]
  }'
```

Response:
```json
{"job_id": "ef167bdd-5c1c-4383-ae3b-a9966186b525"}
```

### Step 3 — Score and rank candidates against the job

Weights must be provided as floats that **sum exactly to 1.0** (omit the field to use the defaults from `.env`).

```bash
curl -s -X POST http://localhost:8001/api/v1/matches/ \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "ef167bdd-5c1c-4383-ae3b-a9966186b525",
    "candidate_ids": ["3e2e6da0-57cf-4aa7-840f-c80fee8bfc2e"],
    "weights": {
      "tfidf": 0.4,
      "bm25": 0.4,
      "skills": 0.2
    }
  }'
```

**Live response (captured from running instance):**

```json
{
  "status": "success",
  "matches": [
    {
      "candidate_id": "3e2e6da0-57cf-4aa7-840f-c80fee8bfc2e",
      "tfidf_score": 0.35147705803291995,
      "bm25_score": 1.0,
      "skill_score": 1.0,
      "final_score": 74.06,
      "explanation_log": {
        "tfidf_contribution": 14.06,
        "bm25_contribution": 40.0,
        "skill_contribution": 20.0,
        "matched_skills": ["Docker", "FastAPI", "PostgreSQL", "Python"],
        "missing_skills": [],
        "tags_detected": ["backend"],
        "tag_evidence": {
          "backend": [
            "experience/project keyword: backend",
            "skill: PostgreSQL",
            "experience/project keyword: postgresql",
            "skill: Docker",
            "experience/project keyword: python",
            "skill: Python",
            "experience/project keyword: fastapi",
            "experience/project keyword: microservices",
            "skill: FastAPI"
          ]
        }
      }
    }
  ]
}
```

**Reading the explainability log:**

| Field | Meaning |
|---|---|
| `final_score` | Weighted sum (0–100). Here: 14.06 + 40.0 + 20.0 = 74.06 |
| `matched_skills` | Exact literal strings from the candidate that overlap with job required skills (after normalisation). Displayed as submitted — not canonicalised — for human readability. |
| `missing_skills` | Required skills from the job description not found in the candidate's profile. |
| `tags_detected` | Auto-assigned role tags (`backend`, `frontend`, `full-stack`, `data science`, `AI/ML`, `bioinformatics`). |
| `tag_evidence` | The exact skill strings and experience keywords that triggered each tag — fully auditable. |
| `bm25_score: 1.0` | Single-candidate BM25 fallback: if any keyword overlaps, score is normalised to 1.0 (see Design Decisions). |

---

## Key Design Decisions

1. **Append-only match history.** `match_results` rows are never updated or deleted — each call to `POST /api/v1/matches/` writes a new row. This gives a full audit trail of scoring decisions over time, even if the same candidate is re-scored against the same job with different weights.
  
  ### 5. API Rate Limiting
  To prevent brute-force attacks and denial-of-service, all key endpoints are rate-limited via `slowapi`:
  - **Global default:** 60 requests per minute
  - **`/api/v1/resumes/`:** 10 requests per minute per IP (to prevent bulk uploads)
  - **Response:** Returns `429 Too Many Requests` when limits are exceeded.
  
  Test suites use `TestClient` with the limiter disabled in memory to prevent rate-limit failures during automated testing without compromising the production configuration.

2. **Literal-string explainability.** `matched_skills`, `missing_skills`, and `tag_evidence` always display the exact strings as submitted by the candidate or the job description (e.g. `"FastAPI"` not `"fastapi"`). This avoids recruiter confusion when canonical forms differ from what a candidate wrote.

3. **Weight validation enforced at the API layer.** The `MatchWeights` Pydantic model rejects any payload where `tfidf + bm25 + skills ≠ 1.0` (within floating-point tolerance) or where any weight is negative — returning HTTP 422 with a clear error message.

4. **Skill normalisation via taxonomy JSON.** Raw skill strings extracted by the NER pipeline are mapped to canonical forms before matching using `skill_taxonomy.json` (e.g. `"js"` → `"javascript"`, `"NodeJS"` → `"node.js"`). New aliases can be added without touching application code.

5. **Candidate deduplication via email → SHA256 hash fallback.** When ingesting resumes, the system first tries to match on email address. If no email is present, it falls back to a SHA256 hash of the raw text. Both constraints are enforced by partial unique indexes in PostgreSQL, making deduplication concurrent-safe.

---

## Known Limitations

These are documented honestly and are on the roadmap for Phase 6 (QA + Security Review):

- **No messy / real-world resume tests.** The test suite uses well-structured synthetic resumes. Multi-column PDF layouts, resume-as-table formats, and scanned/image-based PDFs are not yet tested and may produce poor extraction results.
- **BM25 lacks stopword filtering.** BM25 tokenisation uses basic whitespace splitting and lowercasing. Common English stopwords (e.g. "and", "the") are not filtered, which can slightly inflate keyword-frequency scores.
- **PII Encryption & Performance Cost**: Sensitive candidate identifiers (email, phone, name) and unstructured job history text (raw_text, parsed_experience, parsed_projects) are strictly encrypted at the application level using Fernet. Because TF-IDF/BM25 scoring and auto-tagging require reading these texts, the system must decrypt exactly 3 fields per candidate on every match request. This introduces a high-frequency performance penalty, which is an accepted tradeoff for data security. Key rotation is not currently implemented.
- **Stateless Matching Unavailable**: `POST /api/v1/matches/` requires all entities to exist in the database. Callers wanting to run ephemeral/on-the-fly scoring must ingest and persist the entities first.

---

## Testing

```bash
# Run the full suite inside the Docker container
docker-compose exec -T app pytest tests/ -v
```

**Current test count: 70 tests, 0 failures** (verified on Python 3.12.13, pytest 9.0.3).

| Test file | Tests | What is covered |
|---|---|---|
| `test_matches_endpoint.py` | 7 | HTTP-level: weight validation (422s), single-candidate BM25 fallback, repeated calls accepted |
| `test_matching.py` | 8 | Unit: skill normaliser, TF-IDF engine, BM25 engine, scorer pipeline, literal-case preservation |
| `test_parser.py` | 25 | PDF/DOCX parsing (happy + error paths), NER extraction (email, phone, skills, experience, education, URLs, certifications, projects), negative-content guards |
| `test_persistence.py` | 5 | DB: new insert, email-match update, hash fallback dedup, concurrent duplicate rejection, append-only row count |
| `test_tagger.py` | 9 | Role tag assignment for all six categories, full-stack stacking, ambiguous/empty inputs, evidence string preservation |

> The 5 `DeprecationWarning` lines in pytest output are from a PyMuPDF Swig binding and are harmless — they do not affect test results.

---

## Project Structure

```
resumeranker/
├── app/
│   ├── api/v1/           # FastAPI routers (resumes, jobs, matches)
│   ├── migrations/       # Alembic async migration scripts
│   ├── models/           # SQLAlchemy ORM models (Candidate, Job, MatchResult)
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/
│   │   ├── matching/     # tfidf_engine.py, bm25_engine.py, scorer.py
│   │   ├── normalization/# normalizer.py, skill_taxonomy.json
│   │   ├── parser/       # pdf_parser.py, docx_parser.py, ner_pipeline.py
│   │   └── tagging/      # tagger.py
│   ├── config.py         # pydantic-settings singleton
│   ├── database.py       # async SQLAlchemy engine + session
│   └── main.py           # FastAPI app entry point
├── data/
│   └── PROJECT_CONTEXT.md# Architecture decisions, known gaps, standing rules
├── tests/                # pytest test suite (70 tests)
├── .env.example          # Environment variable template (copy to .env)
├── alembic.ini           # Alembic configuration
├── docker-compose.yml    # PostgreSQL 16 + FastAPI services
├── Dockerfile            # Multi-stage build (builder + runtime, non-root user)
├── PROGRESS_LOG.md       # Phase-by-phase build history
└── requirements.txt      # Pinned Python dependencies
```

---

## License

This project is licensed under the [MIT License](LICENSE). Note that it was originally built for portfolio and demonstration purposes.

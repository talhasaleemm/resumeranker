# ResumeRanker

[![CI](https://github.com/talhasaleemm/resumeranker/actions/workflows/ci.yml/badge.svg)](https://github.com/talhasaleemm/resumeranker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2B-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-0.3%2B-3386E4?logo=postgres&logoColor=white)](https://github.com/pgvector/pgvector)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16%2B-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)

**AI-powered ATS and Resume Ranker** — parse resumes, extract structured profiles with NLP, and rank candidates against job descriptions using TF-IDF, BM25, and semantic vector embeddings.

## Key Features

- **Semantic Matching**: Combines TF-IDF, BM25, skill overlap, and cosine similarity on 384-dim vector embeddings via `all-MiniLM-L6-v2`
- **NLP-Powered Parsing**: Extracts skills, experience, education, and contact info from PDF/DOCX resumes using spaCy NER + PyMuPDF/pdfplumber
- **Explainable Scores**: Transparent match breakdown with per-candidate contribution analysis and weights audit log
- **Async Processing**: Celery + Redis for non-blocking ingestion and matching pipelines
- **Secure by Design**: Argon2 password hashing, JWT auth, Fernet encryption for PII, blind indexes for searchable email hashing
- **Rate Limited**: SlowAPI-powered rate limiting on all public endpoints
- **Docker First**: Full containerized stack with Docker Compose for one-command local dev
- **Production Ready**: Render deploy blueprint, Alembic migrations, pip-audit security scanning

## Architecture Framework

### End-to-End Pipeline (Steps 1-6)

![ResumeRanker Architecture](docs/assets/ResumeRanker.png)

*Figure: End-to-end pipeline from document input through final leaderboard.*

### Resume-to-Job Matching Engine Deep Dive

The matching engine operates in five distinct phases:

#### A. Pre-computation: Embed & Index
- Resume text is passed through `all-MiniLM-L6-v2` (SentenceTransformer)
- Generates 384-dim L2-normalized vector embeddings
- Stored in `candidates.embedding` column (`pgvector Vector(384)`)

#### B. Target Definition
- Job description is embedded using the same `all-MiniLM-L6-v2` model
- Produces a 384-dim job vector for similarity comparison

#### C. Similarity Retrieval
- Cosine similarity computed via dot product of L2-normalized vectors
- Raw scores range from 0.0 to 1.0 (no batch normalization applied)

#### D. Skills Filtering
- RapidFuzz WRatio fuzzy matching with threshold ≥ 85
- Intersection of required vs candidate skills

#### E. Final Ranking
- Weighted combination: `tfidf×0.05 + bm25×0.15 + skills×0.40 + vector×0.40`
- Scaled to 0-100, sorted descending
- Full explanation log with per-candidate breakdown

### Data Flow

1. **Upload**: Frontend sends multipart resume to `POST /api/v1/resumes/`
2. **Parse**: Celery worker extracts text via PyMuPDF/pdfplumber, runs spaCy NER, encrypts PII, stores `Candidate` with 384-dim `embedding`
3. **Match**: Client calls `POST /api/v1/matches/` → backend computes TF-IDF, BM25, skill overlap, and cosine similarity against job embedding → stores `MatchResult` with full `explanation_log`

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ with pgvector
- Redis 7+
- Node.js 20+ (frontend)
- Docker & Docker Compose (recommended)

### Option A: Docker (Recommended)

```bash
git clone https://github.com/talhasaleemm/resumeranker.git
cd resumeranker
cp .env.example .env
docker compose up --build
```

- API: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- API Docs: `http://localhost:8000/docs`

### Option B: Local Development

```bash
# Backend
git clone https://github.com/talhasaleemm/resumeranker.git
cd resumeranker
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Environment Variables

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql+asyncpg://resumeranker:devpassword123@localhost:5432/resumeranker

# Redis
REDIS_URL=redis://localhost:6379/0

# Security (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET_KEY=your-jwt-secret-here
ENCRYPTION_KEY=your-fernet-key-here
BLIND_INDEX_KEY=your-blind-index-salt-here

# App
APP_ENV=development
DEV_SEED_DEMO_RECRUITER=true
DEV_DEMO_RECRUITER_EMAIL=demo@resumeranker.local
DEV_DEMO_RECRUITER_PASSWORD=demo1234
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health probe |
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/login` | Login (returns JWT) |
| `POST` | `/api/v1/resumes/` | Upload resume (async) |
| `GET` | `/api/v1/resumes/` | List your candidates |
| `POST` | `/api/v1/jobs/` | Create job posting |
| `GET` | `/api/v1/jobs/` | List your jobs |
| `POST` | `/api/v1/matches/` | Run matching (async) |
| `GET` | `/api/v1/tasks/{task_id}` | Poll async task status |

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-timeout httpx

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_matching.py -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=term-missing
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, Tailwind CSS |
| **Backend** | FastAPI (Python 3.12) |
| **Database** | PostgreSQL 16 + pgvector |
| **NLP** | spaCy (en_core_web_sm), SentenceTransformers |
| **Embedding Model** | `all-MiniLM-L6-v2` (384-dim, Hugging Face) |
| **Matching** | scikit-learn TF-IDF, rank-bm25, RapidFuzz |
| **Task Queue** | Celery + Redis |
| **Security** | Argon2, JWT, Fernet encryption |
| **Infrastructure** | Docker, Docker Compose, Render |

## Project Structure

```
├── app/                    # FastAPI backend
│   ├── api/v1/            # REST endpoints
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic (parsing, matching, encryption)
│   │   ├── embedding.py   # SentenceTransformer service
│   │   └── matching/      # TF-IDF, BM25, scorer pipeline
│   ├── migrations/        # Alembic database migrations
│   └── worker.py          # Celery task definitions
├── frontend/              # Next.js frontend
├── tests/                 # pytest test suite
├── docs/                  # Documentation and assets
│   └── assets/            # Images, videos, media
├── scripts/               # Utility scripts
├── data/                  # Runtime data (uploads, etc.)
├── alembic.ini            # Alembic config (DB URL loaded from env)
├── docker-compose.yml     # Container orchestration
├── Dockerfile             # Backend container definition
├── render.yaml            # Render deployment blueprint
├── requirements.txt       # Python dependencies
└── pytest.ini             # pytest configuration
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues, suggesting features, and submitting pull requests.

## License

MIT License - see [LICENSE](LICENSE) for details.

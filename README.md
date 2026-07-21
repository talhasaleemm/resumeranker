# ResumeRanker

[![CI](https://github.com/talhasaleemm/resumeranker/actions/workflows/ci.yml/badge.svg)](https://github.com/talhasaleemm/resumeranker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AI Resume Parser and Candidate Matching Platform**

## Demo Video

<p align="center">
  <video src="ResumeRanker.mp4" controls width="720"></video>
</p>

ResumeRanker is a production-ready, AI-powered backend service designed to automate the extraction of candidate information and rank applicants against job descriptions. Built for scale and accuracy, the platform utilizes advanced NLP and information retrieval algorithms to streamline technical recruitment.

## Features

- **AI Resume Parsing**: Extracts skills, experience, education, and contact info from PDF/DOCX resumes using spaCy NER
- **Multi-Algorithm Matching**: Combines TF-IDF, BM25, skill overlap, and semantic vector search for accurate candidate ranking
- **Explainable Scores**: Transparent match breakdown with per-candidate contribution analysis
- **Async Processing**: Celery + Redis for non-blocking ingestion and matching pipelines
- **Secure by Design**: Argon2 password hashing, JWT auth, Fernet encryption for PII, blind indexes for searchable email hashing
- **Rate Limited**: SlowAPI-powered rate limiting on all public endpoints
- **Docker First**: Full containerized stack with Docker Compose for one-command local dev

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 + pgvector |
| NLP | spaCy (en_core_web_sm) |
| Matching | scikit-learn TF-IDF, rank-bm25, SentenceTransformers |
| Task Queue | Celery + Redis |
| Frontend | Next.js 16, Tailwind CSS |
| Infrastructure | Docker, Docker Compose, Render |

## Project Structure

```
├── app/                    # FastAPI backend
│   ├── api/v1/            # REST endpoints
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic (parsing, matching, encryption)
│   └── worker.py          # Celery task definitions
├── frontend/              # Next.js frontend
├── tests/                 # pytest test suite
├── docs/                  # Documentation and assets
│   └── assets/            # Images, videos, media
├── scripts/               # Utility scripts
├── data/                  # Runtime data (uploads, etc.)
├── alembic/               # Database migrations
├── docker-compose.yml     # Container orchestration
└── render.yaml            # Render deployment blueprint
```

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Node.js 20+ (for frontend)
- Docker & Docker Compose (recommended)

### Option A: Docker (Recommended)

```bash
git clone https://github.com/talhasaleemm/resumeranker.git
cd resumeranker
cp .env.example .env
# Edit .env with your settings
docker compose up --build
```

The API will be available at `http://localhost:8000` and the frontend at `http://localhost:3000`.

### Option B: Local Development

```bash
# Backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://resumeranker:devpassword123@db:5432/resumeranker` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | Secret for JWT signing | *(required in production)* |
| `ENCRYPTION_KEY` | Fernet key for PII encryption | *(required in production)* |
| `BLIND_INDEX_KEY` | Salt for blind index hashing | *(required in production)* |
| `DEV_SEED_DEMO_RECRUITER` | Auto-create demo user on startup | `false` |
| `DEV_DEMO_RECRUITER_EMAIL` | Demo user email | `demo@resumeranker.local` |
| `DEV_DEMO_RECRUITER_PASSWORD` | Demo user password | `demo1234` |

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
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_matching.py -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues, suggesting features, and submitting pull requests.

## License

MIT License - see [LICENSE](LICENSE) for details.

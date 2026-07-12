# ResumeRanker

> AI-assisted resume parsing and candidate-matching platform.

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Web Framework | FastAPI |
| NLP Pipeline | spaCy (NER) |
| Matching | TF-IDF + BM25 |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Containerization | Docker + Docker Compose |

## Features

- PDF and DOCX resume parsing via spaCy NER
- Structured extraction: skills, education, experience, projects, certifications
- Skill normalization taxonomy (aliases → canonical names)
- TF-IDF + BM25 candidate-job matching with weighted scoring
- Auto-tagging: backend / frontend / full-stack / data science / AI-ML / bioinformatics
- Fully explainable match scores (every score traceable to extracted signals)
- Rate limiting and input validation on all upload endpoints
- PostgreSQL persistence with Alembic migrations

## Quick Start

### Prerequisites
- Docker Desktop running
- `.env` file (copy from `.env.example` and fill in values)

```bash
cp .env.example .env
# Edit .env with your values
```

### Run with Docker Compose

```bash
docker-compose up --build
```

This will:
1. Start PostgreSQL
2. Run Alembic migrations
3. Start FastAPI on http://localhost:8000

### API Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

## Development Setup (without Docker)

```bash
# Create virtual environment
py -3 -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Set environment
cp .env.example .env
# Edit DATABASE_URL to point to your local PostgreSQL

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

## Project Structure

```
resumeranker/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings (pydantic-settings)
│   ├── database.py          # Async SQLAlchemy engine
│   ├── api/v1/              # API routers
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/
│   │   ├── parser/          # PDF/DOCX → spaCy NER
│   │   ├── matching/        # TF-IDF + BM25 scoring
│   │   ├── normalization/   # Skill taxonomy + normalizer
│   │   └── tagging/         # Auto-tagging classifier
│   └── migrations/          # Alembic migrations
├── tests/
├── Dockerfile
├── docker-compose.yml
└── PROGRESS_LOG.md
```

## Build Status

See [PROGRESS_LOG.md](PROGRESS_LOG.md) for phase-by-phase build progress.

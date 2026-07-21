# Contributing to ResumeRanker

Thank you for your interest in contributing to ResumeRanker! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by the [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

- Search existing issues before opening a new one
- Use the bug report template
- Include reproduction steps, expected vs actual behavior, and environment details

### Suggesting Features

- Search existing issues and discussions first
- Open a feature request with a clear use case and proposed solution

### Pull Requests

1. Fork the repo and create a feature branch from `main`
2. Make your changes with clear, descriptive commit messages
3. Ensure all tests pass locally:
   ```bash
   pytest tests/ -v
   ```
4. Update documentation if needed
5. Open a PR with a description of the change and any relevant issue references

## Development Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Node.js 20+ (for frontend)

### Backend Setup

```bash
git clone https://github.com/talhasaleemm/resumeranker.git
cd resumeranker
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env
# Edit .env with your database credentials
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Docker Setup

```bash
docker compose up --build
```

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

## Style Guide

- **Python**: Follow PEP 8, use `black` for formatting and `ruff` for linting
- **TypeScript/React**: Follow existing patterns in `frontend/`
- **Commits**: Use conventional commits (`feat:`, `fix:`, `docs:`, etc.)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

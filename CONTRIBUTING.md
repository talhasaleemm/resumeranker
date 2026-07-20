# Contributing to ResumeRanker

Thank you for your interest in improving ResumeRanker! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on what is best for the community

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
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
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
│   ├── services/          # Business logic
│   └── worker.py          # Celery task definitions
├── frontend/              # Next.js frontend
├── tests/                 # pytest test suite
├── docs/                  # Documentation and assets
├── scripts/               # Utility scripts
├── data/                  # Runtime data (uploads, etc.)
└── docker-compose.yml     # Container orchestration
```

## Style Guide

- **Python**: Follow PEP 8, use `black` for formatting and `ruff` for linting
- **TypeScript/React**: Follow existing patterns in `frontend/`
- **Commits**: Use conventional commits (`feat:`, `fix:`, `docs:`, etc.)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

# =========================================================
# Dockerfile — ResumeRanker Phase 16 (production multi-stage)
# Stack: FastAPI + PostgreSQL + spaCy + TF-IDF/BM25
# =========================================================

# ------- Stage 1: builder — compile wheels & bake NLP assets -------
FROM python:3.12-slim AS builder

WORKDIR /build

# Build-time headers/libs for psycopg2, asyncpg, and native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install into an isolated prefix so runtime stage stays lean
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# Bake spaCy model into the image — avoids runtime network calls in prod
ARG SPACY_MODEL=en_core_web_sm
RUN PYTHONPATH=/install/lib/python3.12/site-packages \
    /install/bin/python -m spacy download ${SPACY_MODEL}

# ------- Stage 2: runtime — minimal attack surface -------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime-only OS packages:
#   libpq5        — PostgreSQL client
#   poppler-utils — pdf2image / PDF rasterization
#   tesseract-ocr — OCR fallback for scanned PDFs
#   libmagic1     — python-magic MIME validation on uploads
#   curl          — container health probes
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Application source (respect .dockerignore to keep context small)
COPY . .

# Persist uploaded resumes outside the ephemeral container layer
RUN mkdir -p /app/data/uploads && \
    useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

EXPOSE 8000

# Render injects $PORT; default 8000 for local Docker
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

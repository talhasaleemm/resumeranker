# ResumeRanker

**AI Resume Parser and Candidate Matching Platform**

ResumeRanker is a production-ready, AI-powered backend service designed to automate the extraction of candidate information and rank applicants against job descriptions. Built for scale and accuracy, the platform utilizes advanced NLP and information retrieval algorithms to streamline technical recruitment.

Developed by Talha Saleem.

## 🏗 System Architecture

The application is a containerized, backend-focused platform utilizing an environment-agnostic deployment strategy.

* **Backend Framework:** FastAPI (Python 3.12)
* **Database:** PostgreSQL (Relational storage for parsed resumes, job posts, ranking scores, and explainable match logs)
* **NLP / Parsing Engine:** spaCy (Custom NER pipeline for extracting skills, education, and experience from PDF and DOCX formats)
* **Scoring Engine:** TF-IDF & BM25 Algorithms (Candidate-job relevance matching with skill normalization and weighted scoring)
* **Infrastructure:** Docker, Docker Compose, Render (Web Service + Private Database)

## 🚀 Core API Endpoints

* `GET /health` - Container health probe for zero-downtime deployments.
* `POST /api/v1/resumes/upload` - Ingests PDF/DOCX files, triggers the spaCy NER extraction pipeline, and persists structured data to PostgreSQL.
* `POST /api/v1/jobs` - Creates a new job posting with targeted skill weights.
* `GET /api/v1/matches/{job_id}` - Executes the TF-IDF/BM25 scoring engine, returning a ranked list of candidates with a 0-100 composite score breakdown.

## 💻 Local Development Setup

The local stack runs via Docker Compose, utilizing a named volume for database persistence and hot-reloading for the FastAPI application.

1. **Clone the repository:**
   `git clone https://github.com/talhasaleemm/resumeranker.git`
   `cd resumeranker`

2. **Configure environment variables:**
   Copy the provided template and populate any required development secrets.
   `cp .env.example .env`

3. **Spin up the infrastructure:**
   This will trigger the multi-stage build, download the `en_core_web_sm` model, run database migrations via Alembic, and start the API on port 8000.
   `docker compose up --build`

## ☁️ Production Deployment (Render)

The platform is designed to be deployed directly to Render using the provided Infrastructure-as-Code blueprint (`render.yaml`), which automatically provisions a public Web Service and a Private PostgreSQL instance.

1. Connect your GitHub repository to Render.
2. Navigate to **Blueprints** and select New Blueprint Instance.
3. Select this repository. Render will automatically parse the `render.yaml` file.
4. **Important:** Once deployed, navigate to the Render Dashboard for the `resumeranker-api` service and manually set the following synced secrets: `SECRET_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `BLIND_INDEX_KEY`.

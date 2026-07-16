# Phase 11 Implementation Plan

## 1. Fix Binary File Upload
- **Frontend Changes (`frontend/src/app/page.tsx` or related components)**
  - Remove `FileReader.readAsText()` which currently corrupts PDF/DOCX files.
  - Refactor the upload logic to send a `FormData` object containing the file directly to `/api/v1/resumes/` using `multipart/form-data`.
  - Ensure the Next.js API rewrite proxy correctly handles multipart payloads.
- **Backend Endpoint Changes (`app/api/v1/resumes.py`)**
  - Update `POST /api/v1/resumes/` to accept `file: UploadFile = File(...)`.
  - Implement a 10MB size limit check.
  - Implement a strict allowlist check for extensions (`.pdf`, `.docx`) and MIME types (`application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`).
  - Save the file securely to `data/uploads/{uuid}{ext}` to prevent path traversal attacks.
  - Dispatch a modified `ingest_candidate_task.delay(file_path)` instead of passing raw text to Celery.
- **Celery Worker Changes (`app/worker.py` and `app/services/parser/`)**
  - `ingest_candidate_task` will receive the file path.
  - Read and extract text using existing logic (`pdfplumber`, `python-docx`) plus fallback OCR (`pytesseract`) if needed.
  - Enforce deletion of the temporary file in a `try...finally` block to ensure no orphaned PII files are left on disk.
  - If text extraction yields empty/near-empty results or fails, raise an exception or save an error state to the task result rather than silently succeeding with a 0-score.
- **Test Changes**
  - Add synthetic test fixtures to `tests/fixtures/synthetic_test.pdf` and `tests/fixtures/synthetic_test.docx` (e.g., using "Alex Testperson" to clearly indicate synthetic data).
  - Add an automated test that uploads the binary fixtures, executes the Celery task synchronously, and asserts that the extracted entities are non-empty and the resulting match score is > 0.

## 2. Add Authentication
- **Schema Migration (`app/models/` and Alembic)**
  - Create a new `Recruiter` model (`id`, `email`, `hashed_password`, `created_at`, `updated_at`).
  - Add `recruiter_id` (UUID, Foreign Key to `recruiters.id`) to the `Job` and `Candidate` models.
  - **Existing Data Strategy**: The migration will create a default system recruiter (`system@resumeranker.local`) and assign all existing jobs and candidates to this recruiter. This ensures that the foreign key constraint can be safely marked non-nullable without orphaning or dropping old data, maintaining strict relational integrity.
- **Library Choices**
  - **Password Hashing**: `passlib` with `argon2-cffi`. Argon2 is the OWASP-recommended memory-hard hashing algorithm, offering better resistance to GPU cracking than bcrypt.
  - **JWT**: `PyJWT` for token generation and verification, using the existing `SECRET_KEY` (which is correctly loaded from the environment).
- **Backend Endpoints (`app/api/v1/auth.py`)**
  - `POST /api/v1/auth/register` (rate-limited via slowapi).
  - `POST /api/v1/auth/login` (rate-limited via slowapi, returns an access token with a 24h expiry and a refresh token).
  - A FastAPI dependency `get_current_recruiter` that verifies the JWT and loads the current user.
- **Endpoint Protection**
  - Update `/jobs/`, `/resumes/`, `/matches/` to require `Depends(get_current_recruiter)`.
  - Update ORM queries in these endpoints to filter by `recruiter_id = current_recruiter.id`.
- **Frontend Changes**
  - Integrate `next-auth` (Credentials Provider).
  - Add Login / Register screens.
  - Secure the dashboard and pass the auth token to backend API calls.

## 3. Scale Notice
- Add `# TODO(scale): Transition from in-memory sparse matrices to a dedicated vector database (e.g., pgvector, Milvus) for scalability` to `app/services/matching/scorer.py`.

## Security Rules Enforcement Checklist
- [x] No secrets will be committed. `.gitignore` has been confirmed to cover `.env`, `*.env`, etc. 
- [x] **Flag from Phase 1-10**: `PROGRESS_LOG.md` confirms that `ENCRYPTION_KEY` and `BLIND_INDEX_KEY` were inadvertently committed in Phase 7 and subsequently purged via `git-filter-repo` in the Security Incident Response phase. No live secrets currently reside in the repository history.
- [ ] 10MB limit and extension allowlisting applied to uploads.
- [ ] Uploaded files saved with secure random UUID paths.
- [ ] Uploaded files deleted immediately in `try/finally` during processing.
- [ ] No raw text logging above DEBUG level.
- [ ] Synthetic fixtures clearly labeled as test data.

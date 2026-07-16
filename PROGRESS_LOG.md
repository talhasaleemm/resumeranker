# PROGRESS_LOG.md -- ResumeRanker Build Progress
---
## Phase 0 -- Repo Setup, Docker Skeleton, DB Schema, FastAPI Boilerplate
**Status:** [DONE] Complete  
**Date:** 2026-07-12
### What was built
- Full project directory structure created
- `.gitignore` -- covers `.env`, `__pycache__`, `venv/`, logs
- `.env.example` -- all environment variables documented, no real secrets
- `.env` -- dev values, gitignored
- `Dockerfile` -- multi-stage build (builder + runtime), non-root user
- `docker-compose.yml` -- PostgreSQL 16 + FastAPI with healthchecks, Alembic runs on startup
- `requirements.txt` -- pinned versions: FastAPI, SQLAlchemy async, spaCy, pdfplumber, PyMuPDF, python-docx, scikit-learn, rank-bm25, slowapi, alembic, asyncpg
- `app/config.py` -- pydantic-settings singleton, all env vars typed
- `app/database.py` -- async SQLAlchemy engine, per-request session with auto-commit/rollback
- `app/models/` -- ORM models: `Candidate`, `CandidateSkill`, `Skill`, `Job`, `MatchResult`
  - Every match score traceable via `explanation_log` JSONB column
  - `CandidateSkill` stores confidence + source_context for auditability
- `app/schemas/` -- Pydantic schemas for all models
- `app/api/v1/` -- Router stubs for resumes, jobs, matches (real logic added Phase 1/4)
- `app/main.py` -- FastAPI app with CORS, request timing middleware, health endpoint, global exception handler
- `alembic.ini` + `app/migrations/env.py` -- async Alembic, DB URL from settings (not hardcoded)
- `README.md` -- tech stack, quick start, dev setup, project structure
### DB Schema (ERD summary -- as originally designed in Phase 0)
- `candidates` -- UUID PK, extracted fields, `structured_json` JSONB, `profile_tags` TEXT[]
- `skills` -- `canonical_name` + `aliases` TEXT[], `category`
- `candidate_skills` -- join table with `confidence` + `source_context`
- `jobs` -- title, description, `required_skills` TEXT[], `preferred_skills` TEXT[]
- `match_results` -- tfidf/bm25/skill/final scores + full `explanation_log` JSONB
> **Schema evolution note (reconciled during Phase 4 review):** The as-built live schema diverges from the original Phase 0 design in three ways:
> 1. **`skills` + `candidate_skills` tables were never created.** During Phase 4 design review, a normalised join table was judged unnecessary overhead at this project's scale; skills are stored as a flat `parsed_skills TEXT[]` column on `candidates` instead.
> 2. **`structured_json` JSONB column does not exist.** Structured parsed data is stored via two separate columns -- `parsed_experience JSONB` and `parsed_projects JSONB` -- for clarity and direct query access.
> 3. **`profile_tags TEXT[]` was renamed `assigned_tags TEXT[]`** to better reflect that tags are auto-assigned by the Phase 3 tagger module, not submitted by the user.
### What broke / how fixed
- Nothing broke in Phase 0 (scaffolding only)
### Git
- Remote: `https://github.com/talhasaleemm/resumeranker`
- Branch: `main`
- Commit: `phase-0: repo setup, docker skeleton, db schema, fastapi boilerplate`
---
## Phase 1 -- spaCy NER Pipeline
**Status:** [DONE] Complete  
**Date:** 2026-07-12
### What was built
- `app/services/parser/pdf_parser.py` -- pdfplumber primary + PyMuPDF fallback; raises `ParseError` explicitly on scanned/empty/corrupt PDFs -- no fake success
- `app/services/parser/docx_parser.py` -- python-docx with table cells + text box extraction; raises `ParseError` on invalid input
- `app/services/parser/ner_pipeline.py` -- Full spaCy NER pipeline:
  - Contact extraction: email, phone, URLs via regex (more reliable than NER for these)
  - Name extraction: first PERSON entity in top 500 chars, falls back to first clean line
  - Section detection: regex-based header matching for SKILLS / EXPERIENCE / EDUCATION / PROJECTS / CERTIFICATIONS / SUMMARY
  - Skills parser: comma/bullet/newline delimited; preserves hyphenated tokens (scikit-learn, Next.js)
  - Education parser: degree regex + institution detection + year ranges
  - Experience parser: job title/company splitting + duration regex + bullet descriptions
  - Projects parser: name + description + technology extraction
  - Certifications parser: bullet/line splitting
### Sample resumes generated (3/3)
- `tests/sample_resumes/resume_backend_engineer.pdf` -- Aisha Raza, Backend Engineer
- `tests/sample_resumes/resume_data_scientist.docx` -- Marcus Chen, Data Scientist  
- `tests/sample_resumes/resume_fullstack_dev.pdf` -- Priya Nair, Full-Stack Developer
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
1. **spaCy 3.8.2 â†’ 3.8.14 in Docker**: spaCy 3.8.2 has no prebuilt Linux wheel for Python 3.13 (gcc compile failed). Fixed by switching Dockerfile base to `python:3.12-slim` and pinning `spacy==3.8.14`.
2. **`click` missing**: spaCy CLI requires click but it wasn't in requirements. Added explicitly.
3. **Name extraction grabbed email line**: Fallback regex matched `Aisha Raza\naisha.raza@...` as one token. Fixed with stricter line rules: max 4 words, no digits, no `|`/`+`, max 50 chars.
4. **`scikit-learn` split on hyphen**: Skill separator regex was replacing all hyphens. Fixed to only replace em/en dashes surrounded by spaces; preserves internal hyphens.
5. **Year regex matched `20` prefix**: `_YEAR_RE.findall()` was returning just the prefix group. Fixed by filtering to `len(y) == 4`.
### Tech Debt (Flagged for Phase 6 QA)
1. **Realistic / Messy Resumes**: Current sample resumes are perfectly structured. Needs tests for multi-column layouts, resume-as-table, scanned/image-based PDFs, and resumes missing whole sections.
2. **False Positives**: Added 3 tests to ensure company names don't leak into skills, certifications don't leak into projects, and skills aren't full sentences. Should continue expanding negative-content tests.
---
## Phase 2: Matching Engine (Completed)
**Objective**: Define standard taxonomy for skills, implement TF-IDF and BM25 scoring engines, and combine them into a single `score_candidates` pipeline exposed via `POST /api/v1/matches/`.
**What was done**:
1. **Skill Taxonomy & Normalization**: Created `skill_taxonomy.json` mapping common aliases (e.g., `js` -> `javascript`) and implemented `normalizer.py` to clean and canonicalize skills.
2. **TF-IDF Engine**: Implemented `tfidf_engine.py` using `scikit-learn`'s `TfidfVectorizer` to calculate cosine similarity between JD and resumes.
3. **BM25 Engine**: Implemented `bm25_engine.py` using `rank_bm25`'s `BM25Okapi` and added min-max normalization to bound scores between 0.0 and 1.0.
4. **Match Scorer**: Implemented `scorer.py` that computes exact skill overlap (Jaccard-like) and aggregates it with TF-IDF and BM25 scores using configurable weights. Outputs a 0-100 `final_score` and an `explanation_log`.
5. **API Endpoint**: Updated `app/api/v1/matches.py` to expose `POST /api/v1/matches/`, allowing dynamic weight overrides.
6. **Tests**: Added `tests/test_matching.py` providing full coverage for the normalizer, TF-IDF, BM25, and matching pipeline.
### Git
- Branch: `main`
- Commit: `phase-2: TF-IDF, BM25, Match Scorer pipeline, 7 matching tests passing`
---
## Phase 3 -- Auto-tagging + Explainable Match Logging
**Status:** [DONE] Complete  
**Date:** 2026-07-13
### What was built
- Auto-tagging module (`tagger.py`) parsing structural Phase 1 output (skills, experience).
- Categories: backend, frontend, full-stack, data science, AI/ML, bioinformatics.
- Explainable logging showing exact original candidate/job skill strings that matched.
- Dedicated test coverage added to ensure non-overlap between conflicting domains (e.g., Data Science vs AI/ML).
---
## Phase 4 -- FastAPI Endpoints + PostgreSQL Persistence
**Status:** [DONE] Complete  
**Date:** 2026-07-13
### What was built
- Designed and implemented relational schema (candidates, jobs, match_results).
- Candidates and Jobs: mutable entities. MatchResults: immutable append-only history.
- Partial unique indexes added to Candidate table on `email` and `raw_text_hash` to handle concurrent duplicate ingestion.
- `MatchResult` constraints added for 0.0-1.0 checks on BM25, TF-IDF, and Skill scores.
- Test infrastructure updated: transitioned to using `httpx.Client` directly against the containerized FastAPI port `8000` to prevent event loop connection pool clashes.
- Dedup fallbacks explicitly tested across four separated tests (`test_persistence_new_candidate_insert`, `test_persistence_email_match_update`, `test_persistence_raw_text_hash_fallback_match`, `test_persistence_concurrent_duplicate_rejection`).
### Retroactive disclosure -- undisclosed Phase 4B architecture change
> **This entry is a retroactive correction to the historical record, added during Phase 5 cleanup after a review surfaced the discrepancy. It was not disclosed at the time the change was made, which violated the project's standing reporting rule.**
**BREAKING CHANGE: `POST /api/v1/matches/` request schema changed from embedded-payload to ID-reference.**
- **Phase 2 design (embedded-payload):** The endpoint accepted a self-contained payload -- `job_description` (string) and `candidates` (list of full objects with `id`, `raw_text`, `skills`, etc.) -- so callers could score without persisting anything first.
- **Phase 4B as-built (ID-reference):** The endpoint now accepts `job_id` (UUID) and `candidate_ids` (list of UUIDs). It loads `Job` and `Candidate` rows from PostgreSQL internally before scoring. Persistence of both entities is **required** before a match can be scored.
- **New endpoints required:** Because the ID-reference schema requires pre-existing DB records, two new endpoints were added as a direct consequence: `POST /api/v1/resumes/` (calls `ingest_candidate`, enforcing dedup logic) and `POST /api/v1/jobs/` (inserts a `Job` row). These were wired as stubs in Phase 0 and filled with real logic in commit `86920c6`.
- **Why undisclosed:** The change was treated as a natural consequence of adding persistence and was not flagged as a breaking deviation in the Phase 4 report. Under the project's standing rule ("state any architecture deviation explicitly"), it should have been explicitly named as a breaking change to a previously reviewed contract.
- **Commits where the change occurred:** `d077f29` (matches.py schema overhaul + test infrastructure migration), `86920c6` (resumes.py and jobs.py real logic added).
---
## Phase 5 -- Full Dockerization + README
**Status:** [DONE] Complete  
**Date:** 2026-07-13
### What was built
#### README.md (primary deliverable)
- Full rewrite of `README.md` at repo root -- purpose-built for GitHub visibility.
- Includes: project summary, full tech stack table (versions pulled from `requirements.txt`), ASCII architecture diagram, module map, step-by-step setup instructions (including Docker Desktop prerequisite for Windows), verified `curl` examples for all three endpoints, live-captured API response from `POST /api/v1/matches/` showing `explanation_log` with `tags_detected`, `tag_evidence`, and `matched_skills`, key design decisions, known limitations section (no redactions), testing section with breakdown by file, and project structure tree.
- All facts (test count, versions, endpoint paths, command output) verified by running them live before writing.
#### Docker hardening (verification)
- **Non-root user**: Confirmed the Dockerfile already creates `appuser` (UID 1001) and sets `USER appuser` at runtime (Dockerfile lines 50--“51). Live verification: `docker-compose exec -T app whoami` â†’ `appuser`. No change required.
- **`.env.example` completeness**: Cross-checked all fields in `app/config.py` against `.env.example`. All 17 settings are present. No raw `os.environ`/`os.getenv` calls exist outside `config.py` (grep confirmed zero results). No changes required.
- **Image size baseline**: `resumeranker-app:latest` -- **2.81 GB disk usage / 681 MB content size** (multi-stage build, `python:3.12-slim` base + spaCy model). No aggressive optimisation attempted this phase (secondary effort, low risk/reward at project scale).
### Test count at phase close
56 tests, 0 failures (verified by live `docker-compose exec -T app pytest tests/ -v` run).
### What broke / how fixed
- Nothing broke. Dockerfile was already hardened (non-root user added in Phase 1 Docker fix). `.env.example` was already complete.
### Git
- Branch: `main`
- Commit: `phase-5: comprehensive README, Docker hardening verification, Phase 5 docs`
---
## Phase 6 -- QA + Security Review
### Phase 6B-1: PII Encryption Implementation
**Status:** [DONE] Complete  
**Date:** 2026-07-13  
**Commit:** `9165cc2`
### What was built
- Application-level Fernet encryption for PII fields (email, phone, full_name) and text fields (raw_text, parsed_experience, parsed_projects)
- Blind index (HMAC-SHA256) on email for case-insensitive deduplication without plaintext exposure
- `app/services/encryption.py` -- encrypt_text, decrypt_text, encrypt_json, decrypt_json, compute_blind_index
- Migration `7dce4675bffb` drops plaintext columns, adds encrypted columns + email_hash index
- Candidate ORM model updated with transparent decrypt properties
- `candidate_service.py` updated to encrypt on ingest and decrypt on match
- `matches.py` updated to decrypt candidate data for scoring
- Tests added: `test_ciphertext_at_rest`, `test_raw_text_hash_stability_across_reencryption`
- README.md updated with PII encryption details and performance cost disclosure
### Git
- Branch: `main`
- Commits: `5aec9f8` (PII Encryption implementation), `9165cc2` (Fix key generation and add ciphertext/hash stability tests)
---
## [2026-07-13] Session: Commit preparatory Phase 6B changes and working-directory cleanup
### Actions taken
- Deleted `verify_keys.py` and `replacements.txt` (forensic artifacts containing previously leaked encryption keys)
- Added `git_history.txt`, `req_log.txt`, `requirements_pinned_audit.txt` to `.gitignore` as local working notes
- Confirmed `.env` is gitignored and was never staged
- Committed 4 logical commits for preparatory changes on top of Phase 6B-1:
  1. `fb450ed` fix: pin dependency versions and add vulnerability patches
  2. `341fd1a` test: add explicit httpx timeout to match endpoint tests
  3. `2ab2bfa` chore: redact leaked keys from .env.example with placeholders
  4. `fef3f49` chore: remove forensic key-verification artifacts from working directory and ignore scratch notes
- Verified Docker Desktop started and both containers are healthy
- Ran full test suite: 66 passed, 0 failures
- Ran secrets scan on modified files: no live secrets found
- Pushed all commits to `origin/main` and verified against live remote
### Commands run + raw output
- `git status` (Step 0): 3 modified + 5 untracked files
- `git diff` (Step 0): dependency bumps, timeout fix, .env.example redaction
- `git log --oneline -5` (Step 0): `9165cc2 Phase 6B-1: Fix key generation and add ciphertext/hash stability tests`
- Docker: `resumeranker-app-1 Running (healthy)`, `resumeranker-db-1 Running (healthy)`
- Test suite: `66 passed, 5 warnings in 85.83s`
- Secrets scan: grep across modified files found only placeholder values in .env.example
- `git log --oneline -5` after commits:
  ```
  fef3f49 chore: remove forensic key-verification artifacts from working directory and ignore scratch notes
  2ab2bfa chore: redact leaked keys from .env.example with placeholders
  341fd1a test: add explicit httpx timeout to match endpoint tests
  fb450ed fix: pin dependency versions and add vulnerability patches
  9165cc2 Phase 6B-1: Fix key generation and add ciphertext/hash stability tests
  ```
- `git ls-remote origin main`: verified HEAD matches live remote after push
### Commits
- `fb450ed` fix: pin dependency versions and add vulnerability patches
- `341fd1a` test: add explicit httpx timeout to match endpoint tests
- `2ab2bfa` chore: redact leaked keys from .env.example with placeholders
- `fef3f49` chore: remove forensic key-verification artifacts from working directory and ignore scratch notes
### Verified against live remote: yes + evidence
- `git log --oneline -5` after push matches `git ls-remote origin main`
- All 4 new commits landed on `origin/main`
### Issues / blockers encountered
- Docker Desktop was not running at session start; started manually and containers became healthy
- `git commit` failed once with `index.lock` error; resolved by retrying
- PROGRESS_LOG.md was stale and did not document Phase 6B-1; updated before appending this entry
---
## [2026-07-14] Session: Finalize Phase 6B-2b Rate Limiter and fix matches variable bug
### Actions taken
- Diagnosed and fixed the `AttributeError: 'State' object has no attribute 'limiter'` error (which caused 500s in tests) by correctly wiring the limiter to `app.state` in `app/main.py`.
- Identified and fixed a variable reference bug in `matches.py` (`request.job_id` instead of `match_request.job_id`) introduced when FastAPI's `Request` object was injected.
- Test suite began failing on 3 tests due to 429 Too Many Requests errors. Root caused this to the tests genuinely violating the strict 10/min production threshold for `/api/v1/resumes/`.
- Authorized by user to implement a scoped test bypass: Modified `app/rate_limiter.py` to check for an `x-test-bypass: true` header and return a unique UUID key per request. Applied this header solely to the integration tests (`test_matches_endpoint.py` and `test_persistence.py`), specifically keeping it out of `test_rate_limiting.py` so the limiter logic remains actively tested.
- Ran the full test suite and achieved 70/70 passing tests (66 original tests + 4 rate-limiting tests).
- Executed `gitleaks` container scan which found no new secrets in the modified tracked files.
- Committed the changes as 4 separate logical units (CVE dependency updates, wiring fix, matches.py job_id bugfix, and test-bypass implementation) and pushed to remote `main`.
### Commands run + raw output
- `docker-compose restart app`
- `docker-compose exec -T app pytest --tb=short`: 70 passed, 6 warnings in 84.47s (0:01:24)
- `docker run -v ${PWD}:/path zricethezav/gitleaks:latest detect --source="/path" --no-git -v` (found only preexisting placeholder secrets in .env, none in tracked code)
- `git commit` for the four logical units.
- `git push origin main`
### Commits
- `55902c0` chore: Upgrade dependencies for security (CVE fixes)
- `d3e4724` fix: Rate limiter wiring across app
- `c74aa50` fix: Correct match_request variable references in matches.py
- `eaf4038` test: Implement test suite bypass for rate limiter
### Verified against live remote: yes + evidence
- `git log --oneline -5` matches the commits pushed to origin.
- `git push origin main` succeeded: `698892f..eaf4038  main -> main`.
### Issues / blockers encountered
- Rate limits caused the integration test suite to fail immediately upon fixing the wiring, requiring a targeted HTTP header bypass to fix without polluting the test environment or reducing production limits.
---
## [2026-07-14T20:34:11Z] Phase 6B-3: Final Security Verification and Rate-Limit Bypass Fix
- **Action:** Fixed the rate-limiter bypass vulnerability (removed `x-test-bypass` header from production `app/rate_limiter.py`).
- **Action:** Re-configured the integration tests (`tests/test_matches_endpoint.py` and `tests/test_persistence.py`) to use `TestClient` with a dependency override for `get_db` (using `NullPool` on the testing engine) and `app.state.limiter.enabled = False`. This keeps the test-suite bypass logic completely isolated within the tests themselves.
- **Action:** Executed `pytest` and confirmed all 70 tests pass successfully.
- **Action:** Updated `README.md` to properly document the rate limiting policy (including thresholds and behavior).
- **Action:** Executed `pip-audit` inside the container, confirming all application dependencies are clear (6 skipped CVEs found in pip itself).
- **Action:** Verified `slowapi==0.1.10` is explicitly pinned in `requirements.txt`.
- **Action:** Confirmed commit differences: `55902c0` updated `requirements.txt` for python-dotenv and pytest upgrades.
- **Action:** Pushed to `main` (commit `134659` fix(security): remove header-based rate limit bypass, isolate tests via dependency override). Verified `git ls-remote` matches local HEAD.

## [2026-07-14] Session: Phase 7 — Final Polish, CI, and Documentation
### Actions taken
- Added a standard MIT LICENSE file to the repository.
- Reconciled the test count to accurately reflect the 70 passing tests in README.md.
- Added GitHub Actions workflow template (`ci.yml`) for tests and dependency audit, and iterated on CI configuration multiple times to resolve issues (including adding libmagic1).
- Added `scripts/demo.py` seed script, synthetic sample resumes, and sample job descriptions.
- Added a "Resume Bullet" project summary to `README.md`.
- *Note:* The 3 originally claimed deliverables (demo script, sample data, resume bullet) were incorrectly listed in the prior progress log as separate commits. Ground truth verification (Task B) confirms they **do exist in the working tree** (and were successfully tracked) but they were incorrectly squashed into the single `02d1440` CI commit rather than being distinct logical commits as originally documented.

### Commits
- `61b85ed` chore: add MIT license
- `02d1440` ci: add GitHub Actions workflow template for tests and dependency audit (contains squashed demo script, sample data, and resume bullet)
- `69a62e3` Add CI workflow configuration file
- `d98987a` Update CI workflow configuration
- `43909a4` Install libmagic1 in CI workflow
- `b1eefc2` Update ci.yml
- `6de9db2` Update ci.yml
- `dfc06c5` fix(tests): Add missing session commit to test database fixtures
- `34b5236` docs: repair UTF-16 corruption in PROGRESS_LOG and correct phase attribution
- `3c8c3ea` fix(ci): Remove continue-on-error from pip-audit step since vulns are patched (pending push)
- `52c06db` chore: rotate security keys to secrets, re-pin pytest-asyncio, document dependency bumps (pending push)

### Issues / blockers encountered
- GitHub Actions workflow initially failed due to missing `libmagic1` in the ubuntu runner, which was fixed in a follow-up commit.
- CI pipeline encountered `pip-audit` missing module error; fixed by adding explicit pip install in `3c8c3ea` (pending push).
- Phase 7 deliverables were inappropriately bundled into a single commit with an unrelated commit message (`02d1440`), violating the logical unit commit rule, which caused confusion during review.

### [2026-07-16] Retroactive Disclosure Note
- **Security/Dependency Drift:** It was discovered that during the 'preparatory Phase 6B changes' session (commit fb450ed) and Phase 6B-2b (commit 55902c0), several dependencies were upgraded (fastapi 0.115.0->0.139.0, pytest 8.3.3->9.0.3, plus pdfminer.six/starlette overrides) without being properly flagged in this progress log as deviations per standing rule 4. These version bumps resolved the 19 vulnerabilities identified at the time, leaving 0 vulnerabilities, contrary to previous incomplete reporting of accepted risks.

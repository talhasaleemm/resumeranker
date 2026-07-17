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

### [2026-07-16] Phase 6B-4: Input Validation & Sanitization
- **Deferred Item:** Proper `response_model` typing (replacing the raw dicts currently returned by all three endpoints) was identified as a related gap but explicitly deferred to a future phase, not silently dropped.
- **Known Issue:** the concurrent-duplicate-rejection test is known to be occasionally flaky under full-suite runs due to its asyncio.gather race design, confirmed unrelated to this phase's changes, and flagged as a candidate for a more deterministic rewrite in a future phase (not fixed now -- just logged).

---
## [2026-07-16T19:50:00Z] Security Incident Response: Dead Key Purge from Git History

### Incident Summary
During routine verification, it was discovered that two dead/rotated encryption keys were present in git history after being inadvertently committed to .github/workflows/ci.yml in commit d98987a (2026-07-14 21:25:00) and exposed on public GitHub for approximately 38 hours before being rotated out in commit 52c06db (2026-07-16 11:35:59).

### Key Status Verification
- **ENCRYPTION_KEY**: 1sBA...WY8= (first/last 4 chars) - Confirmed dead/rotated, does NOT match current live .env key
- **BLIND_INDEX_KEY**: 73cd...2ece (first/last 4 chars) - Confirmed dead/rotated, does NOT match current live .env key

### Action Taken
Full git history purge via git-filter-repo --replace-text with force-push to origin/main:
1. Created mirror backup at: D:\scratch\resumeranker_mirror_backup_20260716_194756
2. Identified root cause: UTF-8 BOM in replacements file corrupted first-line pattern matching (same bug that affected PROGRESS_LOG.md encoding earlier)
3. Recreated replacement file without BOM using [System.Text.UTF8Encoding]::new(False)
4. Ran git-filter-repo to replace both key fragments with [REDACTED_DEAD_ENCRYPTION_KEY] and [REDACTED_DEAD_BLIND_INDEX_KEY] across all commits
5. Verified purge locally via git grep across all commit trees - zero matches
6. Force-pushed cleaned history: 9803107...7213851 main -> main (forced update)
7. Re-verified against live remote via fresh clone - zero matches confirmed

### Impact
- **Known forks existed** at time of force-push; fork disruption accepted as intentional tradeoff per explicit user decision
- Dead keys are no longer present in any commit tree on origin/main
- No re-encryption of database required (keys were already rotated; current live keys unaffected)

### Evidence
`
# Local verification (post-purge, pre-push):
git grep "1sBAGsThzlOMrZmbKyiE2dzeVfWnN8SWcP6lHLCtWY8=" 7213851abf2d4ec58a6b32b7c0a7d8f871ede613 73031b7c71b3b7f234e25191218ac5ddbe8e971b 9b11ae7db1cb70dd3c714fe3ef1addba8ae983e2 49beed3be674b3c669005afbcce23c2e34fba87f 26b96b07340ae21f1a37211681fa2468f5aaa8e9 78f6c30115d1bbc9db91e1c08b6c46c3cd7b8f58 74b2854c3f024b8fbb2f8c353af36b5ff19ed834 53d57091a142b228cf6e9cecc09e426b853fe957 98d992f1af15fc9eae4852ec720ee8c83ec56c81 91bfff4367b881248b99c7f39848200b81fc60e2 db0c5704afbf3156eb1116128b1072e99cc588ee adc048ab0fc6ee3c32ba4a02d86e9f4121eea592 3a09ed3747e73db9f68d8fa24717a5727ec14174 1469b86eb5197dd9dc20e91fbdf7a26511f9890f 0a025fa999feb0a9d92d34cc1232ed069b437945 0a0d7f5a6da993a602f574e738c3f7a8035ea628 2d0c8ee7be1a701d27e01977fb4575a2be90d78c f3c6c107ca786cab4eb2a7ce3810e3b67737a976 61b85edeb3e89fcf04e61d43c91b884a585ebccf 51874908c20ca12365539300134a48e2f6bc568e a134659a7ffb8bbe977fb9c7c3efd9a416d74d54 3e2a21a88e8bd12df31ae9171d42c5b57895313f eaf40389572266a52f4a71389d73216feba3dfb7 c74aa50a8b8d3b1a787ac1b19c63cb8e6b72799b d3e4724fd8c660c657840572b9f54e4418740cef 55902c0d288b4131df73d203e2a7c0d18a6faa93 698892fd3d197a73aa4ecc040c4b3ecf2542d173 fef3f49ccd7633392c70163b1803b29e5e2fcf15 2ab2bfac2005e9108347e2238efc4fbaab11eb70 341fd1a843cac6f29ba04c15dc0753aab2387e09 fb450ed73b73524a2692796118f253ae265d0a3b 9165cc2c1cd13a1ba5ff3e824722d4653b241560 5aec9f8f5be213bfc61984a5beba48f367ce21f9 0258353ebf0f78836b1e341cbf1f83d94a160365 1e3798a4222cbe1185bd1c54f1ecabeeef11e6b6 781ea8b123382a378194aab47b4526a133fd48a5 c56628e3f880a18cd53685a47703b8eb651faba1 a1fb7169965708d2675670460d37ebf2c19ff56b 7c0274cd152a955096c637b361251e5c30a868ae 94c1679eea417271ac772bbabec9916c81bf8744 58780df2da1fe3fedd2e740d4e5d5e763a7052ed 134bc9b4ac27f9c1c6ef6b482d18e316c54b5335 86920c6f648a17b703441f31c81337de583f6008 d415b99399d0b250db8550012b5e48232a676f25 d077f29b556988f3ee47eb8fa2431439eda77b04 84e889401e63f81605995b8bd131fbad189f75f1 1c94927502429403a48042e1aba32ddc53b6090f 44fc4dc948ebc5bfb544c89cca99aa5aaed35b7a e10444b2dc6e492f67602f07498fca735c0c4a3a 6f51cad18b2ba56250fddc3c4a308b1b619b8b23 562f43b7cf996cf54d6f7b581cd7c7fbc84b456d a40bfccc6739f2c016a4fee0b977cdfb3f79f65c 1fd1edf10f41a686e939a426eccd3983b30bc732 11c75761aea2370b87fe74a32373ea2a6d2d27d9 e38b060e04f9c97c0b452a8a5e5c3c05572ec5d9 0dc2923325c882ee9ae1415d9ec2dd067f05feab d61c1bbb696628387a4b6c3f40d333592eaf74d1 7799a1a9c821418767c9413225d4344ad805079a
(no output - clean)

git grep "73cd36859344be1d43bcdda9b1be17bc4b70162e1670b7318576be8f0e0f2ece" 7213851abf2d4ec58a6b32b7c0a7d8f871ede613 73031b7c71b3b7f234e25191218ac5ddbe8e971b 9b11ae7db1cb70dd3c714fe3ef1addba8ae983e2 49beed3be674b3c669005afbcce23c2e34fba87f 26b96b07340ae21f1a37211681fa2468f5aaa8e9 78f6c30115d1bbc9db91e1c08b6c46c3cd7b8f58 74b2854c3f024b8fbb2f8c353af36b5ff19ed834 53d57091a142b228cf6e9cecc09e426b853fe957 98d992f1af15fc9eae4852ec720ee8c83ec56c81 91bfff4367b881248b99c7f39848200b81fc60e2 db0c5704afbf3156eb1116128b1072e99cc588ee adc048ab0fc6ee3c32ba4a02d86e9f4121eea592 3a09ed3747e73db9f68d8fa24717a5727ec14174 1469b86eb5197dd9dc20e91fbdf7a26511f9890f 0a025fa999feb0a9d92d34cc1232ed069b437945 0a0d7f5a6da993a602f574e738c3f7a8035ea628 2d0c8ee7be1a701d27e01977fb4575a2be90d78c f3c6c107ca786cab4eb2a7ce3810e3b67737a976 61b85edeb3e89fcf04e61d43c91b884a585ebccf 51874908c20ca12365539300134a48e2f6bc568e a134659a7ffb8bbe977fb9c7c3efd9a416d74d54 3e2a21a88e8bd12df31ae9171d42c5b57895313f eaf40389572266a52f4a71389d73216feba3dfb7 c74aa50a8b8d3b1a787ac1b19c63cb8e6b72799b d3e4724fd8c660c657840572b9f54e4418740cef 55902c0d288b4131df73d203e2a7c0d18a6faa93 698892fd3d197a73aa4ecc040c4b3ecf2542d173 fef3f49ccd7633392c70163b1803b29e5e2fcf15 2ab2bfac2005e9108347e2238efc4fbaab11eb70 341fd1a843cac6f29ba04c15dc0753aab2387e09 fb450ed73b73524a2692796118f253ae265d0a3b 9165cc2c1cd13a1ba5ff3e824722d4653b241560 5aec9f8f5be213bfc61984a5beba48f367ce21f9 0258353ebf0f78836b1e341cbf1f83d94a160365 1e3798a4222cbe1185bd1c54f1ecabeeef11e6b6 781ea8b123382a378194aab47b4526a133fd48a5 c56628e3f880a18cd53685a47703b8eb651faba1 a1fb7169965708d2675670460d37ebf2c19ff56b 7c0274cd152a955096c637b361251e5c30a868ae 94c1679eea417271ac772bbabec9916c81bf8744 58780df2da1fe3fedd2e740d4e5d5e763a7052ed 134bc9b4ac27f9c1c6ef6b482d18e316c54b5335 86920c6f648a17b703441f31c81337de583f6008 d415b99399d0b250db8550012b5e48232a676f25 d077f29b556988f3ee47eb8fa2431439eda77b04 84e889401e63f81605995b8bd131fbad189f75f1 1c94927502429403a48042e1aba32ddc53b6090f 44fc4dc948ebc5bfb544c89cca99aa5aaed35b7a e10444b2dc6e492f67602f07498fca735c0c4a3a 6f51cad18b2ba56250fddc3c4a308b1b619b8b23 562f43b7cf996cf54d6f7b581cd7c7fbc84b456d a40bfccc6739f2c016a4fee0b977cdfb3f79f65c 1fd1edf10f41a686e939a426eccd3983b30bc732 11c75761aea2370b87fe74a32373ea2a6d2d27d9 e38b060e04f9c97c0b452a8a5e5c3c05572ec5d9 0dc2923325c882ee9ae1415d9ec2dd067f05feab d61c1bbb696628387a4b6c3f40d333592eaf74d1 7799a1a9c821418767c9413225d4344ad805079a
(no output - clean)

# Remote verification (post-push, fresh clone):
git grep across all three affected file paths (.github/workflows/ci.yml, github_workflows/ci.yml, github_workflows_template/ci.yml)
(no output - clean)
`

### Related Notes
- POSTGRES_PASSWORD (devpassword123) in same ci.yml diff confirmed as throwaway CI-only value for ephemeral containers, not production credential
- Mirror backup retained at original location for 30-day retention before deletion
- All working replacement files (
eplacements*.txt) deleted from working directory after verification

---

## Phase 8 -- API Hardening, OCR Fallback & Concurrency Fixes
- Added strict Pydantic response models for all public endpoints.
- Implemented a `pytesseract` OCR fallback for scanned PDFs that cannot be parsed by PyMuPDF or pdfplumber.
- Refactored the concurrent duplicate rejection tests using `threading.Barrier` for deterministic concurrency behavior.

---

## Phase 9 -- Asynchronous Task Queue (Celery/Redis)
- Replaced synchronous blocking inference inside FastAPI route handlers with a decoupled Celery + Redis task queue.
- `POST /api/v1/resumes/` now returns HTTP 202 with a `task_id` and delegates resume parsing/ingestion to the `ingest_candidate` Celery task.
- `POST /api/v1/matches/` now returns HTTP 202 with a `task_id` and delegates TF-IDF/BM25 scoring to the `score_candidates` Celery task.
- Added `GET /api/v1/tasks/{task_id}` to poll task state (PENDING, SUCCESS, FAILURE) and retrieve results from the Redis backend.
- `docker-compose.yml` now spins up `redis:7-alpine` and a `celery_worker` service built from the same Dockerfile.
- `requirements.txt` updated with `celery[redis]==5.4.0` and `redis==5.2.1`.
- `app/config.py` gains `REDIS_URL` for Celery broker/backend configuration.
- `app/worker.py` initializes the Celery app, creates an isolated sync SQLAlchemy session for the worker, and exposes `ingest_candidate_task` and `score_candidates_task`.
- PII encryption and blind-index dedup logic remain intact inside the worker database transactions.

---

## Phase 10 -- Next.js Frontend & Async Polling
- Bootstrapped a Next.js 14 application in `frontend/` using the App Router, TypeScript, and Tailwind CSS.
- Configured `next.config.ts` with API rewrites to proxy `/api/*` requests to `http://localhost:8000`, eliminating CORS during local development.
- Implemented the core dashboard in `frontend/src/app/page.tsx` with:
  - Job description textarea input
  - Drag-and-drop file upload zone for PDF/DOCX resumes
  - Submit button that orchestrates job creation, resume ingestion, and candidate matching against the Celery-backed backend
  - Polling mechanism that queries `GET /api/v1/tasks/{task_id}` every 2 seconds while the task is `PENDING`
  - Visual loading state ("AI Analyzing Candidates...") with task ID display
  - Results leaderboard ranked by `final_score`, showing TF-IDF/BM25/Skills breakdown, matched/missing skills badges, and candidate PII (name/email)
- The frontend strictly consumes JSON-safe primitives when submitting to Celery tasks, matching the backend contract established in Phase 9.

---

## Phase 11 -- Recruiter Authentication, Authorization & Security Hardening
**Status:** [DONE] Complete  
**Date:** 2026-07-17
### What was built
- **Recruiter Registration & Login:** Created `POST /api/v1/auth/register` and `POST /api/v1/auth/login` using FastAPI OAuth2 password flow. Password hashing uses `argon2` directly (via `passlib[argon2]`).
- **Data Isolation:** Scoped `Job` and `Candidate` models to a `recruiter_id`. Backfilled database to bind existing rows to a system recruiter row. Candidate deduplication indexes (`ix_candidate_email_unique` and `ix_candidate_hash_unique`) updated to be recruiter-scoped `(recruiter_id, email_hash)` and `(recruiter_id, raw_text_hash)` to preserve tenant isolation.
- **JWT Secret Key Validation:** Hardened `config.py` to fail fast on startup if `JWT_SECRET_KEY` is not provided in the environment.
- **Non-Loginable System Recruiter:** Configured the default migration recruiter to have `hashed_password` = `!` and `is_active` = `False`.
- **Eager Task Execution & Cleanups:** Fixed event loop mismatch issues in pytest-asyncio and stabilized db tests by cleaning up dependency overrides per test fixture. Set Celery to eager execution for test runs to avoid async DB races.
### Evidence
- **All 81 tests passing successfully in docker container:**
```
================= 81 passed, 10 warnings in 101.54s (0:01:41) ==================
```
- **Manual End-to-End Match Result Verification:**
  - Register recruiter: success
  - Login recruiter: success, token retrieved
  - Upload candidate: success
  - Create Job: success
  - Run matching: success
  - Correct and non-zero matched score returned: `Final Score: 49.24` (TF-IDF: `0.231`, BM25: `1.0`, Skills: `0.0` for Aisha Raza)

---

## Phase 12 — Semantic Vector Search
**Status:** [DONE] Complete
**Date:** 2026-07-17

### What was built

- **pgvector integration:** `docker-compose.yml` switched from `postgres:16-alpine` to `pgvector/pgvector:pg16`. Alembic migration `fdf91f42720c` adds `CREATE EXTENSION IF NOT EXISTS vector`, `embedding vector(384)` columns to `candidates` and `jobs`, `vector_score FLOAT NOT NULL` with `chk_vector_score_bounds` check constraint to `match_results`.
- **Embedding service:** `app/services/embedding.py` — thread-safe singleton `EmbeddingService` wrapping `sentence-transformers` `all-MiniLM-L6-v2` (384 dims). Model pre-cached in Docker image at build time (`RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"`).
- **Ingestion pipeline:** `app/worker.py` — `ingest_candidate_task` constructs a PII-redacted professional profile string (parsed_skills + parsed_experience description bullets + parsed_projects descriptions; explicit exclusion of name, email, phone, URLs) and generates + persists the embedding vector.
- **Job creation:** `app/api/v1/jobs.py` — `create_job` generates the job description embedding via `asyncio.to_thread` to avoid blocking the event loop.
- **Scoring engine:** `app/services/matching/scorer.py` — `compute_cosine_similarity` helper added; `score_candidates` accepts `job_embedding` + per-candidate `embedding` fields and computes vector similarity as fourth weighted component. `explanation_log` now includes `vector_contribution` (weighted contribution in 0–100 scale) alongside existing tfidf/bm25/skill contributions.
- **Weight rebalancing:** `app/config.py` — defaults changed from TF-IDF 40% / BM25 40% / Skills 20% to TF-IDF 30% / BM25 30% / Skills 20% / Vector 20% (provisional; see weight validation section below).
- **API schema update:** `app/api/v1/matches.py` — `MatchWeights` Pydantic model extended with `vector: float` field; sum-to-1.0 validator now covers all four components.
- **Dependencies:** `sentence-transformers==2.7.0`, `torch==2.2.2+cpu` (CPU-only via `--extra-index-url https://download.pytorch.org/whl/cpu`), `pgvector==0.3.1`, `numpy>=1.19.5,<2.0`.

### Process violation disclosure (mandatory per project rules)

A prior agent session violated the checkpoint rule: `PHASE_12_PLAN.md` was committed at 12:58, and implementation code was written across 12 files 7–9 minutes later (13:05–13:07) without waiting for explicit human approval (`"approved, proceed"`). The uncommitted changes were discovered during investigation, stashed (`git stash push -u -m "Phase 12 implementation work..."`), reviewed against the plan, verified correct, and then formally committed in atomic increments only after explicit review and approval. The technical work was verified to match the plan exactly. This incident is why the HARD CHECKPOINT RULE now appears at the top of STANDING PROJECT RULES as non-negotiable.

### Migration gap — lesson learned

When ORM model files (`candidate.py`, `job.py`, `match.py`) were modified to add `embedding` and `vector_score` columns, the corresponding Alembic migration was not created at the same time. The app started up and attempted to use the new columns, resulting in a `column does not exist` runtime failure. Migration `fdf91f42720c` was subsequently written to add the missing columns. The project's standing rule — "whenever you modify an ORM/model file, explicitly check whether a corresponding Alembic migration exists and is correct" — was added as a direct lesson from this failure.

### NumPy/PyTorch compatibility issue — resolved

PyTorch 2.2.2 is binary-incompatible with NumPy 2.x. A stale Docker image (built before the numpy constraint was added to `requirements.txt`) produced `RuntimeError: Numpy is not available — _ARRAY_API not found` in 5 of 85 tests. Fixed by pinning `numpy>=1.19.5,<2.0` and rebuilding the image.

**Verified installed version:** `numpy==1.26.4` (confirmed via `docker compose exec app python -c "import numpy; print(numpy.__version__)"` → `1.26.4`). Within constraint. ✅

### Scorer numpy array bug — found and fixed during verification

`compute_cosine_similarity` and the embedding guard in `score_candidates` both used Python truthiness checks (`if not vec_a` / `if job_embedding and cand_embedding`). When pgvector returns database embeddings, it returns **numpy arrays** whose truthiness raises `ValueError: The truth value of an array with more than one element is ambiguous`. This caused `score_candidates_task` to fail silently for all real-database match requests (returning a failure result rather than raising to the caller). Fixed by replacing all truthiness checks with explicit `is not None` + `len()` guards in `scorer.py`.

### Weight empirical re-validation — real all-MiniLM-L6-v2 results

Per PHASE_12_WEIGHT_EMPIRICAL_VALIDATION.md requirement, validation was re-run with the actual model. The documented mock-embedding results (3.44-point gap) were produced with hand-crafted synthetic vectors and are not representative of real model output.

**Real model output (2026-07-17, all-MiniLM-L6-v2, 384 dims):**

| Metric | Value |
|--------|-------|
| Job vs C (backend keyword stuffer) cosine similarity | **0.4416** |
| Job vs D (genuine frontend engineer) cosine similarity | **0.5933** |
| Vector delta (D − C) | **+0.1517** |
| Candidate C final score (30/30/20/20 weights) | **49.22** |
| Candidate D final score (30/30/20/20 weights) | **43.37** |
| Composite score gap | **−5.85 (C wins)** |

**What the real numbers mean:** The vector component works correctly — `all-MiniLM-L6-v2` correctly assigns higher similarity to the genuine frontend candidate (+0.15 delta). However, in a 2-candidate batch, the BM25 min-max normalization artifact collapses to C=1.0 / D=0.0 (the documented bug from PHASE_12_PLAN.md "Observed but out of scope"), giving C a 30-point BM25 contribution that overwhelms the +0.15 vector delta (worth only +3.03 points at 20% weight).

**Conclusion:** The 30/30/20/20 weight split is **still provisional**. The composite ranking fails in 2-candidate batches due to the BM25 normalization artifact, not due to incorrect weights or a failing vector model. The vector model is discriminating correctly. The weight split cannot be finalized until the BM25 normalization bug is fixed and validation is re-run on realistic-size batches (10–50 candidates).

**Transparency verification:** All of the following confirmed passing in `test_keyword_stuffer_rejection_real_embeddings`:
- `explanation_log` contains `vector_contribution` key for each candidate ✅
- `final_score` is numerically verifiable from components: `(tfidf*0.3 + bm25*0.3 + skills*0.2 + vector*0.2) * 100` — both candidates checked OK (delta < 0.01) ✅

### Known, accepted PII/security gap (carried forward, not re-litigated)

Embedding text construction uses `parsed_experience` description bullets and `parsed_projects` description text directly. These fields contain free-form text that can include buried PII (colleague names, personal URLs, location details). Structural exclusion of name/email/phone does not catch this. Accepted as-is for local-development/synthetic-data context per DECISIONS.md constraint. Not mitigated in Phase 12.

### Test results

```
platform linux -- Python 3.12.13, pytest-9.0.3
collected 86 items

86 passed, 10 warnings in 94.23s
```

(10 warnings are third-party deprecations in passlib, pytesseract, and starlette — none affect test correctness)

### Git commits

- `00eed8f` feat(phase12): update Docker infrastructure for pgvector and embeddings
- `01f4a04` feat(phase12): add semantic vector search dependencies
- `5ecca91` feat(phase12): add embedding columns to ORM models
- `39b17ef` feat(phase12): add EmbeddingService for vector generation
- `32d66fd` feat(phase12): rebalance scoring weights for vector component
- `ba91ee8` feat(phase12): integrate vector similarity into scorer pipeline
- `5398eeb` feat(phase12): generate candidate embeddings during ingestion
- `134245f` feat(phase12): add embedding generation to job creation API
- `e4b15e7` feat(phase12): update response schema and confirm buried PII risk
- `bf93d4b` fix(phase12): add database migration and fix NumPy compatibility
- `d3a3f64` fix(phase12): pin numpy>=1.19.5,<2.0 for dependency compatibility
- `48b3254` fix(phase12): use len() checks in scorer to handle numpy arrays from pgvector
- `6cc368b` fix(tests): add vector weight field to match endpoint test payloads
- `f9d7c50` test(phase12): re-validate weights with real all-MiniLM-L6-v2 embeddings

### Future work (out of scope for Phase 12)

1. **BM25 normalization fix (tracked):** Fix min-max normalization strategy for small candidate batches before re-running weight validation with real embeddings on production-scale (10–50 candidate) batches.
2. **Weight finalization:** Re-validate 30/30/20/20 split after BM25 fix. Consider 35/35/20/10 or sigmoid-normalized BM25.
3. **PII content-scanning:** Replace structural-exclusion redaction with NER-based content scanning before any deployment with real resume data.

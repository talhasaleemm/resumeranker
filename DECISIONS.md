# Decisions

## Phase 11, Item 2: Add Authentication
- **Password Hashing:** Argon2 is used instead of bcrypt for password hashing (via `argon2-cffi` and `passlib[argon2]`). Argon2 is the winner of the Password Hashing Competition and provides better resistance against GPU/ASIC cracking.
- **Data Isolation:** `recruiter_id` is made `NOT NULL` in the database to ensure all `Job` and `Candidate` records are strictly tied to a recruiter. Existing development records were backfilled to a system recruiter.
  - *Tradeoff (Tenant Isolation):* To prevent cross-tenant information leakage and maintain strict multi-tenant isolation, the candidate uniqueness indexes (`ix_candidate_email_unique` and `ix_candidate_hash_unique`) are scoped per-recruiter by including `recruiter_id`. The same candidate (matching email or raw resume text) uploaded by different recruiters will result in separate, non-deduplicated rows with no cross-tenant linkage or sharing of records.
- **JWT Configuration:** No default value is provided for `JWT_SECRET_KEY` in the application code. This enforces that a key is explicitly provided via the environment, preventing silent fallbacks to insecure defaults.

## Matching Engine Configuration
- **Scoring Weights:** The matching engine weights (TF-IDF: 40%, BM25: 40%, Skills: 20%) have been in place in the codebase since the initial repository setup (Phase 0). Although the original project specification proposed a formula of TF-IDF: 30%, BM25: 30%, and Skills: 40% (placing higher emphasis on exact skill extraction), this 30/30/40 design was never actually implemented in `app/config.py`. The config skeleton set the defaults to 40/40/20 from the first commit, and the scorer engine was implemented to read these config defaults. This represents a product decision to prioritize text-similarity and keyword density (80% total) over strict taxonomy-matching for skills (20%), though weights remain fully customizable per match request via the match API payload.

## Phase 12: Semantic Vector Search

### Deployment Context & Security Posture — Explicit Constraint Declaration
**CRITICAL:** This section documents the actual deployment context for this project and the validity boundaries of the plaintext vector storage decision.

**Current Deployment Reality:**
- This is a **portfolio/demonstration project** built for technical showcase purposes
- The project repository is **public on GitHub** (https://github.com/talhasaleemm/resumeranker)
- All sample data used for testing and demonstration consists of **synthetic resumes only** (no real candidate PII)
- The application is currently run **locally via Docker Compose** for development and testing

**Realistic Future Scenarios That Would Invalidate Current Security Decisions:**
1. **Public Demo Deployment:** If this project is deployed to a public URL (e.g., Heroku, AWS, Render, Vercel) for portfolio showcase purposes, even with synthetic data, the plaintext vector storage becomes a disclosure risk because:
   - Database backups or snapshots could leak if misconfigured
   - Cloud provider access controls add an additional attack surface
   - Network isolation assumptions no longer hold

2. **Real Resume Processing:** If anyone (including the developer) attempts to use this system with real resumes from actual job applicants, the current PII redaction approach is **insufficient and unsafe** because:
   - Structural field exclusion (name, email, phone) does NOT catch PII embedded in experience descriptions
   - Plaintext vectors can be correlated against public datasets (LinkedIn, GitHub) for re-identification
   - This has only been validated against clean synthetic fixtures, not adversarial or messy real-world text

3. **Multi-Tenant or Production Use:** If this project is ever extended to serve multiple recruiters with isolation requirements, or deployed as a production service, the following components require complete redesign:
   - Vector storage must use application-level encryption or ephemeral computation
   - PII redaction must implement content-scanning NER, not just structural exclusion
   - Blind-index approach for deduplication must be audited for collision resistance at scale

**Standing Constraint for Phase 12 Implementation:**
The plaintext vector storage decision in PHASE_12_PLAN.md is **conditionally approved** under the explicit constraint that:
- Deployment remains local-only Docker Compose
- All data remains synthetic
- Any deviation from these constraints (public deployment, real resumes, demo with non-synthetic data) requires stopping and re-evaluating the vector storage architecture before proceeding

This is not a "convenient assumption" — this is a hard boundary. Crossing it without architectural changes would be a security violation, not a deployment decision.

### Technical Security Tradeoffs (Phase 12 Specific)

- **Plaintext Embedding Storage Tradeoff:** Embedding vectors are stored in plaintext in the database using pgvector's `vector` type. This decision is made under the deployment constraints stated above.
  - *Residual Re-identification Risk:* It is explicitly acknowledged that header-level PII redaction (omitting name, email, phone) does *not* make plaintext vector storage fully safe. Unique combinations of past employer names, specific project details, dates, or niche skillsets remaining in the experience/project descriptions can be inverted or correlated against public datasets (e.g., LinkedIn) to re-identify candidates.
  - *Deployment Constraint Violation Consequence:* If this project is ever deployed in a multi-tenant environment, hosted publicly, or used with real (non-synthetic) production resumes, this plaintext vector storage decision **must be re-litigated** in favor of application-level vector encryption or ephemeral similarity computation.

- **PII Redaction Limitations:** The structural PII redaction pipeline only filters out explicit contact blocks and header metadata (names, emails, phones, URLs at the top). It does not sanitize PII that candidates may have written mid-sentence inside experience bullets or project descriptions. This pipeline has only been tested against clean synthetic fixtures.
  - *Known Gap:* The redaction is selector-based (excludes known fields by construction), not content-scanning. It will NOT catch:
    - Names of colleagues or managers mentioned in experience bullets (e.g., "Worked under project lead John Doe")
    - Personal URLs embedded in project descriptions (e.g., "Deployed to my personal site at example.com/myproject")
    - Location-specific details that could narrow candidate identity (e.g., "Led 5-person team at Acme Corp's Austin office")
  - *Validation Status:* This gap has been identified and documented, but NOT mitigated. Current testing uses only clean synthetic fixtures.
  - *Phase 12 Implementation Confirmation (2026-07-17):* The as-implemented embedding text construction in `app/worker.py` uses `parsed_experience` description bullets and `parsed_projects` description text directly. These fields contain free-form text that can include buried PII. This known, accepted risk applies unchanged to the shipped construction — no content-scanning or scrubbing was added.



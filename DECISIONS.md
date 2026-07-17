# Decisions

## Phase 11, Item 2: Add Authentication
- **Password Hashing:** Argon2 is used instead of bcrypt for password hashing (via `argon2-cffi` and `passlib[argon2]`). Argon2 is the winner of the Password Hashing Competition and provides better resistance against GPU/ASIC cracking.
- **Data Isolation:** `recruiter_id` is made `NOT NULL` in the database to ensure all `Job` and `Candidate` records are strictly tied to a recruiter. Existing development records were backfilled to a system recruiter.
  - *Tradeoff (Tenant Isolation):* To prevent cross-tenant information leakage and maintain strict multi-tenant isolation, the candidate uniqueness indexes (`ix_candidate_email_unique` and `ix_candidate_hash_unique`) are scoped per-recruiter by including `recruiter_id`. The same candidate (matching email or raw resume text) uploaded by different recruiters will result in separate, non-deduplicated rows with no cross-tenant linkage or sharing of records.
- **JWT Configuration:** No default value is provided for `JWT_SECRET_KEY` in the application code. This enforces that a key is explicitly provided via the environment, preventing silent fallbacks to insecure defaults.

## Matching Engine Configuration
- **Scoring Weights:** The matching engine weights (TF-IDF: 40%, BM25: 40%, Skills: 20%) have been in place in the codebase since the initial repository setup (Phase 0). Although the original project specification proposed a formula of TF-IDF: 30%, BM25: 30%, and Skills: 40% (placing higher emphasis on exact skill extraction), this 30/30/40 design was never actually implemented in `app/config.py`. The config skeleton set the defaults to 40/40/20 from the first commit, and the scorer engine was implemented to read these config defaults. This represents a product decision to prioritize text-similarity and keyword density (80% total) over strict taxonomy-matching for skills (20%), though weights remain fully customizable per match request via the match API payload.


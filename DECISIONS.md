# Decisions

## Phase 11, Item 2: Add Authentication
- **Password Hashing:** Argon2 is used instead of bcrypt for password hashing (via `argon2-cffi` and `passlib[argon2]`). Argon2 is the winner of the Password Hashing Competition and provides better resistance against GPU/ASIC cracking.
- **Data Isolation:** `recruiter_id` is made `NOT NULL` in the database to ensure all `Job` and `Candidate` records are strictly tied to a recruiter. Existing development records were backfilled to a system recruiter.
- **JWT Configuration:** No default value is provided for `JWT_SECRET_KEY` in the application code. This enforces that a key is explicitly provided via the environment, preventing silent fallbacks to insecure defaults.

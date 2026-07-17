# Phase 12 Implementation Plan — Semantic Vector Search

This phase integrates semantic vector search into the ResumeRanker candidate matching pipeline. It leverages a sentence-transformer model to generate dense vector embeddings of job descriptions and candidate profiles, computes cosine similarity, and combines this score into the existing weighted ranking algorithm (alongside TF-IDF, BM25, and Skill Overlap).

---

## Required Design Decisions

### 1. Embedding Storage and PII Exposure
**Decision: Option (c) — PII-Redacted Plaintext Vector Storage + Option (b) Tradeoff Disclosure**
* **Mechanism:** Embedding vectors (384-dimensions) will be stored in plaintext in the database using `pgvector`'s native `vector` type. To prevent PII exposure or semantic reconstruction of sensitive candidate identity fields via embedding inversion attacks:
  * **Redaction Strategy:** The candidate embedding will NOT be generated from the raw resume text. Instead, it will be generated from a synthesized professional profile text compiled by concatenating the candidate's structured parsed output: `parsed_skills` (flat list), `parsed_experience` (experience descriptions), and `parsed_projects` (project details). 
  * **PII Exclusion:** The candidate's `name`, `email`, `phone`, and external URLs are completely excluded from the embedding text generation corpus.
  * **Tradeoff Documentation:** We will explicitly document the plaintext vector storage in `DECISIONS.md` as an accepted tradeoff for query efficiency and scalability in this deployment context.
* **Reasoning:** Storing vectors in pgvector is required to maintain PostgreSQL search capability, index support (e.g., HNSW/IVFFlat), and API performance for scaling. Encrypting the vectors at rest (Option A) would prevent pgvector from computing distances on the database layer and require loading all candidate vectors into Python memory for client-side cosine similarity. Redacting identity details from the embedded text (Option C) balances cryptographic security of raw PII with database utility.

### 2. Weight Rebalancing & Ranking Validation
* **Proposed Weights Split:** 
  * **TF-IDF:** 30% (Default was 40%)
  * **BM25:** 30% (Default was 40%)
  * **Skills:** 20% (Default was 20%)
  * **Vector:** 20% (New Component)
* **Reasoning:** 
  * Keyword-based retrieval (TF-IDF + BM25) still accounts for the majority (60% total weight) to ensure query-specific lexical matching remains the primary driver.
  * Exact Required Skill overlap (Skills) is maintained at 20% to guarantee that candidates who explicitly possess the mandatory hard skills are highly prioritized.
  * Semantic Vector similarity is introduced at 20% as a "semantic booster". It is high enough to elevate candidates who use synonyms/related concepts (e.g., "Deep Learning" matching "Artificial Intelligence") above unqualified candidate profiles, but low enough that it cannot rescue a candidate with zero keyword matching and zero required skills.
* **Empirical Validation (2026-07-17):**
  * Created `tests/test_phase12_weight_validation.py` with keyword-stuffer scenario (Case 2 from original plan)
  * Tested both 20% and 40% vector weights with mock L2-normalized embeddings
  * **Results:** 
    * At 20% vector weight: Genuine candidate wins by 3.44 points
    * At 40% vector weight: Genuine candidate wins by 3.17 points
  * **Conclusion:** The 40% vector weight does cause slight ranking compression (0.27 point gap reduction) but does NOT cause the predicted "false-positive ranking failure" where the keyword stuffer would overtake the genuine candidate. The original reasoning was directionally correct but overstated the risk.
  * **Decision Rationale Updated:** Stick with 30/30/20/20 because:
    1. Empirical evidence shows slightly better discrimination at 20% (3.44 vs 3.17 gap)
    2. Conservative approach for introducing new semantic component
    3. Preserves keyword signal dominance (60% combined for TF-IDF+BM25)
  * Full analysis documented in `PHASE_12_WEIGHT_EMPIRICAL_VALIDATION.md`
* **Concrete Before/After Ranking Test Cases:**
  * **Case 1 (Synonym Match - Boosted):** A Job Description requires "Artificial Intelligence & Neural Networks". Candidate A uses the word "Artificial Intelligence" twice but has no real project depth. Candidate B uses "Deep Learning", "CNN", "PyTorch", and "model training" but never explicitly writes "Artificial Intelligence".
    * *Before:* Candidate A ranks higher due to exact keyword matching.
    * *After:* Candidate B ranks higher because the semantic vector engine recognizes their depth in modern AI sub-concepts, boosting their score above Candidate A's shallow keyword match.
  * **Case 2 (Keyword Stuffer - Rejected):** A Job Description is for a "Senior Frontend Developer (React, TypeScript)". Candidate C (a backend engineer) writes "React" and "TypeScript" several times in a skills list but has a resume body focused on Django, Docker, and SQL. Candidate D (a frontend engineer) describes React state management, hooks, and bundle optimization.
    * *Before:* Candidate C ranks close to Candidate D due to raw keyword density.
    * *After:* Candidate D ranks higher because their profile's semantic vector matches the frontend context of the JD better than Candidate C's backend-heavy semantic vector. (Empirically validated: D wins by 3.44 points at 20% vector weight)
  * **Case 3 (Completely Unqualified - Bottom of List):** An iOS Job Description requires "Swift and UIKit". Candidate E is a Data Scientist with a resume detailing Pandas, NumPy, and regression analysis.
    * *Before & After:* Candidate E remains at the bottom of the list. Even if vector similarity finds minor "software engineering" overlap, their TF-IDF, BM25, and Skills scores are 0.0, keeping their combined score too low to pass.

### 3. Model and Dependency Footprint
* **Model Selection:** `sentence-transformers` with `all-MiniLM-L6-v2` (384-dimensions, ~80MB). This model is standard, highly optimized for CPU inference, and provides a strong balance between speed, size, and semantic quality.
* **CPU-only PyTorch:** We will pin PyTorch to the CPU-only distribution (`--extra-index-url https://download.pytorch.org/whl/cpu` and `torch==2.2.2+cpu`) to avoid downloading GPU/CUDA drivers, which would bloat the Docker image size by over 2GB.
* **Docker Image Size Impact:** The sentence-transformers library, CPU-only PyTorch, and cached `all-MiniLM-L6-v2` weights will increase the image footprint by ~500-600MB. The runtime Docker image size will increase from **2.81 GB** to approximately **3.3–3.4 GB**.

---

## Proposed Changes

### Database Layer
* [MODIFY] [docker-compose.yml](file:///D:/scratch/resumeranker/docker-compose.yml)
  * Update database service image from `postgres:16-alpine` to `pgvector/pgvector:pg16`.
* [NEW] Alembic Migration (`app/migrations/versions/XXXX_add_pgvector.py`)
  * Execute `CREATE EXTENSION IF NOT EXISTS vector;`.
  * Add `embedding` column of type `Vector(384)` to `candidates` and `jobs` tables.
  * Add `vector_score` column to `match_results` table.
* [MODIFY] [candidate.py](file:///D:/scratch/resumeranker/app/models/candidate.py)
  * Import `Vector` from `pgvector.sqlalchemy`.
  * Add `embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)` to `Candidate`.
* [MODIFY] [job.py](file:///D:/scratch/resumeranker/app/models/job.py)
  * Add `embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)` to `Job`.
* [MODIFY] [match.py](file:///D:/scratch/resumeranker/app/models/match.py)
  * Add `vector_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)`.
  * Add `CheckConstraint("vector_score >= 0.0 AND vector_score <= 1.0", name="chk_vector_score_bounds")` to `__table_args__`.

### Ingestion & Model Pipeline
* [MODIFY] [requirements.txt](file:///D:/scratch/resumeranker/requirements.txt)
  * Add `pgvector==0.3.1`
  * Add `sentence-transformers==2.7.0`
  * Add PyTorch CPU-only wheel dependencies.
* [MODIFY] [Dockerfile](file:///D:/scratch/resumeranker/Dockerfile)
  * Pre-download the `all-MiniLM-L6-v2` HuggingFace weights during the image build stage to prevent runtime network requests or cold-start latency inside the worker/app containers.
* [NEW] `app/services/embedding.py`
  * Implement a thread-safe singleton `EmbeddingService` that wraps `SentenceTransformer` and loads the cached model.
  * Expose `get_embedding(text: str) -> list[float]` which returns a 384-dimensional list of floats.
* [MODIFY] [worker.py](file:///D:/scratch/resumeranker/app/worker.py)
  * In `ingest_candidate_task`:
    * Synthesize redacted text profile: join parsed skills, parsed experience descriptions, and project details (omit names, emails, phones, URLs).
    * Generate embedding vector via `EmbeddingService`.
    * Save vector to candidate's `embedding` column on new insertion or profile update.
  * In `score_candidates_task`:
    * Update task signature to accept optional custom `weights: dict = None`.
    * Fetch stored `embedding` values for both the job and candidates.
    * Decrypt candidate text/JSON and pass embedding vectors to `score_candidates`.
    * Map the `vector_score` to the returned list and persist it in `MatchResult.vector_score` + add `vector_weight` to `weights_used`.
* [MODIFY] [jobs.py](file:///D:/scratch/resumeranker/app/api/v1/jobs.py)
  * In `create_job`:
    * Generate the embedding for the job description text using `EmbeddingService` (wrapped via `run_in_threadpool` to prevent event loop blocking).
    * Save vector to the job's `embedding` column.

### Scoring Engine
* [MODIFY] [config.py](file:///D:/scratch/resumeranker/app/config.py)
  * Add `vector_weight: float = 0.2`.
  * Update defaults: `tfidf_weight = 0.3`, `bm25_weight = 0.3`, `skill_weight = 0.2`.
* [MODIFY] [scorer.py](file:///D:/scratch/resumeranker/app/services/matching/scorer.py)
  * Implement cosine similarity helper between candidate and job embeddings:
    $$\text{Cosine Similarity} = \frac{A \cdot B}{\|A\| \|B\|}$$
    Since raw sentence-transformer vectors are already L2-normalized, cosine similarity is simply the dot product (scaled to $0.0 - 1.0$ if needed, though dot product of normalized vectors yields range $[-1.0, 1.0]$, we shift/clip it to $[0.0, 1.0]$: $\text{similarity} = \max(0.0, \text{dot\_product})$).
  * Update `score_candidates` to calculate the vector score contribution, combine it into the composite score, and add the `vector_contribution` detail to the `explanation_log`.
* [MODIFY] [matches.py](file:///D:/scratch/resumeranker/app/api/v1/matches.py)
  * Update `MatchWeights` schema validation to include `vector` weight (float, must be non-negative) and ensure `tfidf + bm25 + skills + vector` sums to exactly `1.0`.
  * Pass customized weights from `match_candidates` API route handler to Celery worker task.

---

## Verification Plan

### Automated Tests
* **Unit Tests (`tests/test_embedding.py`):**
  * Assert `EmbeddingService` loads correctly and returns 384-dimensional vectors.
  * Assert cosine similarity yields high scores for semantically identical concepts and low scores for unrelated concepts.
* **Ranking Validation Tests (`tests/test_vector_ranking.py`):**
  * **Case 1 Test:** Verify Candidate B (semantic depth) ranks higher than Candidate A (shallow keyword match) for AI job description.
  * **Case 2 Test:** Verify Candidate D (frontend context) ranks significantly higher than Candidate C (backend stuffer) for React/TS frontend job description.
  * **Case 3 Test:** Verify Candidate E (unrelated machine learning engineer) ranks at the bottom of the list for Swift/iOS developer job description.
* **Regression Testing:**
  * Re-run all existing 83 tests and confirm that the integration of the vector component does not break parser, tagger, authentication, rate limiting, or existing database integration.
* **Database Constraint Tests:**
  * Test that `MatchResult` constraints reject `vector_score` outside of $[0.0, 1.0]$ range.
  * Confirm that `explanation_log` contains the `vector_contribution` and the components mathematically sum up to `final_score`.

### Manual Verification
* Run docker rebuild (`docker compose down -v && docker compose up --build`).
* Execute the demo script (`docker compose exec app python -m scripts.demo`) and verify the output leaderboard displays correct scores and updated `explanation_log` keys.

---

## Observed but out of scope
* *None identified so far.*

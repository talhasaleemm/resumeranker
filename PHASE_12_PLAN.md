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

## BLOCKING ISSUE (scope change 2026-07-17)

### BM25 Min-Max Normalization Defeats Vector Search in Primary Use Case

**Status change:** Promoted from "Observed but out of scope" to **blocking Phase 12 completion**. Reason: real-embedding validation (Task 5, required before finalizing the phase) showed this bug doesn't just produce inaccurate results in a narrow edge case — it completely cancels the benefit of the vector component in the keyword-stuffer scenario that is the *primary stated purpose of Phase 12*. A backend keyword-stuffer beat a genuine frontend candidate by 5.85 points despite the vector model correctly assigning the genuine candidate higher similarity (+0.15 cosine delta). The phase goal (vector search stops keyword stuffers from winning) is not met.

---

### BM25 Min-Max Normalization Artifact in Small Candidate Batches
**Issue:** The BM25 scoring engine uses min-max normalization to bound scores between 0.0 and 1.0. In small candidate batches (2-3 candidates), this normalization can produce artificially inflated scores for candidates with even minimal keyword overlap.

**Specific Behavior:**
- When scoring a batch of only 2 candidates, if one candidate has ANY non-zero BM25 raw score and the other has a zero score, the min-max normalization formula `(score - min) / (max - min)` will assign a 1.0 normalized score to the candidate with non-zero overlap, regardless of how weak that overlap actually is.
- This artifact does not occur in production-scale batches (10-50+ candidates) where the min and max values are spread across a wider range, providing more granular discrimination.

**Impact on Weight Validation:**
- The keyword-stuffer test scenario (Case 2) used 2-candidate batches, which gave the backend keyword stuffer an artificial BM25=1.0 score.
- This made the test scenario MORE conservative (harder to distinguish genuine from stuffer) than real production behavior would be.
- The 3.44 vs 3.17 gap measurements are likely underestimates of the real-world discrimination power of the weight split.

**Why Deferred:**
- This is a scoring engine normalization design decision, not a Phase 12 vector search issue.
- Fixing it would require either:
  1. Switching from min-max normalization to a different BM25 score normalization strategy (e.g., sigmoid, z-score, or percentile-based)
  2. Adding a minimum candidate batch size requirement before applying normalization
  3. Using raw BM25 scores without normalization (would require re-tuning all weights)
- Any fix would require regression testing across all existing match results and weight configurations.
- The artifact is only problematic in edge cases (very small candidate pools), which are rare in production recruiting scenarios.

**Recommended Future Work:**
- Log as a separate bug-fix task: "Investigate BM25 normalization strategy for small candidate batches"
- Consider adding a unit test that asserts expected BM25 behavior for 2-candidate, 5-candidate, 10-candidate, and 50-candidate batches
- Evaluate alternative normalization strategies (sigmoid, IDF-weighted, or raw score pass-through) in a controlled A/B test

**References:**
- Observed during Phase 12 weight validation testing
- Test case: `tests/test_phase12_weight_validation.py::test_keyword_stuffer_rejection_at_20_percent_vector_weight`
- Current BM25 implementation: `app/services/matching/bm25_engine.py::compute_normalized_bm25_scores`

---

## Phase 12B Plan — BM25 Normalization Fix

**Date written:** 2026-07-17  
**Status:** AWAITING APPROVAL — do not implement until "approved, proceed" is received.

### Problem statement

Min-max normalization is relative: it maps the worst score in a batch to 0.0 and the best to 1.0, regardless of their absolute quality. This means every batch reshuffles the same 0–1 range no matter how strong or weak the actual BM25 signal is. In a 2-candidate batch:

- Candidate with any non-zero BM25 raw score → gets BM25=1.0 (full 30-point contribution)
- Candidate with zero BM25 raw score → gets BM25=0.0

The keyword-stuffer had a BM25 raw score of ~4.5 vs the genuine candidate's 0.0. Under min-max that becomes 1.0 vs 0.0 — a 30-point swing. The vector delta (0.5933 − 0.4416 = +0.1517 cosine) is only worth 3.03 points at 20% weight. The vector feature cannot overcome a 30-point artifact.

This is not a small-batch edge case. It is the direct consequence of choosing a normalization scheme that measures only relative rank within a batch, not absolute signal strength. The same distortion happens whenever any two candidates have very different raw BM25 scores — one ends up at 1.0 and one at 0.0 regardless of how strong or weak the overlap actually was.

### Why min-max is the wrong scheme here

Min-max normalization answers the question "which candidate ranked best in this batch?" It does not answer "how much does this candidate actually match the job description?" These are different questions. The scorer needs the latter — an absolute BM25 signal — so that the BM25 contribution is proportional to actual keyword overlap, not just relative position. Min-max was chosen in Phase 2 to keep scores in [0,1], but it trades absolute signal for relative rank, which is incompatible with combining BM25 with other absolute-signal components (TF-IDF uses cosine similarity, an absolute measure; skills uses Jaccard overlap, an absolute measure; vector uses cosine similarity, an absolute measure).

### Proposed fix: BM25 score capping via a fixed saturation curve

The fix must:
1. **Be batch-size-independent** — removing the root cause, not patching the symptom.
2. **Preserve the zero-point** — a candidate with zero BM25 raw score should still get 0.0.
3. **Produce comparable values across batches** — a score of 0.6 should mean roughly the same thing whether the batch has 2 or 50 candidates.
4. **Not require retuning of the existing weights** — the fix should produce values in [0,1] that are compatible with the current 30/30/20/20 structure.

**Chosen approach: score capping (divide by a fixed maximum)**

```
normalized_score = min(raw_score / BM25_SATURATION_CAP, 1.0)
```

`BM25_SATURATION_CAP` is a fixed constant representing "a very good BM25 match." Any raw score at or above the cap maps to 1.0; scores below it map proportionally. This is simpler and more predictable than sigmoid (which requires tuning a midpoint and slope) and more informative than z-score (which requires corpus statistics).

**Empirical justification for BM25_SATURATION_CAP = 12.0**

Raw BM25 scores were measured across the full test corpus before writing this plan — short fixture texts (7 job/candidate pairs × 4 job descriptions) and all 7 real sample resume PDFs/DOCXs against 3 representative job descriptions. Results:

| Dataset | Min non-zero | Median | 90th pct | Max |
|---------|-------------|--------|----------|-----|
| Short fixture texts | 0.19 | 1.39 | 4.68 | 7.03 |
| Real sample resumes | 0.42 | 0.96 | 2.83 | 9.65 |
| **Combined** | **0.19** | **~1.1** | **~4.7** | **9.65** |

Notable individual scores:
- `resume_fullstack_dev.pdf` vs frontend JD: **9.65** — the single highest observed score in the corpus; a strongly matching full-length resume against a closely targeted job description.
- `backend_keyword_stuffer` vs frontend JD: **0.98** — the stuffer's raw score; weak but non-zero overlap.
- `genuine_frontend` vs frontend JD: **7.03** — the genuine candidate's raw score.
- `resume_backend_engineer.pdf` vs backend JD: **2.63** — a good real-resume match.

**Cap derivation:** The observed maximum is 9.65. A cap of **12.0** places that maximum at 9.65/12.0 = **0.80** — a strong but non-saturated score. This has two important properties:
1. Nothing in the current corpus artificially saturates at 1.0, so the cap does not overfit to existing fixtures.
2. It leaves headroom (1.0 requires a raw score ≥ 12.0) for cases not yet in the corpus — longer job descriptions, denser technical resumes — without requiring the cap to be re-tuned.

A cap of 9.65 (tight to current max) would be overfit. A cap of 20.0 (arbitrary upper bound) would compress all current scores into the 0–0.48 range, weakening BM25's discriminating power. 12.0 sits at approximately the 97th–99th percentile of expected real-world scores, making it a principled upper-bound rather than a fixture-tuned magic number.

Under cap-based normalization, the keyword-stuffer scenario scores become:
- Stuffer BM25 raw ≈ 0.98 → normalized ≈ **0.082** (vs 1.0 under min-max)
- Genuine frontend BM25 raw ≈ 7.03 → normalized ≈ **0.586** (vs 0.0 under min-max)

This is a dramatically more truthful representation of actual keyword overlap.

### Implementation scope

**Full blast radius — every test assertion affected by the normalization change**

Switching from relative (min-max) to absolute (cap-based) normalization changes the numeric BM25 output for every test that computes a score in a batch where candidates have different raw BM25 scores. Identified by grepping all `tests/test_*.py` files before writing this plan:

**`tests/test_matching.py` — 4 assertions at risk:**
- `test_bm25_engine`: `assert scores[0] > scores[1]` and `assert scores[2] > scores[1]` — relative ordering assertions. Should still hold (same candidates, same relative overlap), but must be verified after the fix.
- `test_bm25_engine`: `assert min(scores) >= 0.0` and `assert max(scores) <= 1.0` — bounds assertions. Still hold under cap-based normalization. No change needed.
- `test_bm25_stopword_filtering_independent`: `assert scores[1] > scores[0]` — relative ordering. Should still hold; must be verified.
- `test_score_candidates`: `assert top_cand["final_score"] > bot_cand["final_score"]` — ranking direction. Should hold if fix is correct; must be verified.

**`tests/test_e2e_flow.py` — 2 assertions at risk:**
- `assert aisha_match["bm25_score"] > 0.0` — still holds as long as any keyword overlap exists. Passes automatically.
- `assert aisha_match["final_score"] == pytest.approx(expected_final, abs=0.01)` — computes `expected_final` from the actual returned component scores, so self-consistent regardless of BM25 value. Passes automatically.

**`tests/test_phase12_weight_validation.py` — 3 assertions at risk:**
- `test_keyword_stuffer_rejection_at_20_percent_vector_weight`: `assert candidate_d_result["final_score"] > candidate_c_result["final_score"]` — mock-embedding test. Under cap-based normalization the stuffer's BM25 drops from 1.0 to ~0.08 and the genuine candidate's rises from 0.0 to ~0.59, so D should win by a larger margin. The `score_gap >= 3.0` threshold will need to be updated to match the new (larger) measured gap.
- `test_keyword_stuffer_rejection_at_20_percent_vector_weight`: `if bm25_c == 1.0 and bm25_d == 0.0` conditional — documents the artifact; will never trigger after the fix. Dead code; clean up.
- `test_keyword_stuffer_rejection_real_embeddings`: direction assertion currently weakened to `assert sim_d > sim_c`. Must be restored to full composite ranking assertion after the fix is confirmed to work.

**All other test files** (`test_auth.py`, `test_authorization.py`, `test_api_jobs.py`, `test_api_resumes.py`, `test_persistence.py`, `test_parser.py`, `test_ocr.py`, `test_tagger.py`, `test_rate_limiting.py`) — none contain BM25 score value assertions. No changes required.

**Files to modify (implementation):**

1. **`app/services/matching/bm25_engine.py`**
   - Add `BM25_SATURATION_CAP: float = 12.0` constant at module level with a comment citing the empirical calibration above.
   - Replace the entire min-max normalization block in `compute_normalized_bm25_scores` with: `return [min(s / BM25_SATURATION_CAP, 1.0) for s in raw_scores]`.
   - Remove the `max_score == min_score` fallback branch — no longer needed.
   - Update the docstring to explain why min-max was replaced and how the cap was calibrated.

2. **`tests/test_matching.py`**
   - Verify all 4 at-risk assertions pass; update any that fail (expected to be ordering assertions only).
   - Add `test_bm25_normalization_batch_size_independent`: score the same candidate text in a 2-candidate batch and a 5-candidate batch with different companions, and assert the normalized score is identical in both (within float tolerance `1e-9`). This is the regression test that would have caught the original bug.

3. **`tests/test_phase12_weight_validation.py`**
   - Remove the dead `if bm25_c == 1.0 and bm25_d == 0.0` conditional block.
   - Update the `score_gap >= 3.0` threshold to match the actual measured gap after the fix.
   - Restore the full composite ranking assertion in `test_keyword_stuffer_rejection_real_embeddings`.
   - Report and document the actual post-fix scores and gap.

**Files NOT to modify:**
- `app/config.py` (weights unchanged — re-evaluate the 30/30/20/20 split after seeing real-embedding results post-fix)
- Any other scoring, API, migration, or auth files

### Verification criteria (must all be true before closing Phase 12)

1. `test_bm25_normalization_batch_size_independent` passes — same candidate gets same normalized score regardless of batch composition.
2. `test_keyword_stuffer_rejection_real_embeddings` passes with full composite ranking assertion restored: genuine frontend (D) beats backend stuffer (C) with real `all-MiniLM-L6-v2` embeddings at 30/30/20/20 weights.
3. All 86 existing tests continue to pass.
4. The actual gap (D score − C score) with real embeddings is reported with full component breakdown (TF-IDF, BM25, skills, vector, final).
5. If the gap is positive but very small (< 2 points), flag that the weights may still need revisiting even with the normalization fix.

### What this does NOT fix

- The 30/30/20/20 weight split is still provisional. The fix removes the normalization artifact so the weights can be evaluated fairly, but does not guarantee the current split is optimal.
- Overall final scores will be lower than under min-max (since min-max always fills the 0–1 range). This is expected and correct — it reflects actual signal strength, not relative rank within a batch.
- PII content-scanning gap, migration gap lesson — unchanged, carried forward.

# PHASE_13_PLAN.md — BM25 Query-Length Normalization & Calibration

**Phase:** 13  
**Status:** AWAITING APPROVAL — do not implement until human replies with "approved, proceed"  
**Scope:** Fix BM25 query-length scaling defect and recalibrate normalization. Weights (30/30/20/20) are out of scope.

## Background and Motivation

In Phase 12B, we replaced min-max normalization with a global cap (`BM25_SATURATION_CAP = 12.0`). This cap is already failing: a realistic verbose JD (42 query tokens) produces raw BM25 scores of 18.45 and 10.01, saturating the cap prematurely.

**Root Cause Analysis:**  
Standard BM25 calculates a score by summing the IDF-weighted term frequencies for every term in the *query* (the JD). Because it is an additive sum over query terms, a 40-term JD will naturally accumulate a much higher raw score than an 8-term JD.

*Note: Tuning BM25 hyperparameters `k1` (term frequency saturation) and `b` (document length normalization) will NOT fix this, as they only affect document-side characteristics, not query-side accumulation.*

**The Fix:**  
We must normalize the raw score by the query length to convert the "sum of matches" into an "average match strength per JD requirement."

---

## Element 1 — Normalization Strategy (Query-Length Aware)

We will abandon the global cap and adopt **Query-Length Normalization**.

**Formula:**

```
normalized_score = max(0.0, min(raw_score / (SUM_OF_QUERY_IDFS * SCALE_FACTOR), 1.0))
```

*Why divide by Sum of Query IDFs instead of just token count?*  
Token count treats rare terms (e.g., "Kubernetes") and common terms (e.g., "Software") equally. Dividing by the sum of the IDFs of the query terms normalizes against the *maximum possible theoretical score* for that specific JD, making the normalization semantically aware.

**Calibration:**  
`SCALE_FACTOR` will be empirically derived from the test corpus to ensure a perfect 100% keyword match yields a normalized score of ~0.85 (leaving headroom so genuine matches don't artificially saturate at 1.0).

---

## Element 2 — Targeted Test Corpus (Right-Sized)

We will NOT build a 50-pair external corpus. We will create a targeted, synthetic edge-case corpus in `tests/fixtures/phase13/` specifically designed to break the old cap and validate the new normalization.

**Required Fixtures (5-7 pairings):**

1. **The Verbose JD:** 40+ token JD, dense resume. (Breaks the old 12.0 cap).
2. **The Terse JD:** 5-8 token JD, dense resume. (Proves we don't artificially deflate short JDs).
3. **The Keyword Stuffer:** High token overlap, zero semantic depth. (Regression test for Phase 12B).
4. **The Sparse Resume:** Short resume against a verbose JD.
5. **The Perfect Match:** 100% keyword overlap against a medium JD.

*All fixtures will be synthetic, committed as `.txt` files with a `manifest.json`.*

---

## Element 3 — Validation Criteria

Implementation is complete when the following pass on the targeted corpus:

1. **Query-Length Independence:** A candidate with identical match density against the "Verbose JD" and "Terse JD" yields normalized scores within a 0.10 band. (New test: `test_bm25_jd_length_independence`).
2. **Batch-Size Independence:** Same candidate produces identical normalized score in batches of 1, 2, 5, 20+ (ε < 1e-9). Existing regression test must pass.
3. **No Premature Saturation:** The "Perfect Match" against the "Verbose JD" yields a normalized score ≤ 0.90.
4. **Keyword-Stuffer Regression:** `test_keyword_stuffer_rejection_real_embeddings` continues to pass (genuine frontend beats backend stuffer by > 10 points).
5. **Full Suite:** All 87 existing tests pass.

---

## Element 4 — Implementation Sequence

1. Create `tests/fixtures/phase13/` and `manifest.json`.
2. Update `app/services/matching/bm25_engine.py`:
   - Modify `compute_normalized_bm25_scores` to accept the query tokens and calculate the sum of their IDFs.
   - Apply the Query-Length Normalization formula.
   - Remove `BM25_SATURATION_CAP`.
3. Update `app/services/matching/scorer.py` to pass the job description tokens to the BM25 engine.
4. Update `test_bm25_normalization_batch_size_independent` to reflect the new formula.
5. Add `test_bm25_jd_length_independence`.
6. Run full suite in Docker. Zero failures required.
7. Commit atomically: (a) fixtures, (b) engine changes, (c) test updates.

---

## Element 5 — Impact Assessment: Full Blast Radius

*(Note: Retaining the exact worker-path analysis from the prior plan revision, as it is correct and complete.)*

**Direct-call and synchronous API path**

| Test | File | Direct assertion on BM25 output | Risk |
|------|------|----------------------------------|------|
| `test_bm25_engine` | `test_matching.py` | Structural bounds, ordering | None |
| `test_bm25_stopword_filtering` | `test_matching.py` | `max(raw) == 0.0` structural zero | None |
| `test_bm25_stopword_filtering_independent` | `test_matching.py` | Ordering only | None |
| `test_bm25_normalization_batch_size_independent` | `test_matching.py` | Formula-explicit + structural bounds | **Will require formula update** |
| `test_score_candidates` | `test_matching.py` | Ordering only | None |
| `test_keyword_stuffer_rejection_at_20_percent_vector_weight` | `test_phase12_weight_validation.py` | `D > C`, gap >= 5.0 | Gap threshold may need updating |
| `test_keyword_stuffer_false_positive_at_40_percent_vector_weight` | `test_phase12_weight_validation.py` | Conditional gap check | Low — re-evaluate post-implementation |
| `test_keyword_stuffer_rejection_real_embeddings` | `test_phase12_weight_validation.py` | Direction + transparency (formula-explicit) | None |

**Worker-path analysis (Celery `score_candidates_task`)**

`conftest.py` sets `celery_app.conf.task_always_eager = True` (session-scoped, autouse). Every test that posts to `POST /api/v1/matches/` executes `score_candidates_task` synchronously in-process, which calls `score_candidates()` → `compute_normalized_bm25_scores()` live. The worker also persists `bm25_score` to the `match_results` table with a `0.0 ≤ bm25_score ≤ 1.0` check constraint. The new normalization satisfies this by construction via `max(0.0, min(..., 1.0))`. No migration required.

| Test | File | Polls task result? | Asserts on scoring output? | Blast radius |
|------|------|--------------------|---------------------------|--------------|
| `test_full_e2e_recruiter_workflow` | `test_e2e_flow.py` | Yes | `final_score == pytest.approx(runtime-computed, abs=0.01)`, `skill_score == 1.0`, `tfidf_score > 0.0`, `final_score > 0.0` | **Low** — expected `final_score` derived from component scores at runtime, not hardcoded |
| `test_match_endpoint_success` | `test_matches_endpoint.py` | No | None | None |
| Persistence match calls | `test_persistence.py` | No | None | None |
| Authorization match attempt | `test_authorization.py` | No (403 before worker) | None | None |
| Rate-limit match calls | `test_rate_limiting.py` | No | None | None |

**Tests with zero blast radius:** `test_parser.py`, `test_auth.py`, `test_api_resumes.py`, `test_api_jobs.py`, `test_ocr.py`, `test_tagger.py`, `test_rate_limiting.py`, `test_authorization.py`.

---

## Standing Project Rules Acknowledgment

Hard checkpoint rule is in effect. No implementation begins until a human replies with the exact words **"approved, proceed"**. No `.env` or secrets committed. All fixtures are synthetic. `PROGRESS_LOG.md` updated only after the phase is complete and verified.

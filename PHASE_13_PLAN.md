# PHASE_13_PLAN.md — BM25 Scoring Calibration

**Phase:** 13  
**Status:** AWAITING APPROVAL — do not implement until human replies with "approved, proceed"  
**Scope:** BM25 scoring calibration only. Weights (30/30/20/20) and all other components are out of scope unless measurement reveals a clear defect, in which case it is flagged here and treated as a separate decision.

---

## Background and Motivation

`BM25_SATURATION_CAP = 12.0` was set in Phase 12B based on a corpus whose observed maximum raw score was 9.65. That cap has already been shown to be wrong: a realistic verbose JD (42 query tokens) produces raw BM25 scores of 18.45 and 10.01 against test candidates — both candidates' genuine signal already exceeds or saturates the cap before Phase 13 has started any calibration work.

The root defect is not just a wrong constant. There are two separable problems:

1. **k1/b are untuned defaults, never chosen for resume-length documents.** The library defaults are `k1=1.5, b=0.75` (confirmed from `BM25Okapi.__init__` in [rank_bm25/rank_bm25.py](https://github.com/dorianbrown/rank_bm25/blob/master/rank_bm25.py)). These govern how term-frequency saturation and document-length normalization behave. They are sensible for web-search documents but resumes are longer and more repetitive than typical search-engine documents, and job descriptions vary enormously in verbosity (terse 10-token JDs vs. verbose 42-token JDs). Using `b=0.75` (strong length normalization) may over-penalize longer resumes; `k1=1.5` may allow term-frequency to accumulate more than is useful for highly repetitive resume text.

2. **The cap is the wrong abstraction if JD length drives raw score magnitude.** Okapi BM25 raw scores scale with query term count — a 42-token JD produces higher raw scores than an 8-token JD against the same corpus, independent of match quality. A single global cap cannot simultaneously provide good discrimination for both terse and verbose JDs. This is a structural problem that tuning k1/b alone does not fully address.

This plan pursues **both**: (a) evaluate whether tuned k1/b can reduce the sensitivity that causes the cap problem, and (b) replace the single global cap with a length-aware normalization approach if measurement confirms the structural problem is real and material.


---

## Element 1 — BM25 Hyperparameters: k1/b Defaults and Tuning Decision

**Confirmed defaults (from rank_bm25 source, `BM25Okapi.__init__`):**

```
k1 = 1.5    # term-frequency saturation parameter
b  = 0.75   # document-length normalization strength
epsilon = 0.25  # IDF floor multiplier (fraction of average_idf applied to negative-IDF terms)
```

These are never passed explicitly in `bm25_engine.py` — the engine runs on these defaults.

**What k1 and b actually control:**

- `k1` governs term-frequency saturation. As `k1 → 0`, a single mention of a query term saturates immediately (binary presence/absence). As `k1` increases, additional occurrences of the term continue to add score. `k1=1.5` is mid-range: a term appearing 5 times contributes roughly 3× the score of one appearance (not 5×). For resume text, where repetition is common but not meaningful signal, a lower `k1` (e.g. 1.2) reduces score inflation from repeated mentions without eliminating them entirely.

- `b` governs how strongly document length penalizes the TF component. `b=0.75` is strongly normalizing: a 500-token resume is penalized relative to a 200-token resume even if the longer resume has more relevant content. This is appropriate for web documents where length indicates verbosity, but resumes are expected to grow with experience — length often correlates positively with depth. A lower `b` (e.g. 0.5–0.6) would reduce this penalty.

**Approach: both k1/b tuning AND revised normalization, not either/or.**

Tuning k1/b addresses the underlying mechanism (how raw scores are produced). But the Phase 12B finding — that a 42-token JD already produces scores of 18.45 — demonstrates that even with adjusted k1/b, raw score magnitude will still vary with JD query length. A single global cap conflates two different things: absolute match quality and query verbosity. These are separable. Therefore the plan pursues both:

1. Measure the effect of candidate k1/b values (k1 ∈ {1.2, 1.5}, b ∈ {0.5, 0.75}) on the measured corpus score distribution. The tuned values are adopted if they demonstrably reduce score variance that is attributable to JD length rather than match quality, while preserving discrimination between strong, moderate, and weak matches.

2. Evaluate a query-length-aware normalization as an alternative or complement to the global cap. The concrete candidate is score normalization by query token count: `normalized = max(0.0, min(raw / (k * n_query_tokens), 1.0))` where `n_query_tokens` is the post-stopword token count of the job description and `k` is a calibrated scale factor. This directly removes the JD-length dependency from the normalized score, making scores across terse and verbose JDs directly comparable. The measurement task (Element 3) must confirm whether this outperforms a recalibrated global cap before it is adopted.


---

## Element 2 — Corpus Requirements

### Scale and Coverage

The calibration corpus must contain **at least 40–50 distinct job/candidate pairings**, spanning:

- **Domains:** backend engineering, frontend engineering, data science/ML, DevOps/SRE, mobile (iOS/Android), bioinformatics/computational biology
- **Seniority levels:** junior (0–2 years), mid-level (3–5 years), senior/staff (6+ years) — at least two seniority levels per domain
- **Writing styles:** dense keyword lists (ATS-optimized, terse skill bullets), narrative prose (paragraph-form experience descriptions), hybrid (bullet headings + paragraph content), verbosity extremes (terse 8–15 token JDs and verbose 35–50 token JDs)
- **Match quality tiers:** for each JD, at least one strong-match candidate, one moderate-match candidate (right domain, missing 2–3 key skills or wrong seniority), and one weak/no-match candidate (different domain or unrelated content)

This structure ensures the distribution measurement covers the axes that drive BM25 score variance: JD length, resume length, term overlap density, and domain vocabulary divergence.

### Addressing the Representativeness Problem

The Phase 12 cap failed because it was derived from a small all-LLM-generated corpus. LLM-generated text has systematic statistical properties: consistent sentence structure, vocabulary drawn from a bounded "resume cliché" distribution, and length patterns that cluster more tightly than real human writing. Generating 50 more LLM resumes does not fix this — it scales up the same distribution.

**Concrete approach:**

1. **Real public job postings (transformed, not reproduced verbatim).** The O*NET Open Resource Center publishes occupational task and knowledge data in the public domain (CC-BY 4.0 equivalent), including skill requirement descriptions for hundreds of occupations. These provide authentic vocabulary distributions for each domain at no copyright risk. The plan is to use O*NET task descriptions as the vocabulary source when constructing job descriptions — not to reproduce O*NET text wholesale, but to ground the terminology in real occupational language patterns. Similarly, Kaggle's "Resume Dataset" (Gaurav Dutta, CC0 license) contains hundreds of real-format resumes submitted publicly; a subset of these can be used directly as fixture texts after confirming the dataset's CC0 license status.

2. **Intentional style variation in synthetic content.** For domains where a CC0 dataset source cannot be confirmed (e.g. bioinformatics), LLM-generated fixtures are acceptable, but generation prompts must explicitly force style diversity: write a resume as a terse bullet list, write the same candidate as narrative prose, write a JD with only 8 keywords, write the same JD as a verbose paragraph. These are committed to the fixture directory as separate files, labelled by style variant, not merged.

3. **Explicit limitation statement.** If by the time of implementation no CC0 resume dataset has been confirmed usable, the plan falls back to synthetic-only. In that case DECISIONS.md must record: "Phase 13 corpus is entirely synthetic. The representativeness limitation of Phase 12 (LLM vocabulary clustering) is partially mitigated by explicit style variation in generation prompts, but has not been eliminated. Cap values derived here should be revalidated when real resume ingestion data becomes available." This entry is mandatory, not optional, if synthetic-only is used.

### Fixture Format and Versioning

All corpus fixtures are committed to `tests/fixtures/phase13/` as plaintext `.txt` files (one resume per file, one JD per file) plus a `corpus_manifest.json` that maps each pairing to its: domain, seniority, writing style, expected match tier (strong/moderate/weak), and data source label (synthetic/o*net-grounded/CC0-dataset). This makes every measurement repeatable and auditable.

No fixture is generated ad hoc at test runtime. All are committed, versioned, and re-used by future phases.


---

## Element 3 — Score Distribution Measurement

**What to measure and report:**

Run `compute_bm25_scores` (raw, before normalization) against every job/candidate pairing in the full calibration corpus. Record: raw score per pairing, JD query token count (post-stopword), resume token count, domain, seniority, writing style, match tier.

Report the following statistics on the full distribution of raw scores (strong-match pairings only, moderate-match pairings only, weak/no-match pairings, and all pairings combined):

- p10 (10th percentile)
- p25
- p50 (median)
- p75
- p90
- p99
- Maximum (reported alongside its JD token count and resume token count, since max is context-dependent)

**Why percentiles, not min/max:**

The Phase 12 cap was set at `observed_max × 1.24`. Min and max are the two statistics most sensitive to outliers — a single unusually long JD or an atypically repetitive resume will shift them without representing the distribution. The cap's purpose is to establish a normalization reference point that maps a "strong genuine match" to a high but sub-saturating normalized score. For that purpose, p90 (what a strong match typically looks like) and p99 (what a very strong or outlier match looks like) are far more appropriate anchors than the observed maximum. The Phase 12 methodology of using "observed max" as the sole basis is explicitly named as a failure mode in this project and must not be repeated.

**Key analysis question:**

Plot (or tabulate) raw score vs. JD query token count for strong-match pairings. If these are strongly correlated (r > 0.7), the structural problem is confirmed: a single global cap cannot simultaneously provide good discrimination for terse JDs (where strong matches produce e.g. scores of 2–5) and verbose JDs (where the same quality match produces scores of 15–20). In that case the query-length-aware normalization from Element 1 is adopted. If correlation is low (r < 0.4), a recalibrated global cap is sufficient.

This analysis is the decision gate between a global cap and a length-aware normalization. The decision is not made before measurement.

**Run under all candidate k1/b combinations:**

The distribution measurement is run separately for:
- `k1=1.5, b=0.75` (current defaults)
- `k1=1.2, b=0.75`
- `k1=1.5, b=0.5`
- `k1=1.2, b=0.5`

This produces four sets of percentile tables, allowing direct comparison of how k1/b affect score range, discrimination between match tiers, and sensitivity to JD length. The winning k1/b values are those that: (a) maintain clear separation between strong/moderate/weak match tiers and (b) show lowest correlation between raw score and JD token count.


---

## Element 4 — Proposed Normalization Approach

The final normalization approach is chosen after Element 3 measurement, not before. This section specifies the two candidates and the decision criteria.

### Candidate A: Recalibrated global cap (same structure, better constant)

```python
normalized = max(0.0, min(raw / BM25_SATURATION_CAP, 1.0))
```

Adopted if: the correlation between raw score and JD token count is low (r < 0.4) for strong-match pairings. The new cap value is set such that the p90 of strong-match raw scores maps to approximately 0.75–0.80 (strong but not saturated, leaving headroom for genuinely exceptional matches). This is the same principle as the Phase 12B calibration, but grounded in a p90 statistic from a properly representative corpus instead of an observed maximum from 7 fixtures.

The new cap is a named constant `BM25_SATURATION_CAP` with a full calibration comment in the source replacing the existing one. The old constant (12.0) is explicitly deprecated with a note explaining why it was wrong and what measured value replaced it.

### Candidate B: Query-length-aware normalization

```python
n_query_tokens = len(_tokenize(query))  # post-stopword token count
effective_cap = SCALE_K * max(n_query_tokens, MIN_QUERY_TOKENS)
normalized = max(0.0, min(raw / effective_cap, 1.0))
```

Where `SCALE_K` is a calibrated constant representing the expected raw BM25 score per query token for a strong genuine match (derived from the corpus), and `MIN_QUERY_TOKENS` is a floor (e.g. 5) to prevent extreme compression from very terse JDs.

Adopted if: the correlation between raw score and JD token count is high (r > 0.4) for strong-match pairings, confirming that JD length is a meaningful confound. `SCALE_K` is calibrated from the corpus as: `p90(raw_score_per_token_for_strong_matches)`, measured across all strong-match pairings.

**Note:** This is a slightly more complex formula but introduces only two named constants. Both are calibrated from data and documented with the same level of evidence required by this project's standing rules (actual numbers, actual command output).

### What does NOT change

The normalization formula continues to be batch-size-independent — normalized score is a deterministic function of the raw score (and optionally the JD text), not of who else is in the batch. The Phase 12B regression test (`test_bm25_normalization_batch_size_independent`) must continue to pass under whatever normalization is chosen.


---

## Element 5 — Validation Plan (Defined Before Implementation)

Success criteria are stated here. They are not adjusted retroactively to match whatever the new normalization produces.

### Criterion 1: Ranking correctness across all match tiers

For every domain in the corpus, pick three representative pairings: one strong-match candidate, one moderate-match candidate, and one weak/no-match candidate scored against the same JD. The normalized BM25 scores must satisfy:

```
strong_match_bm25 > moderate_match_bm25 > weak_match_bm25
```

with at least a **0.10 gap** between tiers. This gap size is the minimum discrimination that prevents the composite scorer from treating strong and moderate matches as equivalent given BM25's 30% weight. At 30% weight, a 0.10 BM25 gap = 3 final score points — meaningful but not dominant.

This must hold for **all six domains**, not just the easiest ones.

### Criterion 2: Batch-size independence

A candidate's normalized BM25 score must be identical (within floating-point tolerance, ε < 1e-9) whether it is scored in a batch of 1, 2, 5, or 20+ candidates. This is the core invariant introduced in Phase 12B. The existing regression test `test_bm25_normalization_batch_size_independent` covers this. It must pass unchanged after any new normalization constants are set.

### Criterion 3: JD-length independence (or controlled dependence)

For a fixed strong-match candidate paired with three JDs of different verbosity levels (short: 8–12 tokens, medium: 18–25 tokens, verbose: 35–50 tokens), normalized BM25 scores must fall within a **0.20 band** of each other. This is the quantitative statement of the JD-length problem: if the band exceeds 0.20, the global cap approach has failed and the length-aware normalization must be used. (Under a correctly calibrated length-aware normalization, this band should be < 0.10.)

This test does not exist yet and will be written as part of this phase's test suite.

### Criterion 4: No saturation for genuine strong matches

The p90 of normalized BM25 scores for strong-match pairings must be ≤ 0.85. A normalized score of 1.0 (saturation) means additional match quality is invisible to the scorer — it's a flat ceiling. At 30% weight, saturation eliminates up to 30 final score points of discrimination. The cap is calibrated so that strong-but-not-perfect matches do not saturate.

### Criterion 5: End-to-end ranking preservation

The keyword-stuffer test (`test_keyword_stuffer_rejection_real_embeddings`) must continue to pass: genuine frontend candidate (D) ranks above backend keyword-stuffer (C) by > 10 points in a batch of 2. This test uses real all-MiniLM-L6-v2 embeddings and was the original driver of the Phase 12B fix. It must not regress.

### Numerical criterion for "good enough"

The implementation is complete when:
- All five criteria above pass on the full calibration corpus
- All 87 existing tests continue to pass (no regressions)
- The calibration constant(s) are documented in source with the specific percentile values they are derived from


---

## Element 6 — Structural Test Fragility Fix

Every scoring change in this project (Phase 11 weight change, Phase 12 normalization change) has broken unrelated tests because they pinned exact float values. This section catalogues all affected tests and specifies the structural fix, so future scoring changes do not repeat this pattern.

### The structural rule

A test's assertion type must match its purpose:
- **If the test's purpose is "does the ranking order correct?"** → use ordering assertions (`assert score_a > score_b`) or relative comparisons (`assert (score_a - score_b) >= threshold`). Never assert an exact float.
- **If the test's purpose is "does the formula produce the right arithmetic result?"** → an exact-value assertion is correct. But the formula must be stated explicitly in the assertion's failure message so a future reader can verify it is still arithmetically correct and not just empirically matching a stale expected value.

### Classification of existing BM25/score-touching tests

**Category 1 — Ordering/ranking tests (purpose: correct relative ranking)**

These already use ordering assertions and are structurally correct. No change needed to their assertion style. They may need updated threshold values if normalization changes materially affect the gap magnitude.

| Test | File | Current assertion | Status |
|------|------|------------------|--------|
| `test_bm25_engine` | `test_matching.py` | `scores[0] > scores[1]`, `scores[2] > scores[1]`, bounds checks | Already ordering — safe |
| `test_bm25_stopword_filtering` | `test_matching.py` | `max(raw) == 0.0` (zero-overlap structural) | Safe — tests zero, not a calibrated value |
| `test_bm25_stopword_filtering_independent` | `test_matching.py` | `scores[1] > scores[0]` | Already ordering — safe |
| `test_score_candidates` | `test_matching.py` | `top_cand["final_score"] > bot_cand["final_score"]`, `top_cand["candidate_id"] == "cand_1"` | Already ordering — safe |
| `test_keyword_stuffer_rejection_at_20_percent_vector_weight` | `test_phase12_weight_validation.py` | `D_final > C_final`, gap >= 5.0 | Ordering + threshold — acceptable; threshold may need updating if normalization changes gap magnitude, but the direction assertion is permanent |
| `test_keyword_stuffer_rejection_real_embeddings` | `test_phase12_weight_validation.py` | `sim_d > sim_c`, `D_final > C_final`, `abs(manual - reported) < 0.01` | Mixed: direction (safe), transparency check (safe, formula-explicit) |
| `test_bm25_normalization_batch_size_independent` | `test_matching.py` | `normalized == max(0, min(raw/CAP, 1.0))` (formula-explicit), `strong_norm < 1.0`, `zero_norm == 0.0`, `strong_norm > 0.0` | Formula-explicit + structural bounds — correct form; **will need updated expected formula if normalization formula changes in Phase 13** |


**Category 2 — Arithmetic transparency tests (purpose: verify formula mechanics)**

These assert the formula explicitly, not an empirically observed float. They are structurally correct in form. If the normalization formula changes, the expected formula in the test must be updated to reflect the new formula — not relaxed.

| Test | File | What it asserts | Required change in Phase 13 |
|------|------|----------------|------------------------------|
| `test_bm25_normalization_batch_size_independent` Property 1 | `test_matching.py` | `norm == max(0, min(raw/BM25_SATURATION_CAP, 1.0))` | If formula changes to length-aware, update to `norm == max(0, min(raw/(SCALE_K * n_tokens), 1.0))`. The form must remain formula-explicit. |
| Transparency check in `test_keyword_stuffer_rejection_real_embeddings` | `test_phase12_weight_validation.py` | `abs((tfidf*0.3 + bm25*0.3 + skills*0.2 + vector*0.2)*100 - final_score) < 0.01` | No change — this tests the composite formula, not the BM25 normalization formula. Passes regardless of cap value. |

**Category 3 — Tests that use exact BM25 scores purely coincidentally (must be converted)**

After reviewing all test files, there are **no tests in the suite that pin a specific numeric BM25 raw score or a specific normalized BM25 float value as an expected constant** (e.g. `assert bm25_score == 0.342`). The Phase 12B regression tests deliberately used formula-explicit or structural-bound assertions to avoid this. The `test_e2e_flow.py` uses `pytest.approx` for `final_score` but derives it algebraically from the component scores at runtime, not from a hardcoded expected value — this is the correct pattern and should be preserved.

**The one test requiring review:** `test_e2e_flow.py::test_keyword_stuffer_rejection_real_embeddings` — the gap threshold is `>= 10.0` (stated in Element 5, Criterion 5 of this plan). If the current threshold in the test differs from this criterion, it must be updated to match the stated criterion, not left at its current value.

### New tests this phase must add (structural additions)

All new tests use ordering or formula-explicit assertions only. No hardcoded expected floats.

1. `test_bm25_jd_length_independence` — Criterion 3 from Element 5: same strong-match candidate, three JD lengths, normalized scores within 0.20 band (or 0.10 if length-aware normalization is adopted). This test is written against the chosen normalization approach after measurement, but its assertion form and threshold are committed before measurement begins.

2. `test_bm25_tier_discrimination` — Criterion 1 from Element 5: for each of the six domains, strong > moderate > weak with ≥ 0.10 gap between tiers. Parameterized over the calibration corpus fixture manifest.

3. `test_bm25_k1_b_explicit` — If k1/b are changed from defaults, a test instantiates `BM25Okapi` with the chosen k1/b and verifies the parameters are stored (accesses `bm25.k1` and `bm25.b`). Prevents silent regression to library defaults if the code is modified.


---

## Element 7 — Impact Assessment: Full Blast Radius

Every existing test that asserts a specific BM25 or final_score value, plus every test that imports from `bm25_engine.py` or uses `score_candidates`.

### Tests that directly import from `bm25_engine.py`

| File | What it imports | Direct assertion on BM25 output |
|------|----------------|--------------------------------|
| `tests/test_matching.py` | `compute_normalized_bm25_scores`, `compute_bm25_scores`, `BM25_SATURATION_CAP` | Structural bounds (`>= 0.0`, `<= 1.0`, `> 0.0`, `== 0.0`), ordering, formula-explicit check using `BM25_SATURATION_CAP`. **Will break if: normalization formula changes (Property 1 formula-check will fail unless updated), or if `BM25_SATURATION_CAP` is renamed.** |
| `tests/test_phase12_weight_validation.py` | indirectly via `score_candidates` | No direct `bm25_score` value assertion — uses final_score ordering and gap thresholds. Unlikely to break from normalization change alone. |

### Tests that call `score_candidates` (final_score assertions)

| File | Test | final_score assertion type | Risk |
|------|------|---------------------------|------|
| `tests/test_matching.py` | `test_score_candidates` | `top > bot` (ordering only) | None |
| `tests/test_matching.py` | `test_matched_and_missing_skills_preserve_literal_case` | No score assertion | None |
| `tests/test_e2e_flow.py` | `test_full_e2e_match_flow` | `pytest.approx(runtime-computed expected, abs=0.01)`, `> 0.0` | Low — expected value is computed from components at runtime, not hardcoded. Will not break from normalization change unless the component values change. |
| `tests/test_phase12_weight_validation.py` | `test_keyword_stuffer_rejection_at_20_percent_vector_weight` | `D > C`, gap >= 5.0 | Low for direction; **gap threshold (5.0) may need updating** if BM25 contribution changes significantly. |
| `tests/test_phase12_weight_validation.py` | `test_keyword_stuffer_false_positive_at_40_percent_vector_weight` | `gap >= 3.0` / stuffer-doesn't-win | Low risk — conditional assertion, will need re-evaluation against new normalization. |
| `tests/test_phase12_weight_validation.py` | `test_keyword_stuffer_rejection_real_embeddings` | `D > C`, `abs(manual - reported) < 0.01` | Low — direction safe; transparency check safe. Gap is reported but not asserted at a specific threshold. |

### Tests asserting `bm25_score > 0.0` or `bm25_score == 0.0` directly on response payloads

| File | Test | Assertion | Risk |
|------|------|-----------|------|
| `tests/test_e2e_flow.py` | `test_full_e2e_match_flow` | No assertion on `bm25_score` value directly (the `assert bm25_score > 0.0` was removed in Phase 12B) | None |

### Tests that mention BM25 in weights payloads (not in assertions)

| File | Context |
|------|---------|
| `tests/test_matches_endpoint.py` | Sends `"bm25": 0.3` / `"bm25": 0.5` in request payloads — tests the API input validation, not the scoring output. No impact from normalization changes. |
| `tests/test_e2e_flow.py` | Sends `"bm25": 0.4` in request payload. Same — no impact. |

### Summary: tests that WILL require code changes

1. **`tests/test_matching.py::TestEngines::test_bm25_normalization_batch_size_independent`** — Property 1 formula-check (`norm == max(0, min(raw/BM25_SATURATION_CAP, 1.0))`) will fail if the normalization formula is changed to length-aware. Must be updated to the new formula. This is the right outcome: the test is testing the formula, and updating it is correct, not breakage.

2. **`tests/test_phase12_weight_validation.py::test_keyword_stuffer_rejection_at_20_percent_vector_weight`** — The `gap >= 5.0` threshold was calibrated under Phase 12B's `BM25_SATURATION_CAP = 12.0`. If the new normalization raises the discrimination gap (expected, since the stuffer should score even lower under a well-calibrated normalization), the threshold needs updating upward. If it shrinks, that is a signal that the new normalization is worse, not better, and must be investigated.

### Tests with no expected impact (no BM25 or final_score assertions)

`test_parser.py`, `test_persistence.py`, `test_auth.py`, `test_authorization.py`, `test_api_resumes.py`, `test_api_jobs.py`, `test_ocr.py`, `test_tagger.py`, `test_rate_limiting.py` — none of these touch BM25 or composite scoring. Zero blast radius.

---

### Worker-path analysis (Celery `score_candidates_task`)

Phase 9 routed all match scoring through a Celery task. `conftest.py` sets `celery_app.conf.task_always_eager = True` (session-scoped, autouse), which means `score_candidates_task` executes synchronously in-process during every test run. The call chain is:

```
POST /api/v1/matches/  →  matches.py route handler
  →  score_candidates_task.delay(...)  [runs in-process, eagerly]
    →  app/worker.py: score_candidates_task()
      →  score_candidates()  (scorer.py)
        →  compute_normalized_bm25_scores()  (bm25_engine.py)
```

Every test that posts to `/api/v1/matches/` therefore exercises `bm25_engine.py` live, even if it only asserts on the HTTP status code. The worker also persists `MatchResult` rows to the database with `bm25_score` as a stored column, so normalization changes affect the persisted record too.

**Worker-path test inventory and blast radius:**

| Test | File | Polls task result? | Asserts on bm25/final_score? | Blast radius |
|------|------|--------------------|------------------------------|--------------|
| `test_full_e2e_recruiter_workflow` | `test_e2e_flow.py` | Yes — polls match task and reads `matches[]` | `final_score == pytest.approx(runtime-computed, abs=0.01)`, `skill_score == 1.0`, `tfidf_score > 0.0`, `final_score > 0.0` | **Low** — `final_score` expected value is computed from component scores at runtime, not hardcoded. `bm25_score` is used in the computation but not independently asserted. Safe under any normalization change that preserves `final_score = (tf*w + bm*w + sk*w + vec*w) * 100`. |
| `test_match_endpoint_success` | `test_matches_endpoint.py` | No — asserts `202` + `task_id` only | None | None — worker executes but output not checked |
| Persistence tests (2 calls to `/api/v1/matches/`) | `test_persistence.py` | No — asserts `202` status only | None | None |
| `test_authorization.py` match attempt | `test_authorization.py` | No — asserts `403` (auth check fires before worker) | None | None |
| Rate-limit tests | `test_rate_limiting.py` | No — asserts `429` | None | None |

**`MatchResult` DB column:** `worker.py` persists `bm25_score=r["bm25_score"]` into the `match_results` table. The ORM model has a `chk_bm25_score_bounds` check constraint (`0.0 ≤ bm25_score ≤ 1.0`). Any normalization change must continue to produce values in `[0.0, 1.0]` — both Candidate A (global cap) and Candidate B (length-aware) guarantee this by construction (`max(0.0, min(..., 1.0))`). No migration is needed unless the column type or constraint changes. No migration is planned in this phase.

**Net conclusion for worker path:** The existing blast radius catalog did not explicitly trace this path. After doing so: no test was missed in the "will break" category. `test_full_e2e_recruiter_workflow` is the only worker-path test that asserts on scoring output, and it uses runtime-computed expected values rather than hardcoded floats. It was already listed in the catalog; its worker-path nature is now explicitly documented here. The new tests added in this phase (`test_bm25_jd_length_independence`, `test_bm25_tier_discrimination`, `test_bm25_k1_b_explicit`) exercise `bm25_engine.py` directly and do not go through the worker — this is intentional, as unit-level calibration tests should not depend on the DB/Celery stack.


---

## Implementation Sequence (for reference — not to be started until approved)

1. Confirm usability of CC0 corpus sources (Kaggle Resume Dataset license, O*NET usage terms). If confirmed, download and prepare a representative subset. If not confirmed, generate synthetic fixtures with explicit style variation as described in Element 2.
2. Build corpus fixture files in `tests/fixtures/phase13/` and commit `corpus_manifest.json`.
3. Write and run the distribution measurement script (raw scores × k1/b grid × all pairings). Report full percentile table in this document's Implementation Notes section.
4. Perform the JD-length correlation analysis (Criterion 3). Choose normalization approach (global cap or length-aware) based on the correlation result.
5. Determine final k1/b values from the distribution comparison tables.
6. Update `bm25_engine.py`: pass explicit k1/b to `BM25Okapi`, replace `BM25_SATURATION_CAP` constant (or add length-aware normalization), update calibration comment with actual measured numbers.
7. Update `test_bm25_normalization_batch_size_independent` Property 1 formula if the normalization formula changed.
8. Write new tests: `test_bm25_jd_length_independence`, `test_bm25_tier_discrimination`, `test_bm25_k1_b_explicit`.
9. Update gap thresholds in `test_keyword_stuffer_rejection_at_20_percent_vector_weight` if the new normalization changes the measured gap.
10. Run the full test suite (87 existing + new tests) inside Docker. Report raw output.
11. Run `docker-compose exec -T app pytest tests/ -v` and confirm 0 failures before committing.
12. Commit in logical atomic units: (a) corpus fixtures + manifest, (b) measurement script + results, (c) bm25_engine.py changes, (d) test updates.

---

## Observed but Out of Scope

The following issues were observed while reading the codebase for this plan but are not addressed in Phase 13. Each is logged here for future tracking.

1. **30/30/20/20 weight finalization is still deferred.** DECISIONS.md and PROGRESS_LOG.md both mark these weights as provisional pending BM25 normalization fix and production-scale validation. Phase 13's measurement will produce a cleaner scoring foundation, after which weight validation should be Phase 14's first task. Not changed here.

2. **`test_keyword_stuffer_false_positive_at_40_percent_vector_weight`** uses a conditional structure (`if gap < 3.0: pytest.fail(...)`) rather than a direct assertion. This produces test output that can look like a pass when it is actually documenting a known failure. The test is annotated "document the result rather than assert a specific outcome" — that is a testing anti-pattern when the "observation" is actually a condition that should fail. This warrants a structural rewrite in a future phase focused on test quality. Not changed here.

3. **`scratch_test_bm25_ablation.py` and other `scratch_*.py` files** in `tests/` are working artifacts that were never cleaned up. They are not collected by pytest (no `test_` prefix on the class/function names that are collected), but they add noise to the test directory. These should be deleted or moved to a `scripts/` directory in a future cleanup pass. Not changed here.

4. **The concurrent-duplicate-rejection test** is documented as occasionally flaky. This is a pre-existing known issue, not introduced by Phase 13.

---

## Standing Project Rules Acknowledgment

- The hard checkpoint rule is in effect. This document is the checkpoint. No implementation begins until a human replies with the exact words **"approved, proceed"**.
- No `.env`, secrets, or credentials will be committed.
- Corpus fixtures use synthetic or legitimately reusable public data only — no real PII, no verbatim reproduction of copyrighted job postings.
- All constants in the final implementation are derived from measured data with reported evidence (actual numbers, actual script output), not chosen to make a specific test pass.
- PROGRESS_LOG.md will be updated with a Phase 13 section only after the phase is complete and all tests are passing.
- If implementation reveals that the 30/30/20/20 weight split is now clearly wrong under the new normalization, that is flagged as a separate decision and not changed inline.

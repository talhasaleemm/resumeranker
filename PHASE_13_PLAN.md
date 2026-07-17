# Phase 13 Plan — BM25 Empirical Re-Calibration

**Date written:** 2026-07-17
**Status:** AWAITING APPROVAL — do not implement until "approved, proceed" is received.

---

## Context

DECISIONS.md (Phase 12B entry) flags that `BM25_SATURATION_CAP = 12.0` was calibrated
against a small synthetic test corpus (7 fixture texts + 7 sample resumes × 3 JDs;
observed max raw score: 9.65) and must be revisited against real-world-scale data.

Pre-plan empirical investigation has already confirmed the flag is warranted:
running the existing 7 sample resumes against a verbose 42-token JD produces raw scores
of **18.45** and **10.01** — the backend engineer resume alone already exceeds the cap of
12.0 and saturates at 1.0. This means the cap is broken in the current codebase for any
recruiter writing a detailed, multi-requirement JD. This phase fixes it.

---

## 1. BM25 Hyperparameters — Current State

**Finding (verified pre-plan):** `BM25Okapi` is instantiated as `BM25Okapi(tokenized_corpus)`
with no keyword arguments, taking all library defaults:

```
BM25Okapi.__init__ signature: k1=1.5, b=0.75, epsilon=0.25
```

These are the **original Robertson & Zaragoza (2009) defaults**, not tuned for resume
matching. Their meaning in this context:

- **k1 = 1.5**: Term-frequency saturation parameter. A term appearing once contributes
  roughly 60% of the score it would contribute appearing ∞ times. For resumes — where a
  keyword appearing 2-3× is common but rarely meaningful beyond 1× — k1=1.5 likely
  over-rewards repetition compared to a lower value like k1=1.2.

- **b = 0.75**: Document-length normalization. A document twice the average length has
  its TF contribution halved relative to an average-length document. Resume length varies
  enormously (observed range in current corpus: 6 tokens to 248 tokens after stopword
  removal), so b=0.75 imposes a heavy penalty on longer, content-rich resumes relative to
  short ones. A lower b (e.g. 0.5) reduces this length penalty.

**Is k1/b tuning the right fix, or is cap recalibration sufficient?**

The root diagnosis from Phase 12B was that the cap was set using observed max from too
small a corpus — it's not that k1/b are catastrophically wrong. The evidence:

- Pre-plan scoring shows strong ranking order is preserved across k1/b variants at the
  current corpus scale (Strong 7.28 > Medium 1.25 > Weak 0.21 under defaults; Strong
  6.88 > Medium 1.20 > Weak 0.21 under k1=1.2, b=0.75 — order unchanged, magnitude
  reduced ~5%).
- The immediate problem is that verbose JDs (42 query tokens) produce raw scores of 18.45
  for strong matches, which saturates the cap at 1.0. The cap is the binding constraint,
  not k1/b mistuning.
- Changing k1/b without also re-deriving the cap would still produce an incorrectly
  calibrated cap — so the cap recalibration is necessary regardless.

**Decision:** Retain current defaults (k1=1.5, b=0.75) for this phase. The rationale is:
1. The ranking order across match quality tiers is correct with current defaults.
2. k1/b tuning is a second-order concern that requires a different type of validation
   (comparative ranking quality across many query/document pairs, not just cap calibration).
3. Any k1/b change would invalidate the newly calibrated cap and require another full
   re-measurement pass — scope creep for a phase whose goal is cap defensibility.

k1/b tuning is logged as future work (see "Observed but out of scope" section).

**However:** The plan does introduce `BM25_K1` and `BM25_B` as named module-level
constants (currently set to the library defaults, 1.5 and 0.75) in `bm25_engine.py`.
This makes the parameters explicit and auditable rather than silently defaulted, and makes
future tuning a one-line change with a documented rationale rather than a magic-number hunt.

---

## 2. Corpus Requirements

### Why bigger-synthetic-only is insufficient

LLM-generated resumes share systematic statistical properties that real resumes don't:
uniform sentence length, repeated boilerplate phrasing ("Experienced professional with
a passion for…"), vocabulary drawn from the same training distribution as the job
descriptions used to generate them, and near-absence of the idiosyncratic formatting
(dense skill lists, terse bullet points, multi-column layouts, inconsistent punctuation)
that characterizes real submissions. A larger synthetic-only corpus reduces sampling
noise within that distribution but does not expand the distribution itself.

The primary consequence for BM25 specifically: raw score magnitude scales with the
number of distinct matched query tokens. If all synthetic JDs happen to be 15-25 tokens
(the range used in Phase 12), the observed raw score ceiling will be artificially
depressed relative to what real recruiters write (which can be 40-100+ tokens for
senior roles). This is precisely what happened — Phase 12's corpus used short JDs and
missed the 18.45 score produced by a realistic verbose JD.

### Approach: synthetic corpus + verified real public text anchors

Full real-world resumes cannot be used (PII constraints, this repo is public). However,
**public job descriptions** from open job boards are usable as long as they are:
- Paraphrased, not reproduced wholesale (copyright; attribution where required)
- Synthetic/fictional candidate resumes matched against them

**Concrete plan:**

1. **Synthetic candidate corpus (40 resumes):** Hand-authored, clearly fictional resumes
   (names like "Candidate_A_Backend_Senior", no real identifying information) across
   6 domains × varied seniority × varied writing style:

   | Domain | Seniority | Writing style |
   |--------|-----------|---------------|
   | Backend (Python/FastAPI) | Junior, Mid, Senior | Dense keyword list |
   | Backend (Python/FastAPI) | Junior, Mid, Senior | Narrative prose |
   | Frontend (React/TS) | Mid, Senior | Dense |
   | Frontend (React/TS) | Mid, Senior | Narrative |
   | Data Science / ML | Mid, Senior | Dense |
   | Data Science / ML | Mid, Senior | Narrative |
   | DevOps / SRE | Mid, Senior | Dense |
   | DevOps / SRE | Mid, Senior | Narrative |
   | Mobile (iOS/Android) | Mid, Senior | Dense |
   | Bioinformatics / Research | Mid, Senior | Dense |

   Writing style distinction matters specifically for BM25: a "dense" resume lists
   skills as comma-separated tokens (`Python, FastAPI, PostgreSQL, Docker`), while
   "narrative" describes them in sentences (`Built high-throughput REST services using
   FastAPI and async PostgreSQL with connection pooling`). BM25 IDF behavior differs
   between these formats and the corpus must cover both.

   Each resume: 200-400 tokens post-stopword-removal (matching the real-sample range
   of 202-248 tokens seen in current fixtures). Total ~40 resumes.

2. **Real public text anchors (10 paraphrased job descriptions):** Derived from actual
   public job postings on LinkedIn/Indeed/Hacker News (open positions, publicly visible
   without login, no paywall), paraphrased to avoid verbatim reproduction, covering:
   - Backend engineer (terse, ~15 tokens) × 2
   - Backend engineer (verbose, ~40-60 tokens) × 2
   - Frontend engineer (medium, ~20 tokens) × 1
   - Data scientist (medium, ~25 tokens) × 1
   - DevOps engineer (verbose, ~45 tokens) × 1
   - ML Engineer (verbose, ~50 tokens) × 1
   - Mobile developer (terse, ~12 tokens) × 1
   - Bioinformatics/research (verbose, ~55 tokens) × 1

   These 10 JDs are the representativeness anchor: they provide real query-token density
   and vocabulary distribution. The synthetic resumes are matched against them.

   **Attribution:** Each paraphrased JD will carry a comment in the fixture file noting
   the domain and approximate source type (e.g., `# Paraphrased from public backend
   engineering JD; no verbatim reproduction`). No company names, applicant names, or
   identifying details retained.

3. **Total corpus: 40 resumes × 10 JDs = 400 pairings.** This is well above the 40-50
   minimum specified, spans all 6 required domains, and includes both terse and verbose
   JDs (the critical gap in Phase 12's corpus).

### Storage as versioned fixtures

All fixture files committed under `tests/fixtures/phase13/`:
- `resumes/` — 40 plaintext `.txt` files (not PDF/DOCX; parsing is already tested
  separately and adding parsing overhead here would slow the measurement script)
- `job_descriptions/` — 10 `.txt` files
- `README.md` — describes corpus construction, attribution notes, and methodology

Using `.txt` directly for BM25 measurement means the tokenizer operates on the same
text the real pipeline would process (post-PDF extraction), without introducing
extraction variability as a confound.

### Runtime estimate

Pre-plan benchmark: 10 JDs × 50 candidates = 500 pairings in **0.138s**. The Phase 13
corpus (10 JDs × 40 resumes = 400 pairings) will complete in < 0.2s. Adding percentile
statistics and output formatting: < 5s total. No timeout risk whatsoever.

---

## 3. Measuring the Real BM25 Score Distribution

The measurement script (`tests/fixtures/phase13/measure_bm25_distribution.py`) will:

1. Load all 40 resume fixtures and 10 JD fixtures.
2. Score every JD against the full 40-candidate batch using `compute_bm25_scores`.
3. Collect all raw positive scores across all 400 pairings.
4. Report the **full percentile distribution**: p10, p25, p50, p75, p90, p95, p99, max,
   mean, stdev — not just min/max/median.
5. Report the distribution separately for:
   - **Terse JDs** (≤ 20 query tokens): expected lower raw score ceiling
   - **Verbose JDs** (> 20 query tokens): expected higher ceiling; this is the regime
     the Phase 12 cap was not calibrated for
6. Report how many pairs produce raw scores that currently exceed `BM25_SATURATION_CAP`
   (a direct measure of how broken the current cap is).

**Why percentiles, not max:**

`max` is the single most outlier-sensitive statistic and is the specific methodology
that produced the unreliable Phase 12 cap (observed max was 9.65 from the small corpus;
real verbose JDs produce 18.45, a 91% increase). The p99 is far more stable — it
tolerates one extreme outlier per 100 pairings before being affected — and represents
the realistic ceiling for the vast majority of real usage. The cap will be derived from
the p99 of the verbose-JD subgroup (the hardest regime), with headroom above it. The
p95 of the same group will be reported as a secondary reference.

---

## 4. Proposed New BM25_SATURATION_CAP Derivation

**Pre-plan finding that shapes this:**

With 7 existing resumes and a verbose 42-token JD:
- `resume_backend_engineer.pdf`: raw = **18.45** (exceeds current cap of 12.0)
- `resume_fullstack_dev.pdf`: raw = **10.01** (near cap)
- Distribution of positive scores across 7 resumes × 6 JDs (n=34 positive pairs):
  p90 = 10.01, p95 = 17.21, p99 = 18.45, max = 18.45

This directly confirms the cap is insufficient for verbose JDs.

**Derivation approach:**

After running the full Phase 13 corpus measurement, the new cap will be set as:

```
BM25_SATURATION_CAP = ceil(p99_verbose_jd_subgroup * 1.25)
```

Where:
- `p99_verbose_jd_subgroup` = the p99 of raw scores from JDs with > 20 query tokens only
  (the stress test regime)
- `1.25` headroom factor: places the p99 match at 0.80 normalized (same as Phase 12's
  design intent), leaving 25% headroom above the measured p99 for unseen denser JDs

The `ceil()` rounds to a clean integer to avoid false precision on a heuristic constant.

This is a deliberate structural improvement over Phase 12's derivation: `p99 × 1.25`
is outlier-resistant (p99 not max), regime-specific (verbose JDs only, not pooled
with terse JDs that have lower ceilings), and the 1.25 factor is explicit and reasoned
rather than implicit in the choice of a round number.

**Ceiling: the cap must be measured and reported, then set to the derived value.** It
will NOT be set to "whatever makes existing tests pass." If the derived value is, say,
28, the cap becomes 28 — regardless of whether that breaks existing test thresholds.
Any test whose threshold changes as a result will be updated with the correct number and
the reason documented in the commit message.

**Non-constant capping strategy consideration:**

The prompt raises the possibility of a JD-length-aware cap (since BM25 raw scores scale
with query term count). This is correct in principle: a 10-token JD and a 50-token JD
have fundamentally different raw score ceilings. However, implementing a per-JD cap
introduces complexity (the cap becomes a function of query length, making it harder to
reason about composite scores) and requires fitting a scaling function to the measured
data. For this phase, a single constant derived from the verbose-JD p99 is preferred:
it is conservative for verbose JDs (the hard case) and slightly over-generous for terse
JDs (terse JDs already produce lower raw scores and are less likely to hit the cap).
A query-length-proportional cap is logged as a future refinement.

---

## 5. Validation Plan — Numerical Criteria Defined Before Implementation

The following criteria must ALL be satisfied for Phase 13 to be marked complete.
They are defined here, before any code is written, so success is not retroactively
defined by whatever the new cap happens to produce.

### Criterion 1: No saturation on genuine strong matches in the full corpus

**Definition:** A "strong match" is a resume from the same domain as the JD at mid/senior
level. A "weak match" is a resume from a different domain.

**Threshold:** After applying the new cap, no strong-match pair in the full 400-pair
corpus should normalize to exactly 1.0, UNLESS its raw score genuinely places it at the
absolute ceiling (i.e., above the p99 threshold for that JD length regime). In practice:
the new cap is derived so p99 maps to 0.80, meaning only the top 1% of pairings saturate.

Measured as: `count(normalized_bm25 == 1.0) / 400 pairings ≤ 1%`

### Criterion 2: Strong > Moderate > Weak ordering holds across all 10 JDs

For each JD, the median BM25 normalized score of same-domain candidates must exceed the
median of different-domain candidates:

`median(same-domain normalized scores) > median(different-domain normalized scores)`

This must hold for all 10 JDs independently.

### Criterion 3: Score gap is non-trivial

A same-domain senior candidate should score at least **2× the normalized BM25** of a
clearly different-domain candidate (e.g., a bioinformatics resume against a frontend JD).
Measured as:
`mean(top-2 same-domain normalized) ≥ 2 × mean(bottom-2 different-domain normalized)`
for each JD.

### Criterion 4: Batch-size invariance holds

The `test_bm25_normalization_batch_size_independent` regression test (added in Phase 12B)
must pass. No additional regression: `normalized = max(0, min(raw / cap, 1.0))` for any
raw score, regardless of batch.

### Criterion 5: Keyword-stuffer scenario still produces correct ranking

`test_keyword_stuffer_rejection_real_embeddings` must still pass: D (genuine frontend)
beats C (backend stuffer) with real all-MiniLM-L6-v2 embeddings at 30/30/20/20 weights.
The gap may change from the current +24.15 — report the new number explicitly.

### Criterion 6: Full test suite passes (87 tests)

All 87 existing tests pass. Any test whose expected value changes gets an updated value
with the reason documented in the commit message (not silently patched).

---

## 6. Test Fragility Fix — Structural Conversion

Every time BM25 scoring has changed (Phase 12 normalization, Phase 12B cap), tests broke
because they pinned exact float values that were never meaningful as exact values — they
were just whatever the scorer happened to produce when the test was written.

### Category A: Tests whose purpose is "is the ranking correct?"
These should assert ordering/direction, not exact values.

| Test | Current assertion | Purpose | Change |
|------|-------------------|---------|--------|
| `test_bm25_engine` | `scores[0] > scores[1]`, `scores[2] > scores[1]` | Ranking order | Already ordering — no change needed |
| `test_bm25_engine` | `min(scores) >= 0.0`, `max(scores) <= 1.0` | Bounds | Already range — no change needed |
| `test_bm25_stopword_filtering_independent` | `scores[1] > scores[0]` | Ranking order | Already ordering — no change needed |
| `test_score_candidates` | `top_cand["final_score"] > bot_cand["final_score"]` | Ranking direction | Already ordering — no change needed |
| `test_keyword_stuffer_rejection_at_20_percent_vector_weight` | `score_gap >= 5.0` | Gap magnitude | **Needs update:** threshold was 3.0 → updated to 5.0 post-Phase-12B based on cap-based numbers; re-verify after new cap and update to measured value |
| `test_keyword_stuffer_rejection_real_embeddings` | `D.final > C.final` | Ranking direction | Already ordering — verify still holds |

### Category B: Tests whose purpose is "does the arithmetic formula produce the correct output?"
These legitimately pin exact values because they're testing the scorer formula itself.

| Test | Current assertion | Purpose | Change |
|------|-------------------|---------|--------|
| `test_e2e_flow.py::test_full_e2e_recruiter_workflow` | `final_score == pytest.approx(expected_final, abs=0.01)` | Formula consistency (expected_final is computed from returned components, so it's self-consistent regardless of what values they take) | **Keep** — this is self-referential, not a pinned magic number |
| `test_bm25_normalization_batch_size_independent` | `abs(norm - expected) < 1e-9` | Formula `max(0, min(raw/CAP, 1.0))` produces correct output | **Keep** — this is explicitly testing the formula, not a specific score value |
| `test_keyword_stuffer_rejection_real_embeddings` | `abs(manual - final_score) < 0.01` | Transparency: score verifiable from components | **Keep** — formula verification, not a pinned value |

### Category C: Tests added in Phase 13
The new corpus-based BM25 distribution tests (Criterion 1–3 above) will assert:
- `count(normalized == 1.0) / n ≤ 0.01` — range assertion
- `median(same-domain) > median(different-domain)` — ordering assertion
- `mean(top-2) >= 2 × mean(bottom-2)` — ratio assertion

None will pin exact float values.

### Summary: no tests currently need structural conversion
The existing tests are already correctly structured — they use ordering and range
assertions rather than pinned floats, with the exception of `score_gap >= 5.0` (which
needs to be updated to the new measured value after the cap changes, not converted to
a different structure). The fragility issue in prior phases came from applying a cap
change without understanding what the new numbers would be — this phase derives the
numbers first and sets thresholds based on them.

---

## 7. Impact Assessment — Blast Radius

Tests that assert a specific BM25 or final_score **value** (not just ordering):

| File | Test | Assertion | Risk |
|------|------|-----------|------|
| `tests/test_matching.py` | `test_bm25_engine` | `min(scores) >= 0.0`, `max(scores) <= 1.0` | Low — bounds hold for any valid cap |
| `tests/test_matching.py` | `test_bm25_normalization_batch_size_independent` | `abs(norm - expected) < 1e-9`, `strong_norm < 1.0`, `strong_norm > 0.0`, `zero_norm == 0.0` | Low — all structural; only `< 1.0` could break if strong match saturates at new cap, but design intent is to prevent that |
| `tests/test_phase12_weight_validation.py` | `test_keyword_stuffer_rejection_at_20_percent_vector_weight` | `score_gap >= 5.0` | **Medium** — gap magnitude will change with new cap; needs re-measurement and threshold update |
| `tests/test_phase12_weight_validation.py` | `test_keyword_stuffer_rejection_real_embeddings` | `abs(manual - final_score) < 0.01` | Low — self-consistent formula check |
| `tests/test_e2e_flow.py` | `test_full_e2e_recruiter_workflow` | `final_score == pytest.approx(expected_final, abs=0.01)` | Low — self-consistent |
| `tests/test_e2e_flow.py` | `test_full_e2e_recruiter_workflow` | `skill_score == 1.0`, `tfidf_score > 0.0`, `final_score > 0.0` | Low — unaffected by BM25 cap change |

**All other test files** (`test_auth.py`, `test_authorization.py`, `test_api_jobs.py`,
`test_api_resumes.py`, `test_persistence.py`, `test_parser.py`, `test_ocr.py`,
`test_tagger.py`, `test_rate_limiting.py`) — confirmed no BM25 or final_score value
assertions. No changes required.

---

## Files to Create / Modify

### New files
- `tests/fixtures/phase13/README.md` — corpus methodology, attribution, construction notes
- `tests/fixtures/phase13/resumes/` — 40 synthetic plaintext resume fixtures
- `tests/fixtures/phase13/job_descriptions/` — 10 JD fixtures (synthetic + paraphrased)
- `tests/fixtures/phase13/measure_bm25_distribution.py` — measurement script (committed,
  runnable as `docker compose exec app python tests/fixtures/phase13/measure_bm25_distribution.py`)
- `tests/test_bm25_calibration.py` — automated tests for Criteria 1–3 above, using the
  Phase 13 corpus as fixtures

### Files to modify
- `app/services/matching/bm25_engine.py` — add `BM25_K1` and `BM25_B` named constants;
  update `BM25_SATURATION_CAP` to the derived value; update `BM25Okapi` instantiation to
  use the named constants; update calibration comment
- `tests/test_matching.py` — update `score_gap >= 5.0` threshold in
  `test_keyword_stuffer_rejection_at_20_percent_vector_weight` to the new measured value
- `DECISIONS.md` — update BM25_SATURATION_CAP entry with new value and derivation rationale

### Files NOT to modify
- `app/config.py` — weights unchanged (30/30/20/20 not re-litigated this phase)
- Any model, migration, API, auth, or frontend files

---

## Observed but out of scope

1. **k1/b hyperparameter tuning:** The analysis above shows k1/b don't explain the
   primary problem (cap calibration does), and tuning them without a comparative ranking
   quality evaluation across many query/document pairs would be premature. Logged for a
   future phase that includes proper A/B evaluation methodology.

2. **Query-length-proportional cap:** BM25 raw scores scale with query token count
   (empirically: 6-token JD produces max ~2.6; 42-token JD produces max ~18.5 with the
   same corpus). A proportional cap `f(|query|)` would be more principled than a single
   constant. Deferred because it requires fitting a scaling function to the measured data
   and adds composite-score reasoning complexity. Worth revisiting if the single-constant
   cap still shows significant compression at the terse end.

3. **Weight split re-evaluation:** PROGRESS_LOG notes 30/30/20/20 is still provisional.
   The Phase 13 corpus provides a 10-JD × 40-resume baseline that could support weight
   re-evaluation, but that is a separate phase decision. If the BM25 recalibration reveals
   an obvious imbalance, it will be flagged here under a separate heading rather than
   fixed inline.

4. **BM25 IDF small-corpus behavior:** The currently documented behavior (BM25=0.0 in
   1–2 candidate batches) is correct and accepted. Phase 13 does not change this.

---

## Implementation Order (after "approved, proceed")

1. Build the 40-resume + 10-JD corpus. Commit to `tests/fixtures/phase13/`.
2. Run measurement script. Report the percentile distribution here (will be filled in
   post-measurement, before touching `bm25_engine.py`).
3. Derive `BM25_SATURATION_CAP` from `ceil(p99_verbose × 1.25)`. Verify Criteria 1–3
   are satisfied at the derived value before committing anything.
4. Update `bm25_engine.py`: add `BM25_K1`, `BM25_B` constants; update cap; update
   `BM25Okapi` instantiation; update calibration comment.
5. Update `test_matching.py`: update `score_gap >= 5.0` to measured value.
6. Add `tests/test_bm25_calibration.py` with Criteria 1–3 tests.
7. Run full test suite (87 existing + new calibration tests). Report output.
8. Update `DECISIONS.md`.
9. Update `PROGRESS_LOG.md` (only once all above verified).
10. Commit in atomic units: corpus, measurement, engine fix, tests, docs.

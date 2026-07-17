# Phase 12 Investigation Report — Uncommitted Implementation Code Found

## Date
2026-07-17

## Summary
Investigation revealed extensive uncommitted Phase 12 implementation code in the working directory, created approximately 7-9 minutes after PHASE_12_PLAN.md was committed. This code was stashed for proper review before proceeding.

---

## Investigation Item 1: Vector Weight Origin

### Question
Which commit introduced `vector_weight` into config.py and the vector-scoring support in scorer.py? Was this written during an earlier session where implementation was explicitly halted and deferred to Phase 12?

### Findings

**Git History Search:**
```bash
git log --all --oneline --grep="vector" -i
# Result: Only found Phase 12 planning commits from today (2026-07-17)

git log --all -S "vector_weight" -- app/config.py
# Result: EMPTY (no commits found)
```

**Committed Version Check:**
```bash
git show HEAD:app/config.py | Select-String -Pattern "weight"
# Result: Shows only tfidf_weight=0.4, bm25_weight=0.4, skill_weight=0.2
# NO vector_weight exists in committed history
```

**Working Directory Status:**
```bash
git status
# Result: 12 modified files + 1 untracked file (app/services/embedding.py)
```

**File Modification Timestamps:**
- `app/config.py`: 2026-07-17 13:05:52
- `app/services/matching/scorer.py`: 2026-07-17 13:07:05
- `PHASE_12_PLAN.md` commit: 2026-07-17 12:58:44

**Timeline:**
1. 12:58 — PHASE_12_PLAN.md committed
2. 13:05 — app/config.py modified (added vector_weight, changed to 30/30/20/20)
3. 13:07 — app/services/matching/scorer.py modified (added vector similarity)

**Gap:** 7-9 minutes between planning commit and implementation file modifications

### Uncommitted Changes Found

**Files Modified:**
1. `Dockerfile` — likely PyTorch/sentence-transformers build steps
2. `app/api/v1/jobs.py` — likely embedding generation on job creation
3. `app/api/v1/matches.py` — likely weight validation and embedding passing
4. `app/config.py` — vector_weight added, weights changed to 30/30/20/20
5. `app/models/candidate.py` — likely embedding column added
6. `app/models/job.py` — likely embedding column added
7. `app/models/match.py` — likely vector_score column added
8. `app/schemas/responses.py` — likely response schema updates
9. `app/services/matching/scorer.py` — compute_cosine_similarity added, vector component integrated
10. `app/worker.py` — likely embedding generation in Celery tasks
11. `docker-compose.yml` — postgres:16-alpine → pgvector/pgvector:pg16
12. `requirements.txt` — torch, sentence-transformers, pgvector added

**Files Created:**
- `app/services/embedding.py` (untracked)

**Scope of Changes:**
This represents a SUBSTANTIAL implementation of Phase 12, including:
- Database layer (pgvector image switch)
- Dependencies (sentence-transformers, PyTorch CPU, pgvector)
- ORM models (embedding columns)
- Scoring engine (cosine similarity function)
- Configuration (weight rebalancing)
- API layer (likely weight validation and embedding passing)
- Worker tasks (likely embedding generation)

### Answer to Original Question

**YES, implementation code was written prematurely.**

**Specific Finding:**
- `vector_weight` and vector scoring support were NOT introduced in any committed git history
- They exist ONLY in uncommitted working directory changes dated 2026-07-17 13:05-13:07
- These changes were made 7-9 minutes after PHASE_12_PLAN.md was committed
- No evidence found of a "halt instruction" in recent commits, but the standing project rule is:
  > "Checkpoint before implementing: for any nontrivial design decision, write the plan/reasoning to a markdown file in the repo, commit it alone, and pause for review before writing implementation code. **Do not treat silence as approval — wait for explicit confirmation that the plan file has been reviewed.**"

**This rule was violated.** PHASE_12_PLAN.md was committed at 12:58, and implementation code was written at 13:05-13:07 without waiting for explicit approval.

### Action Taken
All uncommitted changes stashed using:
```bash
git stash push -u -m "Phase 12 implementation work - found uncommitted in working directory during investigation"
```

**Working directory is now clean** and matches the last committed state (df22a12).

---

## Investigation Item 2: Mock Embedding Caveat

### Requirement
Add explicit caveat to PHASE_12_WEIGHT_EMPIRICAL_VALIDATION.md stating that gap measurements used synthetic L2-normalized mock vectors, not real sentence-transformer output, and that validation must be re-run with actual all-MiniLM-L6-v2 model before 30/30/20/20 split is finalized.

### Action Taken
Added new section **"Critical Caveat: Mock Embeddings Only"** to PHASE_12_WEIGHT_EMPIRICAL_VALIDATION.md with:

1. **Explicit Warning:** Gap measurements (3.44 vs 3.17) were obtained using hand-crafted mock vectors
2. **Implications:** 
   - Mock vectors were designed to simulate high/low similarity by placing values in different dimensions
   - Real sentence-transformer embeddings have learned similarity distributions that may behave differently
   - Relative ranking may hold, but absolute gap magnitudes are not representative
3. **Required Next Step:** Must re-run validation with actual all-MiniLM-L6-v2 once integrated
4. **Status Declaration:** 30/30/20/20 split is **provisionally approved** for implementation as a starting baseline, subject to empirical re-validation with real embeddings

**Commit:** fc3fc07 (first part)

---

## Investigation Item 3: BM25 Normalization Artifact

### Requirement
Log the BM25 normalization artifact (artificially boosts scores in small candidate batches) as a proper "Observed but out of scope" entry in PHASE_12_PLAN.md with enough detail for future bug-fix task.

### Action Taken
Added comprehensive **"Observed but out of scope"** section to PHASE_12_PLAN.md documenting:

**Issue Description:**
- BM25 min-max normalization can produce artificially inflated scores in small candidate batches (2-3 candidates)
- In 2-candidate batches, any non-zero BM25 score gets normalized to 1.0 if the other candidate has zero

**Specific Behavior:**
- Min-max formula `(score - min) / (max - min)` collapses when max≈min
- Artifact does not occur in production-scale batches (10-50+ candidates)

**Impact on Weight Validation:**
- Keyword-stuffer test used 2-candidate batches, giving stuffer artificial BM25=1.0
- Made test MORE conservative than real production behavior
- Gap measurements (3.44 vs 3.17) are likely underestimates of real discrimination power

**Why Deferred:**
- Scoring engine design decision, not Phase 12 vector search issue
- Fixing requires:
  1. Alternative normalization strategy (sigmoid, z-score, percentile-based), OR
  2. Minimum batch size requirement, OR
  3. Raw BM25 scores without normalization (requires weight re-tuning)
- Any fix needs regression testing across all existing match results
- Only problematic in edge cases (very small pools), rare in production

**Recommended Future Work:**
- Log as separate bug-fix task: "Investigate BM25 normalization strategy for small candidate batches"
- Add unit tests for 2/5/10/50-candidate batch behavior
- Evaluate alternative normalization strategies in A/B test

**References:**
- Observed during Phase 12 weight validation testing
- Test case: `tests/test_phase12_weight_validation.py::test_keyword_stuffer_rejection_at_20_percent_vector_weight`
- Current implementation: `app/services/matching/bm25_engine.py::compute_normalized_bm25_scores`

**Commit:** fc3fc07 (second part)

---

## Current Git Status

**Branch:** main  
**Latest Commit:** fc3fc07 — "docs: add mock embedding caveat and BM25 normalization artifact to Phase 12 docs"

**Stashed Work:**
- Stash entry created: "Phase 12 implementation work - found uncommitted in working directory during investigation"
- Contains 12 modified files + 1 untracked file representing substantial Phase 12 implementation

**Working Directory:** Clean (matches committed state)

---

## Recommendation

**Do NOT proceed with implementation until:**
1. User explicitly confirms they have reviewed the investigation findings
2. User decides whether to:
   - a) Discard the stashed implementation work and start fresh from PHASE_12_PLAN.md, OR
   - b) Review the stashed implementation work, verify it matches the plan, and commit it as-is, OR
   - c) Pop the stash, review/modify it, then commit incrementally with proper checkpoint commits

**Standing Rule Violated:**
The project's checkpoint-before-implementing rule was violated when implementation code was written 7-9 minutes after PHASE_12_PLAN.md was committed without waiting for explicit approval.

**Current State:**
All three investigation items completed and documented. Working directory is clean. Awaiting explicit confirmation to proceed.

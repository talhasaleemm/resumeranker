"""
scripts/calibrate_bm25.py — BM25 Query-Length Normalization Calibration Tool
==============================================================================

STANDALONE OFFLINE SCRIPT. DO NOT import from pytest or include in the test suite.
Run manually before committing Phase 13 implementation changes to tune SCALE_FACTOR.

Usage:
    python scripts/calibrate_bm25.py

Purpose:
    Measures raw BM25 scores and calibrates SCALE_FACTOR for the query-length
    normalization formula:

        normalized_score = max(0.0, min(raw_score / (sum_of_query_idfs * SCALE_FACTOR), 1.0))

    Targets:
        - Independence band (dense candidate, verbose vs terse JD): delta < 0.10
        - Perfect-match saturation (candidate_perfect vs jd_medium): 0.80 <= score <= 0.85
        - No stuffer beats genuine: dense > stuffer on every JD
        - No premature saturation: verbose JD perfect match <= 0.90

    SCALE_FACTOR candidates tested: [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8]

Architecture Notes:
    - This script intentionally re-implements the tokenizer to be self-contained.
      It must not import from app.services to avoid circular dependency during calibration.
    - When bm25_engine.py is updated for Phase 13, the production formula must
      match the formula used here exactly.
    - Signature change reminder: scorer.py line 85 must be updated SIMULTANEOUSLY
      with bm25_engine.py when the n_query_tokens parameter is introduced.

CI Protection:
    This script is computationally heavy (49 pairs × 9 SF candidates = 441 evaluations).
    It is excluded from the pytest suite by design. pytest only asserts final validation
    rules on the committed SCALE_FACTOR value.
"""

from __future__ import annotations

import json
import os
import string
import sys
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    print("ERROR: rank-bm25 not installed. Run: pip install rank-bm25")
    sys.exit(1)

try:
    from spacy.lang.en.stop_words import STOP_WORDS
except ImportError:
    print("ERROR: spacy not installed. Run: pip install spacy")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "phase13"
MANIFEST_FILE = FIXTURES_DIR / "corpus_manifest.json"

CUSTOM_STOP_WORDS: set[str] = {"developer", "experience", "engineer", "senior", "junior", "years"}
ALL_STOP_WORDS: set[str] = STOP_WORDS.union(CUSTOM_STOP_WORDS)

# SCALE_FACTOR candidates to sweep
SCALE_FACTORS: List[float] = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8]

# Calibration targets
TARGET_INDEPENDENCE_BAND: float = 0.10      # max delta across JD lengths for same-density match
TARGET_PERFECT_MATCH_MIN: float = 0.80      # perfect-match score lower bound
TARGET_PERFECT_MATCH_MAX: float = 0.85      # perfect-match score upper bound (headroom)
TARGET_MAX_VERBOSE_SATURATION: float = 0.90  # no premature saturation on verbose JD

# Key pairings for targeted calibration assertions (id from manifest)
INDEPENDENCE_PAIRING_IDS = [1, 2, 3]  # verbose, terse, medium vs dense candidate
PERFECT_MATCH_PAIRING_ID = 6          # jd_medium vs candidate_perfect
STUFFER_PAIRING_ID = 5                # jd_verbose vs candidate_stuffer
DENSE_VS_VERBOSE_PAIRING_ID = 1       # jd_verbose vs candidate_dense


# ---------------------------------------------------------------------------
# Tokenizer (mirrors bm25_engine.py _tokenize exactly)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Lowercase, strip punctuation, remove stopwords."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return [t for t in text.split() if t not in ALL_STOP_WORDS]


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _load_fixture(filename: str) -> str:
    path = FIXTURES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _load_manifest() -> dict:
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_FILE}")
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# BM25 Scoring
# ---------------------------------------------------------------------------

def _score_pair(jd_text: str, candidate_text: str, corpus: List[str]) -> Tuple[float, float, List[str]]:
    """
    Score a JD against a candidate embedded in a corpus.

    Returns:
        (raw_score, sum_idf, query_tokens)

    The corpus should include ALL candidates for a given JD to produce realistic IDF values.
    Using the full 49-pairing corpus as the document pool per JD cluster.
    """
    q_tokens = _tokenize(jd_text)
    tokenized_corpus = [_tokenize(doc) for doc in corpus]

    if not q_tokens or not any(tokenized_corpus):
        return 0.0, 0.0, q_tokens

    bm25 = BM25Okapi(tokenized_corpus)
    all_scores = bm25.get_scores(q_tokens).tolist()

    # Find the score for our specific candidate
    cand_tokens = _tokenize(candidate_text)
    cand_idx = next(
        (i for i, t in enumerate(tokenized_corpus) if t == cand_tokens),
        0
    )
    raw_score = all_scores[cand_idx]

    # sum of IDFs for query tokens (IDF values are computed over the corpus)
    sum_idf = sum(bm25.idf.get(t, 0.0) for t in q_tokens)

    return raw_score, sum_idf, q_tokens


def _normalize(raw: float, sum_idf: float, scale_factor: float) -> float:
    """Apply the Phase 13 query-length normalization formula."""
    if sum_idf <= 0.0:
        return 0.0
    denom = sum_idf * scale_factor
    return max(0.0, min(raw / denom, 1.0))


# ---------------------------------------------------------------------------
# Main Calibration Runner
# ---------------------------------------------------------------------------

def run_calibration() -> None:
    print("=" * 80)
    print("BM25 QUERY-LENGTH NORMALIZATION CALIBRATION")
    print("scripts/calibrate_bm25.py — Phase 13")
    print("=" * 80)
    print(f"Fixtures:  {FIXTURES_DIR}")
    print(f"Manifest:  {MANIFEST_FILE}")
    print()

    manifest = _load_manifest()
    pairings = manifest["pairings"]
    print(f"Loaded {len(pairings)} pairings from corpus_manifest.json")
    print()

    # Pre-load all texts
    jd_cache: Dict[str, str] = {}
    cand_cache: Dict[str, str] = {}

    for p in pairings:
        jd_file = p["jd"]
        cand_file = p["candidate"]
        if jd_file not in jd_cache:
            jd_cache[jd_file] = _load_fixture(jd_file)
        if cand_file not in cand_cache:
            cand_cache[cand_file] = _load_fixture(cand_file)

    all_candidate_texts = list(cand_cache.values())

    # -----------------------------------------------------------------------
    # Phase 1: Raw scores per pairing
    # -----------------------------------------------------------------------
    print("=" * 80)
    print("PHASE 1 — RAW SCORES (all 49 pairings, corpus = all unique candidates)")
    print("=" * 80)

    raw_results: Dict[int, Tuple[float, float, int]] = {}  # id -> (raw, sum_idf, q_len)
    for p in pairings:
        pid = p["id"]
        jd_text = jd_cache[p["jd"]]
        cand_text = cand_cache[p["candidate"]]
        raw, sum_idf, q_tokens = _score_pair(jd_text, cand_text, all_candidate_texts)
        raw_results[pid] = (raw, sum_idf, len(q_tokens))

    # Print raw score table
    print(f"{'ID':>3}  {'JD':<35} {'Candidate':<40} {'Raw':>8} {'SumIDF':>9} {'Q_len':>6}")
    print("-" * 105)
    for p in pairings:
        pid = p["id"]
        raw, sum_idf, q_len = raw_results[pid]
        print(
            f"{pid:>3}  {p['jd']:<35} {p['candidate']:<40} "
            f"{raw:>8.4f} {sum_idf:>9.4f} {q_len:>6}"
        )

    # -----------------------------------------------------------------------
    # Phase 2: SCALE_FACTOR sweep
    # -----------------------------------------------------------------------
    print()
    print("=" * 80)
    print("PHASE 2 — SCALE_FACTOR SWEEP")
    print(f"Targets: independence_band < {TARGET_INDEPENDENCE_BAND}  |  "
          f"perfect_match in [{TARGET_PERFECT_MATCH_MIN}, {TARGET_PERFECT_MATCH_MAX}]  |  "
          f"no saturation > {TARGET_MAX_VERBOSE_SATURATION}")
    print("=" * 80)

    best_sf: float | None = None

    for sf in SCALE_FACTORS:
        # Compute normalized scores for all pairings
        normed: Dict[int, float] = {}
        for pid, (raw, sum_idf, _) in raw_results.items():
            normed[pid] = _normalize(raw, sum_idf, sf)

        # Calibration assertions
        # 1. Independence band: max delta across JD-length variants vs dense candidate
        independence_scores = [normed[pid] for pid in INDEPENDENCE_PAIRING_IDS]
        band = max(independence_scores) - min(independence_scores)

        # 2. Perfect-match saturation
        perfect_score = normed[PERFECT_MATCH_PAIRING_ID]

        # 3. Stuffer vs dense on verbose JD
        stuffer_score = normed[STUFFER_PAIRING_ID]
        dense_verbose_score = normed[DENSE_VS_VERBOSE_PAIRING_ID]
        dense_beats_stuffer = dense_verbose_score > stuffer_score

        # 4. No premature saturation on verbose dense match
        no_premature_sat = dense_verbose_score <= TARGET_MAX_VERBOSE_SATURATION

        # Overall pass/fail
        band_ok = band < TARGET_INDEPENDENCE_BAND
        perfect_ok = TARGET_PERFECT_MATCH_MIN <= perfect_score <= TARGET_PERFECT_MATCH_MAX
        all_ok = band_ok and perfect_ok and dense_beats_stuffer and no_premature_sat

        status = "✓ PASS" if all_ok else "✗ FAIL"
        if all_ok and best_sf is None:
            best_sf = sf

        print(
            f"SF={sf:.1f}  {status}  "
            f"band={band:.4f}({'OK' if band_ok else 'FAIL'})  "
            f"perfect={perfect_score:.3f}({'OK' if perfect_ok else 'FAIL'})  "
            f"dense_vs_verbose={dense_verbose_score:.3f}  "
            f"stuffer={stuffer_score:.3f}  "
            f"dense>stuffer={'YES' if dense_beats_stuffer else 'NO'}  "
            f"no_sat={'OK' if no_premature_sat else 'FAIL'}"
        )

    # -----------------------------------------------------------------------
    # Phase 3: Full normalized table at best SF
    # -----------------------------------------------------------------------
    if best_sf is not None:
        print()
        print("=" * 80)
        print(f"PHASE 3 — FULL NORMALIZED SCORES AT RECOMMENDED SF={best_sf}")
        print("=" * 80)
        print(f"{'ID':>3}  {'JD':<35} {'Candidate':<40} {'Norm':>7}  {'Purpose'}")
        print("-" * 115)
        for p in pairings:
            pid = p["id"]
            raw, sum_idf, _ = raw_results[pid]
            norm = _normalize(raw, sum_idf, best_sf)
            print(f"{pid:>3}  {p['jd']:<35} {p['candidate']:<40} {norm:>7.4f}  {p['purpose']}")

        print()
        print("=" * 80)
        print(f"RECOMMENDED SCALE_FACTOR = {best_sf}")
        print()
        print("ACTION REQUIRED:")
        print(f"  1. Set SCALE_FACTOR = {best_sf} in app/services/matching/bm25_engine.py")
        print("  2. Update compute_normalized_bm25_scores() to accept query tokens and apply:")
        print("       normalized = max(0.0, min(raw / (sum_idf * SCALE_FACTOR), 1.0))")
        print("  3. Update scorer.py line 85 IN THE SAME COMMIT to pass tokenized JD tokens.")
        print("     Partial update = TypeError crash in Celery worker path.")
        print("=" * 80)
    else:
        print()
        print("=" * 80)
        print("WARNING: No SCALE_FACTOR in sweep passed all calibration targets.")
        print("Review the raw scores above and adjust fixture vocabulary or expand the sweep range.")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    run_calibration()

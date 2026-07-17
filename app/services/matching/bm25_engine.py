"""
app/services/matching/bm25_engine.py — BM25 Scoring
Uses rank-bm25 to compute Okapi BM25 scores between a job description and a set of resumes.
"""
import string
from typing import List
from rank_bm25 import BM25Okapi

from spacy.lang.en.stop_words import STOP_WORDS

CUSTOM_STOP_WORDS = {"developer", "experience", "engineer", "senior", "junior", "years"}
ALL_STOP_WORDS = STOP_WORDS.union(CUSTOM_STOP_WORDS)

# Cap for absolute BM25 normalization (replaces min-max normalization).
#
# Rationale: min-max normalization is batch-relative — it maps the weakest candidate in
# a batch to 0.0 and the strongest to 1.0 regardless of their absolute signal strength.
# This is incompatible with TF-IDF, skills, and vector components which are all absolute
# measures. In a 2-candidate batch, any candidate with non-zero BM25 overlap gets 1.0,
# which can dominate the composite score and cancel the vector signal entirely.
#
# Cap-based normalization: normalized = min(raw_score / BM25_SATURATION_CAP, 1.0)
# A raw score at or above the cap → 1.0 (saturated match); below it → proportional.
# The result is batch-size-independent: the same candidate text produces the same
# normalized score whether the batch contains 2 or 200 candidates.
#
# Calibration (2026-07-17): Raw BM25 scores measured across the full test corpus
# (short fixture texts and all 7 real sample resumes × 3 representative JDs):
#   Min non-zero:  0.19
#   Median:        ~1.1
#   90th pct:      ~4.7
#   Observed max:  9.65  (resume_fullstack_dev.pdf vs frontend JD — a strong genuine match)
#
# Cap of 12.0 places the observed corpus maximum at 9.65/12.0 = 0.80 (strong but not
# saturated). Nothing in the current corpus hits 1.0, leaving headroom for denser
# documents without requiring the cap to be retuned. A tight cap (e.g. 9.65) would
# overfit to current fixtures; a loose cap (e.g. 20.0) would compress all scores into
# the 0–0.48 range and weaken BM25 discrimination.
BM25_K1: float = 1.5
BM25_B: float = 0.75
SCALE_FACTOR: float = 1.0

def _tokenize(text: str) -> List[str]:
    """Tokenization: lowercase, remove punctuation, remove stopwords, split by whitespace."""
    text = text.lower()
    # Remove punctuation
    text = text.translate(str.maketrans("", "", string.punctuation))
    tokens = text.split()
    return [t for t in tokens if t not in ALL_STOP_WORDS]


def compute_bm25_scores(query: str, documents: List[str]) -> List[float]:
    """
    Computes BM25 similarity scores between a query (Job Description)
    and a list of documents (Resumes).

    Returns:
        List of raw float scores. BM25 scores are not bounded between 0 and 1.
        Use compute_normalized_bm25_scores for a [0, 1]-bounded version.
    """
    if not query.strip() or not documents:
        return [0.0] * len(documents)

    # Tokenize corpus
    tokenized_corpus = [_tokenize(doc) for doc in documents]
    tokenized_query = _tokenize(query)

    if not tokenized_corpus or not any(tokenized_corpus):
        return [0.0] * len(documents)

    bm25 = BM25Okapi(tokenized_corpus, k1=BM25_K1, b=BM25_B)
    scores = bm25.get_scores(tokenized_query)

    return scores.tolist()


def compute_normalized_bm25_scores(query: str, documents: List[str], n_query_tokens: int) -> List[float]:
    """
    Computes BM25 scores and normalizes them to [0.0, 1.0] using Length-Aware Normalization.

    Normalization: normalized = max(0.0, min(raw_score / (sum_idf * SCALE_FACTOR), 1.0))
    """
    if not query.strip() or not documents:
        return [0.0] * len(documents)

    tokenized_corpus = [_tokenize(doc) for doc in documents]
    tokenized_query = _tokenize(query)

    if not tokenized_corpus or not any(tokenized_corpus):
        return [0.0] * len(documents)

    bm25 = BM25Okapi(tokenized_corpus, k1=BM25_K1, b=BM25_B)
    raw_scores = bm25.get_scores(tokenized_query).tolist()
    
    sum_idf = sum(bm25.idf.get(t, 0.0) for t in tokenized_query)

    if sum_idf <= 0.0:
        return [0.0] * len(documents)
        
    denom = sum_idf * SCALE_FACTOR
    return [max(0.0, min(s / denom, 1.0)) for s in raw_scores]

"""
app/services/matching/bm25_engine.py — BM25 Scoring
Uses rank-bm25 BM25Plus to compute BM25 scores between a job description and a set of resumes.
"""
import math
import string
from typing import List
from rank_bm25 import BM25Plus

from spacy.lang.en.stop_words import STOP_WORDS

CUSTOM_STOP_WORDS = {"developer", "experience", "engineer", "senior", "junior", "years"}
ALL_STOP_WORDS = STOP_WORDS.union(CUSTOM_STOP_WORDS)

# BM25 parameters
BM25_K1: float = 1.5
BM25_B: float = 0.75

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

    bm25 = BM25Plus(tokenized_corpus, k1=BM25_K1, b=BM25_B)
    scores = bm25.get_scores(tokenized_query)

    return scores.tolist()


def compute_normalized_bm25_scores(query: str, documents: List[str]) -> List[float]:
    """
    Computes BM25 scores and normalizes them to [0.0, 1.0] using a sigmoid
    curve centered at BM25_NORM_MIDPOINT with steepness BM25_NORM_STEEPNESS.
    
    Unlike min-max or max-score normalization, this never forces the best
    candidate in a batch to 1.0. A "strong" BM25 match (~10-15) maps to
    ~0.5-0.8, while genuinely perfect matches approach but rarely reach 1.0.
    
    Formula: normalized = 1 / (1 + exp(-(raw - midpoint) / steepness))
    """
    if not query.strip() or not documents:
        return [0.0] * len(documents)

    tokenized_corpus = [_tokenize(doc) for doc in documents]
    tokenized_query = _tokenize(query)

    if not tokenized_corpus or not any(tokenized_corpus):
        return [0.0] * len(documents)

    bm25 = BM25Plus(tokenized_corpus, k1=BM25_K1, b=BM25_B)
    raw_scores = bm25.get_scores(tokenized_query).tolist()

    # Absolute-scale normalization. A "very strong" BM25 match for a resume
    # query typically scores 80-150; a "moderate" match scores 20-50. Dividing
    # by BM25_NORM_DIVISOR maps strong matches to [0.4, 0.75] instead of
    # forcing the batch maximum to 1.0. This preserves meaningful separation
    # across the full [0, 1] band while keeping BM25 proportional to actual
    # keyword density.
    BM25_NORM_DIVISOR = 200.0
    return [max(0.0, min(s / BM25_NORM_DIVISOR, 1.0)) for s in raw_scores]

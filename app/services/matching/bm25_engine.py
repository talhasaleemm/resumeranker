"""
app/services/matching/bm25_engine.py — BM25 Scoring
Uses rank-bm25 to compute Okapi BM25 scores between a job description and a set of resumes.
"""
import string
from typing import List
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> List[str]:
    """Simple tokenization: lowercase, remove punctuation, split by whitespace."""
    text = text.lower()
    # Remove punctuation
    text = text.translate(str.maketrans("", "", string.punctuation))
    return text.split()


def compute_bm25_scores(query: str, documents: List[str]) -> List[float]:
    """
    Computes BM25 similarity scores between a query (Job Description)
    and a list of documents (Resumes).
    
    Returns:
        List of float scores. Note: BM25 scores are not bounded between 0 and 1.
        They scale with the corpus, so they must be normalized if combined linearly.
    """
    if not query.strip() or not documents:
        return [0.0] * len(documents)

    # Tokenize corpus
    tokenized_corpus = [_tokenize(doc) for doc in documents]
    tokenized_query = _tokenize(query)
    
    if not tokenized_corpus or not any(tokenized_corpus):
        return [0.0] * len(documents)

    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(tokenized_query)
    
    return scores.tolist()


def compute_normalized_bm25_scores(query: str, documents: List[str]) -> List[float]:
    """
    Computes BM25 scores and min-max normalizes them to a 0.0 - 1.0 range
    so they can be safely combined with TF-IDF and Skill overlap scores.
    """
    raw_scores = compute_bm25_scores(query, documents)
    
    if not raw_scores:
        return []
        
    min_score = min(raw_scores)
    max_score = max(raw_scores)
    
    if max_score == min_score:
        return [0.0 if max_score == 0 else 1.0 for _ in raw_scores]
        
    # Min-Max normalize
    normalized = [(s - min_score) / (max_score - min_score) for s in raw_scores]
    return normalized

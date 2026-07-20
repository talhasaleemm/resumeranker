"""
app/services/matching/tfidf_engine.py — TF-IDF Scoring
Uses scikit-learn TfidfVectorizer to compute cosine similarity between a job description and a set of resumes.
"""
from typing import List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def compute_tfidf_scores(query: str, documents: List[str]) -> List[float]:
    """
    Computes TF-IDF cosine similarity scores between a query (e.g. Job Description)
    and a list of documents (e.g. Resumes).
    
    Returns:
        List of float scores between 0.0 and 1.0.
    """
    if not query.strip() or not documents:
        return [0.0] * len(documents)

    # Add the query as the first document in the corpus to fit the vectorizer
    corpus = [query] + documents
    
    # Using stop words and lowercasing by default
    vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
    
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        # Happens if all words are stop words or vocabulary is empty
        return [0.0] * len(documents)
    
    # Query is index 0, documents are indices 1..N
    query_vector = tfidf_matrix[0:1]
    doc_vectors = tfidf_matrix[1:]
    
    # Compute cosine similarity
    similarity_scores = cosine_similarity(query_vector, doc_vectors)
    scores = similarity_scores.flatten().tolist()

    return scores

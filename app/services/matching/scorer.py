"""
app/services/matching/scorer.py — Match Scorer Pipeline
Combines TF-IDF, BM25, and exact skill matching into a unified 0-100 match score.
"""
from typing import List, Dict, Any
from app.config import get_settings
from app.services.matching.tfidf_engine import compute_tfidf_scores
from app.services.matching.bm25_engine import compute_normalized_bm25_scores
from app.services.normalization.normalizer import normalize_skills_list, normalize_skill
from app.services.tagging.tagger import assign_tags


def compute_skill_overlap(job_skills: List[str], candidate_skills: List[str]) -> float:
    """
    Computes Jaccard-like overlap for skills.
    Normalizes both lists, then calculates what percentage of job_skills
    are present in the candidate_skills.
    """
    if not job_skills:
        return 1.0  # If job requires no specific skills, auto-pass skill check

    norm_job_skills = set(normalize_skills_list(job_skills))
    norm_cand_skills = set(normalize_skills_list(candidate_skills))
    
    if not norm_job_skills:
        return 1.0

    overlap = norm_job_skills.intersection(norm_cand_skills)
    return len(overlap) / len(norm_job_skills)


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Computes cosine similarity between two vectors.
    Since SentenceTransformer vectors are L2-normalized, this is equivalent
    to the dot product. Shifted/clipped to [0.0, 1.0].
    Accepts both Python lists and numpy arrays (pgvector returns numpy arrays).
    """
    # Use len() check instead of truthiness to avoid ValueError with numpy arrays
    # ("The truth value of an array with more than one element is ambiguous")
    if vec_a is None or vec_b is None or len(vec_a) == 0 or len(vec_b) == 0:
        return 0.0
    dot_product = sum(x * y for x, y in zip(vec_a, vec_b))
    return max(0.0, min(1.0, dot_product))


def score_candidates(
    job_description: str,
    job_required_skills: List[str],
    candidates: List[Dict[str, Any]],
    job_embedding: List[float] = None,
    weights: Dict[str, float] = None
) -> List[Dict[str, Any]]:
    """
    Main matching pipeline.
    
    candidates must be a list of dicts with at least:
        - id: str/UUID
        - raw_text: str (for tfidf/bm25)
        - skills: List[str] (for exact skill match)
        - embedding: List[float] (optional, for vector similarity)
        
    # TODO(scale): Transition from in-memory sparse matrices to a dedicated vector database (e.g., pgvector, Milvus) for scalability
        
    Returns a list of dicts containing the match_result for each candidate.
    """
    settings = get_settings()
    
    if not candidates:
        return []

    # Resolve active weights
    w_tfidf = weights.get("tfidf", settings.tfidf_weight) if weights else settings.tfidf_weight
    w_bm25 = weights.get("bm25", settings.bm25_weight) if weights else settings.bm25_weight
    w_skills = weights.get("skills", settings.skill_weight) if weights else settings.skill_weight
    w_vector = weights.get("vector", settings.vector_weight) if weights else settings.vector_weight

    # Prepare corpus
    candidate_texts = [c.get("raw_text", "") for c in candidates]
    
    # 1. Compute TF-IDF
    tfidf_scores = compute_tfidf_scores(job_description, candidate_texts)
    
    # 2. Compute BM25 (Normalized)
    bm25_scores = compute_normalized_bm25_scores(job_description, candidate_texts)
    
    results = []
    
    for i, candidate in enumerate(candidates):
        cand_id = candidate.get("id")
        cand_skills = candidate.get("skills", [])
        cand_embedding = candidate.get("embedding", None)
        
        # 3. Compute Skill Overlap
        skill_score = compute_skill_overlap(job_required_skills, cand_skills)
        
        # 4. Compute Vector Similarity (Cosine Similarity)
        vec_score = 0.0
        # Use explicit None checks + len to avoid ValueError when embeddings are numpy arrays
        # (pgvector returns numpy arrays whose truthiness requires .any()/.all())
        if job_embedding is not None and cand_embedding is not None and len(job_embedding) > 0 and len(cand_embedding) > 0:
            vec_score = compute_cosine_similarity(job_embedding, cand_embedding)
            
        tf_score = tfidf_scores[i]
        bm_score = bm25_scores[i]
        
        # Weighted Final Score (0.0 - 1.0)
        raw_final = (
            (tf_score * w_tfidf) +
            (bm_score * w_bm25) +
            (skill_score * w_skills) +
            (vec_score * w_vector)
        )
        
        # Ensure it sums to exactly 0-100 cleanly
        total_weight = w_tfidf + w_bm25 + w_skills + w_vector
        if total_weight > 0:
            raw_final = raw_final / total_weight
            
        final_score_100 = round(raw_final * 100, 2)
        
        # Explanation Log for transparency
        norm_job_skills_set = set(normalize_skills_list(job_required_skills))
        norm_cand_skills_set = set(normalize_skills_list(cand_skills))
        
        matched_skills = []
        for orig_cand_skill in cand_skills:
            if normalize_skill(orig_cand_skill) in norm_job_skills_set:
                matched_skills.append(orig_cand_skill)
                
        missing_skills = []
        for orig_job_skill in job_required_skills:
            if normalize_skill(orig_job_skill) not in norm_cand_skills_set:
                missing_skills.append(orig_job_skill)
                
        matched_skills = sorted(list(set(matched_skills)))
        missing_skills = sorted(list(set(missing_skills)))
        
        assigned_tags, tag_evidence = assign_tags(candidate)
        
        explanation = {
            "tfidf_contribution": round(tf_score * w_tfidf * 100, 2),
            "bm25_contribution": round(bm_score * w_bm25 * 100, 2),
            "skill_contribution": round(skill_score * w_skills * 100, 2),
            "vector_contribution": round(vec_score * w_vector * 100, 2),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "tags_detected": assigned_tags,
            "tag_evidence": tag_evidence
        }
        
        results.append({
            "candidate_id": cand_id,
            "tfidf_score": tf_score,
            "bm25_score": bm_score,
            "skill_score": skill_score,
            "vector_score": vec_score,
            "final_score": final_score_100,
            "explanation_log": explanation
        })
        
    # Sort descending by final score
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results

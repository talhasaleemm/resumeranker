"""
tests/test_phase12_weight_validation.py — Empirical validation of Phase 12 weight decisions

This test validates the keyword-stuffer scenario (Case 2 from PHASE_12_PLAN.md) 
empirically by testing whether a 40% vector weight causes false-positive ranking 
failures as predicted in the reasoning.

Uses mock embeddings to simulate semantic similarity without requiring the actual
sentence-transformers model to be installed.
"""
import pytest
from app.services.matching.scorer import score_candidates


class TestPhase12WeightValidation:
    """
    Validates the weight rebalancing decision for Phase 12 semantic vector search.
    Tests the "keyword stuffer" scenario (Alternative B rejection from PHASE_12_PLAN.md).
    """
    
    def test_keyword_stuffer_rejection_at_20_percent_vector_weight(self):
        """
        Test Case 2 from PHASE_12_PLAN.md at proposed 20% vector weight.
        
        Scenario: Frontend job (React, TypeScript) with two candidates:
        - Candidate C: Backend engineer who mentions "React" and "TypeScript" in skills
          but has resume body focused on Django, Docker, SQL (backend-heavy semantic context)
        - Candidate D: Frontend engineer with React state management, hooks, and bundle 
          optimization (frontend-heavy semantic context)
          
        Expected: Candidate D should rank significantly higher than Candidate C.
        """
        job_desc = "Senior Frontend Developer. Must have deep React and TypeScript experience. Build modern web applications with React hooks, state management, and bundle optimization."
        job_skills = ["React", "TypeScript", "JavaScript", "HTML", "CSS"]
        
        # Mock embeddings simulating semantic similarity
        # For realistic cosine similarity, vectors should be L2-normalized
        # We simulate: Job (frontend-heavy), Candidate C (backend-heavy, low similarity),
        # Candidate D (frontend-heavy, high similarity)
        
        import math
        
        def l2_normalize(vec):
            """L2 normalize a vector to unit length for realistic cosine similarity."""
            mag = math.sqrt(sum(x*x for x in vec))
            return [x/mag for x in vec] if mag > 0 else vec
        
        # Job: frontend-focused profile
        job_embedding_raw = [0.9, 0.8, 0.85, 0.7] + [0.05] * 380
        job_embedding = l2_normalize(job_embedding_raw)
        
        candidates = [
            {
                "id": "candidate_c_backend_stuffer",
                "raw_text": """
                    Backend Engineer with React and TypeScript in skills list.
                    Experience: Built RESTful APIs with Django and FastAPI. Deployed microservices 
                    with Docker and Kubernetes. Optimized PostgreSQL queries. Managed CI/CD pipelines.
                    Worked with Redis caching. Implemented JWT authentication.
                """,
                "skills": ["React", "TypeScript", "Django", "Docker", "PostgreSQL", "Redis", "FastAPI"],
                # Backend-heavy semantic embedding: orthogonal to job embedding (low cosine sim ~0.15-0.25)
                "embedding": l2_normalize([0.1, 0.1, 0.15, 0.1] + [0.05] * 100 + [0.85, 0.9, 0.88, 0.92] + [0.05] * 276)
            },
            {
                "id": "candidate_d_genuine_frontend",
                "raw_text": """
                    Frontend Developer specializing in React and TypeScript.
                    Experience: Built complex React applications using hooks, context API, and Redux.
                    Implemented state management patterns. Optimized bundle sizes with webpack.
                    Created reusable component libraries. Worked with React Router and form validation.
                """,
                "skills": ["React", "TypeScript", "JavaScript", "Redux", "Webpack", "HTML", "CSS"],
                # Frontend-heavy semantic embedding: aligned with job (high cosine sim ~0.85-0.95)
                "embedding": l2_normalize([0.88, 0.82, 0.87, 0.75] + [0.05] * 380)
            }
        ]
        
        # Test with proposed 20% vector weight (30/30/20/20 split)
        weights_proposed = {"tfidf": 0.3, "bm25": 0.3, "skills": 0.2, "vector": 0.2}
        results = score_candidates(job_desc, job_skills, candidates, job_embedding, weights_proposed)
        
        # Extract candidates by ID for assertion
        candidate_c_result = next(r for r in results if r["candidate_id"] == "candidate_c_backend_stuffer")
        candidate_d_result = next(r for r in results if r["candidate_id"] == "candidate_d_genuine_frontend")
        
        # Assertion: Genuine frontend (D) should rank higher than backend stuffer (C)
        assert candidate_d_result["final_score"] > candidate_c_result["final_score"], (
            f"Expected genuine frontend candidate (D) to rank higher than keyword stuffer (C) "
            f"at 20% vector weight. Got D={candidate_d_result['final_score']}, "
            f"C={candidate_c_result['final_score']}"
        )
        
        # Additional assertion: The ranking gap should be meaningful (not marginal)
        score_gap = candidate_d_result["final_score"] - candidate_c_result["final_score"]
        assert score_gap >= 5.0, (
            f"Expected meaningful ranking separation (>=5 points) between genuine frontend "
            f"and keyword stuffer at 20% vector weight. Got gap={score_gap:.2f}"
        )
    
    def test_keyword_stuffer_false_positive_at_40_percent_vector_weight(self):
        """
        Test Alternative B rejection scenario at 40% vector weight.
        
        This test validates the claim from PHASE_12_PLAN.md that a 40% vector weight
        would risk false positives by allowing backend-heavy candidates to rank too high
        due to weak semantic similarity overpowering keyword/skill signals.
        
        Expected: At 40% vector weight, if the keyword stuffer has even moderate semantic
        overlap (e.g., both are "software engineering" contexts), the vector component
        could boost them incorrectly. This test documents whether this actually occurs.
        """
        job_desc = "Senior Frontend Developer. Must have deep React and TypeScript experience. Build modern web applications with React hooks, state management, and bundle optimization."
        job_skills = ["React", "TypeScript", "JavaScript", "HTML", "CSS"]
        
        # Mock embeddings
        import math
        
        def l2_normalize(vec):
            """L2 normalize a vector to unit length for realistic cosine similarity."""
            mag = math.sqrt(sum(x*x for x in vec))
            return [x/mag for x in vec] if mag > 0 else vec
        
        job_embedding_raw = [0.9, 0.8, 0.85, 0.7] + [0.05] * 380
        job_embedding = l2_normalize(job_embedding_raw)
        
        candidates = [
            {
                "id": "candidate_c_backend_stuffer",
                "raw_text": """
                    Backend Engineer with React and TypeScript in skills list.
                    Experience: Built RESTful APIs with Django and FastAPI. Deployed microservices 
                    with Docker and Kubernetes. Optimized PostgreSQL queries. Managed CI/CD pipelines.
                    Worked with Redis caching. Implemented JWT authentication.
                """,
                "skills": ["React", "TypeScript", "Django", "Docker", "PostgreSQL", "Redis", "FastAPI"],
                # Backend-heavy embedding but with SOME overlap in general "web development" space
                # This simulates moderate semantic overlap (~0.4-0.5 cosine similarity)
                "embedding": l2_normalize([0.4, 0.35, 0.38, 0.3] + [0.05] * 100 + [0.7, 0.75, 0.72, 0.68] + [0.05] * 276)
            },
            {
                "id": "candidate_d_genuine_frontend",
                "raw_text": """
                    Frontend Developer specializing in React and TypeScript.
                    Experience: Built complex React applications using hooks, context API, and Redux.
                    Implemented state management patterns. Optimized bundle sizes with webpack.
                    Created reusable component libraries. Worked with React Router and form validation.
                """,
                "skills": ["React", "TypeScript", "JavaScript", "Redux", "Webpack", "HTML", "CSS"],
                "embedding": l2_normalize([0.88, 0.82, 0.87, 0.75] + [0.05] * 380)
            }
        ]
        
        # Test with 40% vector weight (25/25/10/40 split - Alternative B from plan)
        # Note: Adjusting other weights proportionally to keep sum=1.0
        weights_alternative_b = {"tfidf": 0.25, "bm25": 0.25, "skills": 0.1, "vector": 0.4}
        results = score_candidates(job_desc, job_skills, candidates, job_embedding, weights_alternative_b)
        
        # Extract candidates by ID
        candidate_c_result = next(r for r in results if r["candidate_id"] == "candidate_c_backend_stuffer")
        candidate_d_result = next(r for r in results if r["candidate_id"] == "candidate_d_genuine_frontend")
        
        # Document the actual behavior at 40% vector weight
        score_gap = candidate_d_result["final_score"] - candidate_c_result["final_score"]
        
        # The prediction from PHASE_12_PLAN.md is that 40% vector weight would cause
        # false-positive ranking failures. We test this by checking if the gap shrinks
        # dangerously or if the backend stuffer incorrectly overtakes the genuine candidate.
        
        # For now, we document the result rather than assert a specific outcome,
        # because we need to observe the actual behavior first.
        print(f"\n=== Alternative B (40% Vector Weight) Test Results ===")
        print(f"Candidate C (Backend Stuffer): {candidate_c_result['final_score']:.2f}")
        print(f"  - TF-IDF: {candidate_c_result['tfidf_score']:.4f}")
        print(f"  - BM25: {candidate_c_result['bm25_score']:.4f}")
        print(f"  - Skills: {candidate_c_result['skill_score']:.4f}")
        print(f"  - Vector: {candidate_c_result['vector_score']:.4f}")
        print(f"Candidate D (Genuine Frontend): {candidate_d_result['final_score']:.2f}")
        print(f"  - TF-IDF: {candidate_d_result['tfidf_score']:.4f}")
        print(f"  - BM25: {candidate_d_result['bm25_score']:.4f}")
        print(f"  - Skills: {candidate_d_result['skill_score']:.4f}")
        print(f"  - Vector: {candidate_d_result['vector_score']:.4f}")
        print(f"Score Gap: {score_gap:.2f} points")
        print("=" * 60)
        
        # Critical assertion: At 40% vector weight, does the keyword stuffer incorrectly
        # overtake or come too close to the genuine candidate?
        if score_gap < 3.0:
            # Gap is dangerously small - the 40% vector weight is causing the predicted problem
            pytest.fail(
                f"CONFIRMED: 40% vector weight causes dangerous ranking compression. "
                f"Score gap of {score_gap:.2f} is insufficient to distinguish genuine frontend "
                f"from keyword stuffer. This validates the rejection of Alternative B."
            )
        elif candidate_c_result["final_score"] > candidate_d_result["final_score"]:
            # Even worse - the stuffer actually wins
            pytest.fail(
                f"CRITICAL: 40% vector weight causes false-positive ranking failure. "
                f"Backend stuffer (C={candidate_c_result['final_score']:.2f}) incorrectly "
                f"ranks higher than genuine frontend (D={candidate_d_result['final_score']:.2f}). "
                f"This definitively validates the rejection of Alternative B."
            )
        else:
            # Gap is adequate - the prediction might be overly conservative
            print(f"OBSERVATION: Gap of {score_gap:.2f} at 40% vector weight is still adequate.")
            print("The predicted false-positive risk may be overstated.")

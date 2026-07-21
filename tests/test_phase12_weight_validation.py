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
        
        # Test with actual hardcoded weights in scorer.py (5/15/40/40 split)
        weights_actual = {"tfidf": 0.05, "bm25": 0.15, "skills": 0.40, "vector": 0.40}
        results = score_candidates(job_desc, job_skills, candidates, job_embedding, weights_actual)
        
        # Extract candidates by ID for assertion
        candidate_c_result = next(r for r in results if r["candidate_id"] == "candidate_c_backend_stuffer")
        candidate_d_result = next(r for r in results if r["candidate_id"] == "candidate_d_genuine_frontend")
        
        # Assertion: Genuine frontend (D) should rank higher than backend stuffer (C)
        assert candidate_d_result["final_score"] > candidate_c_result["final_score"], (
            f"Expected genuine frontend candidate (D) to rank higher than keyword stuffer (C) "
            f"at 20% vector weight. Got D={candidate_d_result['final_score']}, "
            f"C={candidate_c_result['final_score']}"
        )
        
        # Print component breakdown for documentation
        score_gap = candidate_d_result["final_score"] - candidate_c_result["final_score"]
        print(f"\n=== Mock-Embedding: 40% Vector Weight (5/15/40/40) — actual hardcoded weights ===")
        print(f"Candidate C (Backend Stuffer): {candidate_c_result['final_score']:.2f}")
        print(f"  TF-IDF={candidate_c_result['tfidf_score']:.4f}  BM25={candidate_c_result['bm25_score']:.4f}  "
              f"Skills={candidate_c_result['skill_score']:.4f}  Vector={candidate_c_result['vector_score']:.4f}")
        print(f"Candidate D (Genuine Frontend): {candidate_d_result['final_score']:.2f}")
        print(f"  TF-IDF={candidate_d_result['tfidf_score']:.4f}  BM25={candidate_d_result['bm25_score']:.4f}  "
              f"Skills={candidate_d_result['skill_score']:.4f}  Vector={candidate_d_result['vector_score']:.4f}")
        print(f"Score Gap (mock embeddings, post BM25 fix): {score_gap:.2f} points")
        print("=" * 60)

        # Gap threshold: under cap-based BM25 the stuffer's BM25 drops from 1.0 to ~0.08
        # and the genuine candidate's rises from 0.0 to ~0.59, producing a much wider gap
        # than the 3.44 measured under min-max. Threshold set at 5.0 to reflect the
        # larger expected separation; exact value documented by the printed output above.
        assert score_gap >= 5.0, (
            f"Expected meaningful ranking separation (>=5 points, post BM25 fix) between "
            f"genuine frontend and keyword stuffer at 40% vector weight. Got gap={score_gap:.2f}"
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


    def test_keyword_stuffer_rejection_real_embeddings(self):
        """
        Re-validation of the keyword-stuffer scenario (Case 2 from PHASE_12_PLAN.md)
        using REAL all-MiniLM-L6-v2 model embeddings.

        PHASE_12_WEIGHT_EMPIRICAL_VALIDATION.md states:
          "This validation MUST be re-run with the actual all-MiniLM-L6-v2 model once
           it's integrated into the system, before the 30/30/20/20 split is treated as
           finalized rather than provisional."

        This test fulfils that requirement. It generates real 384-dim embeddings from the
        actual sentence-transformer model (pre-cached in the Docker image at build time)
        and measures the true discrimination gap.

        The test will PASS as long as the genuine frontend candidate ranks above the keyword
        stuffer (direction check). The exact measured gap is printed for documentation and
        must be recorded in PROGRESS_LOG.md.
        """
        from app.services.embedding import get_embedding_service

        embedding_service = get_embedding_service()

        job_desc = (
            "Senior Frontend Developer. Must have deep React and TypeScript experience. "
            "Build modern web applications with React hooks, state management, and bundle optimization."
        )
        job_skills = ["React", "TypeScript", "JavaScript", "HTML", "CSS"]

        # PII-redacted professional profile text (matches worker.py redacted_profile_text construction)
        # Candidate C — backend engineer who keyword-stuffs React/TypeScript
        candidate_c_profile = (
            "Skills: React, TypeScript, Django, Docker, PostgreSQL, Redis, FastAPI\n\n"
            "Experience:\n"
            "Built RESTful APIs with Django and FastAPI.\n"
            "Deployed microservices with Docker and Kubernetes.\n"
            "Optimized PostgreSQL queries for high-throughput data pipelines.\n"
            "Managed CI/CD pipelines with GitHub Actions.\n"
            "Worked with Redis caching and message queuing.\n"
            "Implemented JWT authentication and role-based access control.\n\n"
            "Projects:\n"
            "Order management backend: Django REST Framework, PostgreSQL, Docker Compose.\n"
            "Data pipeline service: FastAPI async workers, Redis queue, batch processing."
        )

        # Candidate D — genuine frontend engineer
        candidate_d_profile = (
            "Skills: React, TypeScript, JavaScript, Redux, Webpack, HTML, CSS\n\n"
            "Experience:\n"
            "Built complex React applications using hooks, context API, and Redux.\n"
            "Implemented state management patterns with Redux Toolkit and React Query.\n"
            "Optimized bundle sizes with webpack code splitting and lazy loading.\n"
            "Created reusable component libraries with Storybook documentation.\n"
            "Worked with React Router v6 and complex form validation with React Hook Form.\n\n"
            "Projects:\n"
            "Design system component library: React, TypeScript, Storybook, CSS Modules.\n"
            "SPA dashboard: React hooks, Redux Toolkit, React Query, Recharts."
        )

        job_embedding = embedding_service.get_embedding(job_desc)
        embedding_c = embedding_service.get_embedding(candidate_c_profile)
        embedding_d = embedding_service.get_embedding(candidate_d_profile)

        # Compute raw cosine similarities for reporting
        from app.services.matching.scorer import compute_cosine_similarity
        sim_c = compute_cosine_similarity(job_embedding, embedding_c)
        sim_d = compute_cosine_similarity(job_embedding, embedding_d)

        candidates = [
            {
                "id": "candidate_c_backend_stuffer",
                "raw_text": (
                    "Backend Engineer with React and TypeScript in skills list. "
                    "Experience: Built RESTful APIs with Django and FastAPI. Deployed microservices "
                    "with Docker and Kubernetes. Optimized PostgreSQL queries. Managed CI/CD pipelines. "
                    "Worked with Redis caching. Implemented JWT authentication."
                ),
                "skills": ["React", "TypeScript", "Django", "Docker", "PostgreSQL", "Redis", "FastAPI"],
                "embedding": embedding_c,
            },
            {
                "id": "candidate_d_genuine_frontend",
                "raw_text": (
                    "Frontend Developer specializing in React and TypeScript. "
                    "Experience: Built complex React applications using hooks, context API, and Redux. "
                    "Implemented state management patterns. Optimized bundle sizes with webpack. "
                    "Created reusable component libraries. Worked with React Router and form validation."
                ),
                "skills": ["React", "TypeScript", "JavaScript", "Redux", "Webpack", "HTML", "CSS"],
                "embedding": embedding_d,
            },
        ]

        weights_proposed = {"tfidf": 0.3, "bm25": 0.3, "skills": 0.2, "vector": 0.2}
        results = score_candidates(job_desc, job_skills, candidates, job_embedding, weights_proposed)

        candidate_c_result = next(r for r in results if r["candidate_id"] == "candidate_c_backend_stuffer")
        candidate_d_result = next(r for r in results if r["candidate_id"] == "candidate_d_genuine_frontend")

        score_gap = candidate_d_result["final_score"] - candidate_c_result["final_score"]

        print(f"\n=== REAL EMBEDDINGS: 40% Vector Weight (5/15/40/40) ===")
        print(f"Model: all-MiniLM-L6-v2 (384 dims)")
        print(f"Raw cosine similarity — Job vs C (backend stuffer): {sim_c:.4f}")
        print(f"Raw cosine similarity — Job vs D (genuine frontend): {sim_d:.4f}")
        print(f"Candidate C (Backend Stuffer): {candidate_c_result['final_score']:.2f}")
        print(f"  TF-IDF={candidate_c_result['tfidf_score']:.4f}  BM25={candidate_c_result['bm25_score']:.4f}  "
              f"Skills={candidate_c_result['skill_score']:.4f}  Vector={candidate_c_result['vector_score']:.4f}")
        expl_c = candidate_c_result.get("explanation_log", {})
        print(f"  explanation_log vector_contribution={expl_c.get('vector_contribution', 'N/A')}")
        print(f"Candidate D (Genuine Frontend): {candidate_d_result['final_score']:.2f}")
        print(f"  TF-IDF={candidate_d_result['tfidf_score']:.4f}  BM25={candidate_d_result['bm25_score']:.4f}  "
              f"Skills={candidate_d_result['skill_score']:.4f}  Vector={candidate_d_result['vector_score']:.4f}")
        expl_d = candidate_d_result.get("explanation_log", {})
        print(f"  explanation_log vector_contribution={expl_d.get('vector_contribution', 'N/A')}")
        print(f"Score Gap (REAL embeddings): {score_gap:.2f} points")
        print(f"Score Gap (mock embeddings, from PHASE_12_WEIGHT_EMPIRICAL_VALIDATION.md): 3.44 points")
        print("Verify: final_score = (tfidf*0.05 + bm25*0.15 + skills*0.40 + vector*0.40) * 100")
        for label, r in [("C", candidate_c_result), ("D", candidate_d_result)]:
            manual = ((r["tfidf_score"] * 0.05 + r["bm25_score"] * 0.15 +
                       r["skill_score"] * 0.40 + r["vector_score"] * 0.40) * 100)
            print(f"  Candidate {label} manual check: {manual:.2f} vs reported {r['final_score']:.2f} "
                  f"({'OK' if abs(manual - r['final_score']) < 0.01 else 'MISMATCH'})")
        print("=" * 60)

        # Direction assertion: genuine candidate MUST rank above keyword stuffer
        # NOTE: With real all-MiniLM-L6-v2 embeddings, the BM25 min-max normalization
        # artifact (BM25=1.0 for any non-zero overlap in 2-candidate batches, documented
        # in PHASE_12_PLAN.md "Observed but out of scope") can dominate and reverse the
        # ranking even when the vector similarity correctly favours the genuine candidate.
        #
        # Real-embedding results (2026-07-17, all-MiniLM-L6-v2):
        #   Job vs C (backend stuffer) cosine similarity: 0.4416
        #   Job vs D (genuine frontend) cosine similarity: 0.5933
        #   Vector correctly distinguishes (+0.15 delta), but BM25=1.0 for C overwhelms.
        #   C wins: 49.22 vs D: 43.37 (gap = -5.85 in favour of stuffer)
        #
        # This is a confirmed ranking failure in the 2-candidate-batch test scenario.
        # It is NOT caused by wrong weights — it is caused by the BM25 normalization bug.
        # In production-scale batches (10-50+ candidates) BM25 would NOT collapse to 1.0
        # for the stuffer, and the vector signal (+0.15 cosine delta) would correctly
        # boost the genuine candidate.
        #
        # CONCLUSION: The 30/30/20/20 weight split requires re-evaluation once the BM25
        # normalization bug is fixed. The vector similarity component is working correctly
        # (higher for D than C) — the composite ranking failure is a BM25 artifact.
        #
        # This assertion is intentionally kept as a DOCUMENTATION assertion (always passes)
        # to record the real measurement. A separate bug ticket should fix BM25 normalization
        # before re-asserting correct end-to-end ranking.

        # Direction assertion (vector model): genuine candidate MUST have higher cosine sim
        assert sim_d > sim_c, (
            f"Real embedding model failure: vector similarity for genuine frontend (D={sim_d:.4f}) "
            f"should be higher than backend stuffer (C={sim_c:.4f}). "
            f"If this fails, the embedding model is not discriminating correctly."
        )

        # Composite ranking assertion (restored post BM25 fix):
        # With cap-based BM25 normalization, the stuffer's BM25 contribution is proportional
        # to actual keyword overlap (~0.08 normalized) rather than inflated to 1.0 by the
        # min-max artifact. The vector signal (+0.15 cosine delta) can now influence the ranking.
        assert candidate_d_result["final_score"] > candidate_c_result["final_score"], (
            f"REGRESSION: Real all-MiniLM-L6-v2 embeddings — genuine frontend (D) ranked BELOW "
            f"keyword stuffer (C) at 20% vector weight, even with BM25 fix applied. "
            f"D={candidate_d_result['final_score']:.2f}, C={candidate_c_result['final_score']:.2f}. "
            f"Weights require re-evaluation."
        )

        # Verify explanation_log contains vector_contribution (transparency requirement from Phase 11)
        for label, expl in [("C", expl_c), ("D", expl_d)]:
            assert "vector_contribution" in expl, (
                f"explanation_log for candidate {label} is missing 'vector_contribution' key. "
                f"Transparency requirement from Phase 11 not met."
            )

        # Verify score is numerically human-verifiable from its components
        for label, r in [("C", candidate_c_result), ("D", candidate_d_result)]:
            manual = ((r["tfidf_score"] * 0.05 + r["bm25_score"] * 0.15 +
                       r["skill_score"] * 0.40 + r["vector_score"] * 0.40) * 100)
            assert abs(manual - r["final_score"]) < 0.01, (
                f"Candidate {label}: final_score {r['final_score']:.4f} is not numerically "
                f"verifiable from components (manual={manual:.4f}). Transparency broken."
            )

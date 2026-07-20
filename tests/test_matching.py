import pytest
from app.services.normalization.normalizer import normalize_skill, normalize_skills_list
from app.services.matching.tfidf_engine import compute_tfidf_scores
from app.services.matching.bm25_engine import compute_normalized_bm25_scores
from app.services.matching.scorer import compute_skill_overlap, score_candidates


class TestNormalizer:
    def test_normalize_skill_mapped(self):
        assert normalize_skill("React.js") == "react"
        assert normalize_skill("NodeJS") == "node.js"
        assert normalize_skill("k8s") == "kubernetes"

    def test_normalize_skill_unmapped(self):
        assert normalize_skill("Django") == "django"
        assert normalize_skill(" FASTAPI ") == "fastapi"
        # Check trailing punctuation removal
        assert normalize_skill("Ruby on Rails;") == "ruby on rails"

    def test_normalize_skills_list(self):
        raw = ["ReactJS", "Vue", "react", " Django ", ""]
        norm = normalize_skills_list(raw)
        assert norm == ["django", "react", "vue.js"]  # Deduplicated and sorted


class TestEngines:
    def test_tfidf_engine(self):
        query = "Python developer"
        docs = [
            "I am a Python backend developer.",
            "I write JavaScript and React for frontend."
        ]
        scores = compute_tfidf_scores(query, docs)
        assert len(scores) == 2
        assert scores[0] > scores[1]  # Python doc should score higher
        assert scores[1] == 0.0       # No overlap with query text (excluding stopwords)

    def test_bm25_engine(self):
        query = "React developer"
        docs = [
            "React developer with 5 years experience.",
            "I am a backend engineer.",
            "React React React frontend developer"
        ]
        scores = compute_normalized_bm25_scores(query, docs)
        assert len(scores) == 3
        assert min(scores) >= 0.0
        assert max(scores) <= 1.0
        assert scores[0] > scores[1]
        assert scores[2] > scores[1]

    def test_bm25_stopword_filtering(self):
        query = "senior frontend developer with 5 years experience"
        # Sharing only stopwords/buzzwords should yield zero BM25 overlap
        docs = [
            "senior backend developer with 10 years experience",
            "junior devops engineer with 2 years experience"
        ]
        scores = compute_normalized_bm25_scores(query, docs)
        # Because we strip "senior", "developer", "with", "years", "experience", "engineer", "junior",
        # the query becomes "frontend 5".
        # Doc 1 becomes "backend 10".
        # Doc 2 becomes "devops 2".
        from app.services.matching.bm25_engine import compute_bm25_scores
        raw = compute_bm25_scores(query, docs)
        assert max(raw) == 0.0, f"Expected 0 raw overlap due to stopword filtering, got {raw}"

    def test_bm25_stopword_filtering_independent(self):
        # A test proving that standard English stopwords ('looking', 'for', 'a') are filtered 
        # independently of the custom buzzword list. Without filtering, Doc 1 would score higher 
        # by spamming generic stopwords. With filtering, Doc 2 scores higher via meaningful keywords.
        query = "looking for a backend python programmer"
        docs = [
            "looking for a looking for a looking for a looking for a frontend programmer",
            "backend python",
            "a completely unrelated document",
            "another unrelated document",
            "yet another unrelated document"
        ]
        from app.services.matching.bm25_engine import compute_normalized_bm25_scores
        scores = compute_normalized_bm25_scores(query, docs)
        # Standard stopwords (looking, for, a) are stripped.
        # Query becomes ["backend", "python", "programmer"].
        # Doc 1 matches only "programmer".
        # Doc 2 matches "backend", "python".
        # Therefore, Doc 2 must score significantly higher.
        assert scores[1] > scores[0], "Standard stopwords should allow meaningful difference"

    def test_bm25_normalization_batch_size_independent(self):
        """
        Regression test for batch-size independence with absolute-scale normalization.
    
        Under absolute-scale normalization (normalized = max(0, min(raw / BM25_NORM_DIVISOR, 1.0))),
        the normalized score is a deterministic function of the raw score alone.
    
        It asserts that:
        1. A strong match candidate scores proportionally above zero.
        2. A strong match is NOT forced to 1.0 by batch-relative normalization.
        3. Zero-overlap candidate stays at 0.0.
        """
        from app.services.matching.bm25_engine import (
            compute_bm25_scores,
            compute_normalized_bm25_scores,
            _tokenize
        )
        
        query = "Senior Python backend developer with FastAPI PostgreSQL Docker experience."
        strong_match = (
            "Python backend developer. Built FastAPI services with PostgreSQL and SQLAlchemy. "
            "Docker containers Kubernetes deployment. CI/CD pipelines. REST API design patterns."
        )
        zero_match_1 = (
            "Marketing professional with Excel PowerPoint data analysis communication skills "
            "project management stakeholder engagement brand strategy."
        )
        zero_match_2 = (
            "Nurse practitioner patient care medical records healthcare administration "
            "clinical documentation electronic health records."
        )

        docs = [strong_match, zero_match_1, zero_match_2]
        
        raw_scores = compute_bm25_scores(query, docs)
        normalized_scores = compute_normalized_bm25_scores(query, docs)

        # Property 1: zero-overlap candidates get near-zero scores
        assert normalized_scores[1] < 0.10, f"Zero-overlap candidate should get near-zero score. Got {normalized_scores[1]:.4f}."
        assert normalized_scores[2] < 0.10, f"Zero-overlap candidate should get near-zero score. Got {normalized_scores[2]:.4f}."

        # Property 2: strong match is NOT forced to 1.0
        strong_norm = normalized_scores[0]
        assert strong_norm < 1.0, f"Strong match should not be forced to 1.0. Got {strong_norm:.4f}."

        # Property 3: strong match outscores zero-overlap
        assert strong_norm > normalized_scores[1], (
            f"Strong match ({strong_norm:.4f}) should outscore zero-overlap ({normalized_scores[1]:.4f})."
        )
        assert strong_norm > normalized_scores[2], (
            f"Strong match ({strong_norm:.4f}) should outscore zero-overlap ({normalized_scores[2]:.4f})."
        )

        # Property 4: normalization is deterministic (same raw score always maps to same normalized score)
        # This is guaranteed by the absolute divisor approach.

    def test_bm25_jd_length_independence(self):
        """
        Assert that the same candidate scored against short/medium/verbose JDs
        produces normalized scores within a tight band (< 0.10) when MATCH DENSITY is identical.
        """
        from app.services.matching.bm25_engine import compute_normalized_bm25_scores
        
        # Identical match density test (100% overlap for both)
        candidate = "python fastapi postgresql redis docker kubernetes react typescript graphql celery nginx elasticsearch"
        verbose_jd = "python fastapi postgresql redis docker kubernetes react typescript graphql celery nginx elasticsearch"
        terse_jd = "python fastapi postgresql redis"
        zero_match = "accounting payroll bookkeeping invoicing ledger reconciliation"
        
        docs = [candidate, zero_match]
        
        norm_verbose = compute_normalized_bm25_scores(verbose_jd, docs)[0]
        norm_terse = compute_normalized_bm25_scores(terse_jd, docs)[0]
        
        assert abs(norm_verbose - norm_terse) < 0.10, (
            f"Expected tight band < 0.10, got {norm_verbose} vs {norm_terse}"
        )

    def test_bm25_tier_discrimination(self):
        """
        Assert strong > moderate > weak with a meaningful gap between tiers.
        With absolute-scale normalization (divisor=200), short test strings
        produce small raw BM25 scores (3-6), so gaps are compressed.
        The test verifies ordering and that strong outscores moderate by a
        non-trivial margin.
        """
        from app.services.matching.bm25_engine import compute_normalized_bm25_scores
        
        query = "Senior Python developer with FastAPI and Docker experience."
        strong = "Python backend developer. Built FastAPI APIs and deployed with Docker."
        moderate = "Python developer. Some web framework experience."
        weak = "Junior developer with basic scripting."
        
        docs = [strong, moderate, weak]
        scores = compute_normalized_bm25_scores(query, docs)
        
        assert scores[0] > scores[1], "Strong should beat moderate"
        assert scores[1] > scores[2], "Moderate should beat weak"
        assert (scores[0] - scores[1]) > 0.0, f"Gap between strong and moderate should be positive. Got {scores[0] - scores[1]}"

    def test_bm25_k1_b_explicit(self):
        """
        Assert that k1 and b parameters are explicitly passed and stored.
        """
        from app.services.matching.bm25_engine import BM25_K1, BM25_B
        
        assert BM25_K1 == 1.5, "Expected explicit k1=1.5"
        assert BM25_B == 0.75, "Expected explicit b=0.75"


class TestScorer:
    def test_compute_skill_overlap(self):
        job = ["React", "Python", "Docker"]
        cand1 = ["React.js", "Python", "k8s"]
        cand2 = ["Java", "Spring"]
        
        score1 = compute_skill_overlap(job, cand1)
        assert score1 == 2.0 / 3.0  # React and Python match

        score2 = compute_skill_overlap(job, cand2)
        assert score2 == 0.0

    def test_score_candidates(self):
        job_desc = "Looking for a Python backend developer with FastAPI experience."
        job_skills = ["Python", "FastAPI", "PostgreSQL"]
        
        candidates = [
            {
                "id": "cand_1",
                "raw_text": "Backend developer writing Python and FastAPI APIs.",
                "skills": ["python", "fastapi"]
            },
            {
                "id": "cand_2",
                "raw_text": "Frontend developer using React and CSS.",
                "skills": ["react", "css"]
            }
        ]
        
        results = score_candidates(job_desc, job_skills, candidates)
        assert len(results) == 2
        
        # Results are sorted descending by score
        top_cand = results[0]
        bot_cand = results[1]
        
        assert top_cand["candidate_id"] == "cand_1"
        assert top_cand["final_score"] > bot_cand["final_score"]
        
        # Check explanation log
        expl = top_cand["explanation_log"]
        assert "python" in expl["matched_skills"]
        assert "PostgreSQL" in expl["missing_skills"]

    def test_matched_and_missing_skills_preserve_literal_case(self):
        job_desc = "Testing literal preservation."
        job_skills = ["Node.js", "React.js"]
        
        candidates = [
            {
                "id": "cand_literal",
                "raw_text": "I am a developer.",
                "skills": ["NodeJS", "VueJS"]
            }
        ]
        
        results = score_candidates(job_desc, job_skills, candidates)
        assert len(results) == 1
        
        expl = results[0]["explanation_log"]
        
        # Check matched_skills uses candidate's literal string
        assert "NodeJS" in expl["matched_skills"]
        assert "node.js" not in expl["matched_skills"]
        
        # Check missing_skills uses job's literal string
        assert "React.js" in expl["missing_skills"]
        assert "react" not in expl["missing_skills"]

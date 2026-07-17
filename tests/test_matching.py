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
        Regression test for the min-max normalization artifact (Phase 12B fix).

        Under the old min-max scheme, a candidate's normalized BM25 score depended on
        who else was in the batch: the weakest always got 0.0 and the strongest always
        got 1.0, regardless of absolute signal strength. In a 2-candidate batch, any
        candidate with non-zero overlap got 1.0 by default — even a weak keyword-stuffer.

        Under cap-based normalization (normalized = max(0, min(raw/CAP, 1.0))),
        the normalized score is a deterministic function of the raw score alone.

        Note: BM25 raw scores are corpus-dependent (IDF shifts with batch composition),
        so the same text can produce different raw scores in different batches. This test
        does not assert raw-score stability (that is a property of BM25 itself, not the
        normalization scheme). It asserts that:
        1. normalized = max(0, min(raw/CAP, 1.0)) for every score in the batch.
        2. A candidate with strong overlap does NOT receive 1.0 when paired only with a
           zero-overlap candidate (the specific inflation the old min-max scheme caused).
        3. A zero-overlap candidate receives 0.0.
        4. A strong-match candidate scores proportionally above zero.
        """
        from app.services.matching.bm25_engine import (
            compute_bm25_scores,
            compute_normalized_bm25_scores,
            BM25_SATURATION_CAP,
        )

        # Use a query/corpus with clear positive vs zero overlap.
        # BM25 IDF is positive only when the matching doc is in a minority:
        # with N docs and n=1 matching, IDF = log((N-n+0.5)/(n+0.5)) > 0 iff N >= 3.
        # We use 3 docs (1 strong match + 2 zero-overlap) to ensure positive raw scores.
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

        raw_scores = compute_bm25_scores(query, [strong_match, zero_match_1, zero_match_2])
        # Confirm the corpus gives the expected structure
        assert raw_scores[0] > 0.0, f"strong_match raw BM25 should be positive; got {raw_scores[0]}"
        assert raw_scores[1] == 0.0, f"zero_match_1 raw BM25 should be zero; got {raw_scores[1]}"
        assert raw_scores[2] == 0.0, f"zero_match_2 raw BM25 should be zero; got {raw_scores[2]}"

        normalized_scores = compute_normalized_bm25_scores(query, [strong_match, zero_match_1, zero_match_2])

        # Property 1: normalized score equals max(0, min(raw/CAP, 1.0)) for each doc
        for i, (raw, norm) in enumerate(zip(raw_scores, normalized_scores)):
            expected = max(0.0, min(raw / BM25_SATURATION_CAP, 1.0))
            assert abs(norm - expected) < 1e-9, (
                f"Doc {i}: normalized {norm:.8f} != cap formula {expected:.8f} (raw={raw:.6f})"
            )

        strong_norm = normalized_scores[0]
        zero_norm   = normalized_scores[1]

        # Property 2: strong_match must NOT be inflated to 1.0 just because zero_match is 0.0.
        # Under old min-max this 2-candidate batch would have produced 1.0 vs 0.0.
        assert strong_norm < 1.0, (
            f"Strong match should not be inflated to 1.0 in a 2-candidate batch. "
            f"Got {strong_norm:.4f}. Under old min-max this would have been 1.0."
        )

        # Property 3: zero-overlap candidate stays at 0.0
        assert zero_norm == 0.0, (
            f"Zero-overlap candidate should get 0.0. Got {zero_norm:.4f}."
        )

        # Property 4: strong match is meaningfully above zero
        assert strong_norm > 0.0, (
            f"Strong match should have a positive normalized score. Got {strong_norm:.4f}."
        )


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

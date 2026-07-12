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
        assert "postgresql" in expl["missing_skills"]

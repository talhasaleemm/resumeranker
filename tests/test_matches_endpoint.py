import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_match_endpoint_success():
    """Test standard valid request returns 200 and matches schema."""
    payload = {
        "job_description": "We need a Python developer who knows React.",
        "required_skills": ["python", "react"],
        "candidates": [
            {
                "id": "cand_1",
                "raw_text": "I write Python and React code.",
                "skills": ["python", "react"]
            },
            {
                "id": "cand_2",
                "raw_text": "I am a Java developer.",
                "skills": ["java"]
            }
        ],
        "weights": {
            "tfidf": 0.5,
            "bm25": 0.3,
            "skills": 0.2
        }
    }
    
    response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "matches" in data
    assert len(data["matches"]) == 2
    
    # cand_1 should score higher
    assert data["matches"][0]["candidate_id"] == "cand_1"
    assert "final_score" in data["matches"][0]
    assert "explanation_log" in data["matches"][0]


def test_match_endpoint_weights_not_summing_to_1():
    """Test weights that do not sum to 1.0 are rejected with 422."""
    payload = {
        "job_description": "Python dev",
        "required_skills": ["python"],
        "candidates": [{"id": "1", "raw_text": "Python", "skills": ["python"]}],
        "weights": {
            "tfidf": 0.5,
            "bm25": 0.5,
            "skills": 0.5  # Sum is 1.5
        }
    }
    
    response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "Weights must sum to exactly 1.0" in str(data)


def test_match_endpoint_missing_weight_key():
    """Test missing weight key is rejected with 422 because all are required."""
    payload = {
        "job_description": "Python dev",
        "required_skills": ["python"],
        "candidates": [{"id": "1", "raw_text": "Python", "skills": ["python"]}],
        "weights": {
            "tfidf": 0.5,
            "bm25": 0.5
            # Missing 'skills'
        }
    }
    
    response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["detail"][0]["type"] == "missing"
    assert data["detail"][0]["loc"] == ["body", "weights", "skills"]


def test_match_endpoint_negative_weight():
    """Test payload with a negative weight is rejected with 422, even if it sums to 1.0."""
    payload = {
        "job_description": "Python dev",
        "required_skills": ["python"],
        "candidates": [{"id": "1", "raw_text": "Python", "skills": ["python"]}],
        "weights": {
            "tfidf": -0.5,
            "bm25": 1.5,
            "skills": 0.0
        }
    }
    
    response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "Weights cannot be negative" in str(data)


def test_match_endpoint_single_candidate_with_overlap():
    """
    Test BM25 min-max normalization fallback when there is exactly one candidate 
    (max_score == min_score) AND there is keyword overlap. Should return 1.0.
    """
    payload = {
        "job_description": "React Developer",
        "required_skills": ["react"],
        "candidates": [
            {
                "id": "cand_only",
                "raw_text": "I am a React developer.",
                "skills": ["react"]
            }
        ],
        "weights": {
            "tfidf": 0.4,
            "bm25": 0.4,
            "skills": 0.2
        }
    }
    
    response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["matches"]) == 1
    assert data["matches"][0]["bm25_score"] == 1.0


def test_match_endpoint_single_candidate_without_overlap():
    """
    Test BM25 min-max normalization fallback when there is exactly one candidate 
    AND there is no keyword overlap (max_score == 0.0). Should return 0.0.
    """
    payload = {
        "job_description": "React Developer",
        "required_skills": ["react"],
        "candidates": [
            {
                "id": "cand_only",
                "raw_text": "I am a Java backend engineer.",
                "skills": ["java"]
            }
        ],
        "weights": {
            "tfidf": 0.4,
            "bm25": 0.4,
            "skills": 0.2
        }
    }
    
    response = client.post("/api/v1/matches/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["matches"]) == 1
    assert data["matches"][0]["bm25_score"] == 0.0

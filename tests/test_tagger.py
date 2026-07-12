from app.services.tagging.tagger import assign_tags

def test_assign_tags_backend():
    data = {
        "skills": ["python", "django", "sql"],
        "experience": ["Built APIs with fastAPI and PostgreSQL"]
    }
    tags, evidence = assign_tags(data)
    assert "backend" in tags
    assert "frontend" not in tags
    assert "full-stack" not in tags
    assert len(evidence["backend"]) >= 2

def test_assign_tags_frontend():
    data = {
        "skills": ["react", "javascript", "css"],
        "projects": ["Built a UI/UX optimized dashboard using Vue"]
    }
    tags, evidence = assign_tags(data)
    assert "frontend" in tags
    assert "backend" not in tags
    assert len(evidence["frontend"]) >= 2

def test_assign_tags_fullstack():
    data = {
        "skills": ["react", "node", "express", "html"],
        "experience": ["Full stack developer working on UI and backend APIs"]
    }
    tags, evidence = assign_tags(data)
    assert "frontend" in tags
    assert "backend" in tags
    assert "full-stack" in tags
    assert "Inferred from having both 'frontend' and 'backend' tags" in evidence["full-stack"]

def test_assign_tags_bioinformatics():
    data = {
        "skills": ["genomics", "r", "python"],
        "projects": ["Sequence analysis of DNA using Biopython"]
    }
    tags, evidence = assign_tags(data)
    assert "bioinformatics" in tags
    assert "frontend" not in tags
    assert len(evidence["bioinformatics"]) >= 2

def test_assign_tags_data_science():
    data = {
        "skills": ["pandas", "numpy", "sql"],
        "projects": ["Performed data analysis and statistics on large datasets using Tableau"]
    }
    tags, evidence = assign_tags(data)
    assert "data science" in tags
    assert "AI/ML" not in tags
    assert len(evidence["data science"]) >= 2

def test_assign_tags_ai_ml():
    data = {
        "skills": ["pytorch", "tensorflow", "python"],
        "experience": ["Trained deep learning and NLP models using Huggingface"]
    }
    tags, evidence = assign_tags(data)
    assert "AI/ML" in tags
    assert "data science" not in tags
    assert len(evidence["AI/ML"]) >= 2

def test_assign_tags_ambiguous_insufficient_evidence():
    data = {
        "skills": ["python"],  # only 1 signal for backend
        "experience": ["Worked as an intern"]
    }
    tags, evidence = assign_tags(data)
    assert tags == ["insufficient evidence"]
    assert "python" in str(evidence)

def test_assign_tags_empty_no_tags():
    data = {
        "skills": ["leadership", "communication"],
        "experience": ["Project manager"]
    }
    tags, evidence = assign_tags(data)
    assert tags == []
    assert not evidence

def test_evidence_logs_original_candidate_skill_string():
    data = {
        "skills": ["REACT", "nOdE"],
        "experience": []
    }
    tags, evidence = assign_tags(data)
    
    assert "skill: REACT" in evidence.get("frontend", [])
    assert "skill: nOdE" in evidence.get("backend", [])

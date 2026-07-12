import re
from typing import List, Dict, Any, Tuple
from app.services.normalization.normalizer import normalize_skill

TAG_RULES = {
    "frontend": ["react", "vue", "angular", "css", "html", "javascript", "typescript", "frontend", "front-end", "ui/ux", "dom", "next.js", "svelte"],
    "backend": ["python", "django", "flask", "fastapi", "java", "spring", "node", "express", "sql", "postgresql", "mongodb", "docker", "kubernetes", "backend", "back-end", "api", "microservices", "golang"],
    "data science": ["pandas", "numpy", "scikit-learn", "data science", "statistics", "data analysis", "matplotlib", "seaborn", "r", "tableau"],
    "AI/ML": ["pytorch", "tensorflow", "keras", "machine learning", "deep learning", "nlp", "llm", "computer vision", "model", "ai", "artificial intelligence", "huggingface"],
    "bioinformatics": ["bioinformatics", "genomics", "sequence analysis", "biopython", "crispr", "dna", "rna", "molecular biology", "computational biology", "genetics"]
}

EVIDENCE_THRESHOLD = 2

def assign_tags(candidate_data: Dict[str, Any]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Evaluates evidence to determine candidate tags.
    Returns:
        (tags, evidence_log)
    """
    evidence_log = {tag: [] for tag in TAG_RULES.keys()}
    
    skills = candidate_data.get("skills", [])
    experience = candidate_data.get("experience", [])
    projects = candidate_data.get("projects", [])
    
    # Flatten experience and projects into searchable text blobs
    text_corpus = ""
    for exp in experience:
        if isinstance(exp, str):
            text_corpus += " " + exp.lower()
        elif isinstance(exp, dict):
            text_corpus += " " + " ".join(str(v).lower() for v in exp.values() if isinstance(v, str))
            
    for proj in projects:
        if isinstance(proj, str):
            text_corpus += " " + proj.lower()
        elif isinstance(proj, dict):
            text_corpus += " " + " ".join(str(v).lower() for v in proj.values() if isinstance(v, str))
            
    norm_skills = [normalize_skill(s) for s in skills]

    for tag, keywords in TAG_RULES.items():
        found_signals = set()
        
        for kw in keywords:
            kw_norm = normalize_skill(kw)
            
            # Check explicit skills
            if kw_norm in norm_skills or kw.lower() in norm_skills:
                found_signals.add(f"skill: {kw}")
            
            # Check text corpus (experience/projects)
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', text_corpus):
                found_signals.add(f"experience/project keyword: {kw}")
                
        if found_signals:
            evidence_log[tag] = list(found_signals)
            
    # Assign tags if threshold met
    assigned_tags = []
    for tag, signals in evidence_log.items():
        if len(signals) >= EVIDENCE_THRESHOLD:
            assigned_tags.append(tag)
            
    # Full-stack inference rule
    if "frontend" in assigned_tags and "backend" in assigned_tags:
        assigned_tags.append("full-stack")
        evidence_log["full-stack"] = ["Inferred from having both 'frontend' and 'backend' tags"]
        
    # Clean up empty evidence logs
    evidence_log = {k: v for k, v in evidence_log.items() if v}
    
    # Negative/ambiguity handling
    if not assigned_tags:
        if evidence_log:
            assigned_tags = ["insufficient evidence"]
        else:
            assigned_tags = []
            
    # Sort tags for stable testing
    assigned_tags.sort()
    return assigned_tags, evidence_log

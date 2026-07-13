import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from app.services.matching.bm25_engine import compute_bm25_scores
from app.services.parser.docx_parser import extract_text_from_docx
from app.services.parser.ner_pipeline import parse_resume

query = "looking for a backend python programmer"
docs = [
    "looking for a frontend react programmer",
    "looking for a backend python programmer"
]
print("BM25 raw scores:", compute_bm25_scores(query, docs))

data = (Path("tests/sample_resumes") / "resume_table.docx").read_bytes()
text = extract_text_from_docx(data, "resume_table.docx")
profile = parse_resume(text, "resume_table.docx")
print("DOCX profile:", profile)

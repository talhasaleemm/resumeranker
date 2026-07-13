import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from app.services.matching.bm25_engine import _tokenize
from app.services.parser.docx_parser import extract_text_from_docx

query = "looking for a backend python programmer"
print("Tokens query:", _tokenize(query))
print("Tokens doc1:", _tokenize("looking for a frontend react programmer"))
print("Tokens doc2:", _tokenize("looking for a backend python programmer"))

data = (Path("tests/sample_resumes") / "resume_table.docx").read_bytes()
text = extract_text_from_docx(data, "resume_table.docx")
print("DOCX raw text:", repr(text))

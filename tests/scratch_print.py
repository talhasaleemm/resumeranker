import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from app.services.parser.ner_pipeline import parse_resume
from app.services.parser.pdf_parser import extract_text_from_pdf

def run(filename):
    data = (Path("tests/sample_resumes") / filename).read_bytes()
    text = extract_text_from_pdf(data, filename)
    profile = parse_resume(text, filename)
    display = {k: v for k, v in profile.items() if k != "raw_sections"}
    print(f"=== {filename} ===")
    print(json.dumps(display, indent=2, ensure_ascii=False))

run("resume_multicolumn.pdf")

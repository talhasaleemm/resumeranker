import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from app.services.parser.pdf_parser import extract_text_from_pdf, _try_pdfplumber, _try_pymupdf
import fitz

data = (Path("tests/sample_resumes") / "resume_multicolumn.pdf").read_bytes()

print("==== pdfplumber ====")
print(repr(_try_pdfplumber(data, "resume_multicolumn.pdf")[:200]))

print("\n==== pymupdf ('text') ====")
print(repr(_try_pymupdf(data, "resume_multicolumn.pdf")[:200]))

print("\n==== pymupdf blocks ====")
doc = fitz.open(stream=data, filetype="pdf")
page = doc[0]
blocks = page.get_text("blocks")
for b in blocks:
    print(b[:4], repr(b[4]))

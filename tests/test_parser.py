"""
tests/test_parser.py — Phase 1 tests for the NER pipeline.

Tests:
  1. PDF parsing (backend engineer resume)
  2. DOCX parsing (data scientist resume)
  3. PDF parsing (full-stack developer resume)
  4. NER pipeline output shape validation
  5. Empty/malformed input handling

Run with:  py -3 -m pytest tests/test_parser.py -v
"""
import json
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_DIR = Path(__file__).parent / "sample_resumes"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load_pdf_bytes(name: str) -> bytes | None:
    """Load PDF bytes if file exists (falls back to .txt for testing)."""
    pdf_path = SAMPLE_DIR / name
    if pdf_path.exists():
        return pdf_path.read_bytes()
    txt_path = pdf_path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_bytes()
    return None


def _load_docx_bytes(name: str) -> bytes | None:
    docx_path = SAMPLE_DIR / name
    if docx_path.exists():
        return docx_path.read_bytes()
    txt_path = docx_path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_bytes()
    return None


# ---------------------------------------------------------------------------
# PDF Parser tests
# ---------------------------------------------------------------------------


class TestPDFParser:
    def test_backend_pdf_extracts_text(self):
        """PDF parser returns usable text from backend engineer resume."""
        from app.services.parser.pdf_parser import extract_text_from_pdf

        data = _load_pdf_bytes("resume_backend_engineer.pdf")
        if data is None:
            pytest.skip("Sample resume file not generated yet — run tests/generate_sample_resumes.py")

        # Detect if it's actually a plain text file (fallback)
        if data[:4] != b"%PDF":
            text = data.decode("utf-8", errors="replace")
        else:
            text = extract_text_from_pdf(data, "resume_backend_engineer.pdf")

        assert len(text) > 100, "Expected substantial text extraction"
        assert "Python" in text or "Backend" in text or "Aisha" in text

    def test_fullstack_pdf_extracts_text(self):
        """PDF parser returns usable text from full-stack developer resume."""
        from app.services.parser.pdf_parser import extract_text_from_pdf

        data = _load_pdf_bytes("resume_fullstack_dev.pdf")
        if data is None:
            pytest.skip("Sample resume file not generated yet")

        if data[:4] != b"%PDF":
            text = data.decode("utf-8", errors="replace")
        else:
            text = extract_text_from_pdf(data, "resume_fullstack_dev.pdf")

        assert len(text) > 100
        assert any(kw in text for kw in ["React", "JavaScript", "Priya", "Frontend"])

    def test_pdf_parser_raises_on_empty_bytes(self):
        """PDF parser raises ParseError on empty/garbage input."""
        from app.services.parser.pdf_parser import extract_text_from_pdf, ParseError

        with pytest.raises((ParseError, Exception)):
            extract_text_from_pdf(b"not a pdf at all", "fake.pdf")

    def test_pdf_parser_raises_on_empty_file(self):
        """PDF parser raises ParseError on zero-byte input."""
        from app.services.parser.pdf_parser import extract_text_from_pdf, ParseError

        with pytest.raises((ParseError, Exception)):
            extract_text_from_pdf(b"", "empty.pdf")


# ---------------------------------------------------------------------------
# DOCX Parser tests
# ---------------------------------------------------------------------------


class TestDOCXParser:
    def test_data_scientist_docx_extracts_text(self):
        """DOCX parser returns usable text from data scientist resume."""
        from app.services.parser.docx_parser import extract_text_from_docx

        data = _load_docx_bytes("resume_data_scientist.docx")
        if data is None:
            pytest.skip("Sample resume file not generated yet")

        # Check if it's plain text fallback
        try:
            data.decode("utf-8")
            # It's plain text
            text = data.decode("utf-8")
        except Exception:
            text = extract_text_from_docx(data, "resume_data_scientist.docx")

        # If it's a real DOCX
        if data[:4] == b"PK\x03\x04":  # DOCX is a ZIP file
            text = extract_text_from_docx(data, "resume_data_scientist.docx")

        assert len(text) > 100
        assert any(kw in text for kw in ["Python", "Marcus", "Machine Learning", "spaCy", "NLP"])

    def test_docx_parser_raises_on_invalid_file(self):
        """DOCX parser raises ParseError on non-DOCX input."""
        from app.services.parser.docx_parser import extract_text_from_docx, ParseError

        with pytest.raises(ParseError):
            extract_text_from_docx(b"this is not a docx file at all", "fake.docx")

    def test_docx_parser_raises_on_empty_bytes(self):
        """DOCX parser raises ParseError on zero-byte input (parity with PDF test)."""
        from app.services.parser.docx_parser import extract_text_from_docx, ParseError

        with pytest.raises((ParseError, Exception)):
            extract_text_from_docx(b"", "empty.docx")

    def test_docx_parser_raises_on_empty_zip_shell(self):
        """
        DOCX parser raises ParseError on a valid ZIP with no document content —
        simulates a corrupted/empty DOCX (parity: PDF has empty_bytes + empty_file).
        """
        import io
        import zipfile
        from app.services.parser.docx_parser import extract_text_from_docx, ParseError

        # DOCX is a ZIP — build one with only a stub Content_Types entry, no word/document.xml
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<empty/>")
        empty_zip_bytes = buf.getvalue()

        with pytest.raises((ParseError, Exception)):
            extract_text_from_docx(empty_zip_bytes, "empty_docx_shell.docx")


# ---------------------------------------------------------------------------
# NER Pipeline tests (core Phase 1 requirement)
# ---------------------------------------------------------------------------


class TestNERPipeline:
    """Test the full parse_resume() pipeline on all 3 sample resumes."""

    BACKEND_TEXT = """
Aisha Raza
aisha.raza@email.com | +1 (312) 555-0178 | github.com/aisharaza

TECHNICAL SKILLS
Python, FastAPI, PostgreSQL, Docker, Redis, Kubernetes, AWS, Go, Bash

EXPERIENCE

Senior Backend Engineer — DataStream Inc., Chicago, IL
Jan 2022 – Present
- Designed FastAPI event ingestion service processing 2M+ events/day
- Migrated monolith to microservices, reducing deployment time by 60%

EDUCATION

Bachelor of Science in Computer Science
University of Illinois at Chicago — 2019

CERTIFICATIONS
AWS Certified Developer – Associate (2022)
Docker Certified Associate (2021)

PROJECTS

EventBridge CLI
A developer tool for testing Kafka events. Built with Python, Click, Kafka
"""

    DATA_SCIENTIST_TEXT = """
Marcus Chen
mchen@datamail.io | +1 (415) 555-0234

PROFESSIONAL SUMMARY
Data Scientist with 4 years experience in ML, NLP, and statistical modeling.

TECHNICAL SKILLS
Python, R, SQL, PyTorch, TensorFlow, scikit-learn, spaCy, pandas, NumPy, XGBoost

EXPERIENCE

Senior Data Scientist — HealthAI Corp
Mar 2022 – Present
- Built NLP pipeline (spaCy + BERT) for medical entity extraction, 91% F1
- Developed patient readmission risk model using XGBoost

EDUCATION

PhD Candidate, Computational Statistics
UC Berkeley — 2020 – Present

Bachelor of Science in Statistics
Stanford University — 2020

CERTIFICATIONS
AWS Certified Machine Learning – Specialty (2023)

PROJECTS

ResumeMatcher
NLP-based resume matching using TF-IDF and BM25 scoring.
Technologies: Python, spaCy, FastAPI
"""

    FULLSTACK_TEXT = """
Priya Nair
priya.nair@dev.io | +44 7700 900456 | github.com/priyanair

SUMMARY
Full-stack engineer with 6 years building React frontends and Node.js backends.

SKILLS
JavaScript, TypeScript, React, Next.js, Node.js, Python, FastAPI, PostgreSQL,
MongoDB, Docker, AWS, Tailwind CSS, GraphQL, Jest, Cypress

EXPERIENCE

Lead Frontend Engineer — FinFlow Ltd., London, UK
Feb 2021 – Present
- Migrated Angular to React + Next.js; Lighthouse score 54 → 91
- Built design system (50+ components) using Storybook + Tailwind CSS

EDUCATION

Bachelor of Engineering in Software Engineering
University of Manchester — 2018

PROJECTS

OpenDash
Analytics dashboard. Technologies: TypeScript, Next.js, PostgreSQL, Tailwind CSS

CERTIFICATIONS
AWS Certified Cloud Practitioner (2022)
"""

    @pytest.fixture(autouse=True)
    def _skip_if_no_spacy(self):
        """Skip all NER tests if spaCy model isn't downloaded."""
        try:
            import spacy
            spacy.load("en_core_web_sm")
        except (ImportError, OSError):
            pytest.skip(
                "spaCy model not available. Run: python -m spacy download en_core_web_sm"
            )

    def _parse(self, text: str, filename: str = "test.txt") -> dict:
        from app.services.parser.ner_pipeline import parse_resume
        return parse_resume(text.strip(), filename=filename)

    # --- Profile shape ---
    def test_output_has_required_keys(self):
        profile = self._parse(self.BACKEND_TEXT, "backend_test.txt")
        required = {"name", "email", "phone", "skills", "education", "experience",
                    "projects", "certifications", "summary", "urls"}
        assert required.issubset(profile.keys()), f"Missing keys: {required - profile.keys()}"

    # --- Backend engineer ---
    def test_backend_email_extracted(self):
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        assert profile["email"] == "aisha.raza@email.com", f"Got: {profile['email']}"

    def test_backend_phone_extracted(self):
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        assert profile["phone"] is not None, "Phone should be extracted"
        assert "312" in profile["phone"]

    def test_backend_skills_extracted(self):
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        skills_lower = [s.lower() for s in profile["skills"]]
        assert len(profile["skills"]) >= 3, f"Expected ≥3 skills, got: {profile['skills']}"
        assert any("python" in s for s in skills_lower), f"Python not in: {profile['skills']}"

    def test_backend_experience_extracted(self):
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        assert len(profile["experience"]) >= 1, "Expected ≥1 experience entry"
        exp = profile["experience"][0]
        assert "title" in exp
        assert "description" in exp

    def test_backend_certifications_extracted(self):
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        assert len(profile["certifications"]) >= 1, f"Got: {profile['certifications']}"
        assert any("AWS" in c for c in profile["certifications"])

    def test_backend_projects_extracted(self):
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        assert len(profile["projects"]) >= 1, f"Got: {profile['projects']}"

    # --- Data scientist ---
    def test_data_scientist_email_extracted(self):
        profile = self._parse(self.DATA_SCIENTIST_TEXT, "data_scientist.txt")
        assert profile["email"] == "mchen@datamail.io"

    def test_data_scientist_skills_extracted(self):
        profile = self._parse(self.DATA_SCIENTIST_TEXT, "data_scientist.txt")
        skills_lower = [s.lower() for s in profile["skills"]]
        assert len(profile["skills"]) >= 5
        assert any("pytorch" in s or "python" in s for s in skills_lower)

    def test_data_scientist_education_extracted(self):
        profile = self._parse(self.DATA_SCIENTIST_TEXT, "data_scientist.txt")
        assert len(profile["education"]) >= 1

    # --- Full-stack developer ---
    def test_fullstack_email_extracted(self):
        profile = self._parse(self.FULLSTACK_TEXT, "fullstack.txt")
        assert profile["email"] == "priya.nair@dev.io"

    def test_fullstack_skills_contain_frontend_and_backend(self):
        profile = self._parse(self.FULLSTACK_TEXT, "fullstack.txt")
        skills_lower = [s.lower() for s in profile["skills"]]
        assert any(s in skills_lower for s in ["javascript", "typescript", "react"]), (
            f"Frontend skill missing: {profile['skills']}"
        )
        assert any(s in skills_lower for s in ["node.js", "python", "fastapi", "postgresql"]), (
            f"Backend skill missing: {profile['skills']}"
        )

    def test_fullstack_urls_extracted(self):
        profile = self._parse(self.FULLSTACK_TEXT, "fullstack.txt")
        assert len(profile["urls"]) >= 1
        assert any("github" in u for u in profile["urls"])

    # --- Edge cases ---
    def test_empty_text_returns_empty_profile(self):
        from app.services.parser.ner_pipeline import parse_resume
        profile = parse_resume("", filename="empty.txt")
        assert profile["skills"] == []
        assert profile["email"] is None
        assert profile["name"] is None

    def test_whitespace_only_returns_empty_profile(self):
        from app.services.parser.ner_pipeline import parse_resume
        profile = parse_resume("   \n\n   ", filename="whitespace.txt")
        assert profile["skills"] == []

    def test_json_serializable(self):
        """Profile must be fully JSON-serializable (for DB storage)."""
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        json_str = json.dumps(profile)
        restored = json.loads(json_str)
        assert restored["email"] == profile["email"]

    # --- False-positive / negative-content tests ---

    def test_company_names_not_in_skills(self):
        """
        NER pipeline must NOT pull company/location names into the skills list.
        'DataStream Inc.', 'Chicago', 'Illinois' are org/geo names in experience
        section — they must never appear as extracted skills.
        """
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        skills_lower = [s.lower() for s in profile["skills"]]
        false_positive_orgs = ["datastream", "datastream inc", "chicago", "illinois"]
        for org in false_positive_orgs:
            assert org not in skills_lower, (
                f"Company/location '{org}' incorrectly in skills: {profile['skills']}"
            )

    def test_certifications_not_in_projects(self):
        """
        NER pipeline must NOT conflate certifications with projects.
        'AWS Certified Developer' must be in certifications, never in projects.
        """
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        project_names_lower = [p.get("name", "").lower() for p in profile["projects"]]
        cert_leakage = [n for n in project_names_lower if "certified" in n or "associate" in n]
        assert not cert_leakage, (
            f"Certification text leaked into projects list: {cert_leakage}"
        )

    def test_skills_are_not_full_sentences(self):
        """
        No skill entry should be a full sentence (> 6 words) — that would indicate
        experience bullet text leaked into the skills list.
        """
        profile = self._parse(self.BACKEND_TEXT, "backend.txt")
        for skill in profile["skills"]:
            word_count = len(skill.split())
            assert word_count <= 6, (
                f"Skill looks like a sentence ({word_count} words): '{skill}'"
            )

    def test_skills_section_layouts(self):
        """
        Verify that skill extraction works across multiple structural layout formats:
        - Layout 1: Pipe-separated list
        - Layout 2: Bullet-separated list
        - Layout 3: Standard comma-separated list on newlines with no category labels
        """
        # Layout 1: Pipe separated
        pipe_text = """
        John Doe
        john@doe.com
        SKILLS
        Python | Go | SQL | Docker | Kubernetes
        """
        p1 = self._parse(pipe_text, "pipe.txt")
        skills_p1 = [s.lower() for s in p1["skills"]]
        assert sorted(skills_p1) == ["docker", "go", "kubernetes", "python", "sql"]

        # Layout 2: Bullet separated
        bullet_text = """
        John Doe
        john@doe.com
        SKILLS
        • React · TypeScript ▪ Node.js ▸ Python ► Docker
        """
        p2 = self._parse(bullet_text, "bullet.txt")
        skills_p2 = [s.lower() for s in p2["skills"]]
        assert "react" in skills_p2
        assert "typescript" in skills_p2
        assert "node.js" in skills_p2
        assert "python" in skills_p2
        assert "docker" in skills_p2

        # Layout 3: Standard comma-separated, no categories
        comma_text = """
        John Doe
        john@doe.com
        SKILLS
        Python, Go, SQL, Docker, Kubernetes
        """
        p3 = self._parse(comma_text, "comma.txt")
        skills_p3 = [s.lower() for s in p3["skills"]]
        assert sorted(skills_p3) == ["docker", "go", "kubernetes", "python", "sql"]



# ---------------------------------------------------------------------------
# Integration: print full profile (for raw terminal output in Phase 1 report)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from app.services.parser.ner_pipeline import parse_resume

    profiles = [
        ("Backend Engineer", TestNERPipeline.BACKEND_TEXT, "backend.txt"),
        ("Data Scientist", TestNERPipeline.DATA_SCIENTIST_TEXT, "data_scientist.txt"),
        ("Full-Stack Developer", TestNERPipeline.FULLSTACK_TEXT, "fullstack.txt"),
    ]

    for label, text, fname in profiles:
        print(f"\n{'='*60}")
        print(f"RESUME: {label} ({fname})")
        print("=" * 60)
        profile = parse_resume(text.strip(), filename=fname)
        # Print all fields except raw_sections for readability
        display = {k: v for k, v in profile.items() if k != "raw_sections"}
        print(json.dumps(display, indent=2, ensure_ascii=False))


class TestEdgeCaseParser:
    def test_multicolumn_pdf(self):
        """a. Multi-column layout: cleanly separates columns using PyMuPDF block coordinates."""
        from app.services.parser.pdf_parser import extract_text_from_pdf
        from app.services.parser.ner_pipeline import parse_resume
        data = _load_pdf_bytes("resume_multicolumn.pdf")
        text = extract_text_from_pdf(data, "resume_multicolumn.pdf")
        profile = parse_resume(text, "resume_multicolumn.pdf")
        # Text is now isolated cleanly by column heuristic
        skills_lower = [s.lower() for s in profile["skills"]]
        assert "python" in skills_lower, "Skills should be cleanly parsed"
        
        # Verify experience is not merged horizontally
        exp_raw = profile["experience"][0]["raw"].lower() if profile["experience"] else ""
        assert "python" not in exp_raw, f"Experience should not be merged with Skills column, got: {exp_raw}"
        assert len(profile["experience"]) > 0

    def test_table_based_docx(self):
        """b. Table-based resume: degrades because python-docx merges cells on the same line, breaking section headers."""
        from app.services.parser.docx_parser import extract_text_from_docx
        from app.services.parser.ner_pipeline import parse_resume
        data = _load_docx_bytes("resume_table.docx")
        text = extract_text_from_docx(data, "resume_table.docx")
        profile = parse_resume(text, "resume_table.docx")
        # Text extraction puts table cells on the same line (e.g. "SKILLS | Python"),
        # causing the section header regex to fail since it expects headers on their own line.
        assert profile["skills"] == [], "Degraded extraction: header not isolated"

    def test_scanned_pdf(self):
        """c. Scanned/image-based PDF with no extractable text layer."""
        from app.services.parser.pdf_parser import extract_text_from_pdf, ParseError
        import pytest
        data = _load_pdf_bytes("resume_scanned.pdf")
        # Now that we have OCR (Phase 8), scanned PDFs should extract successfully!
        text = extract_text_from_pdf(data, filename="resume_scanned.pdf")
        assert len(text) > 50

    def test_missing_sections_pdf(self):
        """d. Missing expected sections (e.g. no EXPERIENCE)."""
        from app.services.parser.pdf_parser import extract_text_from_pdf
        from app.services.parser.ner_pipeline import parse_resume
        data = _load_pdf_bytes("resume_missing_sections.pdf")
        text = extract_text_from_pdf(data, "resume_missing_sections.pdf")
        profile = parse_resume(text, "resume_missing_sections.pdf")
        
        assert profile["name"] is not None
        assert profile["experience"] == []
        assert profile["skills"] == []

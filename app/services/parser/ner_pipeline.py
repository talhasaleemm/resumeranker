"""
app/services/parser/ner_pipeline.py — spaCy NER pipeline.

Converts raw resume text into a structured JSON profile with:
  - name, email, phone
  - skills (via pattern matching + NER + section parsing)
  - education (institution, degree, year)
  - experience (company, title, duration, description)
  - projects (name, description, technologies)
  - certifications

Design decisions:
  - Uses en_core_web_sm/lg NER for PERSON, ORG, GPE, DATE entities.
  - Custom regex patterns handle email, phone, URLs.
  - Section-based parsing handles the resume's structural sections
    (EDUCATION, EXPERIENCE, SKILLS, etc.) using header detection.
  - Does NOT fake output — fields are empty lists/None when not found,
    never filled with placeholder data.
"""
import logging
import re
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
_PHONE_RE = re.compile(
    r"(?:\+?1[\s\-.]?)?"
    r"(?:\(?\d{3}\)?[\s\-.]?)"
    r"\d{3}[\s\-.]?\d{4}"
    r"(?:\s*(?:ext|x|ext\.)\s*\d{1,5})?"
)
_URL_RE = re.compile(
    r"https?://[^\s]+"
    r"|(?:www\.|github\.com/|linkedin\.com/in/)[^\s]+"
)

# Section header detection — covers common resume heading variations
_SECTION_HEADERS = {
    "skills": re.compile(
        r"^(?:technical\s+)?skills?(?:\s+summary)?|"
        r"^core\s+competencies|^technologies|^tech\s+stack|"
        r"^tools?\s+(?:and\s+)?technologies",
        re.I,
    ),
    "experience": re.compile(
        r"^(?:work\s+)?experience|^professional\s+experience|"
        r"^employment(?:\s+history)?|^work\s+history|^career",
        re.I,
    ),
    "education": re.compile(
        r"^education(?:al\s+background)?|^academic(?:\s+background)?|"
        r"^qualifications?|^degrees?",
        re.I,
    ),
    "projects": re.compile(
        r"^(?:personal\s+)?projects?|^side\s+projects?|"
        r"^portfolio|^open[\s\-]?source",
        re.I,
    ),
    "certifications": re.compile(
        r"^certifications?|^licenses?\s+(?:and\s+)?certifications?|"
        r"^credentials?|^awards?\s+(?:and\s+)?certifications?",
        re.I,
    ),
    "summary": re.compile(
        r"^(?:professional\s+)?summary|^objective|^profile|^about",
        re.I,
    ),
}

# Degree keywords for education parsing
_DEGREE_RE = re.compile(
    r"(?:B\.?S\.?|B\.?E\.?|B\.?Tech\.?|B\.?Sc\.?|B\.?A\.?|"
    r"M\.?S\.?|M\.?E\.?|M\.?Tech\.?|M\.?Sc\.?|M\.?B\.?A\.?|"
    r"Ph\.?D\.?|Doctor(?:ate)?|Bachelor[s']?|Master[s']?|Associate[s']?)"
    r"(?:\s+(?:of|in|of\s+Science\s+in|of\s+Arts\s+in))?"
    r"(?:\s+[A-Z][a-zA-Z\s]{0,40})?",
    re.I,
)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


# ---------------------------------------------------------------------------
# spaCy model loader (cached singleton)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _load_nlp(model_name: str = "en_core_web_sm"):
    """Load and cache the spaCy model. Called once per process."""
    import spacy

    try:
        nlp = spacy.load(model_name)
        logger.info("Loaded spaCy model '%s'", model_name)
        return nlp
    except OSError:
        logger.error(
            "spaCy model '%s' not found. Run: python -m spacy download %s",
            model_name,
            model_name,
        )
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_resume(
    raw_text: str,
    filename: str = "unknown",
    spacy_model: str = "en_core_web_sm",
) -> dict[str, Any]:
    """
    Parse raw resume text into a structured profile.

    Args:
        raw_text: Plain text extracted from PDF or DOCX.
        filename: Original filename (for logging).
        spacy_model: spaCy model name to use.

    Returns:
        dict with keys: name, email, phone, urls, skills, education,
        experience, projects, certifications, summary, raw_sections.
    """
    if not raw_text or len(raw_text.strip()) < 20:
        logger.warning("Empty or near-empty text for '%s'", filename)
        return _empty_profile()

    nlp = _load_nlp(spacy_model)
    # spaCy has a 1M char limit — truncate safely for very long resumes
    doc = nlp(raw_text[:1_000_000])

    # Step 1: Extract contact info via regex (more reliable than NER for these)
    email = _extract_email(raw_text)
    phone = _extract_phone(raw_text)
    urls = _extract_urls(raw_text)

    # Step 2: Extract name from NER (first PERSON entity in the first 500 chars)
    name = _extract_name(doc)

    # Step 3: Split text into sections by header detection
    sections = _split_into_sections(raw_text)

    # Step 4: Parse each section
    skills = _parse_skills_section(raw_text, doc)
    education = _parse_education_section(sections.get("education", ""), doc)
    experience = _parse_experience_section(sections.get("experience", ""), doc)
    projects = _parse_projects_section(sections.get("projects", ""), doc)
    certifications = _parse_certifications_section(sections.get("certifications", ""))
    summary = sections.get("summary", "").strip()

    profile = {
        "name": name,
        "email": email,
        "phone": phone,
        "urls": urls,
        "skills": skills,
        "education": education,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "summary": summary,
        "raw_sections": {k: v[:500] for k, v in sections.items()},  # truncated for storage
    }

    logger.info(
        "Parsed '%s': name=%r email=%r skills=%d education=%d experience=%d",
        filename,
        name,
        email,
        len(skills),
        len(education),
        len(experience),
    )
    return profile


# ---------------------------------------------------------------------------
# Contact extraction
# ---------------------------------------------------------------------------

def _extract_email(text: str) -> str | None:
    match = _EMAIL_RE.search(text)
    return match.group(0).lower() if match else None


def _extract_phone(text: str) -> str | None:
    match = _PHONE_RE.search(text)
    if match:
        phone = re.sub(r"[\s\-.()\+]", "", match.group(0))
        if len(phone) >= 10:
            return match.group(0).strip()
    return None


def _extract_urls(text: str) -> list[str]:
    return list(dict.fromkeys(_URL_RE.findall(text)))  # deduplicated, order preserved


def _extract_name(doc) -> str | None:
    """
    Extract candidate name from the first PERSON entity in the first ~500 chars.
    Falls back to the first non-empty line if NER finds nothing.
    """
    # Try NER first — limit to first 500 chars of doc
    for ent in doc.ents:
        if ent.label_ == "PERSON" and ent.start_char < 500:
            name = ent.text.strip()
            if 2 <= len(name.split()) <= 5:  # plausible name length
                return name

    # Fallback: first non-empty, non-email, non-phone, non-pipe line
    for line in doc.text.split("\n")[:5]:
        line = line.strip()
        # A name line: 2–4 words, no special chars, no digits, short
        words = line.split()
        if (
            line
            and not _EMAIL_RE.search(line)
            and not _PHONE_RE.search(line)
            and not _URL_RE.search(line)
            and "|" not in line
            and "+" not in line
            and 2 <= len(words) <= 4
            and len(line) < 50
            and not any(ch.isdigit() for ch in line)
        ):
            return line

    return None


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

def _split_into_sections(text: str) -> dict[str, str]:
    """
    Split resume text into named sections by detecting section headers.
    Returns a dict mapping section name → section text.
    """
    lines = text.split("\n")
    sections: dict[str, list[str]] = {"header": []}
    current_section = "header"

    for line in lines:
        stripped = line.strip()

        detected = _detect_section_header(stripped)
        if detected:
            current_section = detected
            sections.setdefault(current_section, [])
        else:
            sections.setdefault(current_section, []).append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _detect_section_header(line: str) -> str | None:
    """Return the section name if the line looks like a section header, else None."""
    # Must be reasonably short to be a header
    if not line or len(line) > 80:
        return None
    # Strip common decoration: dashes, underscores, colons, ALL CAPS
    clean = re.sub(r"[:\-_|•*#]+", "", line).strip()
    if not clean:
        return None

    for section_name, pattern in _SECTION_HEADERS.items():
        if pattern.match(clean):
            return section_name

    return None


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------

def _parse_skills_section(raw_text: str, doc) -> list[str]:
    """
    Extract skills from the entire resume text.
    Uses n-gram extraction with stop-word removal to identify potential skills.
    """
    if not raw_text:
        return []

    # Normalize separators
    normalized = re.sub(r"[•·▪▸►|/\\]", ",", raw_text)
    normalized = re.sub(r"\s[–—]\s", ",", normalized)
    
    # Split into candidate phrases
    raw_skills = re.split(r"[,;\n]+", normalized)
    
    # Get stop words
    try:
        nlp = _load_nlp()
        stop_words = set(nlp.Defaults.stop_words)
    except Exception:
        stop_words = set()
    
    stop_words.update({"experience", "engineer", "developer", "senior", "junior", "years", "worked", "used", "using", "built", "developed"})
    
    skills: list[str] = []
    for raw in raw_skills:
        skill = raw.strip()
        skill = re.sub(r"^[A-Za-z\s]+:\s*", "", skill).strip()
        if not skill or len(skill) > 60:
            continue
        
        skill = re.sub(r"^[^\w]+|[^\w.)]+$", "", skill).strip()
        if not skill or skill.isdigit():
            continue
        
        # Generate 1-3 word n-grams from the phrase
        tokens = [t.lower() for t in re.findall(r"\b\w+\b", skill) if t.lower() not in stop_words]
        if not tokens:
            continue
        
        # Add original phrase if reasonable length
        if len(skill.split()) <= 6:
            skills.append(skill)
        
        # Add 1-3 word n-grams
        for n in range(1, min(4, len(tokens) + 1)):
            for i in range(len(tokens) - n + 1):
                ngram = " ".join(tokens[i:i+n])
                if 1 < len(ngram) <= 60:
                    skills.append(ngram)
    
    return list(dict.fromkeys(skills))


def _parse_education_section(text: str, doc) -> list[dict]:
    """
    Parse education entries. Each entry: institution, degree, field, years.
    """
    if not text:
        return []

    entries: list[dict] = []
    # Split into blocks by blank lines or ORG entities
    blocks = re.split(r"\n{2,}", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Find degree
        degree_match = _DEGREE_RE.search(block)
        degree = degree_match.group(0).strip() if degree_match else None

        # Find full 4-digit years only
        years = [y for y in _YEAR_RE.findall(block) if len(y) == 4]
        year_range = f"{years[0]}–{years[-1]}" if len(years) >= 2 else (years[0] if years else None)

        # Find institution: look for ORG entities or the first capitalized line
        institution = None
        block_doc = doc.vocab.strings  # lightweight ref
        # Use regex to find institution-like strings (Capitalized multi-word)
        inst_match = re.search(
            r"(?:University|College|Institute|School|Academy)\s+of\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*"
            r"|[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,4}\s+(?:University|College|Institute|School)",
            block,
        )
        if inst_match:
            institution = inst_match.group(0).strip()
        else:
            # Fall back to first line of block
            first_line = block.split("\n")[0].strip()
            if first_line and len(first_line) < 100:
                institution = first_line

        if degree or institution:
            entries.append({
                "institution": institution,
                "degree": degree,
                "years": year_range,
                "raw": block[:200],
            })

    return entries


def _parse_experience_section(text: str, doc) -> list[dict]:
    """
    Parse work experience entries.
    Each entry: company, title, duration, description bullets.
    """
    if not text:
        return []

    entries: list[dict] = []
    # Split on blank lines (most resumes separate jobs with blank lines)
    blocks = re.split(r"\n{2,}", text)

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 20:
            continue

        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        # First line usually: "Job Title at Company" or "Company | Job Title"
        first_line = lines[0]
        company = None
        title = None

        # Pattern: "Title at Company" or "Title - Company"
        at_match = re.search(r"(.+?)\s+(?:at|@|–|-)\s+(.+)", first_line, re.I)
        if at_match:
            title = at_match.group(1).strip()
            company = at_match.group(2).strip()
        else:
            title = first_line  # best guess

        # Find duration from any line
        years = _YEAR_RE.findall(block)
        duration = None
        for line in lines:
            date_match = re.search(
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}"
                r"|(?:19|20)\d{2}\s*[–\-–]\s*(?:(?:19|20)\d{2}|Present|Current)",
                line, re.I
            )
            if date_match:
                duration = date_match.group(0).strip()
                break

        # Remaining lines are the description
        description = "\n".join(lines[1:]) if len(lines) > 1 else ""

        entries.append({
            "company": company,
            "title": title,
            "duration": duration,
            "description": description[:500],
            "raw": block[:300],
        })

    return entries


def _parse_projects_section(text: str, doc) -> list[dict]:
    """
    Parse projects. Each entry: name, description, technologies.
    """
    if not text:
        return []

    entries: list[dict] = []
    blocks = re.split(r"\n{2,}", text)

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 10:
            continue

        lines = [l.strip() for l in block.split("\n") if l.strip()]
        name = lines[0] if lines else None
        description = " ".join(lines[1:]) if len(lines) > 1 else ""

        # Look for tech stack mentions (parentheses are common: "Built with Python, React")
        tech_match = re.search(
            r"(?:built\s+with|technologies?:|tech\s+stack:|using|stack:)\s*([^\n.]+)",
            block, re.I
        )
        technologies = []
        if tech_match:
            raw_tech = tech_match.group(1)
            technologies = [t.strip() for t in re.split(r"[,|/]", raw_tech) if t.strip()]

        if name:
            entries.append({
                "name": name,
                "description": description[:400],
                "technologies": technologies,
                "raw": block[:300],
            })

    return entries


def _parse_certifications_section(text: str) -> list[str]:
    """Parse certifications — typically one per line or bullet."""
    if not text:
        return []

    certs: list[str] = []
    for line in text.split("\n"):
        cert = re.sub(r"^[•·▪▸►\-–—*]\s*", "", line).strip()
        if cert and 3 < len(cert) <= 150:
            certs.append(cert)

    return list(dict.fromkeys(certs))


# ---------------------------------------------------------------------------
# Empty profile template
# ---------------------------------------------------------------------------

def _empty_profile() -> dict[str, Any]:
    return {
        "name": None,
        "email": None,
        "phone": None,
        "urls": [],
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "summary": "",
        "raw_sections": {},
    }

"""
Automated ingestion validation for ResumeRanker.

Part A (integration): POSTs talhasaleem_CV.pdf to the live /api/v1/resumes/
endpoint (with a real JWT), polls the Celery task, and asserts the ingestion
reaches status "success" with a candidate_id and FLAT assigned_tags (regression
guard for the tuple-unpack bug that caused ArraySubscriptError).

Part B (NLP unit): runs the exact same spaCy NER pipeline the worker uses
(parse_resume) on the same PDF bytes and asserts valid Skills / Experience
entities are extracted.

Run:  python tests/automated_ingestion_test.py
"""
import io
import sys
import time
import json
import urllib.request
import urllib.parse

BASE = "http://app:8000"
PDF_PATH = r"/tmp/talhasaleem_CV.pdf"
DEMO_EMAIL = "demo@resumeranker.local"
DEMO_PASSWORD = "demo1234"


def _post(url, raw_body=None, content_type=None, headers=None):
    req = urllib.request.Request(url, data=raw_body, headers=headers or {}, method="POST")
    if content_type:
        req.add_header("Content-Type", content_type)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, resp.read().decode("utf-8")


def login():
    body = urllib.parse.urlencode(
        {"username": DEMO_EMAIL, "password": DEMO_PASSWORD}
    ).encode()
    status, text = _post(
        f"{BASE}/api/v1/auth/login",
        raw_body=body,
        content_type="application/x-www-form-urlencoded",
    )
    assert status == 200, f"login failed: {status} {text}"
    return json.loads(text)["access_token"]


def extract_pdf_text(pdf_bytes):
    """Mirror the worker's text-extraction path for the NLP assertion."""
    import sys as _sys
    _sys.path.insert(0, r"D:\scratch\resumeranker")
    from app.services.parser.pdf_parser import extract_text_from_pdf
    return extract_text_from_pdf(pdf_bytes, "talhasaleem_CV.pdf")


def parse_resume(text):
    import sys as _sys
    _sys.path.insert(0, r"D:\scratch\resumeranker")
    from app.services.parser.ner_pipeline import parse_resume as _parse
    return _parse(text, filename="talhasaleem_CV.pdf")


def upload_resume(token, pdf_bytes):
    boundary = "----rrboundarytest"
    body = (
        b"--" + boundary.encode() + b"\r\n"
        + b'Content-Disposition: form-data; name="file"; filename="talhasaleem_CV.pdf"' + b"\r\n"
        + b"Content-Type: application/pdf" + b"\r\n\r\n"
        + pdf_bytes + b"\r\n"
        + b"--" + boundary.encode() + b"--\r\n"
    )
    status, text = _post(
        f"{BASE}/api/v1/resumes/",
        raw_body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status == 202, f"upload expected 202, got {status} {text}"
    return json.loads(text)["task_id"]


def poll_task(token, task_id, timeout=150):
    deadline = time.time() + timeout
    while time.time() < deadline:
        req = urllib.request.Request(
            f"{BASE}/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            task = json.loads(resp.read().decode("utf-8"))
        if task["status"] not in ("pending", "PENDING", "started"):
            return task
        time.sleep(3)
    raise TimeoutError(f"task {task_id} did not finish in {timeout}s")


def part_a_integration(token, pdf_bytes):
    print("[A] Integration: POST talhasaleem_CV.pdf -> Celery ingest")
    task_id = upload_resume(token, pdf_bytes)
    print(f"    upload accepted, task_id={task_id}")
    task = poll_task(token, task_id)
    print(f"    task status = {task['status']}")
    assert task["status"] == "success", f"task failed: {task.get('result')}"
    result = task["result"]
    assert result["status"] == "success", f"ingestion failure: {result}"
    cid = result.get("candidate_id")
    assert cid, "no candidate_id returned"

    # Regression guard for the tuple-unpack bug: read the persisted candidate
    # row directly and assert assigned_tags is a FLAT 1-D list (not nested).
    import sys as _sys
    _sys.path.insert(0, "/app")
    from sqlalchemy import create_engine, text as _text
    from app.config import get_settings
    settings = get_settings()
    sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        row = conn.execute(
            _text("SELECT assigned_tags FROM candidates WHERE id = :cid"),
            {"cid": cid},
        ).fetchone()
    assert row is not None, "candidate row not found in DB"
    tags = row[0]
    assert isinstance(tags, list), f"assigned_tags must be a list, got {type(tags)}"
    assert not any(isinstance(t, (list, dict)) for t in tags), (
        "REGRESSION: assigned_tags nested (tuple-unpack bug)"
    )
    print(f"    candidate_id = {cid}")
    print(f"    assigned_tags (flat 1-D) = {tags}")
    print("[A] PASS")


def part_b_nlp(pdf_bytes):
    print("[B] NLP: spaCy NER on the same PDF bytes")
    text = extract_pdf_text(pdf_bytes)
    assert len(text.strip()) > 50, "extracted text too short"
    print(f"    extracted {len(text)} chars of raw text")
    profile = parse_resume(text)
    skills = profile.get("skills") or []
    experience = profile.get("experience") or []
    print(f"    parsed_skills ({len(skills)}) = {skills[:8]}")
    print(f"    parsed_experience entries = {len(experience)}")
    assert isinstance(skills, list) and skills, "Skills must be a non-empty list"
    assert all(isinstance(s, str) for s in skills), "Skills must be flat strings"
    assert isinstance(experience, list) and experience, "Experience must be non-empty"
    print("[B] PASS")


def main():
    pdf_bytes = open(PDF_PATH, "rb").read()
    print(f"[test] PDF loaded: {len(pdf_bytes)} bytes\n")
    token = login()
    print("[test] logged in, JWT obtained\n")
    part_a_integration(token, pdf_bytes)
    print()
    part_b_nlp(pdf_bytes)
    print("\n[test] OVERALL PASS: ingestion 200-equivalent success + valid spaCy "
          "Skills/Experience entities, no nested assigned_tags regression.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

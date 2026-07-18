#!/usr/bin/env python3
import io
import json
import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Error: 'httpx' is required to run this script. Install it with: pip install httpx")
    sys.exit(1)

try:
    from docx import Document
except ImportError:
    print("Error: 'python-docx' is required to run this script. Install it with: pip install python-docx")
    sys.exit(1)

# If running inside docker, the app is on port 8000. If on host, 8001.
in_docker = Path('/.dockerenv').exists()
port = 8000 if in_docker else 8001
API_BASE = f"http://localhost:{port}/api/v1"
PHASE13_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "phase13"

def create_docx_buffer(text):
    doc = Document()
    doc.add_paragraph(text)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def main():
    print("=" * 60)
    print("ResumeRanker Quick Demo (Phase 15)")
    print("=" * 60)
    print("This script will ingest O*NET-grounded synthetic fixtures")
    print("then run the matching engine to score them.\\n")

    if not PHASE13_DIR.exists():
        print(f"Error: Phase 13 fixtures not found at {PHASE13_DIR}")
        sys.exit(1)

    candidate_ids = {}
    job_ids = {}

    with httpx.Client(timeout=30.0) as client:
        # 0. Authentication
        print("--- 0. Authentication ---")
        reg_resp = client.post(f"{API_BASE}/auth/register", json={"email": "demo@example.com", "password": "password"})
        if reg_resp.status_code not in (201, 400):
            print(f"❌ Registration failed: {reg_resp.text}")
            sys.exit(1)
        
        resp = client.post(f"{API_BASE}/auth/login", data={"username": "demo@example.com", "password": "password"})
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            client.headers.update({"Authorization": f"Bearer {token}"})
            print("✅ Authenticated as demo@example.com\\n")
        else:
            print(f"❌ Login failed: {resp.text}")
            sys.exit(1)

        # 1. Ingest Resumes
        print("--- 1. Ingesting Candidates (as .docx) ---")
        subset_candidates = [
            "candidate_dense.txt",
            "candidate_sparse.txt",
            "candidate_stuffer.txt",
            "cand_ds_verbose_narrative.txt",
            "cand_ds_nomatch.txt",
            "cand_devops_bulleted.txt",
            "cand_pm_terse.txt"
        ]
        
        for c_name in subset_candidates:
            filepath = PHASE13_DIR / c_name
            if not filepath.exists():
                print(f"Skipping {c_name} (not found)")
                continue
            
            text = filepath.read_text(encoding="utf-8")
            docx_name = c_name.replace(".txt", ".docx")
            docx_buffer = create_docx_buffer(text)
            
            try:
                files = {
                    'file': (
                        docx_name,
                        docx_buffer,
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    )
                }
                resp = client.post(f"{API_BASE}/resumes/", files=files)
                
                if resp.status_code == 202:
                    task_id = resp.json().get("task_id")
                    print(f"✅ Ingest queued: {c_name} -> Task {task_id}")
                else:
                    print(f"❌ Failed to ingest {c_name}: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"❌ Error uploading {c_name}: {e}")

        print("\\nNote: Candidates are ingested asynchronously via Celery.")
        print("Check the web UI or database to view the parsed candidates.")
        
        # 2. Ingest Jobs
        print("\\n--- 2. Ingesting Jobs ---")
        subset_jobs = [
            "jd_verbose.txt",
            "jd_data_scientist.txt",
            "jd_product_manager.txt"
        ]
        for j_name in subset_jobs:
            filepath = PHASE13_DIR / j_name
            if not filepath.exists():
                continue
                
            content = filepath.read_text(encoding='utf-8')
            payload = {
                "title": j_name.replace(".txt", "").replace("jd_", "").replace("_", " ").title(),
                "description": content,
                "required_skills": [],
                "preferred_skills": []
            }
            
            try:
                resp = client.post(f"{API_BASE}/jobs/", json=payload)
                if resp.status_code == 200:
                    jid = resp.json().get("job_id")
                    job_ids[j_name] = jid
                    print(f"✅ Created job: {payload['title']} -> {jid}")
                else:
                    print(f"❌ Failed to create job {j_name}: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"❌ Error creating job {j_name}: {e}")

        print("\\n============================================================")
        print("Demo Seed Complete!")
        print("The database is now populated with jobs and candidates are processing.")
        print("You can view them in the UI and run Match workflows there.")
        print("============================================================")

if __name__ == "__main__":
    main()

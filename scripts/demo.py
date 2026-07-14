#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
try:
    import httpx
except ImportError:
    print("Error: 'httpx' is required to run this script. Install it with: pip install httpx")
    sys.exit(1)

# If running inside docker, the app is on port 8000. If on host, 8001.
port = 8000 if os.environ.get('APP_ENV') else 8001
API_BASE = f"http://localhost:{port}/api/v1"
SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"

def main():
    print("=" * 60)
    print("ResumeRanker Quick Demo")
    print("=" * 60)
    print("This script will ingest synthetic sample resumes and jobs,")
    print("then run the matching engine to score them.")
    print("Note: Candidates are safely deduplicated on email/hash if run twice.\n")

    resumes_dir = SAMPLES_DIR / "resumes"
    jobs_dir = SAMPLES_DIR / "jobs"

    if not resumes_dir.exists() or not jobs_dir.exists():
        print("Error: Sample data directories not found.")
        sys.exit(1)

    candidate_ids = {}
    job_ids = {}

    with httpx.Client(timeout=30.0) as client:
        # 1. Ingest Resumes
        print("--- 1. Ingesting Resumes ---")
        for filepath in resumes_dir.iterdir():
            if not filepath.is_file():
                continue
            try:
                raw_text = ""
                if filepath.suffix == '.pdf':
                    from app.services.parser.pdf_parser import extract_text_from_pdf
                    with open(filepath, "rb") as f:
                        raw_text = extract_text_from_pdf(f.read(), filepath.name)
                elif filepath.suffix == '.docx':
                    from app.services.parser.docx_parser import extract_text_from_docx
                    with open(filepath, "rb") as f:
                        raw_text = extract_text_from_docx(f.read(), filepath.name)
                else:
                    print(f"Skipping {filepath.name}: Unsupported format")
                    continue
                
                payload = {
                    "raw_text": raw_text,
                    "filename": filepath.name
                }
                
                resp = client.post(f"{API_BASE}/resumes/", json=payload)
                
                if resp.status_code == 200:
                    cid = resp.json().get("candidate_id")
                    candidate_ids[filepath.name] = cid
                    print(f"✅ Ingested: {filepath.name} -> {cid}")
                elif resp.status_code == 409:
                    cid = resp.json().get("candidate_id")
                    candidate_ids[filepath.name] = cid
                    print(f"⚠️  Deduplicated (already exists): {filepath.name} -> {cid}")
                else:
                    print(f"❌ Failed to ingest {filepath.name}: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"❌ Error uploading {filepath.name}: {e}")

        # 2. Ingest Jobs
        print("\n--- 2. Ingesting Jobs ---")
        for filepath in jobs_dir.iterdir():
            if not filepath.is_file() or filepath.suffix != '.md':
                continue
            
            # Very simple parser for our synthetic job md files
            content = filepath.read_text(encoding='utf-8')
            lines = content.split('\n')
            title = lines[0].replace('# ', '').strip() if lines else filepath.stem
            
            req_skills = []
            pref_skills = []
            
            is_req = False
            is_pref = False
            for line in lines:
                if "**Required Skills**:" in line:
                    is_req = True
                    is_pref = False
                elif "**Preferred Skills**:" in line:
                    is_req = False
                    is_pref = True
                elif line.strip() and not line.startswith('**'):
                    if is_req:
                        req_skills.extend([s.strip() for s in line.split(',') if s.strip()])
                        is_req = False
                    elif is_pref:
                        pref_skills.extend([s.strip() for s in line.split(',') if s.strip()])
                        is_pref = False

            payload = {
                "title": title,
                "description": content,
                "required_skills": req_skills,
                "preferred_skills": pref_skills
            }
            
            try:
                resp = client.post(f"{API_BASE}/jobs/", json=payload)
                if resp.status_code == 200:
                    jid = resp.json().get("job_id")
                    job_ids[title] = jid
                    print(f"✅ Created job: {title} -> {jid}")
                else:
                    print(f"❌ Failed to create job {title}: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"❌ Error creating job {title}: {e}")

        # 3. Match candidates against jobs
        print("\n--- 3. Running Matches ---")
        if not candidate_ids or not job_ids:
            print("No candidates or jobs to match. Exiting.")
            sys.exit(1)

        c_ids_list = list(candidate_ids.values())
        
        for job_title, jid in job_ids.items():
            print(f"\nEvaluating candidates for: {job_title}")
            print("-" * 40)
            
            payload = {
                "job_id": jid,
                "candidate_ids": c_ids_list
            }
            
            try:
                resp = client.post(f"{API_BASE}/matches/", json=payload)
                if resp.status_code == 200:
                    matches = resp.json().get("matches", [])
                    # Sort by final score descending
                    matches.sort(key=lambda x: x.get("final_score", 0), reverse=True)
                    
                    for idx, match in enumerate(matches, 1):
                        score = match.get("final_score")
                        log = match.get("explanation_log", {})
                        tags = ", ".join(log.get("tags_detected", [])) or "None"
                        matched = ", ".join(log.get("matched_skills", [])) or "None"
                        missing = ", ".join(log.get("missing_skills", [])) or "None"
                        
                        # Find candidate filename by id
                        c_name = "Unknown"
                        for name, i in candidate_ids.items():
                            if i == match["candidate_id"]:
                                c_name = name
                                break
                                
                        print(f"{idx}. {c_name} | Score: {score:.1f}")
                        print(f"   Tags Detected : {tags}")
                        print(f"   Matched Skills: {matched}")
                        print(f"   Missing Skills: {missing}\n")
                else:
                    print(f"❌ Match request failed: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"❌ Error matching job {job_title}: {e}")

    print("=" * 60)
    print("Demo complete!")

if __name__ == "__main__":
    main()

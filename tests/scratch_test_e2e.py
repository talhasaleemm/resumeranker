import requests
import time
import uuid

BASE_URL = "http://localhost:8000"  # Inside the container, hit localhost:8000

def poll_task(task_id, headers):
    while True:
        resp = requests.get(f"{BASE_URL}/api/v1/tasks/{task_id}", headers=headers)
        data = resp.json()
        status = data.get("status", "").lower()
        print(f"Task {task_id} status: {status}")
        if status == "success":
            return data.get("result")
        elif status == "failure":
            raise RuntimeError(f"Task failed: {data}")
        time.sleep(1)

def run_e2e():
    # 1. Register Recruiter
    email = f"e2e_{uuid.uuid4()}@test.com"
    password = "SecurePassword123!"
    print(f"Registering recruiter: {email}")
    register_resp = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    register_resp.raise_for_status()
    print("Registration successful.")

    # 2. Login
    print("Logging in...")
    login_resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    login_resp.raise_for_status()
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful, token retrieved.")

    # 3. Upload Resume
    print("Uploading resume_backend_engineer.pdf...")
    with open("tests/sample_resumes/resume_backend_engineer.pdf", "rb") as f:
        upload_resp = requests.post(
            f"{BASE_URL}/api/v1/resumes/",
            files={"file": ("resume_backend_engineer.pdf", f, "application/pdf")},
            headers=headers
        )
    upload_resp.raise_for_status()
    upload_task_id = upload_resp.json()["task_id"]
    print(f"Upload task started: {upload_task_id}")
    
    # Poll for candidate ingestion completion
    ingest_result = poll_task(upload_task_id, headers)
    print(f"Ingest result: {ingest_result}")
    candidate_id = ingest_result["candidate_id"]
    print(f"Ingestion successful. Candidate ID: {candidate_id}")

    # 4. Create Job
    print("Creating job...")
    job_payload = {
        "title": "Senior Python Backend Engineer",
        "description": "We are looking for a Senior Backend Engineer with extensive experience in Python, FastAPI, Docker, and PostgreSQL. Experience with background tasks via Celery and Redis is highly preferred.",
        "required_skills": ["python", "fastapi", "docker", "postgresql"],
        "preferred_skills": ["celery", "redis"]
    }
    job_resp = requests.post(
        f"{BASE_URL}/api/v1/jobs/",
        json=job_payload,
        headers=headers
    )
    job_resp.raise_for_status()
    job_id = job_resp.json()["job_id"]
    print(f"Job created successfully. Job ID: {job_id}")

    # 5. Run Match
    print("Submitting match request...")
    match_payload = {
        "job_id": job_id,
        "candidate_ids": [candidate_id],
        "weights": {
            "tfidf": 0.4,
            "bm25": 0.4,
            "skills": 0.2
        }
    }
    match_resp = requests.post(
        f"{BASE_URL}/api/v1/matches/",
        json=match_payload,
        headers=headers
    )
    match_resp.raise_for_status()
    match_task_id = match_resp.json()["task_id"]
    print(f"Match task submitted. Task ID: {match_task_id}")

    # Poll for match completion
    match_result = poll_task(match_task_id, headers)
    print("Match successful!")
    print("Result matches:")
    for match in match_result["matches"]:
        print(f"  - Candidate: {match['candidate_name']} ({match['candidate_email']})")
        print(f"    Final Score: {match['final_score']}")
        print(f"    TF-IDF: {match['tfidf_score']}, BM25: {match['bm25_score']}, Skill: {match['skill_score']}")
        print(f"    Explanation: {match['explanation_log']}")
        assert match['final_score'] > 0.0, "Score is zero!"

if __name__ == "__main__":
    run_e2e()

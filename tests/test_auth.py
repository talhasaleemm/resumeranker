import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.config import get_settings
from app.database import get_db
from app.main import app

async def override_get_db():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
    async with TestingSessionLocal() as session:
        yield session
    await engine.dispose()

@pytest.fixture(autouse=True)
def setup_db_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

def test_register_recruiter():
    app.state.limiter.enabled = False
    email = f"new_{uuid.uuid4()}@test.com"
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "securepassword123"
        })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert "id" in data
    assert data["is_active"] is True

def test_register_duplicate_email():
    app.state.limiter.enabled = False
    email = f"dup_{uuid.uuid4()}@test.com"
    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "securepassword123"
        })
        response = client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "securepassword123"
        })
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"

def test_login_success():
    app.state.limiter.enabled = False
    email = f"login_{uuid.uuid4()}@test.com"
    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "securepassword123"
        })
        response = client.post("/api/v1/auth/login", data={
            "username": email,
            "password": "securepassword123"
        })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_failure():
    app.state.limiter.enabled = False
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", data={
            "username": f"wrong_{uuid.uuid4()}@test.com",
            "password": "wrongpassword"
        })
    assert response.status_code == 401

def test_system_recruiter_cannot_login():
    app.state.limiter.enabled = False
    with TestClient(app) as client:
        # The system recruiter was created in the migration with email "system@resumeranker.local"
        response = client.post("/api/v1/auth/login", data={
            "username": "system@resumeranker.local",
            "password": "systempassword"
        })
    # Since its password hash is "!", any password should fail to verify
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

    # Also test that it cannot authenticate even if we force a token (to test get_current_active_recruiter)
    from app.services.auth_service import create_access_token
    token = create_access_token(data={"sub": "system@resumeranker.local"})
    
    # We must use an endpoint protected by get_current_active_recruiter
    with TestClient(app) as client:
        response = client.post("/api/v1/jobs/", json={"title": "foo", "description": "some long description here", "required_skills": []}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"

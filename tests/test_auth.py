import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_register_recruiter():
    email = f"new_{uuid.uuid4()}@test.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/register", json={
            "email": email,
            "password": "securepassword123"
        })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert "id" in data
    assert data["is_active"] is True

@pytest.mark.asyncio
async def test_register_duplicate_email():
    email = f"dup_{uuid.uuid4()}@test.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/auth/register", json={
            "email": email,
            "password": "securepassword123"
        })
        response = await ac.post("/api/v1/auth/register", json={
            "email": email,
            "password": "securepassword123"
        })
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"

@pytest.mark.asyncio
async def test_login_success():
    email = f"login_{uuid.uuid4()}@test.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/auth/register", json={
            "email": email,
            "password": "securepassword123"
        })
        response = await ac.post("/api/v1/auth/login", data={
            "username": email,
            "password": "securepassword123"
        })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_failure():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", data={
            "username": f"wrong_{uuid.uuid4()}@test.com",
            "password": "wrongpassword"
        })
    assert response.status_code == 401

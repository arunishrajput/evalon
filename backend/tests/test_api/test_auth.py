"""End-to-end auth flow: register, login, /me, refresh rotation (incl. reuse
detection), logout, and duplicate-registration rejection."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_creates_participant(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "supersecret123", "full_name": "Alice"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "participant"


async def test_register_duplicate_email_conflicts(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "email_taken"


async def test_login_returns_token_pair(client: AsyncClient):
    payload = {"email": "carol@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/login", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


async def test_login_wrong_password_rejected(client: AsyncClient):
    await client.post(
        "/auth/register", json={"email": "dave@example.com", "password": "supersecret123"}
    )
    resp = await client.post(
        "/auth/login", json={"email": "dave@example.com", "password": "wrongpassword"}
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "invalid_credentials"


async def test_me_requires_valid_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401

    resp = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


async def test_me_returns_current_user(client: AsyncClient):
    payload = {"email": "erin@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    login = await client.post("/auth/login", json=payload)
    access = login.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "erin@example.com"


async def test_refresh_rotates_and_rejects_reuse(client: AsyncClient):
    payload = {"email": "frank@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    login = await client.post("/auth/login", json=payload)
    refresh_token = login.json()["refresh_token"]

    first = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200
    assert first.json()["refresh_token"] != refresh_token

    reuse = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient):
    payload = {"email": "grace@example.com", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    login = await client.post("/auth/login", json=payload)
    refresh_token = login.json()["refresh_token"]

    logout = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401

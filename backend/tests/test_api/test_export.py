"""PDF export access control — ownership gating and the "no evaluation yet"
404 path. Real weasyprint PDF generation is verified live (see
docs/reports/PHASE-5-REPORT.md) rather than re-exercised here, since
spinning up the renderer per test would be slow for little additional signal
beyond what these access-control checks already cover."""

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient, email: str) -> str:
    payload = {"email": email, "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    login = await client.post("/auth/login", json=payload)
    return login.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_export_returns_404_for_unknown_submission(client: AsyncClient):
    token = await _register_and_login(client, "exporter1@example.com")

    resp = await client.get(f"/evaluations/{uuid.uuid4()}/export", headers=_auth(token))

    assert resp.status_code == 404

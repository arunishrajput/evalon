"""Hackathon CRUD, criteria (incl. weight-sum validation), participants, and
join-flow access control."""

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.database import async_session_factory
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient, email: str, *, as_admin: bool = False) -> str:
    payload = {"email": email, "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    if as_admin:
        async with async_session_factory() as session:
            await session.execute(update(User).where(User.email == email).values(role=UserRole.ADMIN))
            await session.commit()
    login = await client.post("/auth/login", json=payload)
    return login.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_create_hackathon_requires_admin(client: AsyncClient):
    participant_token = await _register_and_login(client, "part@example.com")
    resp = await client.post(
        "/hackathons", json={"title": "Should Fail"}, headers=_auth_headers(participant_token)
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "not_authorized"


async def test_create_and_get_hackathon(client: AsyncClient):
    admin_token = await _register_and_login(client, "admin@example.com", as_admin=True)
    create = await client.post(
        "/hackathons",
        json={"title": "AI Hackathon", "max_submissions": 10},
        headers=_auth_headers(admin_token),
    )
    assert create.status_code == 201
    hackathon_id = create.json()["id"]
    assert create.json()["status"] == "draft"

    get_resp = await client.get(f"/hackathons/{hackathon_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "AI Hackathon"


async def test_draft_hackathon_excluded_from_public_listing(client: AsyncClient):
    admin_token = await _register_and_login(client, "admin2@example.com", as_admin=True)
    await client.post("/hackathons", json={"title": "Draft One"}, headers=_auth_headers(admin_token))

    listing = await client.get("/hackathons")
    assert listing.json()["total"] == 0


async def test_criteria_weights_must_sum_to_one(client: AsyncClient):
    admin_token = await _register_and_login(client, "admin3@example.com", as_admin=True)
    create = await client.post(
        "/hackathons", json={"title": "Weighted"}, headers=_auth_headers(admin_token)
    )
    hackathon_id = create.json()["id"]

    bad = await client.put(
        f"/hackathons/{hackathon_id}/criteria",
        json={"criteria": [{"name": "Only One", "weight": 0.5}]},
        headers=_auth_headers(admin_token),
    )
    assert bad.status_code == 422

    good = await client.put(
        f"/hackathons/{hackathon_id}/criteria",
        json={
            "criteria": [
                {"name": "Code Quality", "weight": 0.4},
                {"name": "Innovation", "weight": 0.35},
                {"name": "Understanding", "weight": 0.25},
            ]
        },
        headers=_auth_headers(admin_token),
    )
    assert good.status_code == 200
    assert len(good.json()) == 3


async def test_only_owning_admin_can_modify_hackathon(client: AsyncClient):
    owner_token = await _register_and_login(client, "owner@example.com", as_admin=True)
    other_admin_token = await _register_and_login(client, "other@example.com", as_admin=True)

    create = await client.post(
        "/hackathons", json={"title": "Owned"}, headers=_auth_headers(owner_token)
    )
    hackathon_id = create.json()["id"]

    resp = await client.patch(
        f"/hackathons/{hackathon_id}",
        json={"title": "Hijacked"},
        headers=_auth_headers(other_admin_token),
    )
    assert resp.status_code == 403


async def test_join_flow(client: AsyncClient):
    admin_token = await _register_and_login(client, "admin4@example.com", as_admin=True)
    create = await client.post(
        "/hackathons", json={"title": "Joinable"}, headers=_auth_headers(admin_token)
    )
    hackathon_id = create.json()["id"]
    await client.patch(
        f"/hackathons/{hackathon_id}/status",
        json={"status": "active"},
        headers=_auth_headers(admin_token),
    )

    participant_token = await _register_and_login(client, "joiner@example.com")
    join = await client.post(
        f"/hackathons/{hackathon_id}/join", headers=_auth_headers(participant_token)
    )
    assert join.status_code == 201

    duplicate = await client.post(
        f"/hackathons/{hackathon_id}/join", headers=_auth_headers(participant_token)
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error_code"] == "already_joined"

    participants = await client.get(
        f"/hackathons/{hackathon_id}/participants", headers=_auth_headers(admin_token)
    )
    assert participants.status_code == 200
    assert len(participants.json()) == 1


async def test_cannot_join_draft_hackathon(client: AsyncClient):
    admin_token = await _register_and_login(client, "admin5@example.com", as_admin=True)
    create = await client.post(
        "/hackathons", json={"title": "Still Draft"}, headers=_auth_headers(admin_token)
    )
    hackathon_id = create.json()["id"]

    participant_token = await _register_and_login(client, "eager@example.com")
    resp = await client.post(
        f"/hackathons/{hackathon_id}/join", headers=_auth_headers(participant_token)
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "hackathon_not_active"


async def test_invalid_status_transition_rejected(client: AsyncClient):
    admin_token = await _register_and_login(client, "admin6@example.com", as_admin=True)
    create = await client.post(
        "/hackathons", json={"title": "Status Test"}, headers=_auth_headers(admin_token)
    )
    hackathon_id = create.json()["id"]

    resp = await client.patch(
        f"/hackathons/{hackathon_id}/status",
        json={"status": "finalized"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "invalid_status_transition"


async def test_finalize_requires_active_or_evaluating_status(client: AsyncClient):
    admin_token = await _register_and_login(client, "admin7@example.com", as_admin=True)
    create = await client.post(
        "/hackathons", json={"title": "Finalize Draft Test"}, headers=_auth_headers(admin_token)
    )
    hackathon_id = create.json()["id"]  # still draft — never activated

    resp = await client.post(f"/hackathons/{hackathon_id}/finalize", headers=_auth_headers(admin_token))

    assert resp.status_code == 409
    assert resp.json()["error_code"] == "invalid_status_transition"


async def test_finalize_transitions_to_finalized_status(client: AsyncClient):
    admin_token = await _register_and_login(client, "admin8@example.com", as_admin=True)
    create = await client.post(
        "/hackathons", json={"title": "Finalize Test"}, headers=_auth_headers(admin_token)
    )
    hackathon_id = create.json()["id"]
    await client.patch(
        f"/hackathons/{hackathon_id}/status", json={"status": "active"}, headers=_auth_headers(admin_token)
    )

    resp = await client.post(f"/hackathons/{hackathon_id}/finalize", headers=_auth_headers(admin_token))

    assert resp.status_code == 200
    assert resp.json()["status"] == "finalized"


async def test_only_owning_admin_can_finalize(client: AsyncClient):
    owner_token = await _register_and_login(client, "owner2@example.com", as_admin=True)
    other_token = await _register_and_login(client, "other2@example.com", as_admin=True)
    create = await client.post(
        "/hackathons", json={"title": "Owned Finalize"}, headers=_auth_headers(owner_token)
    )
    hackathon_id = create.json()["id"]
    await client.patch(
        f"/hackathons/{hackathon_id}/status", json={"status": "active"}, headers=_auth_headers(owner_token)
    )

    resp = await client.post(f"/hackathons/{hackathon_id}/finalize", headers=_auth_headers(other_token))

    assert resp.status_code == 403


async def test_list_submissions_requires_owning_admin(client: AsyncClient):
    owner_token = await _register_and_login(client, "owner3@example.com", as_admin=True)
    other_token = await _register_and_login(client, "other3@example.com", as_admin=True)
    create = await client.post(
        "/hackathons", json={"title": "Submissions List Test"}, headers=_auth_headers(owner_token)
    )
    hackathon_id = create.json()["id"]

    ok = await client.get(f"/hackathons/{hackathon_id}/submissions", headers=_auth_headers(owner_token))
    forbidden = await client.get(f"/hackathons/{hackathon_id}/submissions", headers=_auth_headers(other_token))

    assert ok.status_code == 200
    assert ok.json() == []
    assert forbidden.status_code == 403

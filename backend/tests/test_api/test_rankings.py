"""Ranking endpoints: finalization-gated visibility and the participant-
identity-hidden-until-finalized rule (spec Section 10)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.database import async_session_factory
from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.hackathon import Hackathon, HackathonStatus
from app.models.ranking import Ranking
from app.models.submission import Submission
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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_hackathon_with_ranked_submission(*, show_early: bool, finalized: bool) -> tuple[uuid.UUID, uuid.UUID]:
    async with async_session_factory() as db:
        admin = User(email=f"seed-admin-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x", role=UserRole.ADMIN)
        db.add(admin)
        await db.flush()
        participant = User(email=f"seed-part-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
        db.add(participant)
        await db.flush()

        hackathon = Hackathon(
            title="Ranking Visibility Test",
            admin_id=admin.id,
            status=HackathonStatus.EVALUATING,
            settings={"show_rankings_before_finalization": show_early},
        )
        db.add(hackathon)
        await db.flush()

        submission = Submission(
            hackathon_id=hackathon.id, user_id=participant.id, repo_url="https://github.com/x/y", repo_name="y"
        )
        db.add(submission)
        await db.flush()
        db.add(
            Evaluation(
                submission_id=submission.id, hackathon_id=hackathon.id,
                status=EvaluationStatus.COMPLETED, final_score=80.0, report={},
            )
        )
        await db.flush()
        db.add(
            Ranking(
                hackathon_id=hackathon.id, submission_id=submission.id, rank=1,
                percentile=0.0, normalized_score=80.0, finalized=finalized,
            )
        )
        await db.commit()
        return hackathon.id, submission.id


async def test_rankings_hidden_from_participant_before_finalization(client: AsyncClient):
    hackathon_id, _ = await _seed_hackathon_with_ranked_submission(show_early=False, finalized=False)
    token = await _register_and_login(client, "viewer1@example.com")

    resp = await client.get(f"/rankings/{hackathon_id}", headers=_auth(token))

    assert resp.status_code == 409
    assert resp.json()["error_code"] == "rankings_not_visible"


async def test_rankings_visible_when_show_early_setting_enabled(client: AsyncClient):
    hackathon_id, _ = await _seed_hackathon_with_ranked_submission(show_early=True, finalized=False)
    token = await _register_and_login(client, "viewer2@example.com")

    resp = await client.get(f"/rankings/{hackathon_id}", headers=_auth(token))

    assert resp.status_code == 200
    entries = resp.json()
    assert entries[0]["rank"] == 1
    assert entries[0]["participant_name"] is None  # identity hidden until finalized


async def test_rankings_visible_and_identified_once_finalized(client: AsyncClient):
    hackathon_id, _ = await _seed_hackathon_with_ranked_submission(show_early=False, finalized=True)
    token = await _register_and_login(client, "viewer3@example.com")

    resp = await client.get(f"/rankings/{hackathon_id}", headers=_auth(token))

    assert resp.status_code == 200
    entries = resp.json()
    assert entries[0]["participant_name"] is not None


async def test_admin_always_sees_rankings_regardless_of_gate(client: AsyncClient):
    hackathon_id, _ = await _seed_hackathon_with_ranked_submission(show_early=False, finalized=False)
    admin_token = await _register_and_login(client, "adminviewer@example.com", as_admin=True)

    resp = await client.get(f"/rankings/{hackathon_id}", headers=_auth(admin_token))

    assert resp.status_code == 200


async def test_my_ranking_returns_404_when_not_ranked(client: AsyncClient):
    hackathon_id, _ = await _seed_hackathon_with_ranked_submission(show_early=True, finalized=False)
    token = await _register_and_login(client, "unranked@example.com")

    resp = await client.get(f"/rankings/{hackathon_id}/me", headers=_auth(token))

    assert resp.status_code == 404

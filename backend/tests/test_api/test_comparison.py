"""Side-by-side comparison endpoint: input validation (max 3, valid UUIDs)
and the actual comparison payload shape against seeded evaluations."""

import uuid

import pytest
from httpx import AsyncClient

from app.database import async_session_factory
from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.hackathon import Hackathon
from app.models.submission import Submission
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient, email: str) -> str:
    payload = {"email": email, "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    login = await client.post("/auth/login", json=payload)
    return login.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_two_evaluated_submissions() -> tuple[uuid.UUID, list[uuid.UUID]]:
    async with async_session_factory() as db:
        admin = User(email=f"cmp-admin-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
        db.add(admin)
        await db.flush()
        hackathon = Hackathon(title="Comparison Test", admin_id=admin.id)
        db.add(hackathon)
        await db.flush()

        submission_ids = []
        for score in (70.0, 90.0):
            user = User(email=f"cmp-user-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x", full_name="Cmp User")
            db.add(user)
            await db.flush()
            submission = Submission(
                hackathon_id=hackathon.id, user_id=user.id, repo_url="https://github.com/x/y",
                repo_name="y", tech_stack=["Python"],
            )
            db.add(submission)
            await db.flush()
            db.add(
                Evaluation(
                    submission_id=submission.id, hackathon_id=hackathon.id, status=EvaluationStatus.COMPLETED,
                    final_score=score,
                    report={
                        "strengths": ["Clean code"], "weaknesses": ["No tests"],
                        "scores": {"by_criterion": [{"criterion": "Code Quality", "score": score, "weight": 1.0, "agent_id": "code_quality"}]},
                        "agent_results": [{"agent_id": "code_quality", "top_evidence": ["finding 1", "finding 2"]}],
                    },
                )
            )
            submission_ids.append(submission.id)
        await db.commit()
        return hackathon.id, submission_ids


async def test_compare_returns_requested_submissions(client: AsyncClient):
    hackathon_id, submission_ids = await _seed_two_evaluated_submissions()
    token = await _register_and_login(client, "comparer@example.com")

    ids_param = ",".join(str(s) for s in submission_ids)
    resp = await client.get(f"/compare/{hackathon_id}?submission_ids={ids_param}", headers=_auth(token))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["submissions"]) == 2
    scores = {s["submission_id"]: float(s["final_score"]) for s in body["submissions"]}
    assert set(scores.values()) == {70.0, 90.0}
    for submission in body["submissions"]:
        assert submission["scores_by_criterion"][0]["top_evidence"] == ["finding 1", "finding 2"]


async def test_compare_rejects_more_than_three_ids(client: AsyncClient):
    token = await _register_and_login(client, "toomany@example.com")
    ids_param = ",".join(str(uuid.uuid4()) for _ in range(4))

    resp = await client.get(f"/compare/{uuid.uuid4()}?submission_ids={ids_param}", headers=_auth(token))

    assert resp.status_code == 409
    assert resp.json()["error_code"] == "too_many_submissions"


async def test_compare_rejects_invalid_uuid(client: AsyncClient):
    token = await _register_and_login(client, "baduuid@example.com")

    resp = await client.get(f"/compare/{uuid.uuid4()}?submission_ids=not-a-uuid", headers=_auth(token))

    assert resp.status_code == 409
    assert resp.json()["error_code"] == "invalid_submission_ids"


async def test_compare_returns_404_when_no_matching_submissions(client: AsyncClient):
    token = await _register_and_login(client, "nomatch@example.com")

    resp = await client.get(f"/compare/{uuid.uuid4()}?submission_ids={uuid.uuid4()}", headers=_auth(token))

    assert resp.status_code == 404

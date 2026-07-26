"""recompute_rankings_for_hackathon against a real Postgres DB: upserts
Ranking rows correctly, and — critically — never reshuffles an already
finalized leaderboard."""

import uuid

import pytest
from sqlalchemy import select

from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.hackathon import Hackathon
from app.models.ranking import Ranking
from app.models.submission import Submission
from app.models.user import User
from app.scoring.ranking_service import recompute_rankings_for_hackathon

pytestmark = pytest.mark.asyncio


async def _make_hackathon(db) -> Hackathon:
    admin = User(email=f"admin-{uuid.uuid4().hex[:8]}@test.com", hashed_password="x")
    db.add(admin)
    await db.flush()
    hackathon = Hackathon(title="Ranking Test", admin_id=admin.id)
    db.add(hackathon)
    await db.flush()
    return hackathon


async def _make_scored_submission(db, hackathon, score) -> Submission:
    user = User(email=f"user-{uuid.uuid4().hex[:8]}@test.com", hashed_password="x")
    db.add(user)
    await db.flush()
    submission = Submission(hackathon_id=hackathon.id, user_id=user.id, repo_url="https://github.com/x/y")
    db.add(submission)
    await db.flush()
    db.add(
        Evaluation(
            submission_id=submission.id, hackathon_id=hackathon.id,
            status=EvaluationStatus.COMPLETED, final_score=score, report={},
        )
    )
    await db.flush()
    return submission


async def test_recompute_creates_ranking_rows(db_session):
    hackathon = await _make_hackathon(db_session)
    await _make_scored_submission(db_session, hackathon, 80.0)
    await _make_scored_submission(db_session, hackathon, 60.0)
    await db_session.commit()

    rankings = await recompute_rankings_for_hackathon(db_session, hackathon.id)
    await db_session.commit()

    assert len(rankings) == 2
    assert {r.rank for r in rankings} == {1, 2}


async def test_recompute_is_idempotent_reuses_existing_rows(db_session):
    hackathon = await _make_hackathon(db_session)
    await _make_scored_submission(db_session, hackathon, 80.0)
    await db_session.commit()

    await recompute_rankings_for_hackathon(db_session, hackathon.id)
    await db_session.commit()
    first_count = len(list(await db_session.scalars(select(Ranking).where(Ranking.hackathon_id == hackathon.id))))

    await recompute_rankings_for_hackathon(db_session, hackathon.id)
    await db_session.commit()
    second_count = len(list(await db_session.scalars(select(Ranking).where(Ranking.hackathon_id == hackathon.id))))

    assert first_count == second_count == 1


async def test_finalized_rankings_are_not_reshuffled(db_session):
    hackathon = await _make_hackathon(db_session)
    sub_low = await _make_scored_submission(db_session, hackathon, 40.0)
    await db_session.commit()

    rankings = await recompute_rankings_for_hackathon(db_session, hackathon.id)
    for r in rankings:
        r.finalized = True
    await db_session.commit()

    # A new, higher-scoring submission arrives after finalization.
    await _make_scored_submission(db_session, hackathon, 99.0)
    await db_session.commit()

    result = await recompute_rankings_for_hackathon(db_session, hackathon.id)
    await db_session.commit()

    # Untouched — still just the one finalized entry, not recomputed to include the new submission.
    assert len(result) == 1
    assert result[0].submission_id == sub_low.id
    assert result[0].rank == 1

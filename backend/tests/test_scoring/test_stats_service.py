"""Hackathon stats computation against a real Postgres DB: pipeline-stage
bucketing, score histogram (incl. the score=100 edge case), tech stack
frequency, and top-5 preview."""

import uuid

from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.hackathon import Hackathon
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.scoring.stats_service import _bucket_for_score, compute_hackathon_stats, upsert_hackathon_stats

# No module-level `pytestmark = pytest.mark.asyncio` — this file mixes sync
# unit tests (_bucket_for_score) with async DB-integration tests, and
# pytest.ini's `asyncio_mode = auto` already detects async tests without it.


async def _make_hackathon(db) -> Hackathon:
    admin = User(email=f"admin-{uuid.uuid4().hex[:8]}@test.com", hashed_password="x")
    db.add(admin)
    await db.flush()
    hackathon = Hackathon(title="Stats Test", admin_id=admin.id)
    db.add(hackathon)
    await db.flush()
    return hackathon


async def _make_submission(db, hackathon, status, score=None, tech_stack=None) -> Submission:
    user = User(email=f"user-{uuid.uuid4().hex[:8]}@test.com", hashed_password="x")
    db.add(user)
    await db.flush()
    submission = Submission(
        hackathon_id=hackathon.id, user_id=user.id, repo_url="https://github.com/x/y",
        status=status, tech_stack=tech_stack or [], repo_name=f"repo-{uuid.uuid4().hex[:4]}",
    )
    db.add(submission)
    await db.flush()
    if score is not None:
        db.add(
            Evaluation(
                submission_id=submission.id, hackathon_id=hackathon.id,
                status=EvaluationStatus.COMPLETED, final_score=score, report={},
            )
        )
        await db.flush()
    return submission


def test_bucket_for_score_100_falls_in_last_bucket_not_out_of_range():
    assert _bucket_for_score(100.0) == "90-100"


def test_bucket_for_score_boundaries():
    assert _bucket_for_score(0.0) == "0-10"
    assert _bucket_for_score(9.99) == "0-10"
    assert _bucket_for_score(10.0) == "10-20"
    assert _bucket_for_score(55.5) == "50-60"


async def test_compute_hackathon_stats_pipeline_buckets(db_session):
    hackathon = await _make_hackathon(db_session)
    await _make_submission(db_session, hackathon, SubmissionStatus.COMPLETED, score=80.0, tech_stack=["Python"])
    await _make_submission(db_session, hackathon, SubmissionStatus.ANALYZING)
    await _make_submission(db_session, hackathon, SubmissionStatus.PENDING)
    await _make_submission(db_session, hackathon, SubmissionStatus.FAILED)
    await db_session.commit()

    stats = await compute_hackathon_stats(db_session, hackathon.id)

    assert stats["total_submissions"] == 4
    assert stats["evaluations_completed"] == 1
    assert stats["evaluations_in_progress"] == 1
    assert stats["evaluations_queued"] == 1
    assert stats["evaluations_failed"] == 1
    assert stats["score_distribution"]["80-90"] == 1
    assert stats["avg_score"] == 80.0
    assert stats["tech_stack_frequency"] == {"Python": 1}


async def test_compute_hackathon_stats_empty_hackathon_has_no_avg_score(db_session):
    hackathon = await _make_hackathon(db_session)
    await db_session.commit()

    stats = await compute_hackathon_stats(db_session, hackathon.id)

    assert stats["total_submissions"] == 0
    assert stats["avg_score"] is None
    assert stats["top5_preview"] == []


async def test_top5_preview_capped_and_sorted(db_session):
    hackathon = await _make_hackathon(db_session)
    for score in (10.0, 90.0, 50.0, 70.0, 30.0, 60.0):
        await _make_submission(db_session, hackathon, SubmissionStatus.COMPLETED, score=score)
    await db_session.commit()

    stats = await compute_hackathon_stats(db_session, hackathon.id)

    assert len(stats["top5_preview"]) == 5
    assert [p["score"] for p in stats["top5_preview"]] == [90.0, 70.0, 60.0, 50.0, 30.0]
    assert stats["top5_preview"][0]["rank"] == 1


async def test_upsert_hackathon_stats_creates_then_updates_same_row(db_session):
    hackathon = await _make_hackathon(db_session)
    await _make_submission(db_session, hackathon, SubmissionStatus.COMPLETED, score=50.0)
    await db_session.commit()

    first = await upsert_hackathon_stats(db_session, hackathon.id)
    first_id = first.id
    await db_session.commit()

    await _make_submission(db_session, hackathon, SubmissionStatus.COMPLETED, score=70.0)
    await db_session.commit()

    second = await upsert_hackathon_stats(db_session, hackathon.id)
    await db_session.commit()

    assert second.id == first_id  # same row updated, not duplicated
    assert second.total_submissions == 2

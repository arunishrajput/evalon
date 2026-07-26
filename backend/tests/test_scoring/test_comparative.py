"""Comparative Intelligence Agent (spec Section 13's explicit "UNIT TESTS —
Comparative Agent" list): percentile calculation across pool sizes,
sufficient_data gating below the minimum pool size, tech stack comparison,
and the template-based summary across every tier."""

import uuid

import pytest

from app.agents.comparative import ComparativeAgent
from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.hackathon import Hackathon
from app.models.submission import Submission
from app.models.user import User
from app.pipeline.context_builder import RepoContext
from app.pipeline.static_analysis import StaticAnalysisReport

# No module-level `pytestmark = pytest.mark.asyncio` — this file mixes async
# DB-integration tests with a sync parametrized test, and pytest.ini's
# `asyncio_mode = auto` already detects async tests without it.


async def _make_hackathon(db) -> Hackathon:
    admin = User(email=f"admin-{uuid.uuid4().hex[:8]}@test.com", hashed_password="x")
    db.add(admin)
    await db.flush()
    hackathon = Hackathon(title="Test Hackathon", admin_id=admin.id)
    db.add(hackathon)
    await db.flush()
    return hackathon


async def _make_evaluated_submission(db, hackathon, score, by_criterion=None, tech_stack=None) -> Submission:
    user = User(email=f"user-{uuid.uuid4().hex[:8]}@test.com", hashed_password="x")
    db.add(user)
    await db.flush()
    submission = Submission(
        hackathon_id=hackathon.id, user_id=user.id, repo_url="https://github.com/x/y", tech_stack=tech_stack or []
    )
    db.add(submission)
    await db.flush()
    db.add(
        Evaluation(
            submission_id=submission.id,
            hackathon_id=hackathon.id,
            status=EvaluationStatus.COMPLETED,
            final_score=score,
            report={"scores": {"by_criterion": by_criterion or []}},
        )
    )
    await db.flush()
    return submission


def _repo_context(submission_id: str, hackathon_id: str, tech_stack: list[str]) -> RepoContext:
    return RepoContext(
        submission_id=submission_id,
        hackathon_id=hackathon_id,
        repo_url="https://github.com/x/y",
        repo_name="y",
        repo_description=None,
        project_type="Python",
        primary_language="Python",
        language_breakdown={},
        tech_stack=tech_stack,
        dependency_manifest={},
        readme_content=None,
        readme_quality_score=0,
        file_count=0,
        file_paths=[],
        code_samples=[],
        static_analysis=StaticAnalysisReport(),
    )


async def test_insufficient_data_below_min_pool_size(db_session):
    hackathon = await _make_hackathon(db_session)
    await _make_evaluated_submission(db_session, hackathon, 70.0)
    await db_session.commit()

    this_id = str(uuid.uuid4())
    result = await ComparativeAgent().evaluate(
        repo_context=_repo_context(this_id, str(hackathon.id), []),
        submission_id=this_id,
        hackathon_id=str(hackathon.id),
        db=db_session,
        this_score=80.0,
        this_criterion_scores=[],
    )

    assert result.sufficient_data is False
    assert result.total_submissions_in_pool == 2  # 1 other + self
    assert "will be available" in result.summary


async def test_percentile_and_rank_with_sufficient_pool(db_session):
    hackathon = await _make_hackathon(db_session)
    for score in (40.0, 60.0, 80.0):
        await _make_evaluated_submission(db_session, hackathon, score)
    await db_session.commit()

    this_id = str(uuid.uuid4())
    # this_score=70 -> beats 40 and 60, loses to 80: rank 2 of 4, percentile 50%
    result = await ComparativeAgent().evaluate(
        repo_context=_repo_context(this_id, str(hackathon.id), []),
        submission_id=this_id,
        hackathon_id=str(hackathon.id),
        db=db_session,
        this_score=70.0,
        this_criterion_scores=[],
    )

    assert result.sufficient_data is True
    assert result.total_submissions_in_pool == 4
    assert result.rank_in_pool == 2
    assert result.percentile == 50.0
    assert result.pool_average_score == round((40 + 60 + 80 + 70) / 4, 1)


async def test_tech_stack_comparison_shared_and_unique(db_session):
    hackathon = await _make_hackathon(db_session)
    await _make_evaluated_submission(db_session, hackathon, 50.0, tech_stack=["React", "Python"])
    await _make_evaluated_submission(db_session, hackathon, 55.0, tech_stack=["React"])
    await _make_evaluated_submission(db_session, hackathon, 60.0, tech_stack=["Vue"])
    await db_session.commit()

    this_id = str(uuid.uuid4())
    result = await ComparativeAgent().evaluate(
        repo_context=_repo_context(this_id, str(hackathon.id), ["React", "LangGraph"]),
        submission_id=this_id,
        hackathon_id=str(hackathon.id),
        db=db_session,
        this_score=65.0,
        this_criterion_scores=[],
    )

    shared_techs = {s["tech"]: s["count"] for s in result.shared_tech_stacks}
    assert shared_techs == {"React": 2}
    unique_techs = {u["tech"] for u in result.unique_tech_stacks}
    assert unique_techs == {"LangGraph"}


async def test_criterion_comparisons_use_pool_stored_reports(db_session):
    hackathon = await _make_hackathon(db_session)
    for score in (50.0, 60.0, 70.0):
        await _make_evaluated_submission(
            db_session, hackathon, score, by_criterion=[{"criterion": "Code Quality", "score": score}]
        )
    await db_session.commit()

    this_id = str(uuid.uuid4())
    result = await ComparativeAgent().evaluate(
        repo_context=_repo_context(this_id, str(hackathon.id), []),
        submission_id=this_id,
        hackathon_id=str(hackathon.id),
        db=db_session,
        this_score=80.0,
        this_criterion_scores=[{"criterion": "Code Quality", "score": 90.0}],
    )

    assert len(result.criterion_comparisons) == 1
    comparison = result.criterion_comparisons[0]
    assert comparison["criterion"] == "Code Quality"
    assert comparison["your_score"] == 90.0
    assert comparison["pool_average"] == 60.0
    assert comparison["percentile"] == 100.0  # beats all 3 pool scores


@pytest.mark.parametrize(
    "percentile,expected_fragment",
    [
        (95, "top performer"),
        (80, "strong performer"),
        (60, "above-average performer"),
        (30, "below-average performer"),
        (10, "developing submission"),
    ],
)
def test_generate_summary_covers_every_tier(percentile, expected_fragment):
    summary = ComparativeAgent._generate_summary(rank=3, total=10, percentile=percentile)
    assert expected_fragment in summary
    assert "#3 out of 10" in summary

"""pgvector similarity search against a real Postgres/pgvector instance —
proves cosine-distance ordering actually works, not just that the query
doesn't crash."""

import uuid

from app.embedding.retriever import DEFAULT_TOP_K, has_embeddings, retrieve_top_chunks
from app.models.hackathon import Hackathon
from app.models.repo_embedding import RepoEmbedding
from app.models.submission import Submission
from app.models.user import User

EMBEDDING_DIM = 768


def _vector(x: float, y: float = 0.0) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = x
    vec[1] = y
    return vec


async def _seed_submission(db) -> uuid.UUID:
    admin = User(email=f"admin-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
    db.add(admin)
    await db.flush()
    hackathon = Hackathon(title="Retriever Test", admin_id=admin.id)
    db.add(hackathon)
    await db.flush()
    user = User(email=f"user-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
    db.add(user)
    await db.flush()
    submission = Submission(hackathon_id=hackathon.id, user_id=user.id, repo_url="https://github.com/x/y", repo_name="y")
    db.add(submission)
    await db.flush()
    await db.commit()
    return submission.id


async def test_has_embeddings_false_then_true(db_session):
    submission_id = await _seed_submission(db_session)
    assert await has_embeddings(db_session, submission_id) is False

    db_session.add(
        RepoEmbedding(submission_id=submission_id, chunk_type="readme", chunk_content="hi", embedding=_vector(1.0))
    )
    await db_session.commit()

    assert await has_embeddings(db_session, submission_id) is True


async def test_retrieve_top_chunks_orders_by_cosine_similarity(db_session):
    submission_id = await _seed_submission(db_session)
    # query direction is (1, 0); "near" is a small angle away, "mid" is 45
    # degrees, "far" points the opposite direction entirely.
    db_session.add_all(
        [
            RepoEmbedding(submission_id=submission_id, chunk_type="code", chunk_content="near", embedding=_vector(1.0, 0.1)),
            RepoEmbedding(submission_id=submission_id, chunk_type="code", chunk_content="mid", embedding=_vector(1.0, 1.0)),
            RepoEmbedding(submission_id=submission_id, chunk_type="code", chunk_content="far", embedding=_vector(-1.0, 0.0)),
        ]
    )
    await db_session.commit()

    results = await retrieve_top_chunks(db_session, submission_id, _vector(1.0, 0.0), k=3)

    assert [r.chunk_content for r in results] == ["near", "mid", "far"]


async def test_retrieve_top_chunks_respects_k_limit(db_session):
    submission_id = await _seed_submission(db_session)
    db_session.add_all(
        [
            RepoEmbedding(
                submission_id=submission_id, chunk_type="code", chunk_content=f"chunk-{i}", embedding=_vector(1.0, float(i))
            )
            for i in range(DEFAULT_TOP_K + 3)
        ]
    )
    await db_session.commit()

    results = await retrieve_top_chunks(db_session, submission_id, _vector(1.0, 0.0))

    assert len(results) == DEFAULT_TOP_K


async def test_retrieve_top_chunks_scoped_to_submission(db_session):
    submission_id = await _seed_submission(db_session)
    other_submission_id = await _seed_submission(db_session)
    db_session.add_all(
        [
            RepoEmbedding(submission_id=submission_id, chunk_type="code", chunk_content="mine", embedding=_vector(1.0)),
            RepoEmbedding(submission_id=other_submission_id, chunk_type="code", chunk_content="theirs", embedding=_vector(1.0)),
        ]
    )
    await db_session.commit()

    results = await retrieve_top_chunks(db_session, submission_id, _vector(1.0, 0.0))

    assert [r.chunk_content for r in results] == ["mine"]

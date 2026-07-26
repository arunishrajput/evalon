"""embed_and_store_chunks: acquires the embedding lock once for the whole
batch, stores rows keyed to the right submission, and replaces (not
accumulates) on a re-run — e.g. a retried evaluation."""

import uuid

from sqlalchemy import select

from app.embedding.chunker import Chunk
from app.embedding.embedder import embed_and_store_chunks
from app.models.hackathon import Hackathon
from app.models.repo_embedding import RepoEmbedding
from app.models.submission import Submission
from app.models.user import User


class FakeEmbedLLM:
    def __init__(self):
        self.call_count = 0

    async def embed(self, text: str) -> list[float]:
        self.call_count += 1
        vec = [0.0] * 768
        vec[0] = float(len(text))
        return vec


async def _seed_submission(db) -> uuid.UUID:
    admin = User(email=f"admin-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
    db.add(admin)
    await db.flush()
    hackathon = Hackathon(title="Embedder Test", admin_id=admin.id)
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


async def test_embed_and_store_chunks_persists_all_rows(db_session, model_queue, stub_model_load):
    submission_id = await _seed_submission(db_session)
    chunks = [
        Chunk(chunk_type="readme", content="hello"),
        Chunk(chunk_type="code", content="def f(): pass", metadata={"file": "a.py"}),
    ]

    count = await embed_and_store_chunks(
        db=db_session, llm=FakeEmbedLLM(), model_queue=model_queue, submission_id=str(submission_id), chunks=chunks
    )
    await db_session.commit()

    assert count == 2
    rows = list(await db_session.scalars(select(RepoEmbedding).where(RepoEmbedding.submission_id == submission_id)))
    assert {r.chunk_type for r in rows} == {"readme", "code"}
    code_row = next(r for r in rows if r.chunk_type == "code")
    assert code_row.chunk_metadata == {"file": "a.py"}


async def test_embed_and_store_chunks_replaces_prior_run(db_session, model_queue, stub_model_load):
    submission_id = await _seed_submission(db_session)

    await embed_and_store_chunks(
        db=db_session, llm=FakeEmbedLLM(), model_queue=model_queue, submission_id=str(submission_id),
        chunks=[Chunk(chunk_type="readme", content="v1")],
    )
    await db_session.commit()

    await embed_and_store_chunks(
        db=db_session, llm=FakeEmbedLLM(), model_queue=model_queue, submission_id=str(submission_id),
        chunks=[Chunk(chunk_type="readme", content="v2")],
    )
    await db_session.commit()

    rows = list(await db_session.scalars(select(RepoEmbedding).where(RepoEmbedding.submission_id == submission_id)))
    assert len(rows) == 1
    assert rows[0].chunk_content == "v2"


async def test_embed_and_store_chunks_empty_list_is_a_noop(db_session, model_queue, stub_model_load):
    submission_id = await _seed_submission(db_session)

    count = await embed_and_store_chunks(
        db=db_session, llm=FakeEmbedLLM(), model_queue=model_queue, submission_id=str(submission_id), chunks=[]
    )

    assert count == 0
    rows = list(await db_session.scalars(select(RepoEmbedding).where(RepoEmbedding.submission_id == submission_id)))
    assert rows == []

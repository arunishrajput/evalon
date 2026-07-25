"""Importing this package registers every ORM model on the shared declarative
Base — required so that string-based relationship() forward references across
model files resolve correctly, and so Alembic's autogenerate can see the full
schema."""

from app.models.agent_result import AgentResult
from app.models.chat import ChatMessage, ChatSession
from app.models.criterion import Criterion
from app.models.evaluation import Evaluation
from app.models.hackathon import Hackathon, HackathonParticipant, HackathonStats
from app.models.ranking import Ranking
from app.models.repo_embedding import RepoEmbedding
from app.models.submission import Submission
from app.models.user import User

__all__ = [
    "AgentResult",
    "ChatMessage",
    "ChatSession",
    "Criterion",
    "Evaluation",
    "Hackathon",
    "HackathonParticipant",
    "HackathonStats",
    "Ranking",
    "RepoEmbedding",
    "Submission",
    "User",
]

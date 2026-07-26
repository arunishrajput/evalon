"""Maps agent_id -> agent class for the three sequential LLM agents.
Comparative is intentionally excluded — it has a different constructor
signature (no LLMProvider) and runs outside the model-lock-guarded portion
of the graph."""

from app.agents.base import BaseEvaluator
from app.agents.code_quality import CodeQualityAgent
from app.agents.innovation import InnovationAgent
from app.agents.repo_understanding import RepoUnderstandingAgent

AGENT_REGISTRY: dict[str, type[BaseEvaluator]] = {
    RepoUnderstandingAgent.agent_id: RepoUnderstandingAgent,
    CodeQualityAgent.agent_id: CodeQualityAgent,
    InnovationAgent.agent_id: InnovationAgent,
}

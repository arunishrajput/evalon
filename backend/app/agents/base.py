"""Agent interface (spec Section 8). All agents use qwen2.5-coder:7b via
LLMProvider, have a hard 90s timeout, and use the model lock acquired once
at the pipeline level (never acquired by an individual agent)."""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, Field

from app.pipeline.context_builder import RepoContext


class EvidenceItem(BaseModel):
    finding: str
    impact: str = ""
    file_ref: str = ""


class AgentResult(BaseModel):
    agent_id: str
    score_raw: float = Field(ge=0, le=100, default=50.0)
    confidence: float = Field(ge=0, le=1, default=0.5)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    top_evidence: list[str] = Field(default_factory=list)  # top 2 evidence strings for tooltip display
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    reasoning: str = ""
    abstained: bool = False
    abstain_reason: str | None = None
    fallback_used: bool = False
    # Structured extras beyond the persisted AgentResult DB columns (e.g.
    # repo_understanding's project_goals/architecture_pattern, consumed by
    # the Innovation Agent and the report generator within the SAME graph
    # run). Not persisted to agent_results — transient, in-memory only.
    details: dict = Field(default_factory=dict)

    @classmethod
    def create_abstained(cls, agent_id: str, reason: str, fallback_used: bool = False) -> "AgentResult":
        # NOTE: the spec's pseudocode names this classmethod `abstained`, which
        # collides with the `abstained: bool` field of the same name and would
        # break Pydantic's model construction (the classmethod would overwrite
        # the field's default in the class namespace). Renamed to avoid that.
        return cls(
            agent_id=agent_id,
            score_raw=50.0,
            confidence=0.0,
            evidence=[],
            top_evidence=[],
            strengths=[],
            weaknesses=[],
            reasoning="",
            abstained=True,
            abstain_reason=reason,
            fallback_used=fallback_used,
        )


class BaseEvaluator(ABC):
    agent_id: ClassVar[str]
    agent_name: ClassVar[str]
    TIMEOUT_SECONDS: ClassVar[int] = 90

    def __init__(self, llm) -> None:  # llm: LLMProvider, typed loosely to avoid a circular import
        self.llm = llm

    @abstractmethod
    async def evaluate(self, repo_context: RepoContext, **kwargs) -> AgentResult: ...

    async def safe_evaluate(self, repo_context: RepoContext, **kwargs) -> AgentResult:
        """Enforces the hard 90s timeout uniformly for every agent. Does NOT
        catch exceptions — that's the graph node's job (spec Section 7's
        resilience pattern), so failures are handled identically regardless
        of which agent raised them."""
        return await asyncio.wait_for(self.evaluate(repo_context, **kwargs), timeout=self.TIMEOUT_SECONDS)


def parse_llm_json(raw: str) -> dict:
    """Ollama's JSON mode occasionally wraps output in markdown fences despite
    instructions; strip those before parsing. Raises ValueError (caught by
    the generic node-level exception handler) on genuinely malformed output."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc


def clamp_score(value) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 50.0


def clamp_confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5

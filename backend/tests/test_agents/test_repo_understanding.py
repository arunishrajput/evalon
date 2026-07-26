"""Repository Understanding Agent: JSON parsing into AgentResult, top_evidence
fallback, and the `details` payload carried forward for the Innovation Agent."""

import json

import pytest

from app.agents.repo_understanding import RepoUnderstandingAgent
from tests.test_agents.conftest import FakeLLM

pytestmark = pytest.mark.asyncio

_VALID_RESPONSE = json.dumps(
    {
        "project_goals": "Automate invoice reconciliation",
        "target_audience": "Bookkeepers",
        "technical_approach": "Fuzzy matching on CSV bank statements",
        "architecture_pattern": "Simple monolith",
        "key_technologies": ["Flask", "pandas"],
        "demo_maturity": "demo-ready",
        "score_raw": 68,
        "confidence": 0.75,
        "evidence": [{"finding": "README describes the algorithm", "impact": "Shows understanding", "file_ref": "README.md"}],
        "top_evidence": ["README describes the algorithm"],
        "strengths": ["Clear problem statement"],
        "weaknesses": ["No accuracy metric"],
        "reasoning": "The README is thorough.",
    }
)


async def test_evaluate_parses_full_response(repo_context):
    agent = RepoUnderstandingAgent(FakeLLM(response=_VALID_RESPONSE))
    result = await agent.evaluate(repo_context)

    assert result.agent_id == "repo_understanding"
    assert result.score_raw == 68.0
    assert result.confidence == 0.75
    assert result.abstained is False
    assert result.details["architecture_pattern"] == "Simple monolith"
    assert result.details["demo_maturity"] == "demo-ready"


async def test_evaluate_derives_top_evidence_when_missing(repo_context):
    data = json.loads(_VALID_RESPONSE)
    del data["top_evidence"]
    agent = RepoUnderstandingAgent(FakeLLM(response=json.dumps(data)))

    result = await agent.evaluate(repo_context)

    assert result.top_evidence == ["README describes the algorithm"]


async def test_evaluate_clamps_out_of_range_score(repo_context):
    data = json.loads(_VALID_RESPONSE)
    data["score_raw"] = 500
    agent = RepoUnderstandingAgent(FakeLLM(response=json.dumps(data)))

    result = await agent.evaluate(repo_context)

    assert result.score_raw == 100.0


async def test_evaluate_raises_value_error_on_malformed_json(repo_context):
    agent = RepoUnderstandingAgent(FakeLLM(response="not json"))
    with pytest.raises(ValueError):
        await agent.evaluate(repo_context)

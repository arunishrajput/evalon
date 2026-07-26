"""Innovation Agent: consumes the Repository Understanding Agent's `details`
as input (spec Section 8, Agent 3), and degrades gracefully to repo_context
data when understanding is missing or abstained."""

import json

import pytest

from app.agents.base import AgentResult
from app.agents.innovation import InnovationAgent
from tests.test_agents.conftest import FakeLLM

pytestmark = pytest.mark.asyncio

_VALID_RESPONSE = json.dumps(
    {
        "score_raw": 74,
        "confidence": 0.6,
        "problem_originality_notes": "Underexplored problem space.",
        "solution_creativity_notes": "Novel inversion of a common technique.",
        "technical_sophistication_notes": "Combines two approaches.",
        "execution_quality_notes": "Demo-ready.",
        "evidence": [{"finding": "Novel use of X", "impact": "Distinguishes the project", "file_ref": "README.md"}],
        "top_evidence": ["Novel use of X"],
        "strengths": ["Genuinely novel framing"],
        "weaknesses": ["Limited evaluation"],
        "reasoning": "Scores above baseline for originality.",
    }
)


async def test_evaluate_uses_understanding_details_in_prompt(repo_context):
    understanding = AgentResult(
        agent_id="repo_understanding",
        score_raw=70,
        details={
            "project_goals": "Solve X",
            "technical_approach": "Approach Y",
            "architecture_pattern": "Microservices",
            "key_technologies": ["Redis"],
            "demo_maturity": "demo-ready",
        },
    )
    llm = FakeLLM(response=_VALID_RESPONSE)
    agent = InnovationAgent(llm)

    result = await agent.evaluate(repo_context, understanding=understanding)

    assert "Solve X" in llm.last_prompt
    assert "Microservices" in llm.last_prompt
    assert result.score_raw == 74.0
    assert result.details["problem_originality_notes"] == "Underexplored problem space."


async def test_evaluate_degrades_gracefully_when_understanding_missing(repo_context):
    llm = FakeLLM(response=_VALID_RESPONSE)
    agent = InnovationAgent(llm)

    result = await agent.evaluate(repo_context, understanding=None)

    assert "Not determined" in llm.last_prompt
    assert result.score_raw == 74.0  # still produces a real result


async def test_evaluate_degrades_gracefully_when_understanding_abstained(repo_context):
    abstained_understanding = AgentResult.create_abstained("repo_understanding", "model down")
    llm = FakeLLM(response=_VALID_RESPONSE)
    agent = InnovationAgent(llm)

    result = await agent.evaluate(repo_context, understanding=abstained_understanding)

    assert "Not determined" in llm.last_prompt
    assert result.abstained is False

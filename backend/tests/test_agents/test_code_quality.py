"""Code Quality Agent: score_raw must ALWAYS equal the deterministic formula
(never the LLM's opinion), and a failed LLM narrative call must still yield
a valid (non-abstained) fallback_used result — the score never depended on
the LLM in the first place."""

import json

import pytest

from app.agents.code_quality import CodeQualityAgent
from app.core.exceptions import ModelUnavailableError
from app.scoring.aggregator import compute_code_quality_score
from tests.test_agents.conftest import FakeLLM

pytestmark = pytest.mark.asyncio

_VALID_NARRATIVE = json.dumps(
    {
        "reasoning": "Solid modularity undercut by low documentation coverage.",
        "confidence": 0.85,
        "evidence": [{"finding": "2/5 documented", "impact": "New contributors lack guidance", "file_ref": "main.py"}],
        "top_evidence": ["2/5 documented"],
        "strengths": ["Clean structure"],
        "weaknesses": ["Low documentation coverage"],
    }
)


async def test_score_raw_matches_deterministic_formula_when_llm_succeeds(repo_context):
    agent = CodeQualityAgent(FakeLLM(response=_VALID_NARRATIVE))
    result = await agent.evaluate(repo_context)

    assert result.score_raw == compute_code_quality_score(repo_context.static_analysis)
    assert result.abstained is False
    assert result.fallback_used is False
    assert result.reasoning == "Solid modularity undercut by low documentation coverage."


async def test_score_raw_matches_deterministic_formula_when_llm_unavailable(repo_context):
    agent = CodeQualityAgent(FakeLLM(exception=ModelUnavailableError("ollama down")))
    result = await agent.evaluate(repo_context)

    assert result.score_raw == compute_code_quality_score(repo_context.static_analysis)
    assert result.abstained is False  # the score never needed the LLM
    assert result.fallback_used is True
    assert "static analysis" in result.reasoning.lower()


async def test_score_raw_matches_deterministic_formula_when_llm_returns_garbage(repo_context):
    agent = CodeQualityAgent(FakeLLM(response="not valid json"))
    result = await agent.evaluate(repo_context)

    assert result.score_raw == compute_code_quality_score(repo_context.static_analysis)
    assert result.fallback_used is True


async def test_fallback_top_evidence_reflects_real_metrics(repo_context):
    agent = CodeQualityAgent(FakeLLM(exception=ModelUnavailableError("down")))
    result = await agent.evaluate(repo_context)

    assert len(result.top_evidence) <= 2
    assert any("docstring coverage" in item for item in result.top_evidence)

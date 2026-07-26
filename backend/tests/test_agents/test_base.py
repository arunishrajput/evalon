"""AgentResult construction and the LLM JSON-parsing/clamping helpers all
three LLM agents rely on."""

import pytest

from app.agents.base import AgentResult, clamp_confidence, clamp_score, parse_llm_json


def test_create_abstained_sets_neutral_defaults():
    result = AgentResult.create_abstained("code_quality", "model unavailable", fallback_used=True)
    assert result.abstained is True
    assert result.score_raw == 50.0
    assert result.confidence == 0.0
    assert result.abstain_reason == "model unavailable"
    assert result.fallback_used is True


def test_agent_result_field_and_classmethod_do_not_collide():
    """Regression check for the spec pseudocode's naming collision (a
    classmethod named `abstained` would overwrite the `abstained: bool`
    field's default in the class namespace) — see base.py's comment."""
    result = AgentResult(agent_id="x")
    assert result.abstained is False  # the field, not shadowed by a method
    assert callable(AgentResult.create_abstained)


def test_parse_llm_json_plain():
    assert parse_llm_json('{"score_raw": 80}') == {"score_raw": 80}


def test_parse_llm_json_strips_markdown_fences():
    raw = '```json\n{"score_raw": 80}\n```'
    assert parse_llm_json(raw) == {"score_raw": 80}


def test_parse_llm_json_raises_value_error_on_garbage():
    with pytest.raises(ValueError):
        parse_llm_json("not json at all")


def test_clamp_score_bounds():
    assert clamp_score(150) == 100.0
    assert clamp_score(-10) == 0.0
    assert clamp_score(42) == 42.0
    assert clamp_score("not a number") == 50.0


def test_clamp_confidence_bounds():
    assert clamp_confidence(2.0) == 1.0
    assert clamp_confidence(-0.5) == 0.0
    assert clamp_confidence(0.42) == 0.42
    assert clamp_confidence(None) == 0.5

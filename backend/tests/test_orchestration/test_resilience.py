"""Phase 4 verification (spec Section 13's "Graceful Degradation" unit
tests): a failing/timing-out/erroring agent must abstain, never crash the
node, and the model-lock-timeout path must populate all three LLM agents as
abstained rather than skip them silently."""

import asyncio

import pytest

from app.agents.base import AgentResult
from app.core.exceptions import ModelUnavailableError
from app.orchestration.nodes import (
    PipelineContext,
    _run_agent_node,
    acquire_model_lock_node,
)

pytestmark = pytest.mark.asyncio


class _StubAgent:
    agent_id = "repo_understanding"
    agent_name = "Repository Understanding Agent"

    def __init__(self, outcome):
        self._outcome = outcome
        self.call_count = 0

    async def safe_evaluate(self, repo_context, **kwargs):
        self.call_count += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _initial_state(model_lock_acquired: bool = True) -> dict:
    return {
        "submission_id": "test-sub",
        "hackathon_id": "test-hack",
        "repo_context": object(),
        "agent_results": {},
        "errors": [],
        "completed_agents": [],
        "model_lock_acquired": model_lock_acquired,
        "pipeline_start_time": 0.0,
        "aggregation": None,
        "report": None,
    }


def _minimal_ctx(redis_client) -> PipelineContext:
    return PipelineContext(db=None, redis=redis_client, model_queue=None, llm=None, settings=None, criteria=[])


async def test_run_agent_node_success(redis_client):
    good_result = AgentResult(agent_id="repo_understanding", score_raw=80, confidence=0.9)
    agent = _StubAgent(good_result)
    state = await _run_agent_node(_initial_state(), _minimal_ctx(redis_client), agent, "agent_repo_understanding")

    assert state["agent_results"]["repo_understanding"] is good_result
    assert "repo_understanding" in state["completed_agents"]
    assert agent.call_count == 1


async def test_run_agent_node_model_unavailable_abstains(redis_client):
    agent = _StubAgent(ModelUnavailableError("ollama down"))
    state = await _run_agent_node(_initial_state(), _minimal_ctx(redis_client), agent, "agent_repo_understanding")

    result = state["agent_results"]["repo_understanding"]
    assert result.abstained is True
    assert result.fallback_used is True
    assert "repo_understanding" not in state["completed_agents"]
    assert state["errors"] == []  # ModelUnavailableError is an expected degrade path, not an "error"


async def test_run_agent_node_timeout_abstains(redis_client):
    agent = _StubAgent(asyncio.TimeoutError())
    state = await _run_agent_node(_initial_state(), _minimal_ctx(redis_client), agent, "agent_repo_understanding")

    result = state["agent_results"]["repo_understanding"]
    assert result.abstained is True
    assert result.fallback_used is True
    assert "timed out" in result.abstain_reason


async def test_run_agent_node_generic_exception_abstains_and_records_error(redis_client):
    agent = _StubAgent(ValueError("malformed json"))
    state = await _run_agent_node(_initial_state(), _minimal_ctx(redis_client), agent, "agent_repo_understanding")

    result = state["agent_results"]["repo_understanding"]
    assert result.abstained is True
    assert state["errors"] == ["malformed json"]


async def test_run_agent_node_skips_when_lock_not_acquired(redis_client):
    """Pipeline continues (does not re-attempt the agent) when acquire_model_lock_node
    already populated an abstained result for this agent."""
    agent = _StubAgent(AgentResult(agent_id="repo_understanding", score_raw=99))
    state = _initial_state(model_lock_acquired=False)
    state["agent_results"]["repo_understanding"] = AgentResult.create_abstained(
        "repo_understanding", "Model unavailable"
    )

    result_state = await _run_agent_node(state, _minimal_ctx(redis_client), agent, "agent_repo_understanding")

    assert agent.call_count == 0  # never invoked
    assert result_state["agent_results"]["repo_understanding"].score_raw == 50.0  # untouched abstain default


class _FailingLockCM:
    async def __aenter__(self):
        raise ModelUnavailableError("resource contention")

    async def __aexit__(self, *args):
        return False


class _FakeModelQueueTimeout:
    LOCK_KEY = "test:fake:lock:timeout"
    INFERENCE_MODEL = "qwen2.5-coder:7b"
    EMBEDDING_MODEL = "nomic-embed-text"

    def acquire_inference_lock(self, requester_id, priority, timeout):
        return _FailingLockCM()


async def test_acquire_model_lock_node_timeout_abstains_all_llm_agents(redis_client):
    """Spec Section 7: on lock timeout, ALL THREE LLM agents must be marked
    abstained with a ModelUnavailableError reason — not just skipped."""
    ctx = PipelineContext(
        db=None, redis=redis_client, model_queue=_FakeModelQueueTimeout(), llm=None, settings=None, criteria=[]
    )
    state = await acquire_model_lock_node(_initial_state(model_lock_acquired=False), ctx)

    assert state["model_lock_acquired"] is False
    for agent_id in ("repo_understanding", "code_quality", "innovation"):
        result = state["agent_results"][agent_id]
        assert result.abstained is True
        assert result.fallback_used is True
        assert "static analysis only" in result.abstain_reason.lower()


class _SucceedingLockCM:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *args):
        return False


class _FakeModelQueueSuccess:
    LOCK_KEY = "test:fake:lock:success"
    INFERENCE_MODEL = "qwen2.5-coder:7b"
    EMBEDDING_MODEL = "nomic-embed-text"

    def acquire_inference_lock(self, requester_id, priority, timeout):
        return _SucceedingLockCM()


async def test_acquire_model_lock_node_success_leaves_agents_untouched(redis_client):
    ctx = PipelineContext(
        db=None, redis=redis_client, model_queue=_FakeModelQueueSuccess(), llm=None, settings=None, criteria=[]
    )
    state = await acquire_model_lock_node(_initial_state(model_lock_acquired=False), ctx)

    assert state["model_lock_acquired"] is True
    assert state["agent_results"] == {}
    assert ctx.lock_cm is not None

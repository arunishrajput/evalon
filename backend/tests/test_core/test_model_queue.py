"""Phase 0 verification: ModelQueueManager lock acquisition, release, priority
ordering, timeout behavior, and model switching. Runs against a real Redis
instance (that's the point — proving the distributed lock actually serializes
concurrent requesters) but never hits real Ollama; HTTP calls are monkeypatched.
"""

import asyncio

import pytest

from app.core.exceptions import ModelLockTimeoutError
from app.core.model_queue import ModelQueueManager


@pytest.fixture
def stub_model_load(monkeypatch):
    """Skips real Ollama load/unload so lock-behavior tests run fast and
    deterministically. Model-loading logic itself is tested separately below."""

    async def _noop(self, model_name, keep_alive):
        return None

    monkeypatch.setattr(ModelQueueManager, "_ensure_model_loaded", _noop)


async def test_acquire_and_release_inference_lock(model_queue, stub_model_load):
    async with model_queue.acquire_inference_lock("req-1", priority=0, timeout=5):
        lock_value = await model_queue.redis.get(model_queue.LOCK_KEY)
        assert lock_value is not None
        assert lock_value.endswith("::req-1")
    assert await model_queue.redis.get(model_queue.LOCK_KEY) is None


async def test_second_requester_blocks_until_release(model_queue, stub_model_load):
    order: list[str] = []
    release_event = asyncio.Event()

    async def holder():
        async with model_queue.acquire_inference_lock("holder", priority=0, timeout=5):
            order.append("holder-enter")
            await release_event.wait()
        order.append("holder-exit")

    async def waiter():
        await asyncio.sleep(0.1)
        async with model_queue.acquire_inference_lock("waiter", priority=0, timeout=5):
            order.append("waiter-enter")

    holder_task = asyncio.create_task(holder())
    waiter_task = asyncio.create_task(waiter())
    await asyncio.sleep(0.3)
    assert order == ["holder-enter"]  # waiter must still be blocked
    release_event.set()
    await asyncio.gather(holder_task, waiter_task)
    assert order == ["holder-enter", "holder-exit", "waiter-enter"]


async def test_priority_ordering_p0_before_p2_before_p3(model_queue, stub_model_load):
    """A P0 (evaluation) requester queued AFTER P2/P3 requesters must still be
    served first — priority beats arrival order."""
    order: list[str] = []
    release_event = asyncio.Event()

    async def holder():
        async with model_queue.acquire_inference_lock("holder", priority=0, timeout=5):
            await release_event.wait()

    async def waiter(name: str, priority: int):
        async with model_queue.acquire_inference_lock(name, priority=priority, timeout=5):
            order.append(name)

    holder_task = asyncio.create_task(holder())
    await asyncio.sleep(0.05)
    tasks = [
        asyncio.create_task(waiter("low-priority-p3", priority=3)),
    ]
    await asyncio.sleep(0.05)
    tasks.append(asyncio.create_task(waiter("mid-priority-p2", priority=2)))
    await asyncio.sleep(0.05)
    tasks.append(asyncio.create_task(waiter("high-priority-p0", priority=0)))
    await asyncio.sleep(0.3)  # let all three register in the priority queue

    release_event.set()
    await asyncio.gather(holder_task, *tasks)
    assert order == ["high-priority-p0", "mid-priority-p2", "low-priority-p3"]


async def test_lock_timeout_raises_and_cleans_up_queue(model_queue, stub_model_load):
    release_event = asyncio.Event()

    async def holder():
        async with model_queue.acquire_inference_lock("holder", priority=0, timeout=5):
            await release_event.wait()

    holder_task = asyncio.create_task(holder())
    await asyncio.sleep(0.05)

    with pytest.raises(ModelLockTimeoutError):
        async with model_queue.acquire_inference_lock("impatient", priority=0, timeout=0.5):
            pass  # pragma: no cover - should never enter, lock is held

    assert await model_queue.redis.zcard(model_queue.QUEUE_KEY) == 0

    release_event.set()
    await holder_task


async def test_ensure_model_loaded_unloads_other_model_first(model_queue, monkeypatch):
    """Enforces the core invariant: never two Ollama models resident at once."""
    calls: list[tuple[str, str]] = []

    async def fake_get_loaded_models(self):
        return ["llama3.2:3b"] if not calls else []

    async def fake_call_ollama(self, model_name, keep_alive):
        calls.append((model_name, keep_alive))

    monkeypatch.setattr(ModelQueueManager, "_get_loaded_models", fake_get_loaded_models)
    monkeypatch.setattr(ModelQueueManager, "_call_ollama", fake_call_ollama)

    await model_queue._ensure_model_loaded(ModelQueueManager.INFERENCE_MODEL, keep_alive="10m")

    assert calls[0] == ("llama3.2:3b", "0")  # unload the stale model first
    assert calls[1] == (ModelQueueManager.INFERENCE_MODEL, "10m")  # then load target
    assert await model_queue.redis.get(model_queue.CURRENT_MODEL_KEY) == ModelQueueManager.INFERENCE_MODEL


async def test_health_check_reports_expected_shape(model_queue, monkeypatch):
    async def fake_get_loaded_models(self):
        return [ModelQueueManager.INFERENCE_MODEL]

    async def fake_model_pulled(self, model_name):
        return True

    monkeypatch.setattr(ModelQueueManager, "_get_loaded_models", fake_get_loaded_models)
    monkeypatch.setattr(ModelQueueManager, "_model_pulled", fake_model_pulled)

    status = await model_queue.health_check()

    assert status == {
        "ollama_reachable": True,
        "inference_model_available": True,
        "embedding_model_available": True,
        "current_loaded_model": ModelQueueManager.INFERENCE_MODEL,
        "queue_depth": 0,
    }


async def test_get_queue_status_matches_admin_endpoint_contract(model_queue, monkeypatch):
    async def fake_get_loaded_models(self):
        return [ModelQueueManager.INFERENCE_MODEL]

    async def fake_model_pulled(self, model_name):
        return True

    monkeypatch.setattr(ModelQueueManager, "_get_loaded_models", fake_get_loaded_models)
    monkeypatch.setattr(ModelQueueManager, "_model_pulled", fake_model_pulled)

    status = await model_queue.get_queue_status()

    assert set(status.keys()) == {
        "ollama_reachable",
        "inference_model",
        "inference_model_loaded",
        "embedding_model",
        "embedding_model_loaded",
        "lock_held_by",
        "queue_depth",
        "estimated_wait_seconds",
    }
    assert status["inference_model_loaded"] is True
    assert status["embedding_model_loaded"] is False
    assert status["lock_held_by"] is None

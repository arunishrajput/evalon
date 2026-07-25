"""Serializes all Ollama inference calls behind a Redis-backed distributed lock so
the system never attempts to load two Ollama models at once. This is the single
component in EVALON allowed to talk to the Ollama HTTP API directly — everything
else (agents, embedder, chatbot) goes through LLMProvider, which goes through this
manager. See docs/decisions/ADR-006-model-resource-management.md.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from redis.asyncio import Redis

from app.config import Settings
from app.core.exceptions import ModelLockTimeoutError, ModelUnavailableError

_RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class ModelQueueManager:
    """Coordinates exclusive access to the Ollama runtime across all ARQ worker
    processes and the API process via Redis. Priorities: P0 (active evaluation
    agents) > P1 (report generation) > P2 (embedding generation) > P3 (chatbot)."""

    INFERENCE_MODEL = "qwen2.5-coder:7b"
    EMBEDDING_MODEL = "nomic-embed-text"
    LOCK_KEY = "evalon:model:lock"
    QUEUE_KEY = "evalon:model:queue"
    CURRENT_MODEL_KEY = "evalon:model:current"
    LOCK_TIMEOUT = 600  # seconds — max time any single inference call holds the lock
    EMBEDDING_PRIORITY = 2
    POLL_INTERVAL_SECONDS = 0.4
    ESTIMATED_SECONDS_PER_QUEUE_POSITION = 60

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    @asynccontextmanager
    async def acquire_inference_lock(
        self, requester_id: str, priority: int = 2, timeout: int = 300
    ) -> AsyncIterator[None]:
        """Exclusive access to the inference model. Blocks (respecting priority
        order among waiters) until available or `timeout` elapses, unloads the
        embedding model if it's loaded, then loads the inference model."""
        token = await self._wait_and_acquire(requester_id, priority, timeout)
        try:
            await self._ensure_model_loaded(self.INFERENCE_MODEL, keep_alive="10m")
            yield
        finally:
            await self._release_lock(token)

    @asynccontextmanager
    async def acquire_embedding_lock(
        self, requester_id: str, timeout: int = 120
    ) -> AsyncIterator[None]:
        """Exclusive access to the embedding model. Blocks until the inference
        lock is free, unloads the inference model, then loads the tiny embedding
        model (fast to reload afterward)."""
        token = await self._wait_and_acquire(requester_id, self.EMBEDDING_PRIORITY, timeout)
        try:
            await self._ensure_model_loaded(self.EMBEDDING_MODEL, keep_alive="1m")
            yield
        finally:
            await self._release_lock(token)

    async def _wait_and_acquire(self, requester_id: str, priority: int, timeout: int) -> str:
        """Registers the caller in a priority-ordered Redis sorted-set queue and
        polls until it is both at the head of the queue and able to grab the
        lock. Always removed from the queue on the way out, success or timeout."""
        deadline = time.monotonic() + timeout
        queue_member = f"{requester_id}::{uuid.uuid4().hex[:8]}"
        queue_score = priority * 10**13 + int(time.time() * 1000)
        token = f"{uuid.uuid4().hex}::{requester_id}"
        await self.redis.zadd(self.QUEUE_KEY, {queue_member: queue_score})
        try:
            while True:
                if await self._try_claim_if_head(queue_member, token):
                    return token
                if time.monotonic() >= deadline:
                    raise ModelLockTimeoutError(
                        f"Timed out after {timeout}s waiting for model lock ({requester_id})"
                    )
                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
        finally:
            await self.redis.zrem(self.QUEUE_KEY, queue_member)

    async def _try_claim_if_head(self, queue_member: str, token: str) -> bool:
        head = await self.redis.zrange(self.QUEUE_KEY, 0, 0)
        if not head or head[0] != queue_member:
            return False
        acquired = await self.redis.set(
            self.LOCK_KEY, token, nx=True, px=self.LOCK_TIMEOUT * 1000
        )
        return bool(acquired)

    async def _release_lock(self, token: str) -> None:
        await self.redis.eval(_RELEASE_LOCK_LUA, 1, self.LOCK_KEY, token)

    async def _ensure_model_loaded(self, model_name: str, keep_alive: str) -> None:
        """Unloads any other currently-loaded model, then loads `model_name`.
        Two Ollama models are never resident at the same time."""
        for loaded in await self._get_loaded_models():
            if not self._same_model(loaded, model_name):
                await self._unload_model(loaded)
        await self._call_ollama(model_name, keep_alive)
        await self.redis.set(self.CURRENT_MODEL_KEY, model_name)

    async def _unload_model(self, model_name: str) -> None:
        await self._call_ollama(model_name, keep_alive="0")

    async def _call_ollama(self, model_name: str, keep_alive: str) -> None:
        endpoint, payload = self._load_payload(model_name, keep_alive)
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.settings.ollama_base_url}{endpoint}", json=payload, timeout=120
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ModelUnavailableError(f"Ollama call failed for {model_name}: {exc}") from exc

    def _load_payload(self, model_name: str, keep_alive: str) -> tuple[str, dict]:
        if self._same_model(model_name, self.EMBEDDING_MODEL):
            return "/api/embed", {"model": model_name, "input": "", "keep_alive": keep_alive}
        return "/api/generate", {
            "model": model_name,
            "prompt": "",
            "keep_alive": keep_alive,
            "stream": False,
        }

    async def _get_loaded_models(self) -> list[str]:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.settings.ollama_base_url}/api/ps", timeout=10)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ModelUnavailableError(f"Ollama unreachable: {exc}") from exc
        return [m["name"] for m in resp.json().get("models", [])]

    async def _model_pulled(self, model_name: str) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.settings.ollama_base_url}/api/tags", timeout=10)
                resp.raise_for_status()
            except httpx.HTTPError:
                return False
        names = [m["name"] for m in resp.json().get("models", [])]
        return any(self._same_model(name, model_name) for name in names)

    @staticmethod
    def _same_model(a: str, b: str) -> bool:
        return a.split(":")[0] == b.split(":")[0]

    async def health_check(self) -> dict:
        """Ollama connectivity + model availability snapshot. Never loads a
        model as a side effect of checking status."""
        try:
            loaded = await self._get_loaded_models()
            ollama_reachable = True
        except ModelUnavailableError:
            loaded = []
            ollama_reachable = False
        inference_available = ollama_reachable and await self._model_pulled(self.INFERENCE_MODEL)
        embedding_available = ollama_reachable and await self._model_pulled(self.EMBEDDING_MODEL)
        return {
            "ollama_reachable": ollama_reachable,
            "inference_model_available": inference_available,
            "embedding_model_available": embedding_available,
            "current_loaded_model": loaded[0] if loaded else None,
            "queue_depth": await self.redis.zcard(self.QUEUE_KEY),
        }

    async def get_queue_status(self) -> dict:
        """Shape returned by GET /api/v1/admin/model/status."""
        health = await self.health_check()
        current = health["current_loaded_model"]
        lock_value = await self.redis.get(self.LOCK_KEY)
        lock_held_by = lock_value.split("::", 1)[1] if lock_value and "::" in lock_value else None
        queue_depth = health["queue_depth"]
        return {
            "ollama_reachable": health["ollama_reachable"],
            "inference_model": self.INFERENCE_MODEL,
            "inference_model_loaded": bool(current) and self._same_model(current, self.INFERENCE_MODEL),
            "embedding_model": self.EMBEDDING_MODEL,
            "embedding_model_loaded": bool(current) and self._same_model(current, self.EMBEDDING_MODEL),
            "lock_held_by": lock_held_by,
            "queue_depth": queue_depth,
            "estimated_wait_seconds": queue_depth * self.ESTIMATED_SECONDS_PER_QUEUE_POSITION,
        }

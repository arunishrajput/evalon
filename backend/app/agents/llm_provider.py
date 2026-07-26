"""Ollama LLM provider abstraction. Assumes the model lock is already held by
the caller (acquired once at the pipeline level, per Section 7) — this class
does NOT acquire locks itself. Alongside ModelQueueManager (which owns
load/unload lifecycle calls), LLMProvider is the only other component
permitted to call Ollama's inference endpoints directly; every agent,
embedder, and the chatbot must go through it rather than hitting Ollama
themselves (spec's Model Queue Standards)."""

import asyncio
import json
from typing import AsyncIterator

import httpx

from app.config import Settings
from app.core.exceptions import ModelUnavailableError
from app.core.model_queue import ModelQueueManager


class LLMProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = ModelQueueManager.INFERENCE_MODEL

    async def generate(self, prompt: str, system: str, *, json_mode: bool = True, timeout: int = 90) -> str:
        """Raises asyncio.TimeoutError if inference exceeds `timeout` seconds.
        Raises ModelUnavailableError for any other failure — never anything
        else, so callers only need to handle these two exception types."""
        try:
            return await asyncio.wait_for(self._call_generate(prompt, system, json_mode), timeout=timeout)
        except asyncio.TimeoutError:
            raise
        except ModelUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - contract: never raise anything but the two types above
            raise ModelUnavailableError(f"Ollama generate call failed: {exc}") from exc

    async def _call_generate(self, prompt: str, system: str, json_mode: bool) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "keep_alive": "10m",
        }
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(f"{self.settings.ollama_base_url}/api/generate", json=payload, timeout=120)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ModelUnavailableError(f"Ollama unreachable during generate: {exc}") from exc

        data = resp.json()
        response_text = data.get("response")
        if not response_text:
            raise ModelUnavailableError("Ollama returned an empty response")
        return response_text

    async def generate_stream(self, prompt: str, system: str, *, timeout: int = 120) -> AsyncIterator[str]:
        """Token-by-token streaming generate call for the mentor chatbot
        (spec Section 9's SSE token streaming). Assumes the inference lock is
        already held by the caller. Yields response tokens as they arrive;
        raises ModelUnavailableError (never anything else) on any failure,
        matching generate()'s contract."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "keep_alive": "10m",
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{self.settings.ollama_base_url}/api/generate", json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            return
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"Ollama streaming generate failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ModelUnavailableError(f"Ollama returned malformed streaming output: {exc}") from exc

    async def embed(self, text: str) -> list[float]:
        """Assumes the embedding lock is already held by the caller."""
        payload = {"model": ModelQueueManager.EMBEDDING_MODEL, "input": text, "keep_alive": "1m"}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(f"{self.settings.ollama_base_url}/api/embed", json=payload, timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ModelUnavailableError(f"Ollama unreachable during embed: {exc}") from exc

        data = resp.json()
        embeddings = data.get("embeddings")
        if not embeddings:
            raise ModelUnavailableError("Ollama returned no embedding")
        return embeddings[0]

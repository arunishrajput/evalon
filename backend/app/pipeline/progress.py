"""Evaluation progress SSE plumbing. The ARQ worker (a separate process from
the API) emits events by pushing to a Redis list — RPUSH, not just PUBLISH —
so a client that connects to the SSE endpoint after some events have already
fired still sees the full history (spec Section 11: "stored as Redis lists
with 2h TTL for late-connecting clients"). A parallel PUBLISH gives actively
connected clients real-time delivery without polling."""

import json
from datetime import datetime, timezone
from typing import AsyncIterator

from redis.asyncio import Redis

PROGRESS_TTL_SECONDS = 2 * 60 * 60
TERMINAL_EVENTS = {"completed", "error"}
_KEEPALIVE_SECONDS = 15


def _progress_key(submission_id: str) -> str:
    return f"evalon:progress:{submission_id}"


async def emit_progress(redis: Redis, submission_id: str, event: str, data: dict) -> None:
    payload = {"event": event, "data": {**data, "timestamp": datetime.now(timezone.utc).isoformat()}}
    key = _progress_key(submission_id)
    message = json.dumps(payload)
    async with redis.pipeline(transaction=True) as pipe:
        await pipe.rpush(key, message).expire(key, PROGRESS_TTL_SECONDS).publish(key, message).execute()


async def stream_progress(redis: Redis, submission_id: str) -> AsyncIterator[str]:
    """SSE generator: replays history for late joiners, then streams new
    events live until a terminal event (completed/error) or the client
    disconnects. Sends periodic comments as keepalives so proxies (nginx)
    don't time out the connection while nothing new has happened."""
    key = _progress_key(submission_id)

    history = await redis.lrange(key, 0, -1)
    for raw in history:
        yield _to_sse(raw)
        if _is_terminal(raw):
            return

    pubsub = redis.pubsub()
    await pubsub.subscribe(key)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_KEEPALIVE_SECONDS)
            if message is None:
                yield ": keepalive\n\n"
                continue
            raw = message["data"]
            yield _to_sse(raw)
            if _is_terminal(raw):
                return
    finally:
        await pubsub.unsubscribe(key)
        await pubsub.aclose()


def _is_terminal(raw: str) -> bool:
    try:
        return json.loads(raw).get("event") in TERMINAL_EVENTS
    except json.JSONDecodeError:
        return False


def _to_sse(raw: str) -> str:
    return f"data: {raw}\n\n"

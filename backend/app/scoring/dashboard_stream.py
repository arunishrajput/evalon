"""Admin live-dashboard SSE stream (spec Section 6): re-queries
hackathon_stats every 15 seconds and pushes a fresh snapshot — a periodic
poll-and-push, not a pub/sub relay, per the spec's literal "emits updated
stats object every 15 seconds" cadence. A DB session is opened fresh each
cycle rather than held open for the stream's lifetime."""

import asyncio
import json
from typing import AsyncIterator
from uuid import UUID

from app.database import async_session_factory
from app.scoring.stats_service import compute_hackathon_stats

DASHBOARD_POLL_INTERVAL_SECONDS = 15


async def stream_dashboard_stats(hackathon_id: UUID) -> AsyncIterator[str]:
    while True:
        async with async_session_factory() as db:
            stats = await compute_hackathon_stats(db, hackathon_id)
        payload = {"event": "stats_update", "data": stats}
        yield f"data: {json.dumps(payload, default=str)}\n\n"
        await asyncio.sleep(DASHBOARD_POLL_INTERVAL_SECONDS)

"""Admin live-dashboard: snapshot endpoint plus a 15s-interval SSE stream
(spec Section 6)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.exceptions import NotFoundError
from app.database import get_db
from app.dependencies import require_admin
from app.models.hackathon import Hackathon
from app.models.user import User
from app.schemas.dashboard import DashboardStats
from app.scoring.dashboard_stream import stream_dashboard_stats
from app.scoring.stats_service import upsert_hackathon_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{hackathon_id}", response_model=DashboardStats)
async def get_dashboard(
    hackathon_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    if await db.get(Hackathon, hackathon_id) is None:
        raise NotFoundError("Hackathon not found")
    # Computed fresh (not just read from the pre-computed row) so the very
    # first dashboard view — before any background job has run yet — isn't
    # empty; the background job keeps the stored row warm for the SSE stream.
    stats = await upsert_hackathon_stats(db, hackathon_id)
    await db.commit()
    return DashboardStats.model_validate(stats, from_attributes=True)


@router.get("/{hackathon_id}/stream")
async def stream_dashboard(
    hackathon_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if await db.get(Hackathon, hackathon_id) is None:
        raise NotFoundError("Hackathon not found")
    return StreamingResponse(
        stream_dashboard_stats(hackathon_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

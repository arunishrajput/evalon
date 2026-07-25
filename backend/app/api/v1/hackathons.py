"""Hackathon CRUD, criteria management, participants, and joining.

"[admin, owner]" in the spec means: the caller must be an admin AND must be
the specific admin who created the hackathon (hackathons.admin_id) — enforced
by `_load_owned_hackathon` below, not just a role check.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.criterion import Criterion
from app.models.hackathon import Hackathon, HackathonParticipant, HackathonStatus
from app.models.user import User
from app.schemas.common import Page
from app.schemas.hackathon import (
    CriteriaBulkReplace,
    CriterionCreate,
    CriterionRead,
    HackathonCreate,
    HackathonRead,
    HackathonStatusUpdate,
    HackathonUpdate,
    ParticipantRead,
)

router = APIRouter(prefix="/hackathons", tags=["hackathons"])


async def _get_hackathon_or_404(hackathon_id: uuid.UUID, db: AsyncSession) -> Hackathon:
    hackathon = await db.get(Hackathon, hackathon_id)
    if hackathon is None:
        raise NotFoundError("Hackathon not found")
    return hackathon


async def _load_owned_hackathon(
    hackathon_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Hackathon:
    hackathon = await _get_hackathon_or_404(hackathon_id, db)
    if hackathon.admin_id != admin.id:
        raise AuthorizationError("Only the admin who created this hackathon can modify it")
    return hackathon


@router.get("", response_model=Page[HackathonRead])
async def list_hackathons(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Page[HackathonRead]:
    """Public metadata listing — draft hackathons (still being configured by
    their admin) are excluded."""
    base_query = select(Hackathon).where(Hackathon.status != HackathonStatus.DRAFT)
    total = await db.scalar(select(func.count()).select_from(base_query.subquery()))
    rows = await db.scalars(
        base_query.order_by(Hackathon.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(items=list(rows), page=page, page_size=page_size, total=total or 0)


@router.post("", response_model=HackathonRead, status_code=201)
async def create_hackathon(
    payload: HackathonCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Hackathon:
    hackathon = Hackathon(
        title=payload.title,
        description=payload.description,
        admin_id=admin.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        max_submissions=payload.max_submissions,
        settings=payload.settings.model_dump(),
    )
    db.add(hackathon)
    await db.commit()
    await db.refresh(hackathon)
    return hackathon


@router.get("/{hackathon_id}", response_model=HackathonRead)
async def get_hackathon(hackathon_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Hackathon:
    return await _get_hackathon_or_404(hackathon_id, db)


@router.patch("/{hackathon_id}", response_model=HackathonRead)
async def update_hackathon(
    payload: HackathonUpdate,
    hackathon: Hackathon = Depends(_load_owned_hackathon),
    db: AsyncSession = Depends(get_db),
) -> Hackathon:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(hackathon, field, value)
    await db.commit()
    await db.refresh(hackathon)
    return hackathon


@router.delete("/{hackathon_id}", status_code=204)
async def delete_hackathon(
    hackathon: Hackathon = Depends(_load_owned_hackathon),
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.delete(hackathon)
    await db.commit()


_ALLOWED_STATUS_TRANSITIONS: dict[HackathonStatus, set[HackathonStatus]] = {
    HackathonStatus.DRAFT: {HackathonStatus.ACTIVE},
    HackathonStatus.ACTIVE: {HackathonStatus.EVALUATING},
    HackathonStatus.EVALUATING: {HackathonStatus.FINALIZED, HackathonStatus.ACTIVE},
    HackathonStatus.FINALIZED: set(),
}


@router.patch("/{hackathon_id}/status", response_model=HackathonRead)
async def update_hackathon_status(
    payload: HackathonStatusUpdate,
    hackathon: Hackathon = Depends(_load_owned_hackathon),
    db: AsyncSession = Depends(get_db),
) -> Hackathon:
    allowed = _ALLOWED_STATUS_TRANSITIONS.get(hackathon.status, set())
    if payload.status not in allowed:
        raise ConflictError(
            f"Cannot transition hackathon from '{hackathon.status.value}' to '{payload.status.value}'",
            "invalid_status_transition",
        )
    hackathon.status = payload.status
    await db.commit()
    await db.refresh(hackathon)
    return hackathon


@router.get("/{hackathon_id}/criteria", response_model=list[CriterionRead])
async def list_criteria(hackathon_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[Criterion]:
    await _get_hackathon_or_404(hackathon_id, db)
    rows = await db.scalars(
        select(Criterion).where(Criterion.hackathon_id == hackathon_id).order_by(Criterion.display_order)
    )
    return list(rows)


@router.post("/{hackathon_id}/criteria", response_model=CriterionRead, status_code=201)
async def add_criterion(
    payload: CriterionCreate,
    hackathon: Hackathon = Depends(_load_owned_hackathon),
    db: AsyncSession = Depends(get_db),
) -> Criterion:
    criterion = Criterion(hackathon_id=hackathon.id, **payload.model_dump())
    db.add(criterion)
    await db.commit()
    await db.refresh(criterion)
    return criterion


@router.put("/{hackathon_id}/criteria", response_model=list[CriterionRead])
async def replace_criteria(
    payload: CriteriaBulkReplace,
    hackathon: Hackathon = Depends(_load_owned_hackathon),
    db: AsyncSession = Depends(get_db),
) -> list[Criterion]:
    """Weight-sum-to-1.0 validation already ran in CriteriaBulkReplace."""
    existing = await db.scalars(select(Criterion).where(Criterion.hackathon_id == hackathon.id))
    for row in existing:
        await db.delete(row)
    await db.flush()

    new_criteria = [
        Criterion(hackathon_id=hackathon.id, **c.model_dump()) for c in payload.criteria
    ]
    db.add_all(new_criteria)
    await db.commit()
    for criterion in new_criteria:
        await db.refresh(criterion)
    return new_criteria


@router.get("/{hackathon_id}/participants", response_model=list[ParticipantRead])
async def list_participants(
    hackathon: Hackathon = Depends(_load_owned_hackathon),
    db: AsyncSession = Depends(get_db),
) -> list[HackathonParticipant]:
    rows = await db.scalars(
        select(HackathonParticipant).where(HackathonParticipant.hackathon_id == hackathon.id)
    )
    return list(rows)


@router.post("/{hackathon_id}/join", response_model=ParticipantRead, status_code=201)
async def join_hackathon(
    hackathon_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HackathonParticipant:
    hackathon = await _get_hackathon_or_404(hackathon_id, db)
    if hackathon.status != HackathonStatus.ACTIVE:
        raise ConflictError("This hackathon is not currently accepting participants", "hackathon_not_active")

    existing = await db.scalar(
        select(HackathonParticipant).where(
            HackathonParticipant.hackathon_id == hackathon_id,
            HackathonParticipant.user_id == user.id,
        )
    )
    if existing is not None:
        raise ConflictError("You have already joined this hackathon", "already_joined")

    participant = HackathonParticipant(hackathon_id=hackathon_id, user_id=user.id)
    db.add(participant)
    await db.commit()
    await db.refresh(participant)
    return participant

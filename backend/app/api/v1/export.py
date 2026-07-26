"""PDF report export (spec Section 10's server-side export option, alongside
the frontend's client-side window.print() path)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.api.v1.submission_access import get_submission_or_404, require_owner_or_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.dependencies import get_current_user
from app.models.evaluation import Evaluation
from app.models.user import User
from app.scoring.pdf_report import render_evaluation_pdf

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("/{submission_id}/export")
async def export_evaluation_pdf(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    submission = await get_submission_or_404(submission_id, db)
    require_owner_or_admin(submission, user)

    evaluation = await db.scalar(select(Evaluation).where(Evaluation.submission_id == submission_id))
    if evaluation is None or evaluation.report is None:
        raise NotFoundError("No evaluation report is available yet for this submission")

    participant = await db.get(User, submission.user_id)
    pdf_bytes = render_evaluation_pdf(
        report=evaluation.report,
        repo_name=submission.repo_name or submission.repo_url,
        participant_name=(participant.full_name or participant.email) if participant else "Unknown",
        final_score=float(evaluation.final_score) if evaluation.final_score is not None else None,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="evalon-report-{submission_id}.pdf"'},
    )

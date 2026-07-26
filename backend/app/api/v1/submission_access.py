"""Shared ownership check used by both /submissions and /evaluations
endpoints — a submission's report/status is visible to the participant who
submitted it, or any admin."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.models.submission import Submission
from app.models.user import User, UserRole


async def get_submission_or_404(submission_id: uuid.UUID, db: AsyncSession) -> Submission:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise NotFoundError("Submission not found")
    return submission


def require_owner_or_admin(submission: Submission, user: User) -> None:
    if submission.user_id != user.id and user.role != UserRole.ADMIN:
        raise AuthorizationError("You do not have access to this submission")

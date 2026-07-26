"""Demo data seed (spec Section 20's exact demo scenario). Idempotent —
safe to re-run against a database that already has the seed data; existing
rows are left as-is rather than duplicated."""

import asyncio
import logging
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.database import async_session_factory
from app.models.criterion import Criterion
from app.models.hackathon import Hackathon, HackathonStatus
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("evalon.seed")

ADMIN_EMAIL = "admin@evalon.dev"
ADMIN_PASSWORD = "admin123"

PARTICIPANTS = [
    ("participant1@evalon.dev", "Participant One"),
    ("participant2@evalon.dev", "Participant Two"),
    ("participant3@evalon.dev", "Participant Three"),
]
PARTICIPANT_PASSWORD = "test123"

HACKATHON_TITLE = "AI Hackathon 2025"

CRITERIA = [
    ("Code Quality", "Structure, maintainability, and best practices", Decimal("0.40"), "code_quality"),
    ("Innovation", "Novelty and creativity of the approach", Decimal("0.35"), "innovation"),
    ("Project Understanding", "Depth of architectural understanding shown", Decimal("0.25"), "repo_understanding"),
]

DEMO_REPOS = [
    "https://github.com/tiangolo/fastapi",
    "https://github.com/vercel/next.js",
    "https://github.com/fastapi-practices/fastapi_best_architecture",
]


async def _get_or_create_user(db, email: str, password: str, full_name: str, role: UserRole) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        logger.info("  user already exists: %s", email)
        return user
    user = User(email=email, hashed_password=hash_password(password), full_name=full_name, role=role)
    db.add(user)
    await db.flush()
    logger.info("  created user: %s", email)
    return user


async def seed() -> None:
    async with async_session_factory() as db:
        logger.info("Seeding users...")
        admin = await _get_or_create_user(db, ADMIN_EMAIL, ADMIN_PASSWORD, "Demo Admin", UserRole.ADMIN)
        for email, name in PARTICIPANTS:
            await _get_or_create_user(db, email, PARTICIPANT_PASSWORD, name, UserRole.PARTICIPANT)

        logger.info("Seeding demo hackathon...")
        hackathon = await db.scalar(select(Hackathon).where(Hackathon.title == HACKATHON_TITLE))
        if hackathon is None:
            hackathon = Hackathon(
                title=HACKATHON_TITLE,
                description="EVALON's demo hackathon — submit a public GitHub repo to see the full evaluation pipeline.",
                admin_id=admin.id,
                status=HackathonStatus.ACTIVE,
                settings={
                    "allow_private_repos": False,
                    "max_repo_size_mb": 50,
                    "evaluation_mode": "standard",
                    "show_rankings_before_finalization": False,
                },
            )
            db.add(hackathon)
            await db.flush()
            logger.info("  created hackathon: %s (%s)", HACKATHON_TITLE, hackathon.id)
        else:
            logger.info("  hackathon already exists: %s (%s)", HACKATHON_TITLE, hackathon.id)

        existing_criteria = await db.scalar(select(Criterion.id).where(Criterion.hackathon_id == hackathon.id).limit(1))
        if existing_criteria is None:
            for order, (name, description, weight, agent_id) in enumerate(CRITERIA):
                db.add(
                    Criterion(
                        hackathon_id=hackathon.id, name=name, description=description,
                        weight=weight, agent_id=agent_id, display_order=order,
                    )
                )
            logger.info("  created %d judging criteria", len(CRITERIA))
        else:
            logger.info("  criteria already exist for this hackathon")

        await db.commit()

    logger.info("")
    logger.info("Seed complete.")
    logger.info("")
    logger.info("Admin login:       %s / %s", ADMIN_EMAIL, ADMIN_PASSWORD)
    logger.info("Participant login: participant1@evalon.dev / %s (also 2, 3)", PARTICIPANT_PASSWORD)
    logger.info("")
    logger.info("Try submitting one of these to '%s':", HACKATHON_TITLE)
    for repo in DEMO_REPOS:
        logger.info("  - %s", repo)
    logger.info("")
    logger.info(
        "Note: vercel/next.js is ~2.4GB — it will clone fully, then be cleanly "
        "rejected by the default MAX_REPO_SIZE_MB=50 limit (or hit "
        "CLONE_TIMEOUT_SECONDS first). Fine to demonstrate that rejection is "
        "clean, not a crash — but for a snappy live demo, prefer a smaller repo."
    )


if __name__ == "__main__":
    asyncio.run(seed())

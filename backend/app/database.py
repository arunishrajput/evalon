"""Async SQLAlchemy engine, session factory, and declarative base."""

from datetime import datetime
from typing import AsyncIterator

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    # All timestamps are stored in UTC (spec Section 5) — every Mapped[datetime]
    # column defaults to TIMESTAMPTZ instead of SQLAlchemy's naive-by-default
    # DateTime(), with no need to annotate each column individually.
    type_annotation_map = {datetime: DateTime(timezone=True)}


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with async_session_factory() as session:
        yield session

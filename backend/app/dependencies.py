"""FastAPI dependency injection: shared Redis connection, ModelQueueManager,
and JWT-based auth (current user / admin-only)."""

import uuid
from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.model_queue import ModelQueueManager
from app.core.security import TokenType, decode_token
from app.database import get_db
from app.models.user import User, UserRole

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


@lru_cache
def get_model_queue_manager() -> ModelQueueManager:
    return ModelQueueManager(redis=get_redis(), settings=get_settings())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token")
    try:
        payload = decode_token(settings, credentials.credentials)
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired access token") from exc
    if payload.get("type") != TokenType.ACCESS.value:
        raise AuthenticationError("Token is not an access token")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Malformed token") from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin privileges required")
    return user

"""Password hashing and JWT issuance/verification. Refresh tokens are JWTs
with a unique `jti`; the set of currently-valid jtis lives in Redis (spec's
schema has no refresh_tokens table, and Redis is already part of the stack)
so refresh can both rotate (issue a new token, invalidate the old one) and
detect reuse of an already-rotated-away token."""

import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from jose import JWTError, jwt
from passlib.context import CryptContext
from redis.asyncio import Redis

from app.config import Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(
    settings: Settings, subject: str, token_type: TokenType, expires_delta: timedelta
) -> tuple[str, str]:
    jti = uuid.uuid4().hex
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "type": token_type.value, "jti": jti, "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti


def create_access_token(settings: Settings, user_id: str) -> str:
    token, _ = _create_token(
        settings,
        user_id,
        TokenType.ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
    )
    return token


async def create_refresh_token(settings: Settings, redis: Redis, user_id: str) -> str:
    token, jti = _create_token(
        settings,
        user_id,
        TokenType.REFRESH,
        timedelta(days=settings.refresh_token_expire_days),
    )
    await redis.set(
        f"evalon:refresh_token:{jti}",
        user_id,
        ex=timedelta(days=settings.refresh_token_expire_days),
    )
    return token


def decode_token(settings: Settings, token: str) -> dict:
    """Raises JWTError on any invalid/expired/malformed token."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def rotate_refresh_token(settings: Settings, redis: Redis, refresh_token: str) -> tuple[str, str]:
    """Verifies and consumes a refresh token, returning a new (access, refresh)
    pair. Raises JWTError if the token is invalid, expired, wrong type, or has
    already been used (rotated away / revoked)."""
    payload = decode_token(settings, refresh_token)
    if payload.get("type") != TokenType.REFRESH.value:
        raise JWTError("Not a refresh token")

    redis_key = f"evalon:refresh_token:{payload['jti']}"
    user_id = await redis.get(redis_key)
    if user_id is None:
        raise JWTError("Refresh token already used or revoked")

    await redis.delete(redis_key)
    new_access = create_access_token(settings, user_id)
    new_refresh = await create_refresh_token(settings, redis, user_id)
    return new_access, new_refresh


async def revoke_refresh_token(settings: Settings, redis: Redis, refresh_token: str) -> None:
    """Best-effort invalidation for logout — an already-invalid token is not
    an error, there's simply nothing left to revoke."""
    try:
        payload = decode_token(settings, refresh_token)
    except JWTError:
        return
    await redis.delete(f"evalon:refresh_token:{payload['jti']}")

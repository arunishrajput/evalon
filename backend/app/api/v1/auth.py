"""Registration, login, token refresh, logout, and current-user profile."""

from fastapi import APIRouter, Depends, Request
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from app.database import get_db
from app.dependencies import get_current_user, get_redis
from app.models.user import User
from app.schemas.user import RefreshRequest, TokenPair, UserLogin, UserRead, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_tokens(settings: Settings, redis: Redis, user: User) -> TokenPair:
    access = create_access_token(settings, str(user.id))
    refresh = await create_refresh_token(settings, redis, str(user.id))
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit("10/minute")
async def register(
    request: Request,
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> User:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise ConflictError("An account with this email already exists", "email_taken")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> TokenPair:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password", "invalid_credentials")
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated", "account_inactive")
    return await _issue_tokens(settings, redis, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> TokenPair:
    try:
        access, refresh_token = await rotate_refresh_token(settings, redis, payload.refresh_token)
    except JWTError as exc:
        raise AuthenticationError("Invalid, expired, or already-used refresh token") from exc
    return TokenPair(access_token=access, refresh_token=refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    payload: RefreshRequest,
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> None:
    await revoke_refresh_token(settings, redis, payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

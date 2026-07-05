from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, schemas
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


import threading


logger = logging.getLogger(__name__)

_JWT_SECRET_CACHE: str | None = None
_JWT_SECRET_LOCK = threading.Lock()


def _get_jwt_secret() -> str:
    """Load JWT secret from settings or environment variable. Result is cached.

    Thread-safe: uses a lock for the check-then-act lazy initialization pattern.
    The value is deterministic, so the lock is for correctness only.
    """
    global _JWT_SECRET_CACHE
    if _JWT_SECRET_CACHE is not None:
        return _JWT_SECRET_CACHE
    with _JWT_SECRET_LOCK:
        # Double-check under lock
        if _JWT_SECRET_CACHE is not None:
            return _JWT_SECRET_CACHE
        try:
            from pydantic import SecretStr
            from research_agent.config import load_settings
            secret = load_settings().auth.secret_key
            _JWT_SECRET_CACHE = secret.get_secret_value() if isinstance(secret, SecretStr) else str(secret)
        except Exception:
            _JWT_SECRET_CACHE = os.environ.get("SECRET_KEY", "DEV_SECRET_DO_NOT_USE_IN_PROD")
        return _JWT_SECRET_CACHE


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"
    role: str = "viewer"  # P18: viewer | editor | admin


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


DATABASE_URL = "sqlite+aiosqlite:///./.runtime/research.db"
engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session():
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    # Secrets are set dynamically in get_user_manager to avoid hardcoding

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info("User %s has registered", user.id)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        # Token is intentionally NOT logged — it's a sensitive credential.
        # In production, send this token via email instead.
        logger.info("Password reset requested for user %s", user.id)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Verification requested for user %s", user.id)


async def get_user_manager(user_db=Depends(get_user_db)):
    secret = _get_jwt_secret()
    manager = UserManager(user_db)
    manager.reset_password_token_secret = secret
    manager.verification_token_secret = secret
    yield manager


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=_get_jwt_secret(), lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)

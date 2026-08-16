from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_connect_args: dict = {}
_engine_kwargs: dict = {"echo": settings.DB_ECHO, "future": True}

if settings.is_sqlite:
    _connect_args["check_same_thread"] = False
else:
    # Railway Postgres — ulanishlar uzoq turib qolmasin
    _engine_kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=1800)

engine = create_async_engine(settings.DATABASE_URL, connect_args=_connect_args, **_engine_kwargs)

SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — har bir so'rov uchun bitta sessiya."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

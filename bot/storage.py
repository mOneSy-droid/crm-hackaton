"""Botning o'z bazasi — Postgres (lokalda SQLite).

Bu yerda faqat botga tegishli minimal narsa saqlanadi: foydalanuvchining
tanlagan tili va admin ro'yxati. Restoranlar, sharhlar, menyu va bot
tokenlari backendda — bu yerda takrorlanmaydi.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import BOT_DATABASE_URL, DEFAULT_LANGUAGE, SUPER_ADMINS

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class BotUser(Base):
    __tablename__ = "bot_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    language: Mapped[str] = mapped_column(String(5), default=DEFAULT_LANGUAGE)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


_connect_args = {"check_same_thread": False} if BOT_DATABASE_URL.startswith("sqlite") else {}
engine = create_async_engine(BOT_DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

#: Har bir xabarda bazaga bormaslik uchun tillarni xotirada ushlaymiz
_language_cache: dict[int, str] = {}
_admin_cache: set[int] = set()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        rows = (await db.scalars(select(BotUser).where(BotUser.is_admin.is_(True)))).all()
        _admin_cache.update(row.telegram_id for row in rows)
    _admin_cache.update(SUPER_ADMINS)
    logger.info("Bot bazasi tayyor. Adminlar: %d ta", len(_admin_cache))


async def close_db() -> None:
    await engine.dispose()


async def _get_or_create(db: AsyncSession, telegram_id: int) -> BotUser:
    user = await db.get(BotUser, telegram_id)
    if user is None:
        user = BotUser(telegram_id=telegram_id, language=DEFAULT_LANGUAGE)
        db.add(user)
        await db.flush()
    return user


async def get_language(telegram_id: int) -> str:
    if telegram_id in _language_cache:
        return _language_cache[telegram_id]
    async with SessionLocal() as db:
        user = await db.get(BotUser, telegram_id)
    language = user.language if user else DEFAULT_LANGUAGE
    _language_cache[telegram_id] = language
    return language


async def set_language(telegram_id: int, language: str) -> None:
    async with SessionLocal() as db:
        user = await _get_or_create(db, telegram_id)
        user.language = language
        await db.commit()
    _language_cache[telegram_id] = language


def is_admin(telegram_id: int) -> bool:
    return telegram_id in _admin_cache


async def add_admin(telegram_id: int) -> None:
    async with SessionLocal() as db:
        user = await _get_or_create(db, telegram_id)
        user.is_admin = True
        await db.commit()
    _admin_cache.add(telegram_id)


async def remove_admin(telegram_id: int) -> bool:
    """Adminni olib tashlaydi. Sozlamalardagi super-admin bo'lsa False qaytaradi."""
    if telegram_id in SUPER_ADMINS:
        return False
    async with SessionLocal() as db:
        user = await db.get(BotUser, telegram_id)
        if user is not None:
            user.is_admin = False
            await db.commit()
    _admin_cache.discard(telegram_id)
    return True


def admin_ids() -> list[int]:
    return sorted(_admin_cache)

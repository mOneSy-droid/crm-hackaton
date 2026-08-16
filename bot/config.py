"""Bot sozlamalari — hammasi environment variable orqali."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # utf-8-sig: Windowsda .env ko'pincha BOM bilan saqlanadi (Notepad, PowerShell
    # `Out-File -Encoding utf8`). BOM bo'lsa birinchi kalit "﻿TELEGRAM_BOT_TOKEN"
    # bo'lib o'qiladi va topilmaydi.
    load_dotenv(Path(__file__).resolve().parent / ".env", encoding="utf-8-sig")
except ImportError:  # dotenv ixtiyoriy — Railway'da env o'zi beriladi
    pass


def _clean_db_url(raw: str) -> str:
    """Railway `postgres://` beradi — SQLAlchemy async drayveriga o'giradi.

    Eski koddagi xato: URL shartsiz `sqlite:///` deb qaralardi va Postgres
    manzili bilan yiqilardi.
    """
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://") :]
    if raw.startswith("sqlite://") and "+aiosqlite" not in raw:
        raw = "sqlite+aiosqlite://" + raw[len("sqlite://") :]
    return raw


TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

CRM_API_URL: str = os.getenv("CRM_API_URL", "http://localhost:8000").rstrip("/")
BOT_HMAC_SECRET: str = os.getenv("BOT_HMAC_SECRET", "dev-only-bot-shared-secret-change-me")

# Railway Postgres `DATABASE_URL` nomi bilan keladi; o'zimizniki ustunroq
BOT_DATABASE_URL: str = _clean_db_url(
    os.getenv("BOT_DATABASE_URL") or os.getenv("DATABASE_URL") or "sqlite+aiosqlite:///./bot.db"
)

SUPER_ADMINS: set[int] = {
    int(part.strip())
    for part in os.getenv("BOT_SUPER_ADMINS", "").split(",")
    if part.strip().isdigit()
}

OUTBOX_POLL_SECONDS: int = int(os.getenv("OUTBOX_POLL_SECONDS", "5"))

DEFAULT_LANGUAGE = "uz"
LANGUAGES = ("uz", "ru", "en")


def require_token() -> str:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN berilmagan.\n"
            "  .env fayliga qo'shing yoki Railway Variables'ga yozing."
        )
    return TELEGRAM_BOT_TOKEN

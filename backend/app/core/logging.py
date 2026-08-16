from __future__ import annotations

import logging
import re
import sys

from app.core.config import settings

# Telefon raqami, Telegram bot tokeni va Bearer tokenlar logda ochiq turmasligi kerak.
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{6,10}:[A-Za-z0-9_-]{30,}\b"), "<bot-token>"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"), "Bearer <redacted>"),
    (re.compile(r"\+?\d{9,15}"), "<phone>"),
]


class RedactingFilter(logging.Filter):
    """Maxfiy qiymatlarni log yozuvidan olib tashlaydi."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - log hech qachon ilovani yiqitmasin
            return True
        redacted = message
        for pattern, replacement in _REDACTIONS:
            redacted = pattern.sub(replacement, redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def mask_phone(phone: str | None) -> str:
    """`+998901234567` -> `+9989****4567` — UI va logda ko'rsatish uchun."""
    if not phone:
        return ""
    digits = phone.strip()
    if len(digits) <= 8:
        return "*" * len(digits)
    return f"{digits[:5]}{'*' * (len(digits) - 9)}{digits[-4:]}"


def setup_logging() -> None:
    level = logging.DEBUG if settings.ENV == "dev" else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s | %(message)s")
    )
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn o'z handlerlarini qo'yadi — ularni ham filtrlaymiz
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DB_ECHO else logging.WARNING
    )
    # Bu kutubxonalar DEBUG darajasida foydali bo'lmagan shovqin chiqaradi
    for noisy in ("aiosqlite", "asyncio", "httpcore", "httpx", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

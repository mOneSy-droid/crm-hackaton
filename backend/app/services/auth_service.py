from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_opaque_token,
    token_fingerprint,
)
from app.db.base import utcnow
from app.models import LoginToken, RefreshToken, User
from app.schemas.auth import TokenPair


async def issue_token_pair(db: AsyncSession, user: User) -> TokenPair:
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_fingerprint(refresh),
            expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=utcnow(),
        )
    )
    user.last_login_at = utcnow()
    await db.commit()

    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def rotate_refresh_token(db: AsyncSession, user: User, old_token: str) -> TokenPair:
    """Eski refresh tokenni bekor qilib, yangi juftlik beradi."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_fingerprint(old_token))
        .values(revoked_at=utcnow())
    )
    return await issue_token_pair(db, user)


async def find_valid_refresh_token(db: AsyncSession, token: str) -> RefreshToken | None:
    row = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_fingerprint(token))
    )
    if row is None or row.revoked_at is not None:
        return None
    if _aware(row.expires_at) < utcnow():
        return None
    return row


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


# ---------------------------------------------------------------------------
# Botdan saytga bir martalik kirish
# ---------------------------------------------------------------------------


async def create_login_link(db: AsyncSession, user: User, next_path: str | None = None) -> tuple[str, datetime]:
    """Bir martalik token yaratib, frontenddagi to'liq URL'ni qaytaradi.

    Token bazada faqat SHA-256 hash ko'rinishida saqlanadi.
    """
    raw = generate_opaque_token(32)
    expires_at = utcnow() + timedelta(minutes=settings.LOGIN_TOKEN_EXPIRE_MINUTES)

    db.add(
        LoginToken(
            user_id=user.id,
            token_hash=token_fingerprint(raw),
            expires_at=expires_at,
            created_at=utcnow(),
        )
    )
    await db.commit()

    url = f"{settings.FRONTEND_URL.rstrip('/')}/auth/telegram?token={quote(raw)}"
    if next_path:
        url += f"&next={quote(next_path)}"
    return url, expires_at


async def consume_login_token(db: AsyncSession, raw_token: str) -> User | None:
    """Tokenni bir marta ishlatadi. Muddati o'tgan/ishlatilgan bo'lsa None."""
    row = await db.scalar(
        select(LoginToken).where(LoginToken.token_hash == token_fingerprint(raw_token))
    )
    if row is None or row.used_at is not None or _aware(row.expires_at) < utcnow():
        return None

    row.used_at = utcnow()
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        await db.commit()
        return None
    await db.commit()
    return user


def _aware(value: datetime) -> datetime:
    """SQLite timezone'siz datetime qaytaradi — solishtirishdan oldin UTC qilamiz."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

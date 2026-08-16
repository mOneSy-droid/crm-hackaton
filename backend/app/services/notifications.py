from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models import Language, NotificationOutbox

# Bot shu kalitlar bo'yicha o'z shablonini tanlaydi
KIND_NEW_REVIEW = "new_review"
KIND_CREDENTIALS = "credentials"
KIND_BOT_STATUS = "bot_status"
KIND_REVIEW_MODERATED = "review_moderated"
KIND_OWNER_REPLY = "owner_reply"
#: Restoranning shaxsiy boti mijozdan yig'gan ma'lumot (buyurtma, bron, savol)
KIND_TENANT_LEAD = "tenant_lead"


async def enqueue(
    db: AsyncSession,
    *,
    telegram_id: int | None,
    kind: str,
    payload: dict[str, Any],
    language: Language = Language.UZ,
) -> None:
    """Botga yuborilishi kerak bo'lgan xabarni navbatga qo'yadi.

    `telegram_id` yo'q bo'lsa (masalan egasi hali botga yozmagan) — jimgina o'tkazib yuboriladi.
    Commit chaqiruvchi tomonda bo'ladi.
    """
    if not telegram_id:
        return
    db.add(
        NotificationOutbox(
            telegram_id=telegram_id,
            kind=kind,
            payload=json.dumps(payload, ensure_ascii=False),
            language=language,
            created_at=utcnow(),
        )
    )

from __future__ import annotations

import json
import re
import secrets
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Restaurant, Review, ReviewStatus

_CYRILLIC_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(value: str) -> str:
    """Restoran nomidan URL uchun yaroqli slug yasaydi (kirill ham qo'llab-quvvatlanadi)."""
    lowered = value.strip().lower()
    transliterated = "".join(_CYRILLIC_MAP.get(ch, ch) for ch in lowered)
    normalized = unicodedata.normalize("NFKD", transliterated)
    ascii_only = normalized.encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug[:120] or "restoran"


async def unique_slug(db: AsyncSession, name: str) -> str:
    base = slugify(name)
    candidate = base
    for _ in range(5):
        exists = await db.scalar(select(Restaurant.id).where(Restaurant.slug == candidate))
        if exists is None:
            return candidate
        candidate = f"{base}-{secrets.token_hex(2)}"
    return f"{base}-{secrets.token_hex(4)}"


def parse_attributes(raw: str | None) -> dict[str, str]:
    """Bazadagi JSON matnni lug'atga aylantiradi (buzuq bo'lsa bo'sh lug'at)."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}


def merge_attributes(raw: str | None, changes: dict[str, str] | None) -> str:
    """Sohaga xos maydonlarni ustiga qo'shadi.

    Butunlay almashtirmaydi: bot bitta maydonni yangilaganda qolganlari
    yo'qolmasligi kerak. `None` qiymat maydonni o'chiradi.
    """
    current = parse_attributes(raw)
    for key, value in (changes or {}).items():
        if value is None or value == "":
            current.pop(key, None)
        else:
            current[str(key)] = str(value)
    return json.dumps(current, ensure_ascii=False)


async def recalculate_rating(db: AsyncSession, restaurant_id: int) -> None:
    """Reytingni tasdiqlangan sharhlar asosida qayta hisoblaydi.

    Sharh qo'shilganda, moderatsiya qilinganda va o'chirilganda chaqiriladi.
    """
    row = (
        await db.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(
                Review.restaurant_id == restaurant_id,
                Review.status == ReviewStatus.APPROVED,
            )
        )
    ).one()
    avg, count = row[0], row[1] or 0
    restaurant = await db.get(Restaurant, restaurant_id)
    if restaurant is None:
        return
    restaurant.rating_avg = round(float(avg), 2) if avg is not None else 0.0
    restaurant.rating_count = int(count)

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

# Kengaytmaga emas, fayl boshidagi imzoga ishonamiz — ".jpg" deb nomlangan
# skript yuklab bo'lmasin.
_MAGIC: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
]
_WEBP_PREFIX = b"RIFF"
_WEBP_TAG = b"WEBP"


def _detect_extension(head: bytes) -> str | None:
    for magic, ext in _MAGIC:
        if head.startswith(magic):
            return ext
    if head[:4] == _WEBP_PREFIX and head[8:12] == _WEBP_TAG:
        return ".webp"
    return None


def media_root() -> Path:
    root = Path(settings.MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_image(file: UploadFile, folder: str = "uploads") -> str:
    """Rasmni diskka saqlab, ochiq URL qaytaradi.

    Railway'da `MEDIA_ROOT` volume'ga ulanishi kerak, aks holda deployda yo'qoladi.
    """
    content = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Rasm hajmi {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB dan oshmasligi kerak",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Bo'sh fayl yuborildi")

    extension = _detect_extension(content[:16])
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Faqat JPG, PNG, GIF yoki WEBP rasm yuklash mumkin",
        )

    today = datetime.now(timezone.utc).strftime("%Y/%m")
    directory = media_root() / folder / today
    directory.mkdir(parents=True, exist_ok=True)

    name = f"{secrets.token_urlsafe(16)}{extension}"
    (directory / name).write_bytes(content)

    relative = f"{folder}/{today}/{name}"
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{settings.MEDIA_URL_PATH}/{relative}"

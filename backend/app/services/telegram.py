from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class BotTokenInvalid(Exception):
    """@BotFather tokeni noto'g'ri yoki bekor qilingan."""


async def verify_bot_token(token: str) -> dict:
    """Telegram `getMe` orqali tokenni tekshiradi.

    Muvaffaqiyatli bo'lsa bot haqidagi ma'lumotni qaytaradi (`id`, `username`, ...).
    Token hech qachon log qilinmaydi.
    """
    url = f"{TELEGRAM_API}/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        logger.warning("Telegram getMe so'rovi muvaffaqiyatsiz: %s", type(exc).__name__)
        raise BotTokenInvalid("Telegram bilan bog'lanib bo'lmadi, birozdan keyin urinib ko'ring") from exc

    if response.status_code == 401:
        raise BotTokenInvalid("Token noto'g'ri — @BotFather dan yangisini oling")
    if response.status_code != 200:
        raise BotTokenInvalid("Telegram tokenni tasdiqlamadi")

    data = response.json()
    if not data.get("ok") or "result" not in data:
        raise BotTokenInvalid("Telegram tokenni tasdiqlamadi")
    return data["result"]

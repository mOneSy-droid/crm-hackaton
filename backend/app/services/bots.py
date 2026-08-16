from __future__ import annotations

import hashlib
import json
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret, generate_opaque_token
from app.db.base import utcnow
from app.models import BotInstance, BotStatus, Restaurant
from app.schemas.bot import BotConfigOut, BotInstanceOut, BotQuestionnaire
from app.services.botbuilder import generate_bot_config
from app.services.telegram import BotTokenInvalid, verify_bot_token

logger = logging.getLogger(__name__)


def to_bot_out(bot: BotInstance) -> BotInstanceOut:
    return BotInstanceOut(
        id=bot.id,
        restaurant_id=bot.restaurant_id,
        bot_username=bot.bot_username,
        token_hint=bot.token_hint,
        status=bot.status,
        status_detail=bot.status_detail,
        purpose=bot.purpose,
        languages=bot.languages,
        features=bot.features,
        tone=bot.tone,
        has_generated_config=bool(bot.generated_config),
        started_at=bot.started_at,
        created_at=bot.created_at,
    )


async def save_questionnaire(
    db: AsyncSession, restaurant: Restaurant, data: BotQuestionnaire
) -> BotInstance:
    """Anketani saqlaydi va AI orqali bot konfiguratsiyasini generatsiya qiladi.

    Restoran uchun bitta bot qoraliyi yetarli — mavjudi yangilanadi.
    """
    bot = await db.scalar(
        select(BotInstance)
        .where(BotInstance.restaurant_id == restaurant.id)
        .order_by(BotInstance.id.desc())
    )
    if bot is None:
        bot = BotInstance(restaurant_id=restaurant.id)
        db.add(bot)

    bot.purpose = data.purpose
    bot.languages = ",".join(lang.value for lang in data.languages)
    bot.features = ",".join(data.features)
    bot.tone = data.tone

    config = await generate_bot_config(
        restaurant_name=restaurant.name,
        purpose=data.purpose,
        languages=[lang.value for lang in data.languages],
        features=data.features,
        tone=data.tone,
    )
    bot.generated_config = json.dumps(config, ensure_ascii=False)

    if bot.status in (BotStatus.DRAFT, BotStatus.FAILED):
        bot.status = BotStatus.PENDING
        bot.status_detail = "Endi @BotFather dan token oling va shu yerga yuboring"

    await db.flush()
    return bot


async def attach_token(db: AsyncSession, bot: BotInstance, raw_token: str) -> BotInstance:
    """Tokenni Telegramda tekshiradi va shifrlab saqlaydi.

    Ochiq token na bazaga, na logga tushadi.
    """
    # Asosiy botning o'z tokenini ulab bo'lmaydi — Telegram tekshiruvidan
    # OLDIN rad etamiz (tarmoqsiz ham ishlaydi, testlash oson)
    token_head = raw_token.split(":", 1)[0]
    if (
        settings.MAIN_BOT_TELEGRAM_ID
        and token_head == str(settings.MAIN_BOT_TELEGRAM_ID)
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Bu asosiy botning o'z tokeni! @BotFather'da /newbot buyrug'i "
                "bilan YANGI bot yarating va o'shaning tokenini yuboring."
            ),
        )

    try:
        info = await verify_bot_token(raw_token)
    except BotTokenInvalid as exc:
        bot.status = BotStatus.FAILED
        bot.status_detail = str(exc)
        await db.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    bot_user_id = int(info["id"])
    taken_by = await db.scalar(
        select(BotInstance.id).where(
            BotInstance.bot_user_id == bot_user_id, BotInstance.id != bot.id
        )
    )
    if taken_by is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu bot allaqachon boshqa restoranga ulangan",
        )

    bot.bot_user_id = bot_user_id
    bot.bot_username = info.get("username")
    bot.token_encrypted = encrypt_secret(raw_token)
    bot.token_hint = raw_token[-4:]
    bot.webhook_secret = bot.webhook_secret or generate_opaque_token(24)
    bot.status = BotStatus.ACTIVE
    bot.status_detail = None
    bot.started_at = utcnow()

    await db.flush()
    logger.info("Bot #%s restoran #%s uchun faollashtirildi", bot.id, bot.restaurant_id)
    return bot


async def set_status(
    db: AsyncSession, bot: BotInstance, new_status: BotStatus, detail: str | None = None
) -> BotInstance:
    bot.status = new_status
    bot.status_detail = detail
    if new_status == BotStatus.STOPPED:
        bot.started_at = None
    await db.flush()
    return bot


async def build_runner_config(db: AsyncSession, bot: BotInstance) -> BotConfigOut:
    """Bot runner (alohida process) uchun to'liq konfiguratsiya.

    Faqat HMAC bilan imzolangan ichki so'rovlar orqali beriladi.
    """
    if not bot.token_encrypted:
        raise HTTPException(status_code=409, detail="Bu botga hali token ulanmagan")

    restaurant = await db.get(Restaurant, bot.restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")

    try:
        token = decrypt_secret(bot.token_encrypted)
    except ValueError as exc:
        logger.error("Bot #%s tokenini deshifrlash muvaffaqiyatsiz", bot.id)
        raise HTTPException(
            status_code=500, detail="Token deshifrlanmadi — tokenni qayta ulang"
        ) from exc

    try:
        config = json.loads(bot.generated_config) if bot.generated_config else {}
    except json.JSONDecodeError:
        config = {}

    # Runner shu xesh o'zgarganda botni qayta ko'taradi. Token ham kiradi —
    # egasi tokenni almashtirsa eski nusxa to'xtatilishi kerak.
    version = hashlib.sha256(
        f"{bot.updated_at.isoformat()}|{bot.token_hint}|{bot.generated_config or ''}".encode()
    ).hexdigest()[:16]

    return BotConfigOut(
        bot_id=bot.id,
        restaurant_id=restaurant.id,
        restaurant_name=restaurant.name,
        token=token,
        languages=(bot.languages or "uz").split(","),
        tone=bot.tone,
        config=config,
        config_version=version,
    )

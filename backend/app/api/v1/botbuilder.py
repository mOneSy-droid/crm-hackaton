from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import select

from app.api.deps import DbSession, OwnedRestaurant
from app.models import BotInstance, BotStatus
from app.schemas.bot import BotInstanceOut, BotQuestionnaire, BotTokenIn
from app.services import bots as bot_service

router = APIRouter(prefix="/restaurants", tags=["botbuilder"])


async def _load_bot(db, restaurant_id: int, bot_id: int) -> BotInstance:
    bot = await db.get(BotInstance, bot_id)
    if bot is None or bot.restaurant_id != restaurant_id:
        raise HTTPException(status_code=404, detail="Bot topilmadi")
    return bot


@router.get(
    "/{restaurant_id}/bots", response_model=list[BotInstanceOut], summary="Restoran botlari"
)
async def list_bots(restaurant: OwnedRestaurant, db: DbSession) -> list[BotInstanceOut]:
    rows = (
        await db.scalars(
            select(BotInstance)
            .where(BotInstance.restaurant_id == restaurant.id)
            .order_by(BotInstance.id.desc())
        )
    ).all()
    return [bot_service.to_bot_out(b) for b in rows]


@router.post(
    "/{restaurant_id}/bots/questionnaire",
    response_model=BotInstanceOut,
    summary="Anketa asosida bot logikasini generatsiya qilish",
)
async def submit_questionnaire(
    payload: BotQuestionnaire, restaurant: OwnedRestaurant, db: DbSession
) -> BotInstanceOut:
    bot = await bot_service.save_questionnaire(db, restaurant, payload)
    await db.commit()
    await db.refresh(bot)
    return bot_service.to_bot_out(bot)


@router.get(
    "/{restaurant_id}/bots/{bot_id}/config",
    summary="Generatsiya qilingan konfiguratsiyani ko'rish",
    response_model=dict,
)
async def get_generated_config(
    bot_id: Annotated[int, Path(ge=1)], restaurant: OwnedRestaurant, db: DbSession
) -> dict:
    """Token QAYTARILMAYDI — faqat bot matnlari va oqimlari."""
    bot = await _load_bot(db, restaurant.id, bot_id)
    if not bot.generated_config:
        raise HTTPException(status_code=404, detail="Konfiguratsiya hali yaratilmagan")
    return json.loads(bot.generated_config)


@router.post(
    "/{restaurant_id}/bots/{bot_id}/token",
    response_model=BotInstanceOut,
    summary="@BotFather tokenini ulash",
)
async def set_bot_token(
    bot_id: Annotated[int, Path(ge=1)],
    payload: BotTokenIn,
    restaurant: OwnedRestaurant,
    db: DbSession,
) -> BotInstanceOut:
    bot = await _load_bot(db, restaurant.id, bot_id)
    bot = await bot_service.attach_token(db, bot, payload.token)
    await db.commit()
    await db.refresh(bot)
    return bot_service.to_bot_out(bot)


@router.post(
    "/{restaurant_id}/bots/{bot_id}/stop", response_model=BotInstanceOut, summary="Botni to'xtatish"
)
async def stop_bot(
    bot_id: Annotated[int, Path(ge=1)], restaurant: OwnedRestaurant, db: DbSession
) -> BotInstanceOut:
    bot = await _load_bot(db, restaurant.id, bot_id)
    bot = await bot_service.set_status(db, bot, BotStatus.STOPPED, "Egasi to'xtatgan")
    await db.commit()
    await db.refresh(bot)
    return bot_service.to_bot_out(bot)


@router.post(
    "/{restaurant_id}/bots/{bot_id}/start",
    response_model=BotInstanceOut,
    summary="Botni qayta ishga tushirish",
)
async def start_bot(
    bot_id: Annotated[int, Path(ge=1)], restaurant: OwnedRestaurant, db: DbSession
) -> BotInstanceOut:
    bot = await _load_bot(db, restaurant.id, bot_id)
    if not bot.token_encrypted:
        raise HTTPException(status_code=409, detail="Avval @BotFather tokenini ulang")
    bot = await bot_service.set_status(db, bot, BotStatus.ACTIVE)
    await db.commit()
    await db.refresh(bot)
    return bot_service.to_bot_out(bot)

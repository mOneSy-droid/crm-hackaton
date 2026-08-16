from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_login, generate_password, hash_password
from app.models import Category, Industry, Restaurant, User, UserRole
from app.schemas.bot import RestaurantRegisterIn, TelegramUserIn
from app.services.restaurants import merge_attributes, slugify, unique_slug
from app.services.seed import default_industry_id

logger = logging.getLogger(__name__)


async def upsert_telegram_user(db: AsyncSession, data: TelegramUserIn) -> User:
    """Telegram foydalanuvchisini topadi yoki yaratadi.

    Bo'sh qiymatlar mavjud ma'lumotni o'chirmaydi — bot har safar hamma
    maydonni yubormasligi mumkin.
    """
    user = await db.scalar(select(User).where(User.telegram_id == data.telegram_id))
    if user is None:
        user = User(telegram_id=data.telegram_id, role=UserRole.CUSTOMER)
        db.add(user)

    if data.telegram_username:
        user.telegram_username = data.telegram_username
    if data.full_name:
        user.full_name = data.full_name
    if data.phone:
        user.phone = data.phone
    user.language = data.language

    await db.flush()
    return user


async def _unique_username(db: AsyncSession, restaurant_name: str) -> str:
    base = slugify(restaurant_name).replace("-", "")[:10] or "rest"
    for _ in range(6):
        candidate = generate_login(base)
        exists = await db.scalar(select(User.id).where(User.username == candidate))
        if exists is None:
            return candidate
    return generate_login(base + "x")


async def register_restaurant(
    db: AsyncSession, payload: RestaurantRegisterIn
) -> tuple[Restaurant, User, str | None, bool]:
    """Botdan kelgan anketani restoranga aylantiradi.

    Qaytaradi: (restoran, egasi, ochiq_parol_yoki_None, allaqachon_mavjudmi).
    Parol faqat birinchi marta generatsiya qilinganda qaytariladi —
    keyin bazada faqat hash qoladi.
    """
    user = await upsert_telegram_user(db, payload.user)

    # Bir xil nomdagi restoran qayta yuborilsa yangisini yaratmaymiz
    # (botda tarmoq uzilib, "Tasdiqlash" ikki marta bosilishi mumkin).
    existing = await db.scalar(
        select(Restaurant).where(
            Restaurant.owner_id == user.id,
            func.lower(Restaurant.name) == payload.name.strip().lower(),
        )
    )
    if existing is not None:
        return existing, user, None, True

    if user.role == UserRole.CUSTOMER:
        user.role = UserRole.OWNER

    plain_password: str | None = None
    if not user.username or not user.password_hash:
        user.username = user.username or await _unique_username(db, payload.name)
        plain_password = generate_password()
        user.password_hash = hash_password(plain_password)
        user.must_change_password = True

    # Soha ko'rsatilmasa restoran deb qabul qilamiz — eski botlar
    # `industry_key` yubormaydi va ular ishlashda davom etishi kerak
    industry_id: int | None = None
    if payload.industry_key:
        industry_id = await db.scalar(
            select(Industry.id).where(Industry.key == payload.industry_key)
        )
        if industry_id is None:
            # Bot bu xabarni to'g'ridan-to'g'ri foydalanuvchiga ko'rsatadi
            raise HTTPException(
                status_code=422,
                detail="Bunday soha yo'q. Ro'yxatdan sohani qaytadan tanlang.",
            )
    if industry_id is None:
        industry_id = await default_industry_id(db)

    # Yo'nalish faqat shu soha ichidan tanlanadi
    category_id: int | None = None
    if payload.category_key:
        category_id = await db.scalar(
            select(Category.id).where(
                Category.key == payload.category_key,
                Category.industry_id == industry_id,
            )
        )

    restaurant = Restaurant(
        owner_id=user.id,
        industry_id=industry_id,
        category_id=category_id,
        attributes=merge_attributes(None, payload.attributes),
        name=payload.name.strip(),
        slug=await unique_slug(db, payload.name),
        description=payload.description,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        work_hours=payload.work_hours,
        phone=payload.phone or user.phone,
        logo_url=payload.logo_url,
    )
    db.add(restaurant)
    await db.flush()

    logger.info("Yangi restoran #%s ro'yxatdan o'tdi (egasi #%s)", restaurant.id, user.id)
    return restaurant, user, plain_password, False

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import to_me_out
from app.core.security import hash_password, verify_password
from app.models import Restaurant, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ExchangeTokenRequest,
    LoginRequest,
    MeOut,
    RefreshRequest,
    TokenPair,
)
from app.schemas.common import Msg
from app.services import auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair, summary="Login va parol bilan kirish")
async def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    user = await db.scalar(select(User).where(User.username == payload.username.lower().strip()))

    # Foydalanuvchi topilmasa ham parolni tekshirgandek vaqt sarflaymiz —
    # javob vaqtiga qarab login mavjudligini aniqlab bo'lmasin.
    stored = user.password_hash if user and user.password_hash else "pbkdf2_sha256$1$00$00"
    password_ok = verify_password(payload.password, stored)

    if user is None or not password_ok or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Login yoki parol noto'g'ri"
        )

    logger.info("Foydalanuvchi #%s login/parol bilan kirdi", user.id)
    return await auth_service.issue_token_pair(db, user)


@router.post(
    "/telegram/exchange",
    response_model=TokenPair,
    summary="Botdagi bir martalik tokenni JWT ga almashtirish",
)
async def exchange_telegram_token(payload: ExchangeTokenRequest, db: DbSession) -> TokenPair:
    """Bot yuborgan "Saytga avtomatik kirish" linkidagi token shu yerda ishlatiladi.

    Token bir martalik: ikkinchi urinishda 401 qaytadi.
    """
    user = await auth_service.consume_login_token(db, payload.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Link eskirgan yoki allaqachon ishlatilgan. Botdan yangisini oling.",
        )
    logger.info("Foydalanuvchi #%s bot linki orqali kirdi", user.id)
    return await auth_service.issue_token_pair(db, user)


@router.post("/refresh", response_model=TokenPair, summary="Access tokenni yangilash")
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    row = await auth_service.find_valid_refresh_token(db, payload.refresh_token)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token yaroqsiz"
        )
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token yaroqsiz"
        )
    return await auth_service.rotate_refresh_token(db, user, payload.refresh_token)


@router.post("/logout", response_model=Msg, summary="Barcha sessiyalarni yopish")
async def logout(user: CurrentUser, db: DbSession) -> Msg:
    await auth_service.revoke_all_refresh_tokens(db, user.id)
    await db.commit()
    return Msg(detail="Chiqildi")


@router.get("/me", response_model=MeOut, summary="Joriy foydalanuvchi")
async def me(user: CurrentUser, db: DbSession) -> MeOut:
    ids = list(
        (await db.scalars(select(Restaurant.id).where(Restaurant.owner_id == user.id))).all()
    )
    return to_me_out(user, ids)


@router.post("/change-password", response_model=Msg, summary="Parolni o'zgartirish")
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, db: DbSession
) -> Msg:
    if not user.password_hash or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Joriy parol noto'g'ri")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    # Parol o'zgargach eski sessiyalar ishlamasin
    await auth_service.revoke_all_refresh_tokens(db, user.id)
    await db.commit()
    return Msg(detail="Parol yangilandi. Qaytadan kiring.")

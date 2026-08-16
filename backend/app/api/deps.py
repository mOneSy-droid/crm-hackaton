from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models import Restaurant, User, UserRole

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[AsyncSession, Depends(get_db)]

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Avtorizatsiya talab qilinadi",
    headers={"WWW-Authenticate": "Bearer"},
)


# ---------------------------------------------------------------------------
# Sayt foydalanuvchisi (JWT)
# ---------------------------------------------------------------------------


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessiya muddati tugadi, qaytadan kiring",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.PyJWTError:
        raise _UNAUTHORIZED from None

    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    """Ochiq endpointlar uchun: token bo'lsa foydalanuvchini beradi, bo'lmasa None.

    Yaroqsiz token 401 bermaydi — mehmon sifatida qaraladi.
    """
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except jwt.PyJWTError:
        return None
    user = await db.get(User, int(payload["sub"]))
    return user if user and user.is_active else None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole):
    async def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu amal uchun ruxsat yo'q",
            )
        return user

    return _check


require_admin = require_roles(UserRole.ADMIN)
AdminUser = Annotated[User, Depends(require_admin)]


async def get_owned_restaurant(
    db: DbSession,
    user: CurrentUser,
    restaurant_id: Annotated[int, Path(ge=1)],
) -> Restaurant:
    """Restoranni oladi va foydalanuvchi unga egalik qilishini tekshiradi.

    Admin har qanday restoranga kira oladi. Begona restoran uchun 404 qaytariladi —
    403 bersak, mavjudligini fosh qilgan bo'lardik.
    """
    restaurant = await db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")
    if user.role != UserRole.ADMIN and restaurant.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")
    return restaurant


OwnedRestaurant = Annotated[Restaurant, Depends(get_owned_restaurant)]

# Bot xizmatining imzosi `app.api.middleware.BotSignatureMiddleware` da
# tekshiriladi — `/api/v1/bot/*` yo'llari marshrutlashdan oldin filtrlanadi.

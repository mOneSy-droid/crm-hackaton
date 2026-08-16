from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Language, UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class ExchangeTokenRequest(BaseModel):
    """Botdagi "Saytga kirish" tugmasi bergan bir martalik token."""

    token: str = Field(min_length=20, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="access_token amal qilish muddati (sekund)")


class UserOut(BaseModel):
    id: int
    full_name: str | None
    username: str | None
    phone_masked: str | None = Field(
        default=None, description="To'liq raqam API orqali qaytarilmaydi"
    )
    role: UserRole
    language: Language
    telegram_username: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MeOut(UserOut):
    restaurant_ids: list[int] = []


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

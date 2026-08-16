from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models import BotStatus, Language
from app.schemas.restaurant import RestaurantOut, WorkHours


# ---------------------------------------------------------------------------
# Bot -> backend: ro'yxatdan o'tkazish
# ---------------------------------------------------------------------------


class TelegramUserIn(BaseModel):
    telegram_id: int
    telegram_username: str | None = Field(default=None, max_length=64)
    full_name: str | None = Field(default=None, max_length=150)
    language: Language = Language.UZ
    #: Telegram "Kontaktni yuborish" tugmasidan olingan raqam
    phone: str | None = Field(default=None, max_length=20)


class RestaurantRegisterIn(BaseModel):
    """Botdagi anketa to'liq to'ldirilib, foydalanuvchi "Tasdiqlash" bosgach yuboriladi."""

    user: TelegramUserIn
    name: str = Field(min_length=2, max_length=150)
    #: Soha kaliti: restaurant / market / clinic / gym.
    #: Berilmasa restoran deb qabul qilinadi (eski mijozlar bilan moslik uchun).
    industry_key: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    work_hours: WorkHours = Field(default=None, examples=["09:00-23:00"])
    phone: str | None = Field(default=None, max_length=20)
    category_key: str | None = Field(default=None, max_length=40)
    logo_url: str | None = Field(default=None, max_length=500)
    #: `Industry.fields` da tavsiflangan qo'shimcha javoblar
    attributes: dict[str, str] = Field(default_factory=dict)


class RestaurantRegisterOut(BaseModel):
    """Bot shu javobni foydalanuvchiga matn qilib yuboradi.

    `password` faqat SHU BIR MARTA qaytariladi — bazada hash saqlanadi.
    """

    restaurant: RestaurantOut
    username: str
    password: str | None = Field(
        default=None, description="Faqat birinchi ro'yxatdan o'tishda to'ldiriladi"
    )
    login_url: str = Field(description="Bir martalik tokenli avtomatik kirish linki")
    already_registered: bool = False


class LoginLinkRequest(BaseModel):
    telegram_id: int
    #: kirgandan keyin ochilishi kerak bo'lgan sahifa, masalan "/dashboard"
    next_path: str | None = Field(default=None, max_length=200)


class LoginLinkOut(BaseModel):
    login_url: str
    expires_at: datetime


class ProfileSyncOut(BaseModel):
    """Bot "Profilni tahrirlash"ni ochganda joriy ma'lumotni ko'rsatishi uchun."""

    restaurants: list[RestaurantOut]


class RestaurantSearchItem(BaseModel):
    id: int
    name: str
    address: str | None
    rating_avg: float
    rating_count: int
    #: Bot ro'yxatda soha belgisini ko'rsatishi uchun (🍽 / 🛒 / 🏥 / 🏋)
    industry_icon: str = "🏢"
    industry_key: str = "restaurant"


# ---------------------------------------------------------------------------
# BotBuilder
# ---------------------------------------------------------------------------


class BotQuestionnaire(BaseModel):
    purpose: str = Field(min_length=3, max_length=2000)
    languages: list[Language] = Field(default_factory=lambda: [Language.UZ], min_length=1)
    features: list[str] = Field(default_factory=list, max_length=20)
    tone: str | None = Field(default=None, max_length=120)


class BotInstanceCreate(BotQuestionnaire):
    restaurant_id: int


class BotTokenIn(BaseModel):
    """@BotFather bergan token. Faqat shifrlangan holda saqlanadi."""

    token: str = Field(min_length=20, max_length=100)

    @field_validator("token")
    @classmethod
    def _looks_like_bot_token(cls, v: str) -> str:
        v = v.strip()
        head, _, tail = v.partition(":")
        if not head.isdigit() or len(tail) < 20:
            raise ValueError("token '123456789:AA...' ko'rinishida bo'lishi kerak")
        return v


class BotInstanceOut(BaseModel):
    id: int
    restaurant_id: int
    bot_username: str | None
    token_hint: str | None = Field(default=None, description="Token oxiri, masalan '…7fQa'")
    status: BotStatus
    status_detail: str | None
    purpose: str | None
    languages: str | None
    features: str | None
    tone: str | None
    has_generated_config: bool = False
    started_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BotConfigOut(BaseModel):
    """Bot runner shu konfiguratsiyani olib, shaxsiy botni ishga tushiradi."""

    bot_id: int
    restaurant_id: int
    restaurant_name: str
    token: str = Field(description="Deshifrlangan token — faqat runner uchun")
    languages: list[str]
    tone: str | None
    config: dict = Field(default_factory=dict)
    #: Konfiguratsiya o'zgarganini arzon aniqlash uchun. Runner shu qiymat
    #: o'zgarsa botni qayta ishga tushiradi.
    config_version: str = Field(description="Konfiguratsiya va token xeshi")


class TenantLeadIn(BaseModel):
    """Shaxsiy bot yig'gan ma'lumot (buyurtma, bron, savol) — egasiga yuboriladi."""

    bot_id: int
    telegram_id: int
    #: konfiguratsiyadagi oqim identifikatori
    flow_id: str = Field(max_length=60)
    flow_label: str | None = Field(default=None, max_length=120)
    answers: dict[str, str] = Field(default_factory=dict)
    customer_name: str | None = Field(default=None, max_length=150)


# ---------------------------------------------------------------------------
# Bildirishnoma navbati
# ---------------------------------------------------------------------------


class OutboxItem(BaseModel):
    id: int
    telegram_id: int
    kind: str
    payload: dict
    language: Language
    created_at: datetime


class OutboxAck(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)

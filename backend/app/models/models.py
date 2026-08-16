from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OWNER = "owner"
    CUSTOMER = "customer"


class Language(str, enum.Enum):
    UZ = "uz"
    RU = "ru"
    EN = "en"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BotStatus(str, enum.Enum):
    DRAFT = "draft"          # anketa to'ldirilyapti
    PENDING = "pending"      # token kutilyapti / tekshirilyapti
    ACTIVE = "active"        # ishlab turibdi
    STOPPED = "stopped"      # egasi to'xtatgan
    FAILED = "failed"        # token noto'g'ri yoki ishga tushmadi


def _enum(python_enum: type[enum.Enum], name: str) -> SAEnum:
    """Bazada enum qiymatlari nom emas, qiymat sifatida saqlanadi ("owner", "uz")."""
    return SAEnum(
        python_enum,
        name=name,
        values_callable=lambda e: [member.value for member in e],
        native_enum=False,
        length=20,
    )


# ---------------------------------------------------------------------------
# Foydalanuvchilar
# ---------------------------------------------------------------------------


class User(Base, TimestampMixin):
    """Restoran egasi, mijoz yoki admin.

    Ro'yxatdan o'tish Telegram orqali bo'lgani uchun `telegram_id` asosiy
    identifikator. `username`/`password_hash` faqat saytga kirish uchun
    (restoran egalariga avtomatik generatsiya qilinadi).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))

    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    full_name: Mapped[str | None] = mapped_column(String(150))

    username: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    #: generatsiya qilingan parol egasiga hali ko'rsatilmagan bo'lsa True
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), default=UserRole.CUSTOMER)
    language: Mapped[Language] = mapped_column(_enum(Language, "language"), default=Language.UZ)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    restaurants: Mapped[list[Restaurant]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[Review]] = relationship(back_populates="author")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginToken(Base):
    """Bot yuboradigan "Saytga avtomatik kirish" tugmasi ortidagi bir martalik token."""

    __tablename__ = "login_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Restoran
# ---------------------------------------------------------------------------


class Industry(Base):
    """Faoliyat sohasi: restoran, do'kon, klinika, sport zali.

    Tizim bitta biznes modeli bilan ishlaydi — soha faqat MA'LUMOT.
    Yangi soha qo'shish uchun kod yozilmaydi, shu jadvalga qator qo'shiladi.

    Yorliqlar (`*_label_*`) bot va saytda matnlarni almashtiradi: restoranga
    "Taom qo'shish" deb ko'rinadigan tugma do'konga "Mahsulot qo'shish" bo'ladi.
    """

    __tablename__ = "industries"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    icon: Mapped[str] = mapped_column(String(8), default="🏢")

    #: Sohaning o'zi: "Restoranlar" / "Do'konlar"
    name_uz: Mapped[str] = mapped_column(String(80))
    name_ru: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))

    #: Bitta biznes: "restoran" / "do'kon" — gap ichida ishlatiladi
    entity_label_uz: Mapped[str] = mapped_column(String(60))
    entity_label_ru: Mapped[str] = mapped_column(String(60))
    entity_label_en: Mapped[str] = mapped_column(String(60))

    #: Katalogdagi bitta yozuv: "Taom" / "Mahsulot" / "Xizmat"
    item_label_uz: Mapped[str] = mapped_column(String(60))
    item_label_ru: Mapped[str] = mapped_column(String(60))
    item_label_en: Mapped[str] = mapped_column(String(60))

    #: Katalogning o'zi: "Menyu" / "Katalog" / "Xizmatlar"
    catalog_label_uz: Mapped[str] = mapped_column(String(60))
    catalog_label_ru: Mapped[str] = mapped_column(String(60))
    catalog_label_en: Mapped[str] = mapped_column(String(60))

    #: Shu sohaga xos qo'shimcha savollar (JSON ro'yxat). Bot ham, sayt ham
    #: shu tavsif asosida maydonlarni o'zi chizadi — kodda `if` yozilmaydi.
    field_schema: Mapped[str] = mapped_column(Text, default="[]")

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    categories: Mapped[list[Category]] = relationship(back_populates="industry")
    restaurants: Mapped[list[Restaurant]] = relationship(back_populates="industry")


class Category(Base):
    """Soha ichidagi yo'nalish: restoranda milliy/fast-food, do'konda oziq-ovqat/kiyim."""

    __tablename__ = "categories"
    __table_args__ = (
        # Kalit soha ichida yagona — turli sohalarda "boshqa" takrorlanishi mumkin
        UniqueConstraint("industry_id", "key", name="uq_categories_industry_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    industry_id: Mapped[int] = mapped_column(
        ForeignKey("industries.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(40), index=True)
    name_uz: Mapped[str] = mapped_column(String(80))
    name_ru: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    industry: Mapped[Industry] = relationship(back_populates="categories")
    restaurants: Mapped[list[Restaurant]] = relationship(back_populates="category")


class Restaurant(Base, TimestampMixin):
    """Biznes — restoran, do'kon, klinika yoki sport zali.

    Jadval nomi tarixiy sabab bilan `restaurants` bo'lib qoldi; aslida bu
    universal biznes yozuvi va sohasi `industry_id` bilan belgilanadi.
    """

    __tablename__ = "restaurants"
    __table_args__ = (
        Index("ix_restaurants_rating", "rating_avg"),
        Index("ix_restaurants_active_verified", "is_active", "is_verified"),
        Index("ix_restaurants_industry", "industry_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    industry_id: Mapped[int] = mapped_column(
        ForeignKey("industries.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )

    name: Mapped[str] = mapped_column(String(150), index=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    address: Mapped[str | None] = mapped_column(String(300))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    #: "09:00-23:00" ko'rinishida; bot shu formatda so'raydi
    work_hours: Mapped[str | None] = mapped_column(String(40))
    phone: Mapped[str | None] = mapped_column(String(20))
    logo_url: Mapped[str | None] = mapped_column(String(500))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    #: Sohaga xos qo'shimcha maydonlar (JSON obyekt).
    #: Masalan do'kon uchun {"delivery": "Bor", "min_order": "50000"}.
    #: Qaysi maydonlar bo'lishi `Industry.field_schema` da yozilgan.
    attributes: Mapped[str] = mapped_column(Text, default="{}")

    #: sharh qo'shilganda/tasdiqlanganda qayta hisoblanadi
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)

    owner: Mapped[User] = relationship(back_populates="restaurants")
    industry: Mapped[Industry] = relationship(back_populates="restaurants")
    category: Mapped[Category | None] = relationship(back_populates="restaurants")
    reviews: Mapped[list[Review]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    menu_items: Mapped[list[MenuItem]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    bots: Mapped[list[BotInstance]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )


class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float | None] = mapped_column(Float)
    section: Mapped[str | None] = mapped_column(String(80))
    photo_url: Mapped[str | None] = mapped_column(String(500))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    restaurant: Mapped[Restaurant] = relationship(back_populates="menu_items")


# ---------------------------------------------------------------------------
# Sharhlar
# ---------------------------------------------------------------------------


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
        Index("ix_reviews_restaurant_status", "restaurant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReviewStatus] = mapped_column(
        _enum(ReviewStatus, "review_status"), default=ReviewStatus.APPROVED, index=True
    )
    moderation_note: Mapped[str | None] = mapped_column(String(300))
    owner_reply: Mapped[str | None] = mapped_column(Text)
    owner_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), default="telegram")

    restaurant: Mapped[Restaurant] = relationship(back_populates="reviews")
    author: Mapped[User | None] = relationship(back_populates="reviews")
    photos: Mapped[list[ReviewPhoto]] = relationship(
        back_populates="review", cascade="all, delete-orphan", lazy="selectin"
    )


class ReviewPhoto(Base):
    __tablename__ = "review_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))

    review: Mapped[Review] = relationship(back_populates="photos")


# ---------------------------------------------------------------------------
# BotBuilder
# ---------------------------------------------------------------------------


class BotInstance(Base, TimestampMixin):
    """Restoranning @BotFather orqali yaratgan shaxsiy boti.

    Token HECH QACHON ochiq saqlanmaydi — faqat `token_encrypted` (Fernet).
    """

    __tablename__ = "bot_instances"
    __table_args__ = (UniqueConstraint("bot_user_id", name="uq_bot_instances_bot_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )

    bot_username: Mapped[str | None] = mapped_column(String(64))
    bot_user_id: Mapped[int | None] = mapped_column(BigInteger)
    token_encrypted: Mapped[str | None] = mapped_column(Text)
    #: token'ning oxirgi 4 belgisi — UI'da "…AbCd" ko'rinishida ko'rsatish uchun
    token_hint: Mapped[str | None] = mapped_column(String(8))

    status: Mapped[BotStatus] = mapped_column(_enum(BotStatus, "bot_status"), default=BotStatus.DRAFT)
    status_detail: Mapped[str | None] = mapped_column(String(300))

    #: BotBuilder anketasi javoblari
    purpose: Mapped[str | None] = mapped_column(Text)
    languages: Mapped[str | None] = mapped_column(String(40), default="uz")
    features: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(String(120))

    #: AI generatsiya qilgan bot konfiguratsiyasi (JSON matn ko'rinishida)
    generated_config: Mapped[str | None] = mapped_column(Text)
    #: bot process'i uchun webhook yo'lidagi maxfiy segment
    webhook_secret: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    restaurant: Mapped[Restaurant] = relationship(back_populates="bots")


# ---------------------------------------------------------------------------
# Bildirishnomalar (backend -> bot)
# ---------------------------------------------------------------------------


class NotificationOutbox(Base):
    """Bot pollab oladigan navbat.

    Backend Telegram'ga to'g'ridan-to'g'ri yozmaydi — bot xizmati
    `GET /bot/outbox` orqali oladi va yetkazgach `ack` qiladi. Shu tufayli
    Telegram token faqat bot tomonida qoladi.
    """

    __tablename__ = "notification_outbox"
    __table_args__ = (Index("ix_outbox_undelivered", "delivered_at", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    #: bot qaysi shablonni ishlatishini biladi: new_review, credentials, bot_status...
    kind: Mapped[str] = mapped_column(String(40))
    #: shablonga qo'yiladigan qiymatlar, JSON matn
    payload: Mapped[str] = mapped_column(Text, default="{}")
    language: Mapped[Language] = mapped_column(_enum(Language, "language"), default=Language.UZ)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)

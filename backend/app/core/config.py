from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        # utf-8-sig: Windowsda .env ko'pincha BOM bilan saqlanadi (Notepad,
        # PowerShell `Out-File -Encoding utf8`). BOM bo'lsa birinchi kalit
        # o'qilmay qoladi va sozlama sukut bo'yicha qiymatga tushib ketadi.
        env_file_encoding="utf-8-sig",
        extra="ignore",
        case_sensitive=True,
    )

    ENV: Literal["dev", "prod"] = "dev"
    PROJECT_NAME: str = "Restaurant CRM API"
    API_V1_PREFIX: str = "/api/v1"

    # --- auth -------------------------------------------------------------
    SECRET_KEY: str = "dev-only-secret-change-me-please-at-least-32-characters"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    #: bot yuborgan "saytga avtomatik kirish" linki shuncha daqiqa yashaydi
    LOGIN_TOKEN_EXPIRE_MINUTES: int = 15

    # --- bot <-> backend --------------------------------------------------
    BOT_HMAC_SECRET: str = "dev-only-bot-shared-secret-change-me"
    BOT_REQUEST_MAX_SKEW_SECONDS: int = 300
    TOKEN_ENCRYPTION_KEY: str = ""

    # --- infra ------------------------------------------------------------
    DATABASE_URL: str = "sqlite+aiosqlite:///./restaurant_crm.db"
    DB_ECHO: bool = False

    #: Vergul bilan ajratilgan ro'yxat. `list[str]` emas: pydantic-settings
    #: murakkab tipni .env dan JSON deb o'qishga urinadi va yiqiladi.
    #: 8080 — TanStack Start dev serveri, 5173 — oddiy Vite.
    CORS_ORIGINS: str = (
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    FRONTEND_URL: str = "http://localhost:5173"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    MEDIA_ROOT: str = "./media"
    MEDIA_URL_PATH: str = "/media"
    MAX_UPLOAD_BYTES: int = 8 * 1024 * 1024

    # --- BotBuilder (ixtiyoriy) ------------------------------------------
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5"

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def _force_async_driver(cls, v: str) -> str:
        """Railway `postgresql://...` beradi — SQLAlchemy async uchun drayverni qo'shamiz."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        if v.startswith("sqlite://") and "+aiosqlite" not in v:
            v = "sqlite+aiosqlite://" + v[len("sqlite://") :]
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def fernet_key(self) -> bytes:
        """Restoran bot tokenlarini shifrlash kaliti.

        Berilmagan bo'lsa SECRET_KEY dan deterministik hosil qilinadi, shunda
        dev muhitida qo'shimcha sozlashsiz ishlaydi. Productionda alohida kalit
        qo'yish tavsiya etiladi — SECRET_KEY aylantirilganda tokenlar yo'qolmaydi.
        """
        if self.TOKEN_ENCRYPTION_KEY:
            return self.TOKEN_ENCRYPTION_KEY.encode()
        digest = hashlib.sha256(self.SECRET_KEY.encode()).digest()
        return base64.urlsafe_b64encode(digest)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

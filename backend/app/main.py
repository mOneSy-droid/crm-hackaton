from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import *  # noqa: F401,F403 - modellar Base.metadata ga ro'yxatdan o'tsin
from app.api.middleware import BotSignatureMiddleware
from app.api.v1.router import api_router
from app.services.seed import seed_industries
from app.services.storage import media_root

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hackaton uchun jadvallar startda yaratiladi. Production migratsiyalari
    # kerak bo'lsa Alembic qo'shiladi — modellar shunga tayyor.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        await seed_industries(db)

    media_root()
    logger.info("API ishga tushdi (env=%s, db=%s)", settings.ENV, settings.DATABASE_URL.split("@")[-1])
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description=(
        "Restoranlar uchun CRM backend.\n\n"
        "- **Sayt** uchun: JWT (`Authorization: Bearer ...`)\n"
        "- **Telegram bot** uchun: `/api/v1/bot/*` — HMAC-SHA256 imzo "
        "(`X-Timestamp` + `X-Signature`)"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Diqqat: oxirgi qo'shilgan middleware eng tashqarida bo'ladi.
# Imzo tekshiruvi ichkarida — CORS preflight so'rovlariga xalaqit qilmasin.
app.add_middleware(
    BotSignatureMiddleware, protected_prefix=f"{settings.API_V1_PREFIX}/bot"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(settings.MEDIA_URL_PATH, StaticFiles(directory=media_root()), name="media")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Xatolarni foydalanuvchiga tushunarli qilib qaytaramiz.

    Bot bu matnni to'g'ridan-to'g'ri foydalanuvchiga ko'rsatishi mumkin.
    """
    problems = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"] if part not in ("body", "query"))
        problems.append({"field": field or "so'rov", "message": error.get("msg", "noto'g'ri qiymat")})

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Kiritilgan ma'lumotda xatolik bor",
            "problems": problems,
        },
    )


@app.get("/health", tags=["service"], summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.ENV}


@app.get("/", tags=["service"], include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": settings.PROJECT_NAME, "docs": "/docs"}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)

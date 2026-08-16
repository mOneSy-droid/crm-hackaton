from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Path, Query, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.api.serializers import to_review_out
from app.db.base import utcnow
from app.models import (
    BotInstance,
    BotStatus,
    Category,
    Industry,
    NotificationOutbox,
    Restaurant,
    Review,
    ReviewPhoto,
    User,
    UserRole,
)
from app.schemas.bot import (
    BotConfigOut,
    BotInstanceCreate,
    BotInstanceOut,
    BotTokenIn,
    LoginLinkOut,
    LoginLinkRequest,
    OutboxAck,
    OutboxItem,
    ProfileSyncOut,
    RestaurantRegisterIn,
    RestaurantRegisterOut,
    RestaurantSearchItem,
    TelegramUserIn,
    TenantLeadIn,
)
from app.schemas.common import Msg
from app.schemas.restaurant import RestaurantOut, RestaurantUpdate
from app.schemas.review import ReviewCreateFromBot, ReviewOut
from app.services import auth_service, bots as bot_service, notifications
from app.services.registration import register_restaurant, upsert_telegram_user
from app.services.restaurants import merge_attributes, recalculate_rating, unique_slug
from app.services.storage import save_image

logger = logging.getLogger(__name__)

# Butun router HMAC imzo bilan himoyalangan: `BotSignatureMiddleware` shu
# prefiksdagi har bir so'rovni marshrutlashdan oldin tekshiradi.
router = APIRouter(prefix="/bot", tags=["bot"])


async def _get_user(db, telegram_id: int) -> User:
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return user


async def _owned_restaurant(db, telegram_id: int, restaurant_id: int) -> Restaurant:
    user = await _get_user(db, telegram_id)
    restaurant = await db.scalar(
        select(Restaurant)
        .where(Restaurant.id == restaurant_id)
        .options(selectinload(Restaurant.category), selectinload(Restaurant.industry))
    )
    if restaurant is None or (
        restaurant.owner_id != user.id and user.role != UserRole.ADMIN
    ):
        raise HTTPException(status_code=404, detail="Restoran topilmadi")
    return restaurant


# ---------------------------------------------------------------------------
# Foydalanuvchi
# ---------------------------------------------------------------------------


@router.post("/users/sync", response_model=Msg, summary="Telegram foydalanuvchisini saqlash")
async def sync_user(payload: TelegramUserIn, db: DbSession) -> Msg:
    """Til tanlanganda va kontakt yuborilganda chaqiriladi."""
    await upsert_telegram_user(db, payload)
    await db.commit()
    return Msg(detail="Saqlandi")


# ---------------------------------------------------------------------------
# Restoran ro'yxatdan o'tishi
# ---------------------------------------------------------------------------


@router.post(
    "/restaurants/register",
    response_model=RestaurantRegisterOut,
    status_code=status.HTTP_201_CREATED,
    summary="Anketa tasdiqlangach restoranni yaratish",
)
async def register(payload: RestaurantRegisterIn, db: DbSession) -> RestaurantRegisterOut:
    restaurant, owner, password, already = await register_restaurant(db, payload)
    await db.commit()
    await db.refresh(restaurant, attribute_names=["category", "industry"])

    login_url, _ = await auth_service.create_login_link(db, owner, next_path="/dashboard")

    return RestaurantRegisterOut(
        restaurant=RestaurantOut.model_validate(restaurant),
        username=owner.username or "",
        password=password,
        login_url=login_url,
        already_registered=already,
    )


@router.post(
    "/login-link", response_model=LoginLinkOut, summary="Saytga avtomatik kirish linki"
)
async def login_link(payload: LoginLinkRequest, db: DbSession) -> LoginLinkOut:
    user = await _get_user(db, payload.telegram_id)
    url, expires_at = await auth_service.create_login_link(db, user, payload.next_path)
    return LoginLinkOut(login_url=url, expires_at=expires_at)


# ---------------------------------------------------------------------------
# Profilni bot orqali ko'rish va tahrirlash
# ---------------------------------------------------------------------------


@router.get("/profile", response_model=ProfileSyncOut, summary="Egasining restoranlari")
async def profile(telegram_id: Annotated[int, Query()], db: DbSession) -> ProfileSyncOut:
    """Bot "Profilni tahrirlash"ni ochganda joriy ma'lumotni ko'rsatishi uchun."""
    user = await _get_user(db, telegram_id)
    rows = (
        await db.scalars(
            select(Restaurant)
            .where(Restaurant.owner_id == user.id)
            .options(selectinload(Restaurant.category), selectinload(Restaurant.industry))
            .order_by(Restaurant.created_at.desc())
        )
    ).all()
    return ProfileSyncOut(restaurants=[RestaurantOut.model_validate(r) for r in rows])


@router.patch(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantOut,
    summary="Profilni bot orqali tahrirlash",
)
async def edit_profile(
    restaurant_id: Annotated[int, Path(ge=1)],
    telegram_id: Annotated[int, Query()],
    payload: RestaurantUpdate,
    db: DbSession,
) -> RestaurantOut:
    restaurant = await _owned_restaurant(db, telegram_id, restaurant_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("category_id") is not None:
        category = await db.get(Category, data["category_id"])
        if category is None or category.industry_id != restaurant.industry_id:
            raise HTTPException(status_code=422, detail="Bunday yo'nalish yo'q")

    if data.get("name") and data["name"] != restaurant.name:
        restaurant.slug = await unique_slug(db, data["name"])

    if "attributes" in data:
        restaurant.attributes = merge_attributes(restaurant.attributes, data.pop("attributes"))

    for field, value in data.items():
        setattr(restaurant, field, value)

    await db.commit()
    await db.refresh(restaurant, attribute_names=["category", "industry"])
    return RestaurantOut.model_validate(restaurant)


# ---------------------------------------------------------------------------
# Sharh qoldirish
# ---------------------------------------------------------------------------


@router.get(
    "/restaurants/search",
    response_model=list[RestaurantSearchItem],
    summary="Sharh uchun restoran qidirish",
)
async def search_restaurants(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    industry_key: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[RestaurantSearchItem]:
    conditions = [Restaurant.is_active.is_(True)]
    if q:
        conditions.append(Restaurant.name.ilike(f"%{q.strip()}%"))
    if industry_key:
        industry_id = await db.scalar(select(Industry.id).where(Industry.key == industry_key))
        conditions.append(Restaurant.industry_id == (industry_id or -1))

    rows = (
        await db.scalars(
            select(Restaurant)
            .where(*conditions)
            .options(selectinload(Restaurant.industry))
            .order_by(Restaurant.rating_count.desc(), Restaurant.name.asc())
            .limit(limit)
        )
    ).all()
    return [
        RestaurantSearchItem(
            id=r.id,
            name=r.name,
            address=r.address,
            rating_avg=r.rating_avg,
            rating_count=r.rating_count,
            industry_icon=r.industry.icon,
            industry_key=r.industry.key,
        )
        for r in rows
    ]


@router.post(
    "/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Botdan sharh qabul qilish",
)
async def create_review(payload: ReviewCreateFromBot, db: DbSession) -> ReviewOut:
    restaurant = await db.get(Restaurant, payload.restaurant_id)
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")

    author = await db.scalar(select(User).where(User.telegram_id == payload.telegram_id))
    if author is None:
        author = await upsert_telegram_user(db, TelegramUserIn(telegram_id=payload.telegram_id))

    review = Review(
        restaurant_id=restaurant.id,
        author_id=author.id,
        rating=payload.rating,
        text=payload.text,
        source="telegram",
    )
    db.add(review)
    await db.flush()

    for url in payload.photo_urls:
        db.add(ReviewPhoto(review_id=review.id, url=url))

    await db.flush()
    await recalculate_rating(db, restaurant.id)

    owner = await db.get(User, restaurant.owner_id)
    if owner is not None:
        await notifications.enqueue(
            db,
            telegram_id=owner.telegram_id,
            kind=notifications.KIND_NEW_REVIEW,
            payload={
                "review_id": review.id,
                "restaurant_id": restaurant.id,
                "restaurant_name": restaurant.name,
                "rating": review.rating,
                "text": review.text or "",
            },
            language=owner.language,
        )

    await db.commit()
    await db.refresh(review)
    review.author = author
    return to_review_out(review)


@router.post("/upload", summary="Botdan rasm yuklash")
async def upload_from_bot(
    file: Annotated[UploadFile, File(description="JPG, PNG, GIF yoki WEBP")]
) -> dict[str, str]:
    return {"url": await save_image(file, folder="bot")}


# ---------------------------------------------------------------------------
# BotBuilder (bot menyusi orqali)
# ---------------------------------------------------------------------------


@router.post(
    "/botbuilder/questionnaire",
    response_model=BotInstanceOut,
    summary="Anketani botdan qabul qilish",
)
async def bot_questionnaire(
    payload: BotInstanceCreate, telegram_id: Annotated[int, Query()], db: DbSession
) -> BotInstanceOut:
    restaurant = await _owned_restaurant(db, telegram_id, payload.restaurant_id)
    bot = await bot_service.save_questionnaire(db, restaurant, payload)
    await db.commit()
    await db.refresh(bot)
    return bot_service.to_bot_out(bot)


@router.post(
    "/botbuilder/{bot_id}/token",
    response_model=BotInstanceOut,
    summary="@BotFather tokenini botdan qabul qilish",
)
async def bot_token(
    bot_id: Annotated[int, Path(ge=1)],
    telegram_id: Annotated[int, Query()],
    payload: BotTokenIn,
    db: DbSession,
) -> BotInstanceOut:
    instance = await db.get(BotInstance, bot_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Bot topilmadi")
    await _owned_restaurant(db, telegram_id, instance.restaurant_id)

    instance = await bot_service.attach_token(db, instance, payload.token)
    await db.commit()
    await db.refresh(instance)

    owner = await _get_user(db, telegram_id)
    await notifications.enqueue(
        db,
        telegram_id=owner.telegram_id,
        kind=notifications.KIND_BOT_STATUS,
        payload={"bot_username": instance.bot_username, "status": instance.status.value},
        language=owner.language,
    )
    await db.commit()
    return bot_service.to_bot_out(instance)


@router.post(
    "/tenant/lead",
    response_model=Msg,
    summary="Shaxsiy bot yig'gan ma'lumotni egasiga yuborish",
)
async def tenant_lead(payload: TenantLeadIn, db: DbSession) -> Msg:
    """Restoranning o'z boti buyurtma/bron/savol yig'gach shu yerga yuboradi.

    Backend uni egasining Telegramiga navbat orqali yetkazadi — shaxsiy bot
    egasining chat ID'sini bilishi shart emas.
    """
    instance = await db.get(BotInstance, payload.bot_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Bot topilmadi")

    restaurant = await db.get(Restaurant, instance.restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")

    owner = await db.get(User, restaurant.owner_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Egasi topilmadi")

    await notifications.enqueue(
        db,
        telegram_id=owner.telegram_id,
        kind=notifications.KIND_TENANT_LEAD,
        payload={
            "restaurant_name": restaurant.name,
            "bot_username": instance.bot_username or "",
            "flow_label": payload.flow_label or payload.flow_id,
            "customer_name": payload.customer_name or "",
            "answers": payload.answers,
        },
        language=owner.language,
    )
    await db.commit()
    logger.info("Bot #%s dan yangi so'rov qabul qilindi", payload.bot_id)
    return Msg(detail="Qabul qilindi")


@router.get(
    "/botbuilder/runners",
    response_model=list[BotConfigOut],
    summary="Ishga tushirilishi kerak bo'lgan botlar (runner uchun)",
)
async def runner_configs(db: DbSession) -> list[BotConfigOut]:
    """Runner supervisor shu ro'yxat bo'yicha har bir botni alohida process qilib ko'taradi.

    Javobda deshifrlangan tokenlar bor — endpoint faqat HMAC imzo bilan ochiladi
    va hech qachon brauzerga chiqmaydi.
    """
    rows = (
        await db.scalars(
            select(BotInstance).where(
                BotInstance.status == BotStatus.ACTIVE,
                BotInstance.token_encrypted.is_not(None),
            )
        )
    ).all()

    configs: list[BotConfigOut] = []
    for instance in rows:
        try:
            configs.append(await bot_service.build_runner_config(db, instance))
        except HTTPException:
            logger.warning("Bot #%s konfiguratsiyasi o'tkazib yuborildi", instance.id)
    return configs


# ---------------------------------------------------------------------------
# Bildirishnoma navbati
# ---------------------------------------------------------------------------


#: Shuncha urinishdan keyin xabar "o'lik" deb hisoblanadi va boshqa berilmaydi.
#: Ushbu chegara bo'lmasa yetkazib bo'lmaydigan xabar navbatni abadiy band qiladi.
MAX_OUTBOX_ATTEMPTS = 10


@router.get("/outbox", response_model=list[OutboxItem], summary="Yetkazilmagan bildirishnomalar")
async def read_outbox(
    db: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[OutboxItem]:
    rows = (
        await db.scalars(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.delivered_at.is_(None),
                NotificationOutbox.attempts < MAX_OUTBOX_ATTEMPTS,
            )
            .order_by(NotificationOutbox.id.asc())
            .limit(limit)
        )
    ).all()

    items: list[OutboxItem] = []
    for row in rows:
        row.attempts += 1
        try:
            payload = json.loads(row.payload)
        except json.JSONDecodeError:
            payload = {}
        items.append(
            OutboxItem(
                id=row.id,
                telegram_id=row.telegram_id,
                kind=row.kind,
                payload=payload,
                language=row.language,
                created_at=row.created_at,
            )
        )
    await db.commit()
    return items


@router.post("/outbox/ack", response_model=Msg, summary="Yetkazilganini tasdiqlash")
async def ack_outbox(payload: OutboxAck, db: DbSession) -> Msg:
    await db.execute(
        update(NotificationOutbox)
        .where(NotificationOutbox.id.in_(payload.ids), NotificationOutbox.delivered_at.is_(None))
        .values(delivered_at=utcnow())
    )
    await db.commit()
    return Msg(detail="Tasdiqlandi")

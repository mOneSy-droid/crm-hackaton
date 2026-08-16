from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.api.serializers import to_review_out
from app.db.base import utcnow
from app.models import Restaurant, Review, ReviewStatus, UserRole
from app.schemas.common import Msg, Page
from app.schemas.review import ReviewModerate, ReviewOut, ReviewReply
from app.services import notifications
from app.services.restaurants import recalculate_rating

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _can_manage(user, restaurant: Restaurant) -> bool:
    return user is not None and (user.role == UserRole.ADMIN or restaurant.owner_id == user.id)


@router.get("", response_model=Page[ReviewOut], summary="Restoran sharhlari")
async def list_reviews(
    db: DbSession,
    viewer: OptionalUser,
    restaurant_id: Annotated[int, Query(ge=1)],
    status_filter: Annotated[
        ReviewStatus | None,
        Query(alias="status", description="Faqat egasi/admin uchun; mehmonga 'approved'"),
    ] = None,
    rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ReviewOut]:
    restaurant = await db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")

    conditions = [Review.restaurant_id == restaurant_id]
    if _can_manage(viewer, restaurant):
        if status_filter is not None:
            conditions.append(Review.status == status_filter)
    else:
        # Mehmon va begona foydalanuvchi faqat tasdiqlangan sharhlarni ko'radi
        conditions.append(Review.status == ReviewStatus.APPROVED)
    if rating is not None:
        conditions.append(Review.rating == rating)

    total = await db.scalar(select(func.count(Review.id)).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(Review)
            .where(*conditions)
            .options(selectinload(Review.author))
            .order_by(Review.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return Page[ReviewOut](
        items=[to_review_out(r) for r in rows], total=total, limit=limit, offset=offset
    )


async def _load_manageable_review(db, user, review_id: int) -> tuple[Review, Restaurant]:
    review = await db.scalar(
        select(Review).where(Review.id == review_id).options(selectinload(Review.author))
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Sharh topilmadi")
    restaurant = await db.get(Restaurant, review.restaurant_id)
    if restaurant is None or not _can_manage(user, restaurant):
        raise HTTPException(status_code=404, detail="Sharh topilmadi")
    return review, restaurant


@router.patch(
    "/{review_id}/moderate", response_model=ReviewOut, summary="Sharhni tasdiqlash / rad etish"
)
async def moderate_review(
    review_id: Annotated[int, Path(ge=1)],
    payload: ReviewModerate,
    user: CurrentUser,
    db: DbSession,
) -> ReviewOut:
    review, _ = await _load_manageable_review(db, user, review_id)

    review.status = payload.status
    review.moderation_note = payload.moderation_note
    # Sessiyada autoflush o'chirilgan — yangi status hisobga kirishi uchun majburan flush
    await db.flush()

    # Reyting faqat tasdiqlangan sharhlardan hisoblanadi — har o'zgarishda qayta hisoblaymiz
    await recalculate_rating(db, review.restaurant_id)

    if review.author is not None and review.author.telegram_id:
        await notifications.enqueue(
            db,
            telegram_id=review.author.telegram_id,
            kind=notifications.KIND_REVIEW_MODERATED,
            payload={"review_id": review.id, "status": payload.status.value},
            language=review.author.language,
        )

    await db.commit()
    await db.refresh(review)
    return to_review_out(review)


@router.post("/{review_id}/reply", response_model=ReviewOut, summary="Sharhga javob yozish")
async def reply_to_review(
    review_id: Annotated[int, Path(ge=1)],
    payload: ReviewReply,
    user: CurrentUser,
    db: DbSession,
) -> ReviewOut:
    review, restaurant = await _load_manageable_review(db, user, review_id)

    review.owner_reply = payload.text
    review.owner_replied_at = utcnow()

    if review.author is not None and review.author.telegram_id:
        await notifications.enqueue(
            db,
            telegram_id=review.author.telegram_id,
            kind=notifications.KIND_OWNER_REPLY,
            payload={
                "review_id": review.id,
                "restaurant_name": restaurant.name,
                "reply": payload.text,
            },
            language=review.author.language,
        )

    await db.commit()
    await db.refresh(review)
    return to_review_out(review)


@router.delete("/{review_id}", response_model=Msg, summary="Sharhni o'chirish")
async def delete_review(
    review_id: Annotated[int, Path(ge=1)], user: CurrentUser, db: DbSession
) -> Msg:
    review, _ = await _load_manageable_review(db, user, review_id)
    restaurant_id = review.restaurant_id
    await db.delete(review)
    await db.flush()
    await recalculate_rating(db, restaurant_id)
    await db.commit()
    return Msg(detail="Sharh o'chirildi")

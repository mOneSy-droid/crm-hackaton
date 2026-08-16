from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession, OwnedRestaurant
from app.db.base import utcnow
from app.models import BotInstance, BotStatus, MenuItem, Review, ReviewStatus
from app.schemas.restaurant import DashboardStats

router = APIRouter(prefix="/restaurants", tags=["stats"])


@router.get(
    "/{restaurant_id}/stats",
    response_model=DashboardStats,
    summary="Kabinet uchun statistika",
)
async def dashboard_stats(restaurant: OwnedRestaurant, db: DbSession) -> DashboardStats:
    now = utcnow()
    rid = restaurant.id

    pending = await db.scalar(
        select(func.count(Review.id)).where(
            Review.restaurant_id == rid, Review.status == ReviewStatus.PENDING
        )
    )

    async def reviews_since(days: int) -> int:
        return (
            await db.scalar(
                select(func.count(Review.id)).where(
                    Review.restaurant_id == rid,
                    Review.created_at >= now - timedelta(days=days),
                )
            )
            or 0
        )

    breakdown_rows = (
        await db.execute(
            select(Review.rating, func.count(Review.id))
            .where(Review.restaurant_id == rid, Review.status == ReviewStatus.APPROVED)
            .group_by(Review.rating)
        )
    ).all()

    menu_count = await db.scalar(
        select(func.count(MenuItem.id)).where(MenuItem.restaurant_id == rid)
    )
    bots_active = await db.scalar(
        select(func.count(BotInstance.id)).where(
            BotInstance.restaurant_id == rid, BotInstance.status == BotStatus.ACTIVE
        )
    )

    return DashboardStats(
        restaurant_id=rid,
        rating_avg=restaurant.rating_avg,
        rating_count=restaurant.rating_count,
        reviews_pending=pending or 0,
        reviews_last_7_days=await reviews_since(7),
        reviews_last_30_days=await reviews_since(30),
        rating_breakdown={star: 0 for star in range(1, 6)} | {r: c for r, c in breakdown_rows},
        menu_items=menu_count or 0,
        bots_active=bots_active or 0,
    )

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, OwnedRestaurant
from app.models import Review
from app.services.export import build_customers_workbook

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/restaurants", tags=["exports"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/{restaurant_id}/customers/export",
    summary="Mijozlar va sharhlarni Excel'ga eksport qilish",
    response_class=StreamingResponse,
)
async def export_customers(restaurant: OwnedRestaurant, db: DbSession) -> StreamingResponse:
    """Egasiga .xlsx qaytaradi: «Mijozlar» va «Sharhlar» varaqlari.

    Telefon raqamlari faylda ham niqoblangan — API siyosati bilan bir xil.
    """
    reviews = (
        await db.scalars(
            select(Review)
            .where(Review.restaurant_id == restaurant.id)
            .options(selectinload(Review.author))
            .order_by(Review.created_at.desc())
        )
    ).all()

    buf = build_customers_workbook(restaurant, list(reviews))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Fayl nomida faqat ASCII — slug shunga mos
    filename = f"mijozlar_{restaurant.slug}_{stamp}.xlsx"

    logger.info(
        "Eksport: restoran #%s, %d ta sharh", restaurant.id, len(reviews)
    )
    return StreamingResponse(
        buf,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

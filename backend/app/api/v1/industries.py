from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.models import Category, Industry
from app.schemas.common import CategoryOut, IndustryField, IndustryOut

logger = logging.getLogger(__name__)
router = APIRouter(tags=["industries"])


def to_industry_out(industry: Industry, categories: list[Category]) -> IndustryOut:
    try:
        raw_fields = json.loads(industry.field_schema or "[]")
    except json.JSONDecodeError:
        logger.warning("Soha #%s field_schema buzuq", industry.id)
        raw_fields = []

    return IndustryOut(
        id=industry.id,
        key=industry.key,
        icon=industry.icon,
        name_uz=industry.name_uz,
        name_ru=industry.name_ru,
        name_en=industry.name_en,
        entity_label_uz=industry.entity_label_uz,
        entity_label_ru=industry.entity_label_ru,
        entity_label_en=industry.entity_label_en,
        item_label_uz=industry.item_label_uz,
        item_label_ru=industry.item_label_ru,
        item_label_en=industry.item_label_en,
        catalog_label_uz=industry.catalog_label_uz,
        catalog_label_ru=industry.catalog_label_ru,
        catalog_label_en=industry.catalog_label_en,
        fields=[IndustryField(**field) for field in raw_fields],
        categories=[
            CategoryOut.model_validate(category)
            for category in sorted(categories, key=lambda c: (c.sort_order, c.id))
        ],
    )


@router.get(
    "/industries",
    response_model=list[IndustryOut],
    summary="Sohalar va ularning yorliqlari",
)
async def list_industries(db: DbSession) -> list[IndustryOut]:
    """Bot va sayt shu ro'yxatdan yorliqlarni oladi.

    Har bir sohada `fields` bor — sohaga xos qo'shimcha savollar. Mijoz
    interfeysi shu tavsif asosida maydonlarni o'zi chizadi.
    """
    rows = (
        await db.scalars(
            select(Industry)
            .where(Industry.is_active.is_(True))
            .options(selectinload(Industry.categories))
            .order_by(Industry.sort_order.asc())
        )
    ).all()
    return [to_industry_out(industry, industry.categories) for industry in rows]


@router.get(
    "/categories",
    response_model=list[CategoryOut],
    summary="Yo'nalishlar (ixtiyoriy: soha bo'yicha)",
)
async def list_categories(
    db: DbSession,
    industry_key: Annotated[str | None, Query(max_length=40)] = None,
) -> list[CategoryOut]:
    conditions = []
    if industry_key:
        industry_id = await db.scalar(select(Industry.id).where(Industry.key == industry_key))
        if industry_id is None:
            raise HTTPException(status_code=404, detail="Bunday soha yo'q")
        conditions.append(Category.industry_id == industry_id)

    rows = (
        await db.scalars(
            select(Category).where(*conditions).order_by(
                Category.industry_id.asc(), Category.sort_order.asc()
            )
        )
    ).all()
    return [CategoryOut.model_validate(category) for category in rows]

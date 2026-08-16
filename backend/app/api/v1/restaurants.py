from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, OwnedRestaurant
from app.models import Category, Industry, MenuItem, Restaurant, UserRole
from app.schemas.common import Msg, Page
from app.schemas.restaurant import (
    MenuItemCreate,
    MenuItemOut,
    MenuItemUpdate,
    RestaurantOut,
    RestaurantUpdate,
)
from app.services.restaurants import merge_attributes, unique_slug

router = APIRouter(prefix="/restaurants", tags=["restaurants"])

SortBy = Literal["rating", "new", "name"]


def _with_relations(stmt: Select) -> Select:
    """Javob uchun soha va yo'nalish har doim kerak."""
    return stmt.options(selectinload(Restaurant.category), selectinload(Restaurant.industry))


def _apply_sort(stmt: Select, sort: SortBy) -> Select:
    if sort == "rating":
        return stmt.order_by(Restaurant.rating_avg.desc(), Restaurant.rating_count.desc())
    if sort == "name":
        return stmt.order_by(Restaurant.name.asc())
    return stmt.order_by(Restaurant.created_at.desc())


# ---------------------------------------------------------------------------
# Ochiq (autorizatsiyasiz) endpointlar
# ---------------------------------------------------------------------------


@router.get("", response_model=Page[RestaurantOut], summary="Restoranlar ro'yxati / qidiruv")
async def list_restaurants(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100, description="Nom yoki manzil bo'yicha")] = None,
    industry_key: Annotated[str | None, Query(max_length=40, description="Soha kaliti")] = None,
    category_id: Annotated[int | None, Query(ge=1)] = None,
    category_key: Annotated[str | None, Query(max_length=40)] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    sort: SortBy = "rating",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RestaurantOut]:
    conditions = [Restaurant.is_active.is_(True)]

    industry_id: int | None = None
    if industry_key:
        industry_id = await db.scalar(select(Industry.id).where(Industry.key == industry_key))
        # Mavjud bo'lmagan soha uchun bo'sh natija — xato emas
        conditions.append(Restaurant.industry_id == (industry_id or -1))

    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(Restaurant.name.ilike(pattern) | Restaurant.address.ilike(pattern))
    if category_id:
        conditions.append(Restaurant.category_id == category_id)
    if category_key:
        # Kalit soha ichida yagona, shuning uchun soha berilgan bo'lsa
        # qidiruvni shu soha bilan cheklaymiz
        category_stmt = select(Category.id).where(Category.key == category_key)
        if industry_id is not None:
            category_stmt = category_stmt.where(Category.industry_id == industry_id)
        resolved = await db.scalar(category_stmt)
        conditions.append(Restaurant.category_id == (resolved or -1))
    if min_rating is not None:
        conditions.append(Restaurant.rating_avg >= min_rating)

    total = await db.scalar(select(func.count(Restaurant.id)).where(*conditions)) or 0
    stmt = _apply_sort(_with_relations(select(Restaurant).where(*conditions)), sort)
    rows = (await db.scalars(stmt.limit(limit).offset(offset))).all()

    return Page[RestaurantOut](
        items=[RestaurantOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/my", response_model=list[RestaurantOut], summary="Mening restoranlarim")
async def my_restaurants(user: CurrentUser, db: DbSession) -> list[RestaurantOut]:
    stmt = _with_relations(select(Restaurant).where(Restaurant.owner_id == user.id))
    rows = (await db.scalars(stmt.order_by(Restaurant.created_at.desc()))).all()
    return [RestaurantOut.model_validate(r) for r in rows]


@router.get("/slug/{slug}", response_model=RestaurantOut, summary="Slug bo'yicha ochiq profil")
async def get_by_slug(slug: Annotated[str, Path(max_length=180)], db: DbSession) -> RestaurantOut:
    stmt = _with_relations(select(Restaurant).where(Restaurant.slug == slug))
    restaurant = await db.scalar(stmt)
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")
    return RestaurantOut.model_validate(restaurant)


@router.get("/{restaurant_id}", response_model=RestaurantOut, summary="ID bo'yicha ochiq profil")
async def get_restaurant(
    restaurant_id: Annotated[int, Path(ge=1)], db: DbSession
) -> RestaurantOut:
    stmt = _with_relations(select(Restaurant).where(Restaurant.id == restaurant_id))
    restaurant = await db.scalar(stmt)
    if restaurant is None or not restaurant.is_active:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")
    return RestaurantOut.model_validate(restaurant)


# ---------------------------------------------------------------------------
# Egasi uchun
# ---------------------------------------------------------------------------


@router.patch(
    "/{restaurant_id}", response_model=RestaurantOut, summary="Profilni tahrirlash"
)
async def update_restaurant(
    payload: RestaurantUpdate, restaurant: OwnedRestaurant, db: DbSession
) -> RestaurantOut:
    data = payload.model_dump(exclude_unset=True)

    if "category_id" in data and data["category_id"] is not None:
        category = await db.get(Category, data["category_id"])
        if category is None:
            raise HTTPException(status_code=422, detail="Bunday kategoriya yo'q")
        # Yo'nalish biznes sohasiga tegishli bo'lishi kerak — do'konga
        # "Pitseriya" yo'nalishini qo'yib bo'lmaydi
        if category.industry_id != restaurant.industry_id:
            raise HTTPException(
                status_code=422, detail="Bu yo'nalish sizning sohangizga tegishli emas"
            )

    if "name" in data and data["name"] and data["name"] != restaurant.name:
        restaurant.slug = await unique_slug(db, data["name"])

    # Sohaga xos maydonlar ustiga qo'shiladi, butunlay almashtirilmaydi
    if "attributes" in data:
        merged = merge_attributes(restaurant.attributes, data.pop("attributes"))
        restaurant.attributes = merged

    for field, value in data.items():
        setattr(restaurant, field, value)

    await db.commit()
    await db.refresh(restaurant, attribute_names=["category", "industry"])
    return RestaurantOut.model_validate(restaurant)


# ---------------------------------------------------------------------------
# Menyu
# ---------------------------------------------------------------------------


@router.get(
    "/{restaurant_id}/menu", response_model=list[MenuItemOut], summary="Menyu (ochiq)"
)
async def list_menu(
    restaurant_id: Annotated[int, Path(ge=1)],
    db: DbSession,
    only_available: bool = True,
) -> list[MenuItemOut]:
    conditions = [MenuItem.restaurant_id == restaurant_id]
    if only_available:
        conditions.append(MenuItem.is_available.is_(True))
    rows = (
        await db.scalars(
            select(MenuItem)
            .where(*conditions)
            .order_by(MenuItem.sort_order.asc(), MenuItem.id.asc())
        )
    ).all()
    return [MenuItemOut.model_validate(item) for item in rows]


@router.post(
    "/{restaurant_id}/menu",
    response_model=MenuItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Menyuga taom qo'shish",
)
async def create_menu_item(
    payload: MenuItemCreate, restaurant: OwnedRestaurant, db: DbSession
) -> MenuItemOut:
    item = MenuItem(restaurant_id=restaurant.id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return MenuItemOut.model_validate(item)


@router.patch(
    "/{restaurant_id}/menu/{item_id}", response_model=MenuItemOut, summary="Taomni tahrirlash"
)
async def update_menu_item(
    item_id: Annotated[int, Path(ge=1)],
    payload: MenuItemUpdate,
    restaurant: OwnedRestaurant,
    db: DbSession,
) -> MenuItemOut:
    item = await db.get(MenuItem, item_id)
    if item is None or item.restaurant_id != restaurant.id:
        raise HTTPException(status_code=404, detail="Taom topilmadi")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return MenuItemOut.model_validate(item)


@router.delete("/{restaurant_id}/menu/{item_id}", response_model=Msg, summary="Taomni o'chirish")
async def delete_menu_item(
    item_id: Annotated[int, Path(ge=1)], restaurant: OwnedRestaurant, db: DbSession
) -> Msg:
    item = await db.get(MenuItem, item_id)
    if item is None or item.restaurant_id != restaurant.id:
        raise HTTPException(status_code=404, detail="Taom topilmadi")
    await db.delete(item)
    await db.commit()
    return Msg(detail="Taom o'chirildi")


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


@router.post(
    "/{restaurant_id}/verify", response_model=RestaurantOut, summary="Restoranni tasdiqlash (admin)"
)
async def verify_restaurant(
    restaurant_id: Annotated[int, Path(ge=1)], user: CurrentUser, db: DbSession
) -> RestaurantOut:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bu amal uchun ruxsat yo'q")
    restaurant = await db.scalar(
        _with_relations(select(Restaurant).where(Restaurant.id == restaurant_id))
    )
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restoran topilmadi")
    restaurant.is_verified = True
    await db.commit()
    return RestaurantOut.model_validate(restaurant)

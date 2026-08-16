from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.schemas.common import CategoryOut, IndustryBrief

WORK_HOURS_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d\s*-\s*([01]\d|2[0-3]):[0-5]\d$")


def validate_work_hours(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    v = v.strip()
    if not WORK_HOURS_RE.match(v):
        raise ValueError("ish vaqti 'HH:MM-HH:MM' ko'rinishida bo'lishi kerak, masalan 09:00-23:00")
    return v.replace(" ", "")


#: Bir nechta sxemada qayta ishlatiladigan "09:00-23:00" tipi
WorkHours = Annotated[str | None, AfterValidator(validate_work_hours)]


class RestaurantBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    work_hours: WorkHours = Field(default=None, examples=["09:00-23:00"])
    phone: str | None = Field(default=None, max_length=20)
    category_id: int | None = None
    logo_url: str | None = Field(default=None, max_length=500)


class RestaurantCreate(RestaurantBase):
    pass


class RestaurantUpdate(BaseModel):
    """Profilni tahrirlash — faqat yuborilgan maydonlar o'zgaradi."""

    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    work_hours: WorkHours = None
    phone: str | None = Field(default=None, max_length=20)
    category_id: int | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    #: Sohaga xos maydonlar. Yuborilgan kalitlar mavjudlari ustiga qo'shiladi.
    attributes: dict[str, str] | None = None


class RestaurantOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    work_hours: str | None
    phone: str | None
    logo_url: str | None
    is_active: bool
    is_verified: bool
    rating_avg: float
    rating_count: int
    industry: IndustryBrief
    category: CategoryOut | None = None
    #: Sohaga xos qo'shimcha maydonlar, `Industry.fields` bo'yicha
    attributes: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("attributes", mode="before")
    @classmethod
    def _parse_attributes(cls, v: object) -> object:
        """Bazada JSON matn, API'da obyekt sifatida qaytariladi."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v or "{}")
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return v or {}


class MenuItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    price: float | None = Field(default=None, ge=0)
    section: str | None = Field(default=None, max_length=80)
    photo_url: str | None = Field(default=None, max_length=500)
    is_available: bool = True
    sort_order: int = 0


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    price: float | None = Field(default=None, ge=0)
    section: str | None = Field(default=None, max_length=80)
    photo_url: str | None = Field(default=None, max_length=500)
    is_available: bool | None = None
    sort_order: int | None = None


class MenuItemOut(MenuItemBase):
    id: int
    restaurant_id: int

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    restaurant_id: int
    rating_avg: float
    rating_count: int
    reviews_pending: int
    reviews_last_7_days: int
    reviews_last_30_days: int
    rating_breakdown: dict[int, int] = Field(
        description="Yulduzlar bo'yicha taqsimot, masalan {5: 12, 4: 3}"
    )
    menu_items: int
    bots_active: int

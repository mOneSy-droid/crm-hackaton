from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import ReviewStatus


class ReviewAuthorOut(BaseModel):
    id: int | None = None
    display_name: str = Field(description="Ism yoki 'Mehmon' — telefon hech qachon qaytarilmaydi")


class ReviewOut(BaseModel):
    id: int
    restaurant_id: int
    rating: int
    text: str | None
    status: ReviewStatus
    owner_reply: str | None
    owner_replied_at: datetime | None
    photos: list[str] = []
    author: ReviewAuthorOut | None = None
    created_at: datetime


class ReviewModerate(BaseModel):
    status: ReviewStatus
    moderation_note: str | None = Field(default=None, max_length=300)


class ReviewReply(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ReviewCreateFromBot(BaseModel):
    telegram_id: int
    restaurant_id: int
    rating: int = Field(ge=1, le=5)
    text: str | None = Field(default=None, max_length=2000)
    photo_urls: list[str] = Field(default_factory=list, max_length=5)

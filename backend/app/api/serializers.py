from __future__ import annotations

from app.core.logging import mask_phone
from app.models import Restaurant, Review, User
from app.schemas.auth import MeOut, UserOut
from app.schemas.review import ReviewAuthorOut, ReviewOut

GUEST_NAME = "Mehmon"


def to_user_out(user: User) -> UserOut:
    """Telefon raqami hech qachon to'liq qaytarilmaydi — faqat niqoblangan ko'rinishda."""
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        phone_masked=mask_phone(user.phone) or None,
        role=user.role,
        language=user.language,
        telegram_username=user.telegram_username,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def to_me_out(user: User, restaurant_ids: list[int]) -> MeOut:
    return MeOut(**to_user_out(user).model_dump(), restaurant_ids=restaurant_ids)


def to_review_out(review: Review, *, include_author: bool = True) -> ReviewOut:
    author: ReviewAuthorOut | None = None
    if include_author:
        name = GUEST_NAME
        if review.author is not None and review.author.full_name:
            name = review.author.full_name
        author = ReviewAuthorOut(
            id=review.author_id if review.author_id else None, display_name=name
        )
    return ReviewOut(
        id=review.id,
        restaurant_id=review.restaurant_id,
        rating=review.rating,
        text=review.text,
        status=review.status,
        owner_reply=review.owner_reply,
        owner_replied_at=review.owner_replied_at,
        photos=[photo.url for photo in review.photos],
        author=author,
        created_at=review.created_at,
    )


def restaurant_public_url(restaurant: Restaurant, base: str) -> str:
    return f"{base.rstrip('/')}/r/{restaurant.slug}"

"""Klaviaturalar. Har bir tugma matni i18n orqali tarjima qilinadi."""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from i18n import LANGUAGE_NAMES, t

REMOVE = ReplyKeyboardRemove()


def language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(name, callback_data=f"lang:{code}")
          for code, name in LANGUAGE_NAMES.items()]]
    )


def main_menu_kb(lang: str, *, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(t(lang, "menu_register"), callback_data="nav:register"),
            InlineKeyboardButton(t(lang, "menu_review"), callback_data="nav:review"),
        ],
        [
            InlineKeyboardButton(t(lang, "menu_profile"), callback_data="nav:profile"),
            InlineKeyboardButton(t(lang, "menu_mybot"), callback_data="nav:mybot"),
        ],
        [
            InlineKeyboardButton(t(lang, "menu_language"), callback_data="nav:language"),
            InlineKeyboardButton(t(lang, "menu_help"), callback_data="nav:help"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(t(lang, "menu_admin"), callback_data="nav:admin")])
    return InlineKeyboardMarkup(rows)


def contact_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(lang, "share_contact"), request_contact=True)],
         [KeyboardButton(t(lang, "cancel"))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def location_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(lang, "share_location"), request_location=True)],
         [KeyboardButton(t(lang, "cancel"))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def cancel_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(t(lang, "cancel"))]], resize_keyboard=True)


def skip_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "skip"), callback_data="skip")]])


def localized(item: dict, field: str, lang: str) -> str:
    """`name_uz` / `name_ru` / `name_en` orasidan tanlaydi."""
    return item.get(f"{field}_{lang}") or item.get(f"{field}_uz") or ""


def industries_kb(industries: list[dict], lang: str) -> InlineKeyboardMarkup:
    """Sohalar ro'yxati — backenddan keladi, kodda qattiq yozilmagan."""
    rows = [
        [InlineKeyboardButton(
            f"{industry['icon']} {localized(industry, 'name', lang)}",
            callback_data=f"ind:{industry['key']}",
        )]
        for industry in industries
    ]
    return InlineKeyboardMarkup(rows)


def categories_kb(categories: list[dict], lang: str) -> InlineKeyboardMarkup:
    """Tanlangan soha ichidagi yo'nalishlar — ikki ustunda."""
    rows, row = [], []
    for category in categories:
        row.append(
            InlineKeyboardButton(
                localized(category, "name", lang), callback_data=f"cat:{category['key']}"
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def field_choices_kb(choices: list[str], lang: str) -> InlineKeyboardMarkup:
    """Sohaga xos savolning tayyor javoblari + o'tkazib yuborish."""
    rows = [[InlineKeyboardButton(choice, callback_data=f"fld:{choice}")] for choice in choices[:8]]
    rows.append([InlineKeyboardButton(t(lang, "skip"), callback_data="fld_skip")])
    return InlineKeyboardMarkup(rows)


def skip_field_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "skip"), callback_data="fld_skip")]]
    )


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(t(lang, "confirm"), callback_data="confirm"),
            InlineKeyboardButton(t(lang, "retry"), callback_data="retry"),
        ]]
    )


def rating_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⭐" * i, callback_data=f"rate:{i}") for i in (1, 2, 3)],
         [InlineKeyboardButton("⭐" * i, callback_data=f"rate:{i}") for i in (4, 5)]]
    )


def restaurants_kb(restaurants: list[dict], prefix: str) -> InlineKeyboardMarkup:
    rows = []
    for item in restaurants[:10]:
        label = item["name"]
        if item.get("rating_count"):
            label = f"{label} ⭐{item['rating_avg']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{item['id']}")])
    return InlineKeyboardMarkup(rows)


def portal_kb(lang: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "open_portal"), url=url)]])


def profile_fields_kb(lang: str, restaurant_id: int) -> InlineKeyboardMarkup:
    fields = [
        ("name", "prof_field_name"),
        ("address", "prof_field_address"),
        ("work_hours", "prof_field_hours"),
        ("description", "prof_field_description"),
        ("phone", "prof_field_phone"),
        ("logo_url", "prof_field_logo"),
    ]
    rows, row = [], []
    for field, key in fields:
        row.append(InlineKeyboardButton(t(lang, key), callback_data=f"edit:{restaurant_id}:{field}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t(lang, "back"), callback_data="nav:menu")])
    return InlineKeyboardMarkup(rows)


def bb_languages_kb(lang: str, selected: set[str]) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(
            f"{'✅ ' if code in selected else ''}{name}", callback_data=f"bblang:{code}"
        )
        for code, name in LANGUAGE_NAMES.items()
    ]]
    if selected:
        rows.append([InlineKeyboardButton(t(lang, "bb_continue"), callback_data="bblang:done")])
    return InlineKeyboardMarkup(rows)


def admin_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "admin_stats"), callback_data="adm:stats")],
            [
                InlineKeyboardButton(t(lang, "admin_add_admin"), callback_data="adm:add"),
                InlineKeyboardButton(t(lang, "admin_remove_admin"), callback_data="adm:remove"),
            ],
            [InlineKeyboardButton(t(lang, "back"), callback_data="nav:menu")],
        ]
    )

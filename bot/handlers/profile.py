"""Profilni bot orqali ko'rish va tahrirlash.

Ikki tomonlama sinxronizatsiya: avval backenddan joriy ma'lumot olinadi va
foydalanuvchiga ko'rsatiladi, keyin faqat o'zgargan maydon yuboriladi.
"""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from crm_client import CrmApiError
from handlers.common import cancel, crm, lang_of, reply_error, safe_edit, upload_photo
from i18n import CANCEL_TEXTS, t
from keyboards import REMOVE, cancel_kb, profile_fields_kb, restaurants_kb

logger = logging.getLogger(__name__)

PICK, FIELD, VALUE = range(200, 203)

CANCEL_FILTER = filters.Text(CANCEL_TEXTS)
WORK_HOURS_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d\s*-\s*([01]\d|2[0-3]):[0-5]\d$")


async def start_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)

    if update.callback_query is not None:
        await update.callback_query.answer()

    try:
        profile = await crm(context).get_profile(update.effective_user.id)
        restaurants = profile["restaurants"]
    except CrmApiError as exc:
        if exc.status_code == 404:
            await update.effective_message.reply_text(t(lang, "prof_none"))
            return ConversationHandler.END
        await reply_error(update, lang, exc)
        return ConversationHandler.END

    if not restaurants:
        await update.effective_message.reply_text(t(lang, "prof_none"))
        return ConversationHandler.END

    context.user_data["profile_restaurants"] = {r["id"]: r for r in restaurants}

    if len(restaurants) == 1:
        return await _show_card(update, context, lang, restaurants[0])

    await update.effective_message.reply_text(
        t(lang, "prof_pick"), reply_markup=restaurants_kb(restaurants, "prof")
    )
    return PICK


async def pick_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    restaurant_id = int((query.data or "prof:0").split(":", 1)[1])
    restaurant = context.user_data.get("profile_restaurants", {}).get(restaurant_id)
    if restaurant is None:
        await query.edit_message_text(t(lang, "error"))
        return ConversationHandler.END
    return await _show_card(update, context, lang, restaurant)


async def _show_card(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, restaurant: dict
) -> int:
    text = t(
        lang,
        "prof_card",
        name=restaurant["name"],
        rating=restaurant["rating_avg"],
        count=restaurant["rating_count"],
        address=restaurant.get("address") or "—",
        hours=restaurant.get("work_hours") or "—",
        description=restaurant.get("description") or "—",
    )
    markup = profile_fields_kb(lang, restaurant["id"])

    if update.callback_query is not None:
        await safe_edit(update, text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(
            text, reply_markup=markup, parse_mode=ParseMode.HTML
        )
    return FIELD


async def pick_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    _, restaurant_id, field = (query.data or "edit:0:name").split(":", 2)
    context.user_data["edit"] = {"restaurant_id": int(restaurant_id), "field": field}

    restaurant = context.user_data.get("profile_restaurants", {}).get(int(restaurant_id), {})

    if field == "logo_url":
        await query.edit_message_text(t(lang, "prof_enter_logo"))
    else:
        await query.edit_message_text(
            t(lang, "prof_enter", current=restaurant.get(field) or "—")
        )
        await update.effective_message.reply_text(
            t(lang, "prof_enter", current=restaurant.get(field) or "—"),
            reply_markup=cancel_kb(lang),
        )
    return VALUE


async def set_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    edit = context.user_data.get("edit")
    if not edit:
        return ConversationHandler.END

    field = edit["field"]

    if field == "logo_url":
        try:
            value = await upload_photo(update, context)
        except CrmApiError as exc:
            await reply_error(update, lang, exc)
            return VALUE
        if value is None:
            await update.effective_message.reply_text(t(lang, "prof_enter_logo"))
            return VALUE
    else:
        value = (update.effective_message.text or "").strip()
        if field == "work_hours" and not WORK_HOURS_RE.match(value):
            await update.effective_message.reply_text(t(lang, "reg_hours_invalid"))
            return VALUE

    try:
        updated = await crm(context).update_restaurant(
            update.effective_user.id, edit["restaurant_id"], {field: value}
        )
    except CrmApiError as exc:
        await reply_error(update, lang, exc)
        return VALUE

    context.user_data.setdefault("profile_restaurants", {})[updated["id"]] = updated
    context.user_data.pop("edit", None)

    await update.effective_message.reply_text(t(lang, "prof_saved"), reply_markup=REMOVE)
    return await _show_card(update, context, lang, updated)


def build_handler() -> ConversationHandler:
    cancel_handler = MessageHandler(CANCEL_FILTER, cancel)
    return ConversationHandler(
        entry_points=[
            CommandHandler("profile", start_profile),
            CallbackQueryHandler(start_profile, pattern=r"^nav:profile$"),
        ],
        states={
            PICK: [CallbackQueryHandler(pick_restaurant, pattern=r"^prof:\d+$")],
            FIELD: [CallbackQueryHandler(pick_field, pattern=r"^edit:\d+:\w+$")],
            VALUE: [
                cancel_handler,
                MessageHandler(filters.PHOTO, set_value),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER, set_value),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("menu", cancel)],
        name="profile",
        per_message=False,
    )

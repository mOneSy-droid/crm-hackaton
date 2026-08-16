"""Sharh qoldirish oqimi.

Eski koddagi xato: restoranlar ro'yxati `TEXT` lug'atida qattiq yozilgan edi
va sharh hech qayerga yuborilmasdi. Endi ro'yxat backenddan qidiriladi va
sharh haqiqiy API'ga boradi.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from crm_client import CrmApiError
from handlers.common import (
    cancel,
    crm,
    lang_of,
    reply_error,
    safe_edit,
    show_main_menu,
    upload_photo,
)
from i18n import CANCEL_TEXTS, t
from keyboards import REMOVE, cancel_kb, rating_kb, restaurants_kb, skip_kb

logger = logging.getLogger(__name__)

SEARCH, PICK, RATE, COMMENT, PHOTO = range(100, 105)

CANCEL_FILTER = filters.Text(CANCEL_TEXTS)


def _draft(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault("review", {})


async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    context.user_data["review"] = {}

    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_reply_markup(reply_markup=None)

    try:
        restaurants = await crm(context).search_restaurants(limit=10)
    except CrmApiError as exc:
        await reply_error(update, lang, exc)
        return ConversationHandler.END

    if not restaurants:
        await update.effective_message.reply_text(t(lang, "rev_empty"))
        await show_main_menu(update, lang)
        return ConversationHandler.END

    await update.effective_message.reply_text(
        t(lang, "rev_search"), reply_markup=restaurants_kb(restaurants, "rev")
    )
    return SEARCH


async def search_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    query = (update.effective_message.text or "").strip()

    try:
        restaurants = await crm(context).search_restaurants(query, limit=10)
    except CrmApiError as exc:
        await reply_error(update, lang, exc)
        return ConversationHandler.END

    if not restaurants:
        await update.effective_message.reply_text(t(lang, "rev_not_found"))
        return SEARCH

    await update.effective_message.reply_text(
        t(lang, "rev_search"), reply_markup=restaurants_kb(restaurants, "rev")
    )
    return SEARCH


async def pick_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    restaurant_id = int((query.data or "rev:0").split(":", 1)[1])
    draft = _draft(context)
    draft["restaurant_id"] = restaurant_id

    # Tugma matnidan nomni olamiz — qo'shimcha so'rov qilmaslik uchun
    name = "—"
    for row in query.message.reply_markup.inline_keyboard:
        for button in row:
            if button.callback_data == query.data:
                name = button.text.split(" ⭐")[0]
    draft["restaurant_name"] = name

    await safe_edit(update, t(lang, "rev_rate", name=name), reply_markup=rating_kb())
    return RATE


async def set_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    _draft(context)["rating"] = int((query.data or "rate:5").split(":", 1)[1])
    await query.edit_message_text(t(lang, "rev_comment"))
    await update.effective_message.reply_text(t(lang, "rev_comment"), reply_markup=cancel_kb(lang))
    return COMMENT


async def set_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    _draft(context)["text"] = (update.effective_message.text or "").strip()
    await update.effective_message.reply_text(
        t(lang, "rev_photo"), reply_markup=REMOVE
    )
    await update.effective_message.reply_text(t(lang, "rev_photo"), reply_markup=skip_kb(lang))
    return PHOTO


async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    try:
        url = await upload_photo(update, context)
    except CrmApiError as exc:
        logger.warning("Sharh rasmi yuklanmadi: %s", exc.message)
        url = None
    if url:
        _draft(context).setdefault("photo_urls", []).append(url)
    return await _submit(update, context, lang)


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    await update.callback_query.answer()
    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    return await _submit(update, context, lang)


async def _submit(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str) -> int:
    draft = _draft(context)
    try:
        await crm(context).create_review(
            telegram_id=update.effective_user.id,
            restaurant_id=draft["restaurant_id"],
            rating=draft["rating"],
            text=draft.get("text"),
            photo_urls=draft.get("photo_urls", []),
        )
    except CrmApiError as exc:
        await reply_error(update, lang, exc)
        context.user_data.pop("review", None)
        return ConversationHandler.END

    await update.effective_message.reply_text(
        t(lang, "rev_sent", restaurant=draft.get("restaurant_name", "—"), rating=draft["rating"]),
        reply_markup=REMOVE,
    )
    context.user_data.pop("review", None)
    await show_main_menu(update, lang)
    return ConversationHandler.END


def build_handler() -> ConversationHandler:
    cancel_handler = MessageHandler(CANCEL_FILTER, cancel)
    return ConversationHandler(
        entry_points=[
            CommandHandler("review", start_review),
            CallbackQueryHandler(start_review, pattern=r"^nav:review$"),
        ],
        states={
            SEARCH: [
                cancel_handler,
                CallbackQueryHandler(pick_restaurant, pattern=r"^rev:\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER, search_by_name),
            ],
            RATE: [CallbackQueryHandler(set_rating, pattern=r"^rate:[1-5]$")],
            COMMENT: [
                cancel_handler,
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER, set_comment),
            ],
            PHOTO: [
                MessageHandler(filters.PHOTO, add_photo),
                CallbackQueryHandler(skip_photo, pattern=r"^skip$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("menu", cancel)],
        name="reviews",
        per_message=False,
    )

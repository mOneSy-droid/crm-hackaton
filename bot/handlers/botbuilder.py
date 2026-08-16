"""BotBuilder — restoran egasi o'ziga shaxsiy bot yasaydi.

Xavfsizlik: @BotFather tokeni backendga yuboriladi va u yerda shifrlanadi.
Token kelgan xabar darhol o'chiriladi — chat tarixida qolmasin.
Eski koddagi xato: token faqat ":" borligi bilan tekshirilardi va tokenni
yuborgan HAR QANDAY odam avtomatik admin bo'lardi.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN
from crm_client import CrmApiError
from handlers.common import cancel, crm, lang_of, reply_error, show_main_menu
from i18n import CANCEL_TEXTS, t
from keyboards import REMOVE, bb_languages_kb, cancel_kb, restaurants_kb

logger = logging.getLogger(__name__)

PICK, PURPOSE, LANGS, FEATURES, TONE, TOKEN = range(300, 306)

CANCEL_FILTER = filters.Text(CANCEL_TEXTS)


def _draft(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault("botbuilder", {})


async def start_botbuilder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    context.user_data["botbuilder"] = {}

    if update.callback_query is not None:
        await update.callback_query.answer()

    try:
        profile = await crm(context).get_profile(update.effective_user.id)
        restaurants = profile["restaurants"]
    except CrmApiError as exc:
        if exc.status_code == 404:
            await update.effective_message.reply_text(t(lang, "bb_need_restaurant"))
            return ConversationHandler.END
        await reply_error(update, lang, exc)
        return ConversationHandler.END

    if not restaurants:
        await update.effective_message.reply_text(t(lang, "bb_need_restaurant"))
        return ConversationHandler.END

    await update.effective_message.reply_text(t(lang, "bb_intro"))

    if len(restaurants) == 1:
        _draft(context)["restaurant_id"] = restaurants[0]["id"]
        await update.effective_message.reply_text(
            t(lang, "bb_purpose"), reply_markup=cancel_kb(lang)
        )
        return PURPOSE

    await update.effective_message.reply_text(
        t(lang, "prof_pick"), reply_markup=restaurants_kb(restaurants, "bbrest")
    )
    return PICK


async def pick_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    _draft(context)["restaurant_id"] = int((query.data or "bbrest:0").split(":", 1)[1])
    await query.edit_message_text(t(lang, "bb_purpose"))
    return PURPOSE


async def step_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    _draft(context)["purpose"] = (update.effective_message.text or "").strip()
    _draft(context)["languages"] = set()
    await update.effective_message.reply_text(
        t(lang, "bb_languages"), reply_markup=bb_languages_kb(lang, set())
    )
    return LANGS


async def step_languages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    choice = (query.data or "bblang:uz").split(":", 1)[1]
    draft = _draft(context)
    selected: set[str] = draft.setdefault("languages", set())

    if choice == "done":
        if not selected:
            return LANGS
        await query.edit_message_text(t(lang, "bb_features"))
        return FEATURES

    selected.symmetric_difference_update({choice})
    await query.edit_message_reply_markup(reply_markup=bb_languages_kb(lang, selected))
    return LANGS


async def step_features(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    raw = (update.effective_message.text or "").strip()
    _draft(context)["features"] = [part.strip() for part in raw.split(",") if part.strip()]
    await update.effective_message.reply_text(t(lang, "bb_tone"))
    return TONE


async def step_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    draft = _draft(context)
    draft["tone"] = (update.effective_message.text or "").strip()

    await update.effective_message.reply_text(t(lang, "bb_generating"), reply_markup=REMOVE)

    try:
        instance = await crm(context).submit_bot_questionnaire(
            telegram_id=update.effective_user.id,
            restaurant_id=draft["restaurant_id"],
            purpose=draft["purpose"],
            languages=sorted(draft["languages"]),
            features=draft.get("features", []),
            tone=draft.get("tone"),
        )
    except CrmApiError as exc:
        await reply_error(update, lang, exc)
        context.user_data.pop("botbuilder", None)
        return ConversationHandler.END

    draft["bot_id"] = instance["id"]
    await update.effective_message.reply_text(t(lang, "bb_ready"))
    return TOKEN


async def step_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    message = update.effective_message
    token = (message.text or "").strip()

    # Token chatda qolmasin — tekshirishdan oldin o'chiramiz
    try:
        await message.delete()
    except BadRequest:
        logger.info("Token xabarini o'chirib bo'lmadi (huquq yo'q)")

    head, _, tail = token.partition(":")
    if not head.isdigit() or len(tail) < 20:
        await update.effective_chat.send_message(t(lang, "bb_token_invalid"))
        return TOKEN

    # Asosiy botning o'z tokenini ulashga urinish — backendgacha bormasdan
    # tushunarli javob beramiz. (Aks holda runner asosiy bot bilan bitta
    # tokenni talashib, butun tizimni sindiradi — bu bir marta bo'lgan.)
    if token == TELEGRAM_BOT_TOKEN:
        await update.effective_chat.send_message(t(lang, "bb_token_own"))
        return TOKEN

    draft = _draft(context)
    try:
        instance = await crm(context).submit_bot_token(
            update.effective_user.id, draft["bot_id"], token
        )
    except CrmApiError as exc:
        await update.effective_chat.send_message(exc.message)
        return TOKEN

    await update.effective_chat.send_message(
        t(lang, "bb_token_ok", username=instance.get("bot_username") or "—")
    )
    context.user_data.pop("botbuilder", None)
    await show_main_menu(update, lang)
    return ConversationHandler.END


def build_handler() -> ConversationHandler:
    cancel_handler = MessageHandler(CANCEL_FILTER, cancel)
    text = filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER
    return ConversationHandler(
        entry_points=[
            CommandHandler("mybot", start_botbuilder),
            CallbackQueryHandler(start_botbuilder, pattern=r"^nav:mybot$"),
        ],
        states={
            PICK: [CallbackQueryHandler(pick_restaurant, pattern=r"^bbrest:\d+$")],
            PURPOSE: [cancel_handler, MessageHandler(text, step_purpose)],
            LANGS: [CallbackQueryHandler(step_languages, pattern=r"^bblang:")],
            FEATURES: [cancel_handler, MessageHandler(text, step_features)],
            TONE: [cancel_handler, MessageHandler(text, step_tone)],
            TOKEN: [cancel_handler, MessageHandler(text, step_token)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("menu", cancel)],
        name="botbuilder",
        per_message=False,
    )

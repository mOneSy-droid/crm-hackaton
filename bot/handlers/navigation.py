"""/start, /menu, /language, /help va menyu tugmalari."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import storage
from crm_client import CrmApiError
from handlers.common import (
    crm,
    lang_of,
    safe_edit,
    send_help,
    show_language_picker,
    show_main_menu,
)
from i18n import t
from keyboards import language_kb

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = await storage.get_language(user.id)
    await update.effective_message.reply_text(
        t(lang, "welcome", name=user.first_name or ""), reply_markup=language_kb()
    )


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    lang = (query.data or "lang:uz").split(":", 1)[1]
    await storage.set_language(user.id, lang)

    # Backendda ham tilni yangilaymiz — bildirishnomalar shu tilda keladi
    try:
        await crm(context).sync_user(
            telegram_id=user.id,
            language=lang,
            full_name=user.full_name,
            telegram_username=user.username,
        )
    except CrmApiError as exc:
        # Til baribir lokal saqlandi — foydalanuvchini to'xtatmaymiz
        logger.warning("sync_user muvaffaqiyatsiz: %s", exc.message)

    await safe_edit(update, t(lang, "language_saved"))
    await show_main_menu(update, lang)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await lang_of(update)
    if update.callback_query is not None:
        await update.callback_query.answer()
        await show_main_menu(update, lang, edit=True)
        return
    await show_main_menu(update, lang)


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await lang_of(update)
    if update.callback_query is not None:
        await update.callback_query.answer()
        await safe_edit(update, t(lang, "choose_language"), reply_markup=language_kb())
        return
    await show_language_picker(update, lang)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await lang_of(update)
    if update.callback_query is not None:
        await update.callback_query.answer()
    await send_help(update, lang)


def build_handlers() -> list:
    return [
        CommandHandler("start", start),
        CommandHandler("menu", menu),
        CommandHandler("language", language_command),
        CommandHandler("help", help_command),
        CallbackQueryHandler(choose_language, pattern=r"^lang:(uz|ru|en)$"),
        CallbackQueryHandler(menu, pattern=r"^nav:menu$"),
        CallbackQueryHandler(language_command, pattern=r"^nav:language$"),
        CallbackQueryHandler(help_command, pattern=r"^nav:help$"),
    ]

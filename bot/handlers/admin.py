"""Admin panel.

Eski koddagi xavfsizlik teshigi yopildi: avval bot tokeni yuborgan HAR QANDAY
foydalanuvchi avtomatik admin bo'lardi. Endi admin faqat `BOT_SUPER_ADMINS`
sozlamasi orqali yoki mavjud admin tomonidan qo'shiladi.
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

import storage
from crm_client import CrmApiError
from handlers.common import cancel, crm, lang_of, reply_error, safe_edit
from i18n import CANCEL_TEXTS, t
from keyboards import admin_menu_kb, cancel_kb

logger = logging.getLogger(__name__)

ASK_ID = 400

CANCEL_FILTER = filters.Text(CANCEL_TEXTS)


async def open_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = await lang_of(update)
    if not storage.is_admin(update.effective_user.id):
        await update.effective_message.reply_text(t(lang, "admin_denied"))
        return

    if update.callback_query is not None:
        await update.callback_query.answer()
        await safe_edit(update, t(lang, "admin_menu"), reply_markup=admin_menu_kb(lang))
        return
    await update.effective_message.reply_text(
        t(lang, "admin_menu"), reply_markup=admin_menu_kb(lang)
    )


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)
    if not storage.is_admin(update.effective_user.id):
        return

    try:
        restaurants = await crm(context).search_restaurants(limit=50)
        total = len(restaurants)
    except CrmApiError as exc:
        await reply_error(update, lang, exc)
        return

    # Statistika tugmasi ketma-ket bosilsa matn bir xil bo'lishi mumkin —
    # safe_edit «not modified» xatosini yutadi
    await safe_edit(
        update,
        t(lang, "admin_stats_text", restaurants=total, admins=len(storage.admin_ids())),
        reply_markup=admin_menu_kb(lang),
    )


async def ask_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)
    if not storage.is_admin(update.effective_user.id):
        return ConversationHandler.END

    context.user_data["admin_action"] = "add" if query.data == "adm:add" else "remove"
    await query.edit_message_text(t(lang, "admin_ask_id"))
    await update.effective_message.reply_text(t(lang, "admin_ask_id"), reply_markup=cancel_kb(lang))
    return ASK_ID


async def apply_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    if not storage.is_admin(update.effective_user.id):
        return ConversationHandler.END

    raw = (update.effective_message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await update.effective_message.reply_text(t(lang, "admin_bad_id"))
        return ASK_ID

    target = int(raw)
    if context.user_data.get("admin_action") == "add":
        await storage.add_admin(target)
        await update.effective_message.reply_text(t(lang, "admin_added", id=target))
    else:
        removed = await storage.remove_admin(target)
        await update.effective_message.reply_text(
            t(lang, "admin_removed", id=target) if removed else t(lang, "admin_cant_remove_super")
        )

    context.user_data.pop("admin_action", None)
    await open_admin(update, context)
    return ConversationHandler.END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_admin_id, pattern=r"^adm:(add|remove)$")],
        states={
            ASK_ID: [
                MessageHandler(CANCEL_FILTER, cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER, apply_admin_id),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("menu", cancel)],
        name="admin",
        per_message=False,
    )


def build_simple_handlers() -> list:
    return [
        CommandHandler("admin", open_admin),
        CallbackQueryHandler(open_admin, pattern=r"^nav:admin$"),
        CallbackQueryHandler(show_stats, pattern=r"^adm:stats$"),
    ]

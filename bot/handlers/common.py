"""Barcha handlerlar uchun umumiy yordamchilar."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler

import storage
from crm_client import CrmApiError, CrmClient
from i18n import SUPPORT_USERNAME, t
from keyboards import REMOVE, language_kb, main_menu_kb

logger = logging.getLogger(__name__)


def crm(context: ContextTypes.DEFAULT_TYPE) -> CrmClient:
    """`main.py` da `bot_data` ga qo'yilgan yagona klient."""
    return context.bot_data["crm"]


async def safe_edit(
    update: Update, text: str, reply_markup: InlineKeyboardMarkup | None = None, **kwargs
) -> None:
    """Xabarni tahrirlaydi, «Message is not modified» xatosini yutadi.

    Foydalanuvchi bir xil tugmani ikki marta bossa Telegram xato qaytaradi —
    bu foydalanuvchi uchun xato emas, shuning uchun jimgina o'tkazamiz.
    """
    query = update.callback_query
    if query is None:
        return
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, **kwargs)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise
        logger.debug("Xabar o'zgarmagan, tahrirlash o'tkazib yuborildi")


async def lang_of(update: Update) -> str:
    return await storage.get_language(update.effective_user.id)


async def show_main_menu(update: Update, lang: str, *, edit: bool = False) -> None:
    user_id = update.effective_user.id
    markup = main_menu_kb(lang, is_admin=storage.is_admin(user_id))
    text = t(lang, "main_menu")

    if edit and update.callback_query is not None:
        await safe_edit(update, text, reply_markup=markup)
        return
    target = update.effective_message
    await target.reply_text(text, reply_markup=markup)


async def show_language_picker(update: Update, lang: str) -> None:
    await update.effective_message.reply_text(t(lang, "choose_language"), reply_markup=language_kb())


async def reply_error(update: Update, lang: str, exc: Exception) -> None:
    """Backend xatosini foydalanuvchiga muloyim ko'rsatadi.

    `CrmApiError.message` allaqachon foydalanuvchi tilida va tushunarli —
    texnik tafsilotni qo'shmaymiz.
    """
    if isinstance(exc, CrmApiError):
        logger.warning("Backend xatosi %s: %s", exc.status_code, exc.message)
        await update.effective_message.reply_text(exc.message)
    else:
        logger.exception("Kutilmagan xatolik")
        await update.effective_message.reply_text(t(lang, "error"))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Har qanday suhbatni to'xtatadi va klaviaturani tozalaydi."""
    lang = await lang_of(update)
    context.user_data.clear()
    await update.effective_message.reply_text(t(lang, "cancelled"), reply_markup=REMOVE)
    await show_main_menu(update, lang)
    return ConversationHandler.END


async def send_help(update: Update, lang: str) -> None:
    await update.effective_message.reply_text(
        t(lang, "help", support=SUPPORT_USERNAME), parse_mode=ParseMode.HTML
    )


async def download_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[str, bytes] | None:
    """Telegramdagi rasmni yuklab oladi (eng katta o'lchamdagisini)."""
    message = update.effective_message
    if not message or not message.photo:
        return None
    photo = message.photo[-1]
    telegram_file = await context.bot.get_file(photo.file_id)
    content = bytes(await telegram_file.download_as_bytearray())
    return f"{photo.file_unique_id}.jpg", content


async def upload_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Rasmni backendga yuklab, ochiq URL qaytaradi."""
    downloaded = await download_photo(update, context)
    if downloaded is None:
        return None
    filename, content = downloaded
    return await crm(context).upload_photo(filename, content)

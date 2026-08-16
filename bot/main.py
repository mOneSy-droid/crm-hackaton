"""Botni ishga tushirish nuqtasi.

    python main.py
"""

from __future__ import annotations

import logging
import re
import sys
import warnings

from telegram import Update
from telegram.error import BadRequest, Conflict, NetworkError, TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.warnings import PTBUserWarning

# Bizning suhbatlarimizda matn ham, tugma ham bor — bunda `per_message=False`
# yagona to'g'ri sozlama. PTB baribir ogohlantiradi, uni o'chiramiz.
warnings.filterwarnings("ignore", message=r".*per_message=False.*", category=PTBUserWarning)

import storage  # noqa: E402
from config import BOT_HMAC_SECRET, CRM_API_URL, OUTBOX_POLL_SECONDS, require_token  # noqa: E402
from crm_client import CrmClient  # noqa: E402
from handlers import admin, botbuilder, navigation, profile, registration, reviews  # noqa: E402
from handlers.common import cancel, lang_of, show_main_menu  # noqa: E402
from i18n import t  # noqa: E402
from outbox import deliver_pending  # noqa: E402

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

#: Logda bot tokeni yoki telefon raqami ochiq turmasin
_SECRET_PATTERNS = [
    (re.compile(r"\b\d{6,10}:[A-Za-z0-9_-]{30,}\b"), "<bot-token>"),
    (re.compile(r"\+?\d{9,15}"), "<phone>"),
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        redacted = message
        for pattern, replacement in _SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(RedactingFilter())


async def on_startup(application: Application) -> None:
    await storage.init_db()
    application.bot_data["crm"] = CrmClient(CRM_API_URL, BOT_HMAC_SECRET)
    me = await application.bot.get_me()
    logger.info("Bot ishga tushdi: @%s | backend: %s", me.username, CRM_API_URL)


async def on_shutdown(application: Application) -> None:
    crm = application.bot_data.get("crm")
    if crm is not None:
        await crm.close()
    await storage.close_db()


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hech bir handlerga tushmagan matn — foydalanuvchini menyuga qaytaramiz."""
    lang = await lang_of(update)
    await update.effective_message.reply_text(t(lang, "unknown"))
    await show_main_menu(update, lang)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error

    # Bitta token bilan ikkita nusxa polling qilsa Telegram Conflict qaytaradi.
    # Bu kod xatosi emas — qisqa va aniq log yozamiz, traceback shart emas.
    if isinstance(error, Conflict):
        logger.warning(
            "DIQQAT: bu token bilan BOSHQA bot nusxasi ham ishlayapti — "
            "uni to'xtating yoki @BotFather orqali tokenni yangilang"
        )
        return

    # Tarmoq uzilishi bizning kod xatosi emas — to'liq traceback shart emas,
    # aks holda log haqiqiy xatolar ko'rinmay ketadigan darajada to'lib ketadi.
    if isinstance(error, (NetworkError, TimedOut)):
        logger.warning("Telegram bilan aloqa uzildi (%s) — qayta urinadi", type(error).__name__)
        return

    if isinstance(error, BadRequest) and "not modified" in str(error).lower():
        return

    logger.exception("Handlerda xatolik", exc_info=error)
    if isinstance(update, Update) and update.effective_message is not None:
        try:
            lang = await storage.get_language(update.effective_user.id)
            await update.effective_message.reply_text(t(lang, "error"))
        except Exception:  # noqa: BLE001 - xato ustiga xato chiqmasin
            logger.debug("Xato haqida xabar yuborilmadi")
        # Xato haqida xabar berildi — endi keyingi guruhdagi fallback ham
        # ishlab, ustiga "Tushunmadim" deb yubormasin (ikkita xabar chalg'itadi).
        raise ApplicationHandlerStop


def build_application() -> Application:
    application = (
        ApplicationBuilder()
        .token(require_token())
        # Telegram API'ga ulanish O'zbekistondan sekin bo'lishi mumkin —
        # standart 5 soniyalik timeout bilan `TimedOut` chiqib turadi.
        .connect_timeout(20.0)
        .read_timeout(20.0)
        .write_timeout(20.0)
        .pool_timeout(20.0)
        .get_updates_read_timeout(40.0)
        .get_updates_connect_timeout(20.0)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    # Suhbat handlerlari birinchi: ular faol bo'lsa boshqalari aralashmasin
    application.add_handler(registration.build_handler())
    application.add_handler(reviews.build_handler())
    application.add_handler(profile.build_handler())
    application.add_handler(botbuilder.build_handler())
    application.add_handler(admin.build_handler())

    for handler in navigation.build_handlers():
        application.add_handler(handler)
    for handler in admin.build_simple_handlers():
        application.add_handler(handler)

    # Suhbat ichida /cancel fallback sifatida ishlaydi, lekin menyuda turgan
    # foydalanuvchi ham bosishi mumkin — javobsiz qolmasin
    application.add_handler(CommandHandler("cancel", cancel))

    # Eng oxirida, alohida guruhda — aks holda yuqoridagi handlerlarni to'sadi.
    # (Eski koddagi xato: ikkita TEXT handler bir guruhda edi va ikkinchisi
    #  hech qachon ishlamasdi.)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, fallback), group=10
    )

    application.add_error_handler(on_error)

    if application.job_queue is not None:
        application.job_queue.run_repeating(
            deliver_pending, interval=OUTBOX_POLL_SECONDS, first=10, name="outbox"
        )
    else:
        logger.warning(
            "JobQueue mavjud emas — bildirishnomalar yuborilmaydi. "
            "O'rnating: pip install \"python-telegram-bot[job-queue]\""
        )

    return application


if __name__ == "__main__":
    try:
        build_application().run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("To'xtatildi")
        sys.exit(0)

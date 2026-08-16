"""Backend bildirishnomalarini foydalanuvchilarga yetkazish.

Backend Telegram'ga to'g'ridan-to'g'ri yozmaydi — xabarlarni navbatga qo'yadi,
bot esa shu navbatni pollab, o'z tokeni bilan yuboradi. Shu tufayli Telegram
tokeni faqat botda qoladi.

Yetkazilgani tasdiqlanmagan xabar keyingi pollashda yana keladi, shuning uchun
`ack` faqat muvaffaqiyatli yuborilgandan keyin qilinadi.
"""

from __future__ import annotations

import logging

from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import ContextTypes

from crm_client import CrmApiError
from i18n import t

logger = logging.getLogger(__name__)

#: backenddagi `kind` -> i18n kaliti
KIND_TO_KEY = {
    "new_review": "notify_new_review",
    "owner_reply": "notify_owner_reply",
    "bot_status": "notify_bot_status",
    "tenant_lead": "notify_tenant_lead",
}


def _format_answers(answers: dict) -> str:
    """Shaxsiy bot yig'gan javoblarni o'qish oson ro'yxatga aylantiradi."""
    if not answers:
        return "—"
    return "\n".join(f"• {key}: {value}" for key, value in answers.items())


def _render(kind: str, payload: dict, lang: str) -> str | None:
    if kind == "review_moderated":
        approved = payload.get("status") == "approved"
        return t(lang, "notify_review_approved" if approved else "notify_review_rejected")

    if kind == "tenant_lead":
        data = dict(payload)
        data["answers"] = _format_answers(payload.get("answers") or {})
        data.setdefault("customer_name", "—")
        return t(lang, "notify_tenant_lead", **data)

    key = KIND_TO_KEY.get(kind)
    if key is None:
        logger.warning("Noma'lum bildirishnoma turi: %s", kind)
        return None
    return t(lang, key, **payload)


async def deliver_pending(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue har necha soniyada chaqiradi."""
    crm = context.bot_data["crm"]

    try:
        messages = await crm.fetch_outbox(limit=50)
    except CrmApiError as exc:
        logger.warning("Outbox o'qilmadi: %s", exc.message)
        return
    except Exception:  # noqa: BLE001 - tarmoq uzilishi jobni o'ldirmasin
        logger.exception("Outbox o'qishda kutilmagan xatolik")
        return

    delivered: list[int] = []
    for message in messages:
        text = _render(message["kind"], message.get("payload", {}), message.get("language", "uz"))
        if text is None:
            # Yubora olmaydigan xabarni navbatda qoldirmaymiz, aks holda
            # u har pollashda qaytaveradi
            delivered.append(message["id"])
            continue

        try:
            await context.bot.send_message(message["telegram_id"], text)
            delivered.append(message["id"])
        except Forbidden:
            # Foydalanuvchi botni bloklagan — qayta urinish befoyda
            logger.info("Foydalanuvchi botni bloklagan, xabar tashlab yuborildi")
            delivered.append(message["id"])
        except BadRequest as exc:
            # "chat not found" — foydalanuvchi botga hech qachon yozmagan.
            # Bu holat o'zgarmaydi, shuning uchun navbatda qoldirsak xabar
            # abadiy aylanaveradi va logni to'ldiradi.
            logger.info("Xabar yetkazilmadi (%s), navbatdan olib tashlandi", exc.message)
            delivered.append(message["id"])
        except TelegramError as exc:
            logger.warning("Xabar yuborilmadi (%s), navbatda qoladi", type(exc).__name__)

    if delivered:
        try:
            await crm.ack_outbox(delivered)
        except CrmApiError as exc:
            logger.warning("Outbox ack muvaffaqiyatsiz: %s", exc.message)

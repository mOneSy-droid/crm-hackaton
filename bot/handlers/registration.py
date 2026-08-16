"""Restoran ro'yxatdan o'tishi — 7 bosqichli anketa.

Eski koddagi asosiy xato: til inline tugmasi ConversationHandler'dan tashqarida
edi, shuning uchun oqim birinchi bosqichda qotib qolardi. Endi har bir bosqich
o'z holatida, callback tugmalar ham suhbat ichida.
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
from handlers.common import cancel, crm, lang_of, reply_error, show_main_menu, upload_photo
from i18n import CANCEL_TEXTS, t
from keyboards import (
    REMOVE,
    cancel_kb,
    categories_kb,
    confirm_kb,
    contact_kb,
    field_choices_kb,
    industries_kb,
    localized,
    location_kb,
    portal_kb,
    skip_field_kb,
    skip_kb,
)

logger = logging.getLogger(__name__)

INDUSTRY, PHONE, NAME, LOCATION, ADDRESS, DESCRIPTION, HOURS, CATEGORY, EXTRA, LOGO, CONFIRM = (
    range(11)
)

WORK_HOURS_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d\s*-\s*([01]\d|2[0-3]):[0-5]\d$")


def _form(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault("registration", {})


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Birinchi qadam — soha tanlash. Qolgan hamma narsa shunga bog'liq."""
    lang = await lang_of(update)
    context.user_data["registration"] = {}

    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_reply_markup(reply_markup=None)

    try:
        industries = await crm(context).get_industries()
    except CrmApiError as exc:
        await reply_error(update, lang, exc)
        return ConversationHandler.END

    context.user_data["industries"] = industries
    await update.effective_message.reply_text(
        t(lang, "reg_industry"), reply_markup=industries_kb(industries, lang)
    )
    return INDUSTRY


async def step_industry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    key = (query.data or "ind:restaurant").split(":", 1)[1]
    industry = next(
        (item for item in context.user_data.get("industries", []) if item["key"] == key), None
    )
    if industry is None:
        await reply_error(update, lang, CrmApiError(422, t(lang, "error")))
        return ConversationHandler.END

    _form(context)["industry_key"] = key
    context.user_data["industry"] = industry

    await query.edit_message_text(
        f"{industry['icon']} {localized(industry, 'name', lang)}"
    )
    await update.effective_message.reply_text(
        t(lang, "reg_phone"), reply_markup=contact_kb(lang)
    )
    return PHONE


async def step_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    contact = update.effective_message.contact
    if contact is None:
        await update.effective_message.reply_text(
            t(lang, "reg_phone_invalid"), reply_markup=contact_kb(lang)
        )
        return PHONE

    _form(context)["phone"] = contact.phone_number
    await update.effective_message.reply_text(t(lang, "reg_name"), reply_markup=cancel_kb(lang))
    return NAME


async def step_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    name = (update.effective_message.text or "").strip()
    if len(name) < 2:
        await update.effective_message.reply_text(t(lang, "reg_name_short"))
        return NAME

    _form(context)["name"] = name
    await update.effective_message.reply_text(
        t(lang, "reg_location"), reply_markup=location_kb(lang)
    )
    return LOCATION


async def step_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    location = update.effective_message.location
    if location is None:
        await update.effective_message.reply_text(
            t(lang, "reg_location_invalid"), reply_markup=location_kb(lang)
        )
        return LOCATION

    form = _form(context)
    form["latitude"] = location.latitude
    form["longitude"] = location.longitude
    await update.effective_message.reply_text(t(lang, "reg_address"), reply_markup=cancel_kb(lang))
    return ADDRESS


async def step_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    _form(context)["address"] = (update.effective_message.text or "").strip()
    await update.effective_message.reply_text(t(lang, "reg_description"))
    return DESCRIPTION


async def step_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    _form(context)["description"] = (update.effective_message.text or "").strip()
    await update.effective_message.reply_text(t(lang, "reg_hours"))
    return HOURS


async def step_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    value = (update.effective_message.text or "").strip()
    # Backend ham shu formatni talab qiladi — bu yerda tekshirsak,
    # foydalanuvchi 422 xatosini ko'rmaydi
    if not WORK_HOURS_RE.match(value):
        await update.effective_message.reply_text(t(lang, "reg_hours_invalid"))
        return HOURS

    _form(context)["work_hours"] = value.replace(" ", "")

    # Yo'nalishlar tanlangan soha bilan birga kelgan — qo'shimcha so'rov shart emas
    industry = context.user_data.get("industry", {})
    categories = industry.get("categories", [])
    context.user_data["categories"] = categories

    await update.effective_message.reply_text(
        t(lang, "reg_category"), reply_markup=categories_kb(categories, lang)
    )
    return CATEGORY


async def step_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    _form(context)["category_key"] = (query.data or "cat:other").split(":", 1)[1]
    await query.edit_message_text(t(lang, "reg_category"))
    return await _ask_extra_field(update, context, lang, index=0)


# ---------------------------------------------------------------------------
# Sohaga xos qo'shimcha savollar
# ---------------------------------------------------------------------------


async def _ask_extra_field(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, index: int
) -> int:
    """`Industry.fields` dagi savollarni ketma-ket so'raydi.

    Savollar backenddan keladi — bot kodida sohaga oid `if` yozilmagan.
    """
    fields = context.user_data.get("industry", {}).get("fields", [])
    context.user_data["extra_index"] = index

    if index >= len(fields):
        await update.effective_message.reply_text(t(lang, "reg_logo"), reply_markup=skip_kb(lang))
        return LOGO

    field = fields[index]
    prompt = field["label"].get(lang) or field["label"].get("uz") or field["key"]
    hint = t(lang, "reg_extra_optional")

    if field.get("type") == "choice" and field.get("choices"):
        markup = field_choices_kb(field["choices"], lang)
    else:
        markup = skip_field_kb(lang)

    await update.effective_message.reply_text(f"{prompt}\n\n{hint}", reply_markup=markup)
    return EXTRA


async def _save_extra_and_continue(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, value: str | None
) -> int:
    fields = context.user_data.get("industry", {}).get("fields", [])
    index = context.user_data.get("extra_index", 0)

    if value and index < len(fields):
        _form(context).setdefault("attributes", {})[fields[index]["key"]] = value

    return await _ask_extra_field(update, context, lang, index + 1)


async def step_extra_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)
    await query.edit_message_reply_markup(reply_markup=None)

    value = None if query.data == "fld_skip" else (query.data or "fld:").split(":", 1)[1]
    return await _save_extra_and_continue(update, context, lang, value)


async def step_extra_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    value = (update.effective_message.text or "").strip()

    fields = context.user_data.get("industry", {}).get("fields", [])
    index = context.user_data.get("extra_index", 0)
    if index < len(fields) and fields[index].get("type") == "number":
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits:
            await update.effective_message.reply_text(t(lang, "invalid_number"))
            return EXTRA
        value = digits

    return await _save_extra_and_continue(update, context, lang, value)


async def step_logo_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    try:
        _form(context)["logo_url"] = await upload_photo(update, context)
    except CrmApiError as exc:
        # Logotip ixtiyoriy — yuklanmasa ham anketani to'xtatmaymiz
        logger.warning("Logotip yuklanmadi: %s", exc.message)
    return await _show_summary(update, context, lang)


async def step_logo_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await lang_of(update)
    await update.callback_query.answer()
    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    return await _show_summary(update, context, lang)


async def _show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str) -> int:
    form = _form(context)
    industry = context.user_data.get("industry", {})
    lines = [
        f"{industry.get('icon', '🏢')} {localized(industry, 'name', lang)}",
        f"🏪 {form.get('name', '—')}",
        f"📞 {form.get('phone', '—')}",
        f"📍 {form.get('address', '—')}",
        f"🕒 {form.get('work_hours', '—')}",
        f"🏷 {_category_label(context, form.get('category_key'), lang)}",
        f"📝 {form.get('description', '—')}",
    ]

    # Sohaga xos javoblar savol matni bilan ko'rsatiladi
    for field in industry.get("fields", []):
        value = form.get("attributes", {}).get(field["key"])
        if value:
            label = field["label"].get(lang) or field["label"].get("uz") or field["key"]
            lines.append(f"• {label} {value}")

    lines.append(f"🖼 {'✅' if form.get('logo_url') else '—'}")

    await update.effective_message.reply_text(
        t(lang, "reg_confirm", summary="\n".join(lines)),
        reply_markup=confirm_kb(lang),
    )
    return CONFIRM


def _category_label(context: ContextTypes.DEFAULT_TYPE, key: str | None, lang: str) -> str:
    for category in context.user_data.get("categories", []):
        if category["key"] == key:
            return localized(category, "name", lang)
    return key or "—"


async def step_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = await lang_of(update)

    if query.data == "retry":
        await query.edit_message_reply_markup(reply_markup=None)
        return await start_registration(update, context)

    await query.edit_message_text(t(lang, "reg_sending"))

    user = update.effective_user
    form = _form(context)
    payload = {
        "user": {
            "telegram_id": user.id,
            "telegram_username": user.username,
            "full_name": user.full_name,
            "language": lang,
            "phone": form.get("phone"),
        },
        "name": form["name"],
        "industry_key": form.get("industry_key"),
        "description": form.get("description"),
        "address": form.get("address"),
        "latitude": form.get("latitude"),
        "longitude": form.get("longitude"),
        "work_hours": form.get("work_hours"),
        "phone": form.get("phone"),
        "category_key": form.get("category_key"),
        "logo_url": form.get("logo_url"),
        "attributes": form.get("attributes", {}),
    }

    try:
        result = await crm(context).register_restaurant(payload)
    except CrmApiError as exc:
        await reply_error(update, lang, exc)
        context.user_data.clear()
        return ConversationHandler.END

    restaurant = result["restaurant"]
    if result.get("already_registered") or not result.get("password"):
        await update.effective_message.reply_text(
            t(lang, "reg_exists", name=restaurant["name"]),
            reply_markup=portal_kb(lang, result["login_url"]),
        )
    else:
        await update.effective_message.reply_text(
            t(
                lang,
                "reg_success",
                name=restaurant["name"],
                login=result["username"],
                password=result["password"],
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=portal_kb(lang, result["login_url"]),
        )

    context.user_data.clear()
    await update.effective_message.reply_text(t(lang, "main_menu"), reply_markup=REMOVE)
    await show_main_menu(update, lang)
    return ConversationHandler.END


def _text(handler) -> MessageHandler:
    """Matnli bosqich: avval «Bekor qilish» tugmasini tekshiramiz.

    Reply-klaviatura tugmasi oddiy matn bo'lib keladi, shuning uchun uni
    umumiy TEXT handleridan OLDIN ushlash kerak — aks holda foydalanuvchi
    anketadan chiqa olmaydi.
    """
    return MessageHandler(filters.TEXT & ~filters.COMMAND & ~CANCEL_FILTER, handler)


CANCEL_FILTER = filters.Text(CANCEL_TEXTS)
_CANCEL = MessageHandler(CANCEL_FILTER, cancel)


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("register", start_registration),
            CallbackQueryHandler(start_registration, pattern=r"^nav:register$"),
        ],
        states={
            INDUSTRY: [CallbackQueryHandler(step_industry, pattern=r"^ind:")],
            PHONE: [_CANCEL, MessageHandler(filters.CONTACT, step_phone), _text(step_phone)],
            NAME: [_CANCEL, _text(step_name)],
            LOCATION: [_CANCEL, MessageHandler(filters.LOCATION, step_location), _text(step_location)],
            ADDRESS: [_CANCEL, _text(step_address)],
            DESCRIPTION: [_CANCEL, _text(step_description)],
            HOURS: [_CANCEL, _text(step_hours)],
            CATEGORY: [CallbackQueryHandler(step_category, pattern=r"^cat:")],
            EXTRA: [
                _CANCEL,
                CallbackQueryHandler(step_extra_choice, pattern=r"^(fld:|fld_skip$)"),
                _text(step_extra_text),
            ],
            LOGO: [
                MessageHandler(filters.PHOTO, step_logo_photo),
                CallbackQueryHandler(step_logo_skip, pattern=r"^skip$"),
            ],
            CONFIRM: [CallbackQueryHandler(step_confirm, pattern=r"^(confirm|retry)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("menu", cancel)],
        name="registration",
        per_message=False,
    )

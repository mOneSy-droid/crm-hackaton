"""Restoranning shaxsiy boti — kodi emas, KONFIGURATSIYASI o'zgaradi.

Bitta shu fayl barcha mijoz botlarini yuritadi. Har bir bot uchun alohida kod
yozilmaydi: BotBuilder AI yasagan JSON (salomlashuv, tugmalar, savol oqimlari)
shu yerda talqin qilinadi.

Konfiguratsiya shakli:

    {
      "welcome":      {"uz": "...", "ru": "...", "en": "..."},
      "menu_buttons": [{"id": "menu", "label": {"uz": "📋 Menyu", ...}}],
      "flows": [
        {"id": "booking", "trigger": "booking",
         "steps": [{"type": "ask_text", "text": {...}, "save_as": "sana"}]}
      ],
      "fallback":     {"uz": "...", ...}
    }

`menu`, `contact`, `review` tugmalari o'rnatilgan (built-in) — ular backend
bilan ishlaydi. Qolgan tugmalar `flows` dagi mos oqimni ishga tushiradi va
yig'ilgan javoblar restoran egasiga Telegramga yuboriladi.
"""

from __future__ import annotations

import logging
from typing import Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from crm_client import CrmApiError, CrmClient

logger = logging.getLogger(__name__)

BUILTIN_MENU = "menu"
BUILTIN_CONTACT = "contact"
BUILTIN_REVIEW = "review"

LANGUAGE_NAMES = {"uz": "🇺🇿 O'zbek", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

#: Konfiguratsiyada matn topilmaganda ishlatiladigan zaxira iboralar
FALLBACK_TEXT = {
    "choose_language": {
        "uz": "Tilni tanlang:",
        "ru": "Выберите язык:",
        "en": "Choose a language:",
    },
    "menu_empty": {
        "uz": "Menyu hozircha bo'sh.",
        "ru": "Меню пока пустое.",
        "en": "The menu is empty for now.",
    },
    "contact": {
        "uz": "📍 Manzil: {address}\n🕒 Ish vaqti: {hours}\n📞 Telefon: {phone}",
        "ru": "📍 Адрес: {address}\n🕒 Часы работы: {hours}\n📞 Телефон: {phone}",
        "en": "📍 Address: {address}\n🕒 Hours: {hours}\n📞 Phone: {phone}",
    },
    "review_rate": {
        "uz": "Bahoingizni tanlang:",
        "ru": "Выберите оценку:",
        "en": "Choose your rating:",
    },
    "review_text": {
        "uz": "Fikringizni yozing:",
        "ru": "Напишите отзыв:",
        "en": "Write your review:",
    },
    "review_done": {
        "uz": "Rahmat! Sharhingiz qabul qilindi ⭐",
        "ru": "Спасибо! Отзыв принят ⭐",
        "en": "Thank you! Your review was received ⭐",
    },
    "lead_done": {
        "uz": "Rahmat! So'rovingiz qabul qilindi, tez orada bog'lanamiz.",
        "ru": "Спасибо! Заявка принята, мы скоро свяжемся.",
        "en": "Thank you! Your request was received, we'll be in touch.",
    },
    "error": {
        "uz": "Xatolik yuz berdi. Birozdan keyin urinib ko'ring.",
        "ru": "Произошла ошибка. Попробуйте позже.",
        "en": "Something went wrong. Please try again later.",
    },
    "back": {"uz": "🔙 Menyu", "ru": "🔙 Меню", "en": "🔙 Menu"},
}


def pick(mapping: Any, lang: str, default: str = "") -> str:
    """Ko'p tilli lug'atdan matnni oladi; til topilmasa birinchisiga tushadi."""
    if isinstance(mapping, str):
        return mapping
    if not isinstance(mapping, dict) or not mapping:
        return default
    value = mapping.get(lang)
    if isinstance(value, str) and value:
        return value
    for candidate in mapping.values():
        if isinstance(candidate, str) and candidate:
            return candidate
    return default


def fallback(key: str, lang: str, **kwargs: Any) -> str:
    text = pick(FALLBACK_TEXT.get(key, {}), lang, key)
    return text.format(**kwargs) if kwargs else text


class TenantBot:
    """Bitta restoran boti. `start()` chaqirilganda polling boshlanadi."""

    def __init__(self, spec: dict, crm: CrmClient):
        self.spec = spec
        self.crm = crm
        self.bot_id: int = spec["bot_id"]
        self.restaurant_id: int = spec["restaurant_id"]
        self.restaurant_name: str = spec["restaurant_name"]
        self.version: str = spec["config_version"]
        self.config: dict = spec.get("config") or {}
        self.languages: list[str] = [
            code for code in spec.get("languages", ["uz"]) if code in LANGUAGE_NAMES
        ] or ["uz"]

        self._app: Application | None = None
        #: user_id -> {"lang": str, "flow": dict|None, "step": int, "answers": dict}
        self._state: dict[int, dict[str, Any]] = {}

    # -- hayotiy sikl -------------------------------------------------------

    async def start(self) -> None:
        self._app = (
            ApplicationBuilder()
            .token(self.spec["token"])
            .connect_timeout(20.0)
            .read_timeout(20.0)
            .write_timeout(20.0)
            .get_updates_read_timeout(40.0)
            .build()
        )

        self._app.add_handler(CommandHandler("start", self.on_start))
        self._app.add_handler(CommandHandler("menu", self.on_start))
        self._app.add_handler(CallbackQueryHandler(self.on_callback))
        self._app.add_handler(MessageHandler(filters.CONTACT, self.on_contact))
        self._app.add_handler(MessageHandler(filters.LOCATION, self.on_location))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))
        self._app.add_error_handler(self.on_error)

        await self._app.initialize()
        await self._app.start()
        # Eski xabarlarga javob bermaymiz — bot to'xtab turgan paytdagi
        # so'rovlarga kech javob berish foydalanuvchini chalg'itadi
        await self._app.updater.start_polling(drop_pending_updates=True)

    async def stop(self) -> None:
        if self._app is None:
            return
        try:
            if self._app.updater and self._app.updater.running:
                await self._app.updater.stop()
            if self._app.running:
                await self._app.stop()
            await self._app.shutdown()
        finally:
            self._app = None

    # -- holat --------------------------------------------------------------

    def _user(self, user_id: int) -> dict[str, Any]:
        return self._state.setdefault(
            user_id, {"lang": self.languages[0], "flow": None, "step": 0, "answers": {}}
        )

    def _lang(self, user_id: int) -> str:
        return self._user(user_id)["lang"]

    # -- klaviaturalar ------------------------------------------------------

    def _language_kb(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(LANGUAGE_NAMES[code], callback_data=f"lang:{code}")
              for code in self.languages]]
        )

    def _menu_kb(self, lang: str) -> InlineKeyboardMarkup:
        rows, row = [], []
        for button in self.config.get("menu_buttons", []):
            label = pick(button.get("label"), lang, button.get("id", "?"))
            row.append(InlineKeyboardButton(label, callback_data=f"btn:{button['id']}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        if not rows:
            # Konfiguratsiya bo'sh bo'lsa ham bot ishlatib bo'ladigan holda qolsin
            rows = [[InlineKeyboardButton(
                fallback("back", lang), callback_data=f"btn:{BUILTIN_MENU}"
            )]]
        return InlineKeyboardMarkup(rows)

    # -- handlerlar ---------------------------------------------------------

    async def on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        state = self._user(user_id)
        state["flow"] = None
        state["answers"] = {}

        if len(self.languages) > 1 and update.message and update.message.text == "/start":
            await update.effective_message.reply_text(
                fallback("choose_language", state["lang"]), reply_markup=self._language_kb()
            )
            return
        await self._show_menu(update, state["lang"])

    async def _show_menu(self, update: Update, lang: str, edit: bool = False) -> None:
        text = pick(self.config.get("welcome"), lang, f"{self.restaurant_name}")
        markup = self._menu_kb(lang)
        if edit and update.callback_query is not None:
            try:
                await update.callback_query.edit_message_text(text, reply_markup=markup)
                return
            except BadRequest as exc:
                if "not modified" not in str(exc).lower():
                    raise
                return
        await update.effective_message.reply_text(text, reply_markup=markup)

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        state = self._user(user_id)
        data = query.data or ""

        if data.startswith("lang:"):
            state["lang"] = data.split(":", 1)[1]
            await self._show_menu(update, state["lang"], edit=True)
            return

        if data.startswith("rate:"):
            state["answers"]["rating"] = data.split(":", 1)[1]
            await query.edit_message_text(fallback("review_text", state["lang"]))
            state["flow"] = {"id": BUILTIN_REVIEW, "builtin": True}
            state["step"] = 1
            return

        if data.startswith("choice:"):
            await self._accept_answer(update, state, data.split(":", 1)[1])
            return

        if data.startswith("btn:"):
            await self._handle_button(update, state, data.split(":", 1)[1])

    async def _handle_button(self, update: Update, state: dict, button_id: str) -> None:
        lang = state["lang"]
        state["flow"] = None
        state["answers"] = {}
        state["step"] = 0

        if button_id == BUILTIN_MENU:
            await self._send_catalog(update, lang)
            return
        if button_id == BUILTIN_CONTACT:
            await self._send_contact(update, lang)
            return
        if button_id == BUILTIN_REVIEW:
            await update.effective_message.reply_text(
                fallback("review_rate", lang),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⭐" * i, callback_data=f"rate:{i}") for i in (1, 2, 3)],
                     [InlineKeyboardButton("⭐" * i, callback_data=f"rate:{i}") for i in (4, 5)]]
                ),
            )
            return

        flow = self._find_flow(button_id)
        if flow is None:
            await update.effective_message.reply_text(
                pick(self.config.get("fallback"), lang, fallback("error", lang))
            )
            return

        state["flow"] = flow
        state["step"] = 0
        await self._ask_current_step(update, state)

    def _find_flow(self, trigger: str) -> dict | None:
        for flow in self.config.get("flows", []):
            if flow.get("trigger") == trigger or flow.get("id") == trigger:
                return flow
        return None

    # -- o'rnatilgan funksiyalar --------------------------------------------

    async def _send_catalog(self, update: Update, lang: str) -> None:
        try:
            items = await self.crm.get_catalog(self.restaurant_id)
        except CrmApiError:
            await update.effective_message.reply_text(fallback("error", lang))
            return

        if not items:
            await update.effective_message.reply_text(fallback("menu_empty", lang))
            return

        sections: dict[str, list[dict]] = {}
        for item in items:
            sections.setdefault(item.get("section") or "—", []).append(item)

        lines: list[str] = []
        for section, entries in sections.items():
            lines.append(f"<b>{section}</b>")
            for entry in entries:
                price = entry.get("price")
                price_text = f" — {int(price):,} so'm".replace(",", " ") if price else ""
                lines.append(f"• {entry['name']}{price_text}")
            lines.append("")

        await update.effective_message.reply_text(
            "\n".join(lines).strip(), parse_mode=ParseMode.HTML
        )

    async def _send_contact(self, update: Update, lang: str) -> None:
        try:
            data = await self.crm.get_restaurant(self.restaurant_id)
        except CrmApiError:
            await update.effective_message.reply_text(fallback("error", lang))
            return

        await update.effective_message.reply_text(
            fallback(
                "contact",
                lang,
                address=data.get("address") or "—",
                hours=data.get("work_hours") or "—",
                phone=data.get("phone") or "—",
            )
        )
        if data.get("latitude") is not None:
            await update.effective_message.reply_location(
                latitude=data["latitude"], longitude=data["longitude"]
            )

    # -- oqim mexanizmi -----------------------------------------------------

    async def _ask_current_step(self, update: Update, state: dict) -> None:
        flow = state["flow"]
        steps = flow.get("steps", [])
        lang = state["lang"]

        if state["step"] >= len(steps):
            await self._finish_flow(update, state)
            return

        step = steps[state["step"]]
        text = pick(step.get("text"), lang, "…")
        step_type = step.get("type", "ask_text")

        if step_type == "message":
            await update.effective_message.reply_text(text)
            state["step"] += 1
            await self._ask_current_step(update, state)
            return

        if step_type == "ask_choice":
            choices = [str(choice) for choice in step.get("choices", [])][:12]
            rows = [
                [InlineKeyboardButton(choice, callback_data=f"choice:{choice}")]
                for choice in choices
            ]
            await update.effective_message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(rows) if rows else None
            )
            return

        if step_type == "ask_phone":
            await update.effective_message.reply_text(
                text,
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("📞", request_contact=True)]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
            return

        if step_type == "ask_location":
            await update.effective_message.reply_text(
                text,
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("📍", request_location=True)]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
            return

        await update.effective_message.reply_text(text, reply_markup=ReplyKeyboardRemove())

    async def _accept_answer(self, update: Update, state: dict, value: str) -> None:
        flow = state["flow"]
        if flow is None:
            return
        steps = flow.get("steps", [])
        if state["step"] < len(steps):
            step = steps[state["step"]]
            key = step.get("save_as") or f"javob_{state['step'] + 1}"
            state["answers"][key] = value
        state["step"] += 1
        await self._ask_current_step(update, state)

    async def _finish_flow(self, update: Update, state: dict) -> None:
        flow = state["flow"]
        lang = state["lang"]
        user = update.effective_user

        try:
            await self.crm.submit_lead(
                bot_id=self.bot_id,
                telegram_id=user.id,
                flow_id=flow.get("id", "flow"),
                flow_label=pick(flow.get("label"), lang, flow.get("id", "So'rov")),
                answers={k: str(v) for k, v in state["answers"].items()},
                customer_name=user.full_name,
            )
        except CrmApiError as exc:
            logger.warning("Lead yuborilmadi: %s", exc.message)
            await update.effective_message.reply_text(fallback("error", lang))
            state["flow"] = None
            return

        await update.effective_message.reply_text(
            fallback("lead_done", lang), reply_markup=ReplyKeyboardRemove()
        )
        state["flow"] = None
        state["answers"] = {}
        await self._show_menu(update, lang)

    # -- matn / kontakt / lokatsiya -----------------------------------------

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        state = self._user(user_id)
        text = (update.effective_message.text or "").strip()
        lang = state["lang"]

        flow = state["flow"]
        if flow is None:
            await update.effective_message.reply_text(
                pick(self.config.get("fallback"), lang, fallback("error", lang)),
                reply_markup=self._menu_kb(lang),
            )
            return

        # Sharh oqimi o'rnatilgan — matn kelgach backendga yuboriladi
        if flow.get("builtin") and flow.get("id") == BUILTIN_REVIEW:
            await self._submit_review(update, state, text)
            return

        await self._accept_answer(update, state, text)

    async def on_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._user(update.effective_user.id)
        contact = update.effective_message.contact
        if state["flow"] is not None and contact is not None:
            await self._accept_answer(update, state, contact.phone_number)

    async def on_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._user(update.effective_user.id)
        location = update.effective_message.location
        if state["flow"] is not None and location is not None:
            await self._accept_answer(
                update, state, f"{location.latitude:.5f},{location.longitude:.5f}"
            )

    async def _submit_review(self, update: Update, state: dict, text: str) -> None:
        lang = state["lang"]
        rating = int(state["answers"].get("rating", 5))
        try:
            await self.crm.create_review(
                telegram_id=update.effective_user.id,
                restaurant_id=self.restaurant_id,
                rating=rating,
                text=text,
            )
        except CrmApiError as exc:
            logger.warning("Sharh yuborilmadi: %s", exc.message)
            await update.effective_message.reply_text(fallback("error", lang))
        else:
            await update.effective_message.reply_text(fallback("review_done", lang))

        state["flow"] = None
        state["answers"] = {}
        await self._show_menu(update, lang)

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Bitta bot xatosi boshqa botlarga ta'sir qilmasligi kerak
        logger.warning(
            "Bot #%s (%s) handlerida xatolik: %s",
            self.bot_id,
            self.restaurant_name,
            type(context.error).__name__,
        )

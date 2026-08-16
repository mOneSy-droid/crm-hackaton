from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Sen restoranlar uchun Telegram bot konfiguratsiyasini tuzuvchi yordamchisan.
Foydalanuvchi anketasiga qarab QAT'IY JSON qaytar, boshqa hech qanday matn yozma.

JSON sxemasi:
{
  "welcome": {"uz": "...", "ru": "...", "en": "..."},
  "menu_buttons": [{"id": "kebab-case", "label": {"uz": "...", "ru": "...", "en": "..."}}],
  "flows": [
    {"id": "kebab-case", "trigger": "menu_button_id",
     "steps": [{"type": "message|ask_text|ask_phone|ask_location|ask_choice",
                "text": {"uz": "...", "ru": "...", "en": "..."},
                "choices": ["..."],
                "save_as": "field_name"}]}
  ],
  "fallback": {"uz": "...", "ru": "...", "en": "..."}
}

Qoidalar:
- Xabarlar qisqa, muloyim va aniq bo'lsin (1-2 gap).
- Faqat so'ralgan tillarni to'ldir; qolganini bo'sh qoldirma, so'ralgan tildan nusxa ol.
- 3 tadan 6 tagacha menyu tugmasi.
- Foydalanuvchini chalg'itadigan uzun matn yozma."""


def _fallback_config(
    restaurant_name: str, languages: list[str], features: list[str], tone: str | None
) -> dict[str, Any]:
    """AI mavjud bo'lmaganda ishlatiladigan zaxira shablon.

    BotBuilder AI kaliti bo'lmasa ham ishlashi kerak — demo hech qachon buzilmasin.
    """
    primary = languages[0] if languages else "uz"
    greetings = {
        "uz": f"Assalomu alaykum! {restaurant_name} botiga xush kelibsiz. Nima qilamiz?",
        "ru": f"Здравствуйте! Добро пожаловать в бот {restaurant_name}. Чем помочь?",
        "en": f"Hello! Welcome to the {restaurant_name} bot. How can we help?",
    }
    labels = {
        "menu": {"uz": "📋 Menyu", "ru": "📋 Меню", "en": "📋 Menu"},
        "contact": {"uz": "📞 Aloqa", "ru": "📞 Контакты", "en": "📞 Contact"},
        "review": {"uz": "⭐ Sharh qoldirish", "ru": "⭐ Оставить отзыв", "en": "⭐ Leave a review"},
        "booking": {"uz": "🪑 Joy band qilish", "ru": "🪑 Забронировать", "en": "🪑 Book a table"},
    }
    button_ids = ["menu", "contact", "review"]
    if any("bron" in f.lower() or "book" in f.lower() for f in features):
        button_ids.append("booking")

    def localized(mapping: dict[str, str]) -> dict[str, str]:
        return {lang: mapping.get(lang, mapping[primary]) for lang in languages or [primary]}

    return {
        "welcome": localized(greetings),
        "tone": tone or "muloyim va qisqa",
        "menu_buttons": [
            {"id": bid, "label": localized(labels[bid])} for bid in button_ids
        ],
        "flows": [
            {
                "id": "leave-review",
                "trigger": "review",
                "steps": [
                    {
                        "type": "ask_choice",
                        "text": localized(
                            {
                                "uz": "Bahoingizni tanlang:",
                                "ru": "Выберите оценку:",
                                "en": "Choose your rating:",
                            }
                        ),
                        "choices": ["1", "2", "3", "4", "5"],
                        "save_as": "rating",
                    },
                    {
                        "type": "ask_text",
                        "text": localized(
                            {
                                "uz": "Fikringizni yozing:",
                                "ru": "Напишите ваш отзыв:",
                                "en": "Write your review:",
                            }
                        ),
                        "save_as": "text",
                    },
                ],
            }
        ],
        "fallback": localized(
            {
                "uz": "Tushunmadim. Iltimos, menyudan tanlang.",
                "ru": "Не понял. Пожалуйста, выберите из меню.",
                "en": "I didn't get that. Please pick from the menu.",
            }
        ),
        "generated_by": "template",
    }


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def generate_bot_config(
    *,
    restaurant_name: str,
    purpose: str,
    languages: list[str],
    features: list[str],
    tone: str | None,
) -> dict[str, Any]:
    """Anketaga qarab bot konfiguratsiyasini yaratadi.

    ANTHROPIC_API_KEY berilmagan yoki so'rov muvaffaqiyatsiz bo'lsa — shablonga tushadi.
    """
    if not settings.ANTHROPIC_API_KEY:
        return _fallback_config(restaurant_name, languages, features, tone)

    user_message = (
        f"Restoran: {restaurant_name}\n"
        f"Bot maqsadi: {purpose}\n"
        f"Tillar: {', '.join(languages)}\n"
        f"Kerakli funksiyalar: {', '.join(features) or 'kiritilmagan'}\n"
        f"Muloqot uslubi: {tone or 'muloyim va qisqa'}"
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.ANTHROPIC_MODEL,
                    "max_tokens": 2000,
                    "system": _SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
        response.raise_for_status()
        blocks = response.json().get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        config = _extract_json(text)
        if config:
            config["generated_by"] = "ai"
            return config
        logger.warning("BotBuilder: AI javobidan JSON ajratib bo'lmadi, shablonga o'tildi")
    except httpx.HTTPError as exc:
        logger.warning("BotBuilder: AI so'rovi muvaffaqiyatsiz (%s), shablonga o'tildi", type(exc).__name__)

    return _fallback_config(restaurant_name, languages, features, tone)

"""Botning ulanishini tekshiradi — Telegram tokeni kerak emas.

    python scripts/check_wiring.py

Nimani tekshiradi:
  1. Barcha modullar import bo'ladimi
  2. Uch tilda matn kalitlari to'liq mos keladimi
  3. Har bir tugmaning `callback_data` si biror handlerga tushadimi
     (eski botdagi asosiy nosozlik shu edi: tugma bor, handler yo'q)
  4. Bazaga ulanish va til saqlash ishlaydimi
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BOT_DIR))

TMP = Path(tempfile.mkdtemp(prefix="bot_check_"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456789:AAtest-token-for-wiring-check-only-xx")
os.environ["BOT_DATABASE_URL"] = f"sqlite+aiosqlite:///{(TMP / 'check.db').as_posix()}"
os.environ.setdefault("CRM_API_URL", "http://localhost:8000")

from telegram.ext import CallbackQueryHandler, CommandHandler, ConversationHandler  # noqa: E402

import storage  # noqa: E402
from i18n import TEXTS  # noqa: E402
from keyboards import (  # noqa: E402
    admin_menu_kb,
    bb_languages_kb,
    categories_kb,
    confirm_kb,
    field_choices_kb,
    industries_kb,
    language_kb,
    main_menu_kb,
    profile_fields_kb,
    rating_kb,
    restaurants_kb,
    skip_field_kb,
    skip_kb,
)
from main import build_application  # noqa: E402

passed, failed = 0, []


def check(name: str, condition: bool, extra: object = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  [ok]   {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def collect_callback_patterns(application) -> list[re.Pattern]:
    """Ro'yxatdan o'tgan barcha CallbackQueryHandler shablonlarini yig'adi."""
    patterns: list[re.Pattern] = []

    def visit(handler) -> None:
        if isinstance(handler, ConversationHandler):
            nested = [*handler.entry_points, *handler.fallbacks]
            for state_handlers in handler.states.values():
                nested.extend(state_handlers)
            for child in nested:
                visit(child)
            return
        if isinstance(handler, CallbackQueryHandler) and handler.pattern is not None:
            patterns.append(handler.pattern)

    for group in application.handlers.values():
        for handler in group:
            visit(handler)
    return patterns


def collect_commands(application) -> set[str]:
    commands: set[str] = set()

    def visit(handler) -> None:
        if isinstance(handler, ConversationHandler):
            nested = [*handler.entry_points, *handler.fallbacks]
            for state_handlers in handler.states.values():
                nested.extend(state_handlers)
            for child in nested:
                visit(child)
            return
        if isinstance(handler, CommandHandler):
            commands.update(handler.commands)

    for group in application.handlers.values():
        for handler in group:
            visit(handler)
    return commands


def buttons_from(markup) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


async def main() -> int:
    print("\n1) Matnlar uch tilda to'liqmi")
    uz_keys = set(TEXTS["uz"])
    for lang in ("ru", "en"):
        missing = uz_keys - set(TEXTS[lang])
        extra = set(TEXTS[lang]) - uz_keys
        check(f"'{lang}' da yetishmayotgan kalit yo'q", not missing, sorted(missing))
        check(f"'{lang}' da ortiqcha kalit yo'q", not extra, sorted(extra))

    print("\n2) Ilova quriladimi")
    application = build_application()
    check("build_application()", application is not None)

    commands = collect_commands(application)
    expected_commands = {
        "start", "menu", "register", "review", "profile", "mybot",
        "language", "help", "cancel",
    }
    check(
        "setup_profile dagi barcha buyruqlar ro'yxatdan o'tgan",
        expected_commands <= commands,
        sorted(expected_commands - commands),
    )

    print("\n3) Har bir tugma handlerga tushadimi")
    patterns = collect_callback_patterns(application)

    sample_restaurants = [{"id": 1, "name": "Test", "rating_avg": 4.5, "rating_count": 2}]
    sample_categories = [
        {"key": "national", "name_uz": "Milliy", "name_ru": "Национальная", "name_en": "National"}
    ]
    sample_industries = [
        {"key": "restaurant", "icon": "🍽", "name_uz": "Restoranlar",
         "name_ru": "Рестораны", "name_en": "Restaurants"},
        {"key": "market", "icon": "🛒", "name_uz": "Do'konlar",
         "name_ru": "Магазины", "name_en": "Shops"},
    ]

    all_buttons: list[tuple[str, str]] = []
    for label, markup in [
        ("til tanlash", language_kb()),
        ("asosiy menyu", main_menu_kb("uz", is_admin=True)),
        ("sohalar", industries_kb(sample_industries, "uz")),
        ("kategoriyalar", categories_kb(sample_categories, "uz")),
        ("sohaga xos savol", field_choices_kb(["Bor", "Yo'q"], "uz")),
        ("savolni o'tkazish", skip_field_kb("uz")),
        ("o'tkazib yuborish", skip_kb("uz")),
        ("tasdiqlash", confirm_kb("uz")),
        ("reyting", rating_kb()),
        ("sharh: restoranlar", restaurants_kb(sample_restaurants, "rev")),
        ("profil: restoranlar", restaurants_kb(sample_restaurants, "prof")),
        ("botbuilder: restoranlar", restaurants_kb(sample_restaurants, "bbrest")),
        ("profil maydonlari", profile_fields_kb("uz", 1)),
        ("botbuilder tillari", bb_languages_kb("uz", {"uz"})),
        ("admin menyu", admin_menu_kb("uz")),
    ]:
        for data in buttons_from(markup):
            all_buttons.append((label, data))

    orphans = [
        (label, data)
        for label, data in all_buttons
        if not any(pattern.match(data) for pattern in patterns)
    ]
    check(
        f"{len(all_buttons)} ta tugmaning hammasi ushlanadi",
        not orphans,
        orphans,
    )

    print("\n4) Baza")
    await storage.init_db()
    await storage.set_language(42, "ru")
    check("til saqlandi", await storage.get_language(42) == "ru")

    await storage.add_admin(42)
    check("admin qo'shildi", storage.is_admin(42))
    check("admin olib tashlandi", await storage.remove_admin(42) and not storage.is_admin(42))
    await storage.close_db()

    print("\n" + "=" * 60)
    print(f"  Muvaffaqiyatli: {passed}   Xato: {len(failed)}")
    for name in failed:
        print(f"    - {name}")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

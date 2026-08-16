"""Botning ko'rinishini sozlaydi: nom, About, Description, botpic va buyruqlar.

Ishga tushirish (bir marta, yoki matnlar o'zgarganda):

    python setup_profile.py

Hammasi Telegram Bot API orqali qilinadi — @BotFather ga kirish shart emas.

Botpic: shu papkaga `botpic.png` (yoki .jpg) faylini qo'ying — skript uni
avtomatik o'rnatadi. Rasm kvadrat va kamida 512x512 px bo'lgani ma'qul.
Fayl bo'lmasa, bu qadam o'tkazib yuboriladi.

Yangi buyruq qo'shish: pastdagi COMMANDS ro'yxatiga qator qo'shing va skriptni
qayta ishga tushiring. Handlerini `handlers/` ichida ro'yxatdan o'tkazishni
unutmang — aks holda menyuda ko'rinadi, lekin ishlamaydi.
(`scripts/check_wiring.py` aynan shuni tekshiradi.)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from telegram import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    InputProfilePhotoStatic,
    MenuButtonCommands,
)
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder

from config import require_token

BOT_DIR = Path(__file__).resolve().parent
BOTPIC_CANDIDATES = ["botpic.png", "botpic.jpg", "botpic.jpeg"]

# ---------------------------------------------------------------------------
# Bot nomi — Telegram profilda ko'rinadigan nom (64 belgigacha).
# Brend nomi tarjima qilinmaydi, shuning uchun uch tilda ham bir xil.
# Nomni o'zgartirmoqchi bo'lsangiz shu yerni tahrirlang; skript nomni faqat
# haqiqatan o'zgargan bo'lsa yuboradi (Telegram tez-tez almashtirishga cheklov qo'yadi).
# ---------------------------------------------------------------------------
NAME = {
    "uz": "Restaurant CRM",
    "ru": "Restaurant CRM",
    "en": "Restaurant CRM",
}

# ---------------------------------------------------------------------------
# About — profil sahifasidagi qisqa matn (120 belgigacha)
# ---------------------------------------------------------------------------
SHORT_DESCRIPTION = {
    "uz": "Restoraningizni ro'yxatdan o'tkazing, sharhlarni boshqaring va o'zingizga bot yasang.",
    "ru": "Зарегистрируйте ресторан, управляйте отзывами и создайте своего бота.",
    "en": "Register your restaurant, manage reviews and build your own bot.",
}

# ---------------------------------------------------------------------------
# Description — bo'sh chatda «Bu bot nima qila oladi?» ostida (512 belgigacha)
# ---------------------------------------------------------------------------
DESCRIPTION = {
    "uz": (
        "Restoranlar uchun CRM.\n\n"
        "🏪 Restoraningizni 2 daqiqada ro'yxatdan o'tkazing\n"
        "🔐 Saytdagi kabinetga bir bosishda kiring\n"
        "⭐ Mijozlar sharhlarini qabul qiling va javob bering\n"
        "⚙️ Profil, menyu va ish vaqtini shu yerdan tahrirlang\n"
        "🤖 O'zingizga shaxsiy Telegram bot yasang\n\n"
        "Boshlash uchun /start bosing."
    ),
    "ru": (
        "CRM для ресторанов.\n\n"
        "🏪 Зарегистрируйте ресторан за 2 минуты\n"
        "🔐 Входите в кабинет на сайте одним нажатием\n"
        "⭐ Принимайте отзывы клиентов и отвечайте на них\n"
        "⚙️ Редактируйте профиль, меню и часы работы прямо здесь\n"
        "🤖 Создайте своего Telegram-бота\n\n"
        "Нажмите /start, чтобы начать."
    ),
    "en": (
        "CRM for restaurants.\n\n"
        "🏪 Register your restaurant in 2 minutes\n"
        "🔐 Open your website dashboard in one tap\n"
        "⭐ Collect customer reviews and reply to them\n"
        "⚙️ Edit your profile, menu and hours right here\n"
        "🤖 Build your own Telegram bot\n\n"
        "Press /start to begin."
    ),
}

# ---------------------------------------------------------------------------
# Buyruqlar menyusi. Buyruq nomi faqat a-z, 0-9 va _ dan iborat bo'lishi kerak.
# ---------------------------------------------------------------------------
COMMANDS: dict[str, list[tuple[str, str]]] = {
    "uz": [
        ("start", "Botni boshlash"),
        ("menu", "Asosiy menyu"),
        ("register", "Restoran qo'shish"),
        ("review", "Sharh qoldirish"),
        ("profile", "Profilni tahrirlash"),
        ("mybot", "O'zimga bot yasash"),
        ("language", "Tilni o'zgartirish"),
        ("help", "Yordam"),
        ("cancel", "Jarayonni bekor qilish"),
    ],
    "ru": [
        ("start", "Запустить бота"),
        ("menu", "Главное меню"),
        ("register", "Добавить ресторан"),
        ("review", "Оставить отзыв"),
        ("profile", "Редактировать профиль"),
        ("mybot", "Создать своего бота"),
        ("language", "Сменить язык"),
        ("help", "Помощь"),
        ("cancel", "Отменить процесс"),
    ],
    "en": [
        ("start", "Start the bot"),
        ("menu", "Main menu"),
        ("register", "Add a restaurant"),
        ("review", "Leave a review"),
        ("profile", "Edit your profile"),
        ("mybot", "Build your own bot"),
        ("language", "Change language"),
        ("help", "Help"),
        ("cancel", "Cancel the current step"),
    ],
}

#: Telegram "uz" tilini alohida qo'llab-quvvatlamaydi — u standart (tilsiz)
#: variant sifatida o'rnatiladi, ru va en esa o'z language_code'i bilan.
LANGUAGE_CODES = {"uz": None, "ru": "ru", "en": "en"}


async def main() -> int:
    application = ApplicationBuilder().token(require_token()).build()
    bot = application.bot

    async with application:
        me = await bot.get_me()
        print(f"Bot: @{me.username} (id {me.id})\n")

        for lang, code in LANGUAGE_CODES.items():
            label = code or "standart"
            try:
                current = (await bot.get_my_name(language_code=code)).name
                if current == NAME[lang]:
                    print(f"  [==] nom          ({label}) — o'zgarmagan, o'tkazildi")
                else:
                    await bot.set_my_name(name=NAME[lang], language_code=code)
                    print(f"  [ok] nom          ({label})")
            except TelegramError as exc:
                # Telegram nomni tez-tez o'zgartirishga ruxsat bermaydi
                print(f"  [--] nom          ({label}): {exc.message}")

            try:
                await bot.set_my_short_description(
                    short_description=SHORT_DESCRIPTION[lang], language_code=code
                )
                print(f"  [ok] About        ({label})")
            except TelegramError as exc:
                print(f"  [!!] About        ({label}): {exc.message}")

            try:
                await bot.set_my_description(
                    description=DESCRIPTION[lang], language_code=code
                )
                print(f"  [ok] Description  ({label})")
            except TelegramError as exc:
                print(f"  [!!] Description  ({label}): {exc.message}")

            try:
                await bot.set_my_commands(
                    [BotCommand(name, text) for name, text in COMMANDS[lang]],
                    scope=BotCommandScopeAllPrivateChats(),
                    language_code=code,
                )
                print(f"  [ok] buyruqlar    ({label}) — {len(COMMANDS[lang])} ta")
            except TelegramError as exc:
                print(f"  [!!] buyruqlar    ({label}): {exc.message}")
            print()

        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            print("  [ok] menyu tugmasi buyruqlar ro'yxatini ochadi")
        except TelegramError as exc:
            print(f"  [!!] menyu tugmasi: {exc.message}")

        await _set_profile_photo(bot)

    print(f"\nTayyor. Telegramda @{me.username} ni oching va tekshiring.")
    return 0


async def _set_profile_photo(bot) -> None:
    """`botpic.png` bo'lsa profil rasmini o'rnatadi."""
    for filename in BOTPIC_CANDIDATES:
        path = BOT_DIR / filename
        if path.exists():
            break
    else:
        print(
            f"  [--] botpic: {BOT_DIR / 'botpic.png'} topilmadi — o'tkazib yuborildi.\n"
            "       Rasmni shu nom bilan qo'ying va skriptni qayta ishga tushiring\n"
            "       (yoki @BotFather → /setuserpic orqali qo'lda qo'ying)."
        )
        return

    try:
        with path.open("rb") as image:
            await bot.set_my_profile_photo(photo=InputProfilePhotoStatic(photo=image))
        print(f"  [ok] botpic o'rnatildi ({path.name})")
    except TelegramError as exc:
        print(f"  [!!] botpic: {exc.message}")
        print("       Kvadrat va kamida 512x512 px rasm ishlating.")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

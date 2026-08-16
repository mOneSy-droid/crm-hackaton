"""Sohalar va ular ichidagi yo'nalishlar.

YANGI SOHA QO'SHISH: pastdagi `INDUSTRIES` ro'yxatiga bitta yozuv qo'shing.
Kod o'zgartirilmaydi — bot ham, sayt ham yorliqlarni shu yerdan oladi va
`fields` dagi savollarni o'zi chizadi.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Industry

logger = logging.getLogger(__name__)


def _label(uz: str, ru: str, en: str) -> dict[str, str]:
    return {"uz": uz, "ru": ru, "en": en}


#: Har bir soha: yorliqlar, qo'shimcha savollar va yo'nalishlar ro'yxati.
INDUSTRIES: list[dict[str, Any]] = [
    {
        "key": "restaurant",
        "icon": "🍽",
        "name": _label("Restoranlar", "Рестораны", "Restaurants"),
        "entity": _label("restoran", "ресторан", "restaurant"),
        "item": _label("Taom", "Блюдо", "Dish"),
        "catalog": _label("Menyu", "Меню", "Menu"),
        "fields": [
            {
                "key": "delivery",
                "type": "choice",
                "choices": ["Bor", "Yo'q"],
                "label": _label("Yetkazib berish bormi?", "Есть доставка?", "Do you deliver?"),
            },
            {
                "key": "seats",
                "type": "number",
                "label": _label("Necha kishilik joy bor?", "Сколько посадочных мест?",
                                "How many seats?"),
            },
        ],
        "categories": [
            ("national", "Milliy taomlar", "Национальная кухня", "National cuisine"),
            ("fast_food", "Fast-food", "Фаст-фуд", "Fast food"),
            ("cafeteria", "Kafeteriya", "Кафетерий", "Cafeteria"),
            ("european", "Yevropa", "Европейская", "European"),
            ("asian", "Osiyo", "Азиатская", "Asian"),
            ("pizzeria", "Pitseriya", "Пиццерия", "Pizzeria"),
            ("bakery", "Nonvoyxona", "Пекарня", "Bakery"),
            ("coffee", "Qahvaxona", "Кофейня", "Coffee shop"),
            ("other", "Boshqa", "Другое", "Other"),
        ],
    },
    {
        "key": "market",
        "icon": "🛒",
        "name": _label("Do'konlar", "Магазины", "Shops"),
        "entity": _label("do'kon", "магазин", "shop"),
        "item": _label("Mahsulot", "Товар", "Product"),
        "catalog": _label("Katalog", "Каталог", "Catalogue"),
        "fields": [
            {
                "key": "delivery",
                "type": "choice",
                "choices": ["Bor", "Yo'q"],
                "label": _label("Yetkazib berish bormi?", "Есть доставка?", "Do you deliver?"),
            },
            {
                "key": "min_order",
                "type": "number",
                "label": _label(
                    "Eng kam buyurtma summasi (so'm)?",
                    "Минимальная сумма заказа (сум)?",
                    "Minimum order amount (UZS)?",
                ),
            },
            {
                "key": "payment",
                "type": "choice",
                "choices": ["Naqd", "Karta", "Ikkalasi"],
                "label": _label("To'lov turi?", "Способ оплаты?", "Payment method?"),
            },
        ],
        "categories": [
            ("grocery", "Oziq-ovqat", "Продукты", "Grocery"),
            ("clothing", "Kiyim-kechak", "Одежда", "Clothing"),
            ("electronics", "Maishiy texnika", "Электроника", "Electronics"),
            ("construction", "Qurilish mollari", "Стройматериалы", "Construction"),
            ("pharmacy", "Dorixona", "Аптека", "Pharmacy"),
            ("stationery", "Kanstovarlar", "Канцтовары", "Stationery"),
            ("cosmetics", "Kosmetika", "Косметика", "Cosmetics"),
            ("other", "Boshqa", "Другое", "Other"),
        ],
    },
    {
        "key": "clinic",
        "icon": "🏥",
        "name": _label("Klinikalar", "Клиники", "Clinics"),
        "entity": _label("klinika", "клиника", "clinic"),
        "item": _label("Xizmat", "Услуга", "Service"),
        "catalog": _label("Xizmatlar", "Услуги", "Services"),
        "fields": [
            {
                "key": "appointment",
                "type": "choice",
                "choices": ["Navbat bo'yicha", "Oldindan yozilish", "Ikkalasi"],
                "label": _label("Qabul qanday?", "Как ведётся приём?", "How are visits booked?"),
            },
            {
                "key": "emergency",
                "type": "choice",
                "choices": ["Ha", "Yo'q"],
                "label": _label(
                    "Shoshilinch yordam bormi?", "Есть неотложная помощь?", "Emergency care?"
                ),
            },
            {
                "key": "license",
                "type": "text",
                "label": _label("Litsenziya raqami", "Номер лицензии", "Licence number"),
            },
        ],
        "categories": [
            ("general", "Umumiy amaliyot", "Общая практика", "General practice"),
            ("dental", "Stomatologiya", "Стоматология", "Dentistry"),
            ("pediatric", "Bolalar shifokori", "Педиатрия", "Paediatrics"),
            ("diagnostic", "Diagnostika", "Диагностика", "Diagnostics"),
            ("laboratory", "Laboratoriya", "Лаборатория", "Laboratory"),
            ("ophthalmology", "Ko'z shifokori", "Офтальмология", "Ophthalmology"),
            ("other", "Boshqa", "Другое", "Other"),
        ],
    },
    {
        "key": "gym",
        "icon": "🏋",
        "name": _label("Sport va ta'lim", "Спорт и обучение", "Sport & education"),
        "entity": _label("markaz", "центр", "centre"),
        "item": _label("Mashg'ulot", "Занятие", "Class"),
        "catalog": _label("Mashg'ulotlar", "Занятия", "Classes"),
        "fields": [
            {
                "key": "trial",
                "type": "choice",
                "choices": ["Bor", "Yo'q"],
                "label": _label("Sinov darsi bormi?", "Есть пробное занятие?", "Free trial class?"),
            },
            {
                "key": "monthly_fee",
                "type": "number",
                "label": _label(
                    "Oylik to'lov (so'm)?", "Абонемент в месяц (сум)?", "Monthly fee (UZS)?"
                ),
            },
            {
                "key": "age_group",
                "type": "text",
                "label": _label("Yosh chegarasi", "Возрастная группа", "Age group"),
            },
        ],
        "categories": [
            ("fitness", "Fitnes zali", "Фитнес-зал", "Fitness gym"),
            ("martial", "Kurash va jang", "Единоборства", "Martial arts"),
            ("swimming", "Suzish havzasi", "Бассейн", "Swimming pool"),
            ("yoga", "Yoga va stretching", "Йога и стретчинг", "Yoga & stretching"),
            ("language", "Til kurslari", "Языковые курсы", "Language courses"),
            ("it_school", "IT maktabi", "IT-школа", "IT school"),
            ("kids", "Bolalar to'garagi", "Детские кружки", "Kids' clubs"),
            ("other", "Boshqa", "Другое", "Other"),
        ],
    },
]

DEFAULT_INDUSTRY_KEY = "restaurant"


async def seed_industries(db: AsyncSession) -> None:
    """Sohalar va yo'nalishlarni to'ldiradi. Bir necha marta chaqirish xavfsiz.

    Mavjud yozuvlar yangilanadi — matn tuzatilsa qayta ishga tushirish yetarli.
    """
    existing_industries = {
        row.key: row for row in (await db.scalars(select(Industry))).all()
    }
    existing_categories = {
        (row.industry_id, row.key): row for row in (await db.scalars(select(Category))).all()
    }

    added_industries = added_categories = 0

    for order, spec in enumerate(INDUSTRIES):
        industry = existing_industries.get(spec["key"])
        if industry is None:
            industry = Industry(key=spec["key"])
            db.add(industry)
            added_industries += 1

        industry.icon = spec["icon"]
        for field, source in (
            ("name", "name"),
            ("entity_label", "entity"),
            ("item_label", "item"),
            ("catalog_label", "catalog"),
        ):
            for lang in ("uz", "ru", "en"):
                setattr(industry, f"{field}_{lang}", spec[source][lang])
        industry.field_schema = json.dumps(spec["fields"], ensure_ascii=False)
        industry.sort_order = order
        industry.is_active = True

        # Kategoriyalar industry.id ga bog'lanadi — avval ID kerak
        await db.flush()

        for cat_order, (key, uz, ru, en) in enumerate(spec["categories"]):
            category = existing_categories.get((industry.id, key))
            if category is None:
                category = Category(industry_id=industry.id, key=key)
                db.add(category)
                added_categories += 1
            category.name_uz, category.name_ru, category.name_en = uz, ru, en
            category.sort_order = cat_order

    await db.commit()
    if added_industries or added_categories:
        logger.info(
            "Seed: %d ta soha, %d ta yo'nalish qo'shildi", added_industries, added_categories
        )


async def default_industry_id(db: AsyncSession) -> int:
    """Soha ko'rsatilmaganda ishlatiladigan soha."""
    industry_id = await db.scalar(
        select(Industry.id).where(Industry.key == DEFAULT_INDUSTRY_KEY)
    )
    if industry_id is None:
        # Seed ishlamay qolgan bo'lsa ham tizim to'xtamasin
        industry_id = await db.scalar(select(Industry.id).order_by(Industry.sort_order))
    return industry_id

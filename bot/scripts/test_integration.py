"""Bot <-> backend integratsiyasi: haqiqiy backend ko'tariladi va bot
handlerlari yuboradigan AYNAN o'sha payloadlar jo'natiladi.

    python scripts/test_integration.py

Telegram tokeni kerak emas — Telegram tarafi emas, backend kontrakti tekshiriladi.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BOT_DIR.parent
sys.path.insert(0, str(BOT_DIR))
sys.path.insert(0, str(REPO_DIR / "backend"))

TMP = Path(tempfile.mkdtemp(prefix="bot_integration_"))
SHARED_SECRET = "integration-shared-secret"

os.environ.update(
    ENV="dev",
    SECRET_KEY="integration-secret-key-at-least-32-characters-long",
    BOT_HMAC_SECRET=SHARED_SECRET,
    DATABASE_URL=f"sqlite+aiosqlite:///{(TMP / 'backend.db').as_posix()}",
    MEDIA_ROOT=str(TMP / "media"),
    FRONTEND_URL="http://localhost:5173",
    PUBLIC_BASE_URL="http://localhost:8000",
)

import httpx  # noqa: E402

from app.main import app as backend_app  # noqa: E402
from crm_client import CrmApiError, CrmClient  # noqa: E402
from outbox import _render  # noqa: E402

OWNER_ID = 900001
CUSTOMER_ID = 900002

passed, failed = 0, []


def check(name: str, condition: bool, extra: object = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  [ok]   {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def make_client() -> CrmClient:
    client = CrmClient("http://test", SHARED_SECRET)
    client._client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=backend_app), base_url="http://test", timeout=30
    )
    return client


async def main() -> int:
    async with backend_app.router.lifespan_context(backend_app):
        crm = make_client()

        print("\n1) Til tanlash (navigation.choose_language)")
        await crm.sync_user(
            telegram_id=OWNER_ID, language="uz", full_name="Ali Valiyev", telegram_username="ali"
        )
        check("sync_user", True)

        print("\n2) Kategoriyalar (registration.step_hours)")
        categories = await crm.get_categories()
        check("get_categories", len(categories) >= 5, len(categories))
        check(
            "kategoriyada uch til bor",
            all({"name_uz", "name_ru", "name_en", "key"} <= set(c) for c in categories),
        )
        category_key = categories[0]["key"]

        print("\n3) Ro'yxatdan o'tish (registration.step_confirm payloadi)")
        payload = {
            "user": {
                "telegram_id": OWNER_ID,
                "telegram_username": "ali",
                "full_name": "Ali Valiyev",
                "language": "uz",
                "phone": "+998901112233",
            },
            "name": "Osh Markazi",
            "description": "Milliy taomlar",
            "address": "Toshkent, Chilonzor 5",
            "latitude": 41.2995,
            "longitude": 69.2401,
            "work_hours": "09:00-23:00",
            "phone": "+998901112233",
            "category_key": category_key,
            "logo_url": None,
        }
        result = await crm.register_restaurant(payload)
        check("register_restaurant", result["restaurant"]["id"] > 0, result)
        check("login qaytdi", bool(result["username"]))
        check("parol bir marta qaytdi", bool(result["password"]))
        check("kirish linki bor", result["login_url"].startswith("http"))
        restaurant_id = result["restaurant"]["id"]

        # Handler shu kalitlarni o'qiydi — nomi o'zgarsa bot yiqiladi
        check(
            "javob handler kutgan kalitlarga ega",
            {"restaurant", "username", "password", "login_url", "already_registered"}
            <= set(result),
            sorted(result),
        )

        print("\n4) Noto'g'ri ish vaqti (bot oldindan tekshiradi, backend ham)")
        try:
            await crm.register_restaurant(dict(payload, name="Xato Kafe", work_hours="9-23"))
            check("noto'g'ri ish vaqti rad etiladi", False, "xato ko'tarilmadi")
        except CrmApiError as exc:
            check("noto'g'ri ish vaqti rad etiladi", exc.status_code == 422)
            check("xabar foydalanuvchiga tayyor", bool(exc.message) and "422" not in exc.message)

        print("\n5) Sharh qoldirish (reviews._submit)")
        await crm.sync_user(telegram_id=CUSTOMER_ID, language="ru", full_name="Mijoz")
        found = await crm.search_restaurants("Osh", limit=10)
        check("search_restaurants", len(found) == 1, found)
        check(
            "qidiruv natijasi klaviatura kutgan kalitlarga ega",
            {"id", "name", "rating_avg", "rating_count"} <= set(found[0]),
            sorted(found[0]),
        )

        review = await crm.create_review(CUSTOMER_ID, restaurant_id, 5, "Ajoyib!")
        check("create_review", review["rating"] == 5, review)

        print("\n6) Profil (profile.start_profile / set_value)")
        profile = await crm.get_profile(OWNER_ID)
        check("get_profile", len(profile["restaurants"]) == 1)
        card = profile["restaurants"][0]
        check(
            "profil kartasi kutgan maydonlar bor",
            {"name", "rating_avg", "rating_count", "address", "work_hours", "description"}
            <= set(card),
            sorted(card),
        )

        updated = await crm.update_restaurant(OWNER_ID, restaurant_id, {"work_hours": "10:00-22:00"})
        check("update_restaurant", updated["work_hours"] == "10:00-22:00", updated)

        print("\n7) Rasm yuklash (common.upload_photo)")
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
        url = await crm.upload_photo("logo.png", png)
        check("upload_photo", url.startswith("http"), url)
        updated = await crm.update_restaurant(OWNER_ID, restaurant_id, {"logo_url": url})
        check("logotip saqlandi", updated["logo_url"] == url)

        print("\n8) BotBuilder (botbuilder.step_tone / step_token)")
        instance = await crm.submit_bot_questionnaire(
            OWNER_ID, restaurant_id, "Buyurtma qabul qilish", ["uz", "ru"], ["menyu"], "do'stona"
        )
        check("submit_bot_questionnaire", instance["has_generated_config"], instance)
        check("javobda 'id' bor (handler shuni o'qiydi)", "id" in instance, sorted(instance))
        check("javobda ochiq token yo'q", "token" not in instance, sorted(instance))

        try:
            await crm.submit_bot_token(OWNER_ID, instance["id"], "123456789:" + "a" * 25)
            check("soxta token rad etiladi", False, "xato ko'tarilmadi")
        except CrmApiError as exc:
            check("soxta token rad etiladi", exc.status_code == 400, exc.status_code)

        print("\n9) Bildirishnomalar (outbox.deliver_pending)")
        messages = await crm.fetch_outbox()
        check("outboxda yangi sharh bor", any(m["kind"] == "new_review" for m in messages), messages)

        rendered = 0
        for message in messages:
            text = _render(message["kind"], message.get("payload", {}), message.get("language", "uz"))
            if text and not text.startswith("notify_"):
                rendered += 1
        check(
            f"{len(messages)} ta xabarning hammasi matnga aylandi",
            rendered == len(messages),
            f"{rendered}/{len(messages)}",
        )

        await crm.ack_outbox([m["id"] for m in messages])
        check("ack_outbox", await crm.fetch_outbox() == [])

        print("\n9b) Boshqa soha: klinika (registration handleri yuboradigan payload)")
        industries = await crm.get_industries()
        check("sohalar ro'yxati keldi", len(industries) >= 4, len(industries))
        clinic = next((i for i in industries if i["key"] == "clinic"), None)
        check("klinika sohasi bor", clinic is not None)
        check(
            "klinika yorliqlari to'g'ri",
            clinic and clinic["item_label_uz"] == "Xizmat"
            and clinic["catalog_label_uz"] == "Xizmatlar",
            clinic,
        )
        check("klinikaning o'z savollari bor", len(clinic["fields"]) >= 2, clinic["fields"])
        check(
            "savollarda uch til bor",
            all({"uz", "ru", "en"} <= set(f["label"]) for f in clinic["fields"]),
            clinic["fields"],
        )
        check("klinika yo'nalishlari alohida", any(
            c["key"] == "dental" for c in clinic["categories"]), clinic["categories"])

        # Bot registration handleri aynan shunday yuboradi
        clinic_answers = {
            field["key"]: (field["choices"][0] if field.get("choices") else "12345")
            for field in clinic["fields"]
        }
        clinic_owner = 700010
        await crm.sync_user(clinic_owner, language="uz", full_name="Shifokor")
        result = await crm.register_restaurant(
            {
                "user": {"telegram_id": clinic_owner, "full_name": "Shifokor", "language": "uz"},
                "name": "Salomat Klinika",
                "industry_key": "clinic",
                "category_key": "dental",
                "work_hours": "08:00-18:00",
                "attributes": clinic_answers,
            }
        )
        clinic_business = result["restaurant"]
        check("klinika ro'yxatdan o'tdi", clinic_business["id"] > 0, result)
        check("sohasi klinika", clinic_business["industry"]["key"] == "clinic",
              clinic_business["industry"])
        check(
            "sohaga xos javoblar saqlandi",
            all(clinic_business["attributes"].get(k) == v for k, v in clinic_answers.items()),
            clinic_business["attributes"],
        )

        found = await crm.search_restaurants(limit=20)
        check("botda barcha sohalar chiqadi", len(found) >= 2, len(found))
        check("qidiruvda soha belgisi bor", all("industry_icon" in item for item in found),
              found[0])

        print("\n10) Begona restoranni tahrirlab bo'lmaydi")
        await crm.sync_user(telegram_id=900003, language="uz", full_name="Begona")
        try:
            await crm.update_restaurant(900003, restaurant_id, {"name": "O'g'irlangan"})
            check("begona egaga yopiq", False, "xato ko'tarilmadi")
        except CrmApiError as exc:
            check("begona egaga yopiq", exc.status_code == 404, exc.status_code)

        await crm.close()

    print("\n" + "=" * 62)
    print(f"  Muvaffaqiyatli: {passed}   Xato: {len(failed)}")
    for name in failed:
        print(f"    - {name}")
    print("=" * 62)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

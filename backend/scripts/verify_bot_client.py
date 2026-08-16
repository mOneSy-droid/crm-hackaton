"""`bot/crm_client.py` haqiqatan backend bilan tillashishini tekshiradi.

Klient imzoni o'zi hisoblaydi — bu skript uni jonli ASGI ilovaga ulab,
imzo, query-string va xato formatlari mos kelishini tasdiqlaydi.

    .venv\\Scripts\\python.exe scripts\\verify_bot_client.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR.parent / "bot"))

TMP_DIR = Path(tempfile.mkdtemp(prefix="crm_client_"))
BOT_SECRET = "client-verify-secret"

os.environ.update(
    ENV="dev",
    SECRET_KEY="client-verify-secret-key-at-least-32-characters",
    BOT_HMAC_SECRET=BOT_SECRET,
    DATABASE_URL=f"sqlite+aiosqlite:///{(TMP_DIR / 'client.db').as_posix()}",
    MEDIA_ROOT=str(TMP_DIR / "media"),
)

import httpx  # noqa: E402

from app.main import app  # noqa: E402
from crm_client import CrmApiError, CrmClient  # noqa: E402

passed, failed = 0, []


def check(name: str, condition: bool, extra: object = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  [ok]   {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


async def main() -> int:
    async with app.router.lifespan_context(app):
        crm = CrmClient("http://test", BOT_SECRET)
        # Klientni tarmoqqa emas, to'g'ridan-to'g'ri ilovaga ulaymiz
        await crm._client.aclose()
        crm._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30
        )

        print("\nKlient <-> backend")
        await crm.sync_user(700001, language="uz", full_name="Test Egasi", phone="+998900000001")
        check("sync_user", True)

        reg = await crm.register_restaurant(
            {
                "user": {"telegram_id": 700001, "full_name": "Test Egasi", "language": "uz"},
                "name": "Klient Kafe",
                "work_hours": "08:00-20:00",
                "category_key": "cafeteria",
            }
        )
        check("register_restaurant", reg["restaurant"]["id"] > 0, reg)
        restaurant_id = reg["restaurant"]["id"]

        link = await crm.login_link(700001)
        check("login_link", link["login_url"].startswith("http"), link)

        profile = await crm.get_profile(700001)
        check("get_profile (query imzolandi)", len(profile["restaurants"]) == 1, profile)

        updated = await crm.update_restaurant(700001, restaurant_id, {"address": "Yangi manzil"})
        check("update_restaurant", updated["address"] == "Yangi manzil", updated)

        found = await crm.search_restaurants("Klient")
        check("search_restaurants", len(found) == 1, found)

        await crm.sync_user(700002, language="ru", full_name="Mijoz")
        review = await crm.create_review(700002, restaurant_id, 5, "Ajoyib!")
        check("create_review", review["rating"] == 5, review)

        # 1x1 PNG
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
        url = await crm.upload_photo("photo.png", png)
        check("upload_photo", url.endswith(".png"), url)

        bot_draft = await crm.submit_bot_questionnaire(
            700001, restaurant_id, "Buyurtma qabul qilish", ["uz"], ["menyu"], "do'stona"
        )
        check("submit_bot_questionnaire", bot_draft["has_generated_config"], bot_draft)

        outbox = await crm.fetch_outbox()
        check("fetch_outbox", any(i["kind"] == "new_review" for i in outbox), outbox)
        await crm.ack_outbox([i["id"] for i in outbox])
        check("ack_outbox", await crm.fetch_outbox() == [])

        print("\nXatolar tushunarli qaytadimi")
        try:
            await crm.register_restaurant(
                {"user": {"telegram_id": 700001}, "name": "X", "work_hours": "9-23"}
            )
            check("noto'g'ri ish vaqti xato beradi", False, "xato ko'tarilmadi")
        except CrmApiError as exc:
            check("noto'g'ri ish vaqti xato beradi", exc.status_code == 422, exc)
            check("xabar foydalanuvchiga tayyor", "work_hours" in exc.message, exc.message)

        try:
            await crm.get_profile(999999)
            check("noma'lum foydalanuvchi", False, "xato ko'tarilmadi")
        except CrmApiError as exc:
            check("noma'lum foydalanuvchi", exc.status_code == 404, exc)

        await crm.close()

    print("\n" + "=" * 60)
    print(f"  Muvaffaqiyatli: {passed}   Xato: {len(failed)}")
    for name in failed:
        print(f"    - {name}")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

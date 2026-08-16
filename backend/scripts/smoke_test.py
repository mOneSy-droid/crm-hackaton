"""Uchdan-uchgacha tekshiruv: bot -> backend -> sayt oqimi.

Ishga tushirish (backend papkasidan):
    .venv\\Scripts\\python.exe scripts\\smoke_test.py

Vaqtinchalik SQLite bazasi yaratiladi va oxirida o'chiriladi — sizning
`restaurant_crm.db` faylingizga tegmaydi.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

TMP_DIR = Path(tempfile.mkdtemp(prefix="crm_smoke_"))
BOT_SECRET = "smoke-test-bot-secret"

os.environ.update(
    ENV="dev",
    SECRET_KEY="smoke-test-secret-key-at-least-32-characters-long",
    BOT_HMAC_SECRET=BOT_SECRET,
    DATABASE_URL=f"sqlite+aiosqlite:///{(TMP_DIR / 'smoke.db').as_posix()}",
    MEDIA_ROOT=str(TMP_DIR / "media"),
    FRONTEND_URL="http://localhost:5173",
    PUBLIC_BASE_URL="http://localhost:8000",
)

import httpx  # noqa: E402

from app.main import app  # noqa: E402

BASE = "http://test"
PREFIX = "/api/v1"

passed = 0
failed: list[str] = []


def check(name: str, condition: bool, extra: object = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  [ok]   {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def sign(method: str, path: str, body: bytes, nonce: str | None = None) -> dict[str, str]:
    """Bot xizmati aynan shu tarzda imzolashi kerak."""
    ts = str(int(time.time()))
    nonce = nonce or secrets.token_hex(12)
    base = f"{ts}.{nonce}.{method.upper()}.{path}.{hashlib.sha256(body).hexdigest()}"
    signature = hmac.new(BOT_SECRET.encode(), base.encode(), hashlib.sha256).hexdigest()
    return {"X-Timestamp": ts, "X-Nonce": nonce, "X-Signature": signature}


async def bot_post(client: httpx.AsyncClient, path: str, json_body: dict | None = None):
    full = f"{PREFIX}{path}"
    request = client.build_request("POST", BASE + full, json=json_body)
    request.headers.update(sign("POST", full, request.content))
    return await client.send(request)


async def bot_get(client: httpx.AsyncClient, path: str):
    full = f"{PREFIX}{path}"
    request = client.build_request("GET", BASE + full)
    request.headers.update(sign("GET", full, b""))
    return await client.send(request)


async def bot_patch(client: httpx.AsyncClient, path: str, json_body: dict):
    full = f"{PREFIX}{path}"
    request = client.build_request("PATCH", BASE + full, json=json_body)
    request.headers.update(sign("PATCH", full, request.content))
    return await client.send(request)


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    # ASGITransport lifespan'ni o'zi ishga tushirmaydi — jadval yaratish va
    # seed shu yerda bajarilishi uchun kontekstni qo'lda ochamiz.
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=transport, base_url=BASE, timeout=30
    ) as client:
        print("\n1) Xizmat ko'tarildimi")
        r = await client.get("/health")
        check("GET /health", r.status_code == 200, r.text)

        r = await client.get(f"{PREFIX}/categories")
        check("kategoriyalar seed bo'ldi", r.status_code == 200 and len(r.json()) >= 5, r.text)

        print("\n1b) Ko'p sohalilik")
        r = await client.get(f"{PREFIX}/industries")
        industries = r.json()
        keys = {item["key"] for item in industries}
        check("4 ta soha seed bo'ldi", {"restaurant", "market", "clinic", "gym"} <= keys, keys)
        check(
            "har bir sohada yorliqlar bor",
            all(i["item_label_uz"] and i["catalog_label_uz"] and i["entity_label_uz"]
                for i in industries),
            [(i["key"], i["item_label_uz"]) for i in industries],
        )
        market = next(i for i in industries if i["key"] == "market")
        restaurant_ind = next(i for i in industries if i["key"] == "restaurant")
        check("do'kon yorlig'i 'Mahsulot'", market["item_label_uz"] == "Mahsulot", market["item_label_uz"])
        check("restoran yorlig'i 'Taom'", restaurant_ind["item_label_uz"] == "Taom",
              restaurant_ind["item_label_uz"])
        check("sohaga xos savollar bor", len(market["fields"]) >= 2, market["fields"])
        check(
            "savol tavsifi to'liq",
            all({"key", "type", "label"} <= set(f) for f in market["fields"]),
            market["fields"],
        )
        check("yo'nalishlar sohaga bog'langan", len(market["categories"]) >= 5,
              len(market["categories"]))
        check(
            "yo'nalishlar sohalar orasida aralashmagan",
            {c["key"] for c in market["categories"]}.isdisjoint(
                {c["key"] for c in restaurant_ind["categories"]} - {"other"}
            ),
            [c["key"] for c in market["categories"]],
        )

        r = await client.get(f"{PREFIX}/categories", params={"industry_key": "clinic"})
        check("soha bo'yicha yo'nalish filtri", r.status_code == 200 and len(r.json()) >= 5, r.text)
        check("faqat klinika yo'nalishlari", all(
            c["key"] in {"general", "dental", "pediatric", "diagnostic", "laboratory",
                         "ophthalmology", "other"} for c in r.json()), r.json())

        r = await client.get(f"{PREFIX}/categories", params={"industry_key": "yoq-soha"})
        check("mavjud bo'lmagan soha 404", r.status_code == 404, r.status_code)

        print("\n2) Bot imzosi")
        r = await client.post(
            f"{PREFIX}/bot/users/sync", json={"telegram_id": 1, "language": "uz"}
        )
        check("imzosiz so'rov rad etiladi", r.status_code == 401, r.status_code)

        r = await bot_post(
            client,
            "/bot/users/sync",
            {"telegram_id": 555001, "full_name": "Ali Valiyev", "language": "uz",
             "phone": "+998901112233", "telegram_username": "ali"},
        )
        check("imzolangan so'rov o'tadi", r.status_code == 200, r.text)

        print("\n3) Restoran ro'yxatdan o'tishi")
        payload = {
            "user": {"telegram_id": 555001, "full_name": "Ali Valiyev", "language": "uz",
                     "phone": "+998901112233"},
            "name": "Osh Markazi",
            "description": "Milliy taomlar",
            "address": "Toshkent, Chilonzor 5",
            "latitude": 41.2995,
            "longitude": 69.2401,
            "work_hours": "09:00-23:00",
            "category_key": "national",
        }
        r = await bot_post(client, "/bot/restaurants/register", payload)
        check("POST /bot/restaurants/register", r.status_code == 201, r.text)
        reg = r.json()
        restaurant_id = reg["restaurant"]["id"]
        check("login generatsiya qilindi", bool(reg["username"]), reg)
        check("parol bir marta qaytarildi", bool(reg["password"]), "parol yo'q")
        check("kirish linki bor", reg["login_url"].startswith("http"), reg["login_url"])
        check("kategoriya bog'landi", reg["restaurant"]["category"] is not None, reg["restaurant"])

        bad_hours = dict(payload, name="Vaqti Xato", work_hours="9-23")
        r = await bot_post(client, "/bot/restaurants/register", bad_hours)
        check("noto'g'ri ish vaqti rad etiladi", r.status_code == 422, r.status_code)
        check("xato tushunarli qaytadi", "problems" in r.json(), r.text)

        r = await bot_post(client, "/bot/restaurants/register", payload)
        check("takroriy tasdiqlash dublikat yaratmaydi", r.json().get("already_registered") is True, r.text)
        check("takrorda parol qayta yuborilmaydi", r.json().get("password") is None, r.text)

        print("\n4) Botdagi link orqali saytga kirish")
        token = reg["login_url"].split("token=")[1].split("&")[0]
        r = await client.post(f"{PREFIX}/auth/telegram/exchange", json={"token": token})
        check("POST /auth/telegram/exchange", r.status_code == 200, r.text)
        tokens = r.json()
        auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        r = await client.post(f"{PREFIX}/auth/telegram/exchange", json={"token": token})
        check("token bir martalik", r.status_code == 401, r.status_code)

        r = await client.get(f"{PREFIX}/auth/me", headers=auth_headers)
        me = r.json()
        check("GET /auth/me", r.status_code == 200 and me["role"] == "owner", r.text)
        check("telefon niqoblangan", me["phone_masked"] and "*" in me["phone_masked"], me)
        check("to'liq telefon qaytmaydi", "+998901112233" not in r.text, r.text)

        print("\n5) Login/parol bilan kirish")
        r = await client.post(
            f"{PREFIX}/auth/login",
            json={"username": reg["username"], "password": reg["password"]},
        )
        check("POST /auth/login", r.status_code == 200, r.text)
        r = await client.post(
            f"{PREFIX}/auth/login", json={"username": reg["username"], "password": "xato-parol"}
        )
        check("noto'g'ri parol rad etiladi", r.status_code == 401, r.status_code)

        print("\n6) Sharh qoldirish va reyting")
        await bot_post(client, "/bot/users/sync", {"telegram_id": 555002, "full_name": "Mijoz", "language": "ru"})
        for rating in (5, 4):
            r = await bot_post(
                client,
                "/bot/reviews",
                {"telegram_id": 555002, "restaurant_id": restaurant_id, "rating": rating,
                 "text": f"Juda yaxshi ({rating})"},
            )
            check(f"sharh {rating}* qabul qilindi", r.status_code == 201, r.text)

        r = await bot_post(
            client,
            "/bot/reviews",
            {"telegram_id": 555002, "restaurant_id": restaurant_id, "rating": 9},
        )
        check("1-5 dan tashqari reyting rad etiladi", r.status_code == 422, r.status_code)

        r = await client.get(f"{PREFIX}/restaurants/{restaurant_id}")
        check("reyting qayta hisoblandi", r.json()["rating_avg"] == 4.5, r.json())
        check("sharhlar soni to'g'ri", r.json()["rating_count"] == 2, r.json())

        r = await client.get(f"{PREFIX}/reviews", params={"restaurant_id": restaurant_id})
        check("GET /reviews ochiq ishlaydi", r.status_code == 200 and r.json()["total"] == 2, r.text)
        review_id = r.json()["items"][0]["id"]

        print("\n7) Moderatsiya va javob")
        r = await client.patch(
            f"{PREFIX}/reviews/{review_id}/moderate",
            json={"status": "rejected", "moderation_note": "spam"},
            headers=auth_headers,
        )
        check("sharhni rad etish", r.status_code == 200, r.text)
        r = await client.get(f"{PREFIX}/restaurants/{restaurant_id}")
        check("rad etilgan sharh reytingdan chiqdi", r.json()["rating_count"] == 1, r.json())

        r = await client.post(
            f"{PREFIX}/reviews/{review_id}/reply",
            json={"text": "Fikringiz uchun rahmat!"},
            headers=auth_headers,
        )
        check("sharhga javob yozish", r.status_code == 200, r.text)

        print("\n8) Egalik tekshiruvi")
        r = await bot_post(
            client,
            "/bot/restaurants/register",
            {"user": {"telegram_id": 555003, "full_name": "Begona", "language": "uz"},
             "name": "Begona Kafe"},
        )
        other = r.json()
        other_token = other["login_url"].split("token=")[1].split("&")[0]
        r = await client.post(f"{PREFIX}/auth/telegram/exchange", json={"token": other_token})
        other_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.patch(
            f"{PREFIX}/restaurants/{restaurant_id}",
            json={"name": "O'g'irlangan"},
            headers=other_headers,
        )
        check("begona restoranni tahrirlab bo'lmaydi", r.status_code == 404, r.status_code)

        r = await bot_patch(
            client, f"/bot/restaurants/{restaurant_id}?telegram_id=555003", {"name": "O'g'irlangan"}
        )
        check("botdan ham begona restoran yopiq", r.status_code == 404, r.status_code)

        print("\n9) Profilni bot orqali tahrirlash")
        r = await bot_get(client, "/bot/profile?telegram_id=555001")
        check("GET /bot/profile", r.status_code == 200 and len(r.json()["restaurants"]) == 1, r.text)

        r = await bot_patch(
            client,
            f"/bot/restaurants/{restaurant_id}?telegram_id=555001",
            {"work_hours": "10:00-22:00", "description": "Yangilangan tavsif"},
        )
        check("PATCH /bot/restaurants/{id}", r.status_code == 200, r.text)
        check("ish vaqti yangilandi", r.json()["work_hours"] == "10:00-22:00", r.json())

        print("\n10) Kabinet statistikasi")
        r = await client.get(f"{PREFIX}/restaurants/{restaurant_id}/stats", headers=auth_headers)
        check("GET /restaurants/{id}/stats", r.status_code == 200, r.text)
        check("yulduzlar taqsimoti to'liq", len(r.json()["rating_breakdown"]) == 5, r.json())

        print("\n11) BotBuilder")
        r = await client.post(
            f"{PREFIX}/restaurants/{restaurant_id}/bots/questionnaire",
            json={"purpose": "Buyurtma qabul qilish", "languages": ["uz", "ru"],
                  "features": ["menyu", "bron qilish"], "tone": "do'stona"},
            headers=auth_headers,
        )
        check("anketa saqlandi", r.status_code == 200, r.text)
        bot_id = r.json()["id"]
        check("konfiguratsiya generatsiya qilindi", r.json()["has_generated_config"], r.json())

        r = await client.get(
            f"{PREFIX}/restaurants/{restaurant_id}/bots/{bot_id}/config", headers=auth_headers
        )
        check("konfiguratsiyani ko'rish", r.status_code == 200 and "welcome" in r.json(), r.text)
        check("konfiguratsiyada token yo'q", "token" not in r.text.lower(), r.text[:200])

        r = await client.post(
            f"{PREFIX}/restaurants/{restaurant_id}/bots/{bot_id}/token",
            json={"token": "qisqa"},
            headers=auth_headers,
        )
        check("yaroqsiz token formati rad etiladi", r.status_code == 422, r.status_code)

        print("\n12) Bildirishnoma navbati")
        r = await bot_get(client, "/bot/outbox?limit=50")
        check("GET /bot/outbox", r.status_code == 200, r.text)
        kinds = {item["kind"] for item in r.json()}
        check("yangi sharh bildirishnomasi bor", "new_review" in kinds, kinds)
        ids = [item["id"] for item in r.json()]
        r = await bot_post(client, "/bot/outbox/ack", {"ids": ids})
        check("POST /bot/outbox/ack", r.status_code == 200, r.text)
        r = await bot_get(client, "/bot/outbox")
        check("tasdiqlangan xabarlar qaytmaydi", r.json() == [], r.text)

        print("\n13) Qidiruv va filtrlar")
        r = await client.get(f"{PREFIX}/restaurants", params={"q": "Osh"})
        check("nom bo'yicha qidiruv", r.json()["total"] == 1, r.json())
        r = await client.get(f"{PREFIX}/restaurants", params={"category_key": "national"})
        check("kategoriya bo'yicha filtr", r.json()["total"] == 1, r.json())
        r = await client.get(f"{PREFIX}/restaurants", params={"min_rating": 4.5})
        check("reyting bo'yicha filtr", r.json()["total"] == 1, r.json())
        r = await bot_get(client, "/bot/restaurants/search?q=Osh")
        check("botdan restoran qidirish", r.status_code == 200 and len(r.json()) == 1, r.text)

        print("\n13b) Boshqa sohada biznes ochish")
        market_payload = {
            "user": {"telegram_id": 555010, "full_name": "Do'kon Egasi", "language": "uz"},
            "name": "Mega Market",
            "industry_key": "market",
            "category_key": "grocery",
            "address": "Toshkent, Yakkasaroy",
            "work_hours": "08:00-22:00",
            "attributes": {"delivery": "Bor", "min_order": "50000", "payment": "Ikkalasi"},
        }
        r = await bot_post(client, "/bot/restaurants/register", market_payload)
        check("do'kon ro'yxatdan o'tdi", r.status_code == 201, r.text)
        market_shop = r.json()["restaurant"]
        market_id = market_shop["id"]
        check("sohasi do'kon", market_shop["industry"]["key"] == "market", market_shop["industry"])
        check("soha yorlig'i javobda", market_shop["industry"]["item_label_uz"] == "Mahsulot",
              market_shop["industry"])
        check("yo'nalish do'konnikidan", market_shop["category"]["key"] == "grocery",
              market_shop["category"])
        check("sohaga xos maydonlar saqlandi",
              market_shop["attributes"].get("min_order") == "50000", market_shop["attributes"])

        r = await bot_post(
            client,
            "/bot/restaurants/register",
            {"user": {"telegram_id": 555011, "language": "uz"}, "name": "Soxta Soha",
             "industry_key": "yoq-bunday-soha"},
        )
        check("noto'g'ri soha rad etiladi", r.status_code >= 400, r.status_code)

        r = await client.get(f"{PREFIX}/restaurants", params={"industry_key": "market"})
        check("soha bo'yicha filtr", r.json()["total"] == 1, r.json()["total"])
        check("filtrda faqat do'kon", r.json()["items"][0]["id"] == market_id, r.json()["items"])

        r = await client.get(f"{PREFIX}/restaurants", params={"industry_key": "restaurant"})
        check("restoranlar alohida ro'yxatda", all(
            item["industry"]["key"] == "restaurant" for item in r.json()["items"]), r.json())

        # Do'konga restoran yo'nalishini biriktirib bo'lmasligi kerak
        restaurant_category_id = restaurant_ind["categories"][0]["id"]
        r = await bot_patch(
            client,
            f"/bot/restaurants/{market_id}?telegram_id=555010",
            {"category_id": restaurant_category_id},
        )
        check("begona sohaning yo'nalishi rad etiladi", r.status_code == 422, r.status_code)

        # Qisman yangilash qolgan maydonlarni o'chirmasligi kerak
        r = await bot_patch(
            client,
            f"/bot/restaurants/{market_id}?telegram_id=555010",
            {"attributes": {"delivery": "Yo'q"}},
        )
        check("maydon yangilandi", r.json()["attributes"].get("delivery") == "Yo'q",
              r.json()["attributes"])
        check("qolgan maydonlar saqlanib qoldi",
              r.json()["attributes"].get("min_order") == "50000", r.json()["attributes"])

        r = await bot_get(client, "/bot/restaurants/search?industry_key=market")
        check("botda soha bo'yicha qidiruv", len(r.json()) == 1, r.json())
        check("qidiruvda soha belgisi", r.json()[0]["industry_icon"] == "🛒", r.json()[0])

        print("\n14) Replay himoyasi")
        full = f"{PREFIX}/bot/users/sync"
        body = b'{"telegram_id":555004,"language":"uz"}'

        # Ushlab olingan so'rovni aynan qayta yuborish — bloklanishi kerak
        headers = sign("POST", full, body) | {"content-type": "application/json"}
        r1 = await client.post(full, content=body, headers=headers)
        r2 = await client.post(full, content=body, headers=headers)
        check(
            "ushlangan so'rovni qayta yuborib bo'lmaydi",
            r1.status_code == 200 and r2.status_code == 409,
            f"{r1.status_code}/{r2.status_code}",
        )

        # Bir xil mazmunli, lekin yangi nonce bilan so'rov — o'tishi kerak
        # (bot outbox'ni tinimsiz pollaydi, bloklanmasin)
        r3 = await client.post(
            full, content=body, headers=sign("POST", full, body) | {"content-type": "application/json"}
        )
        check("yangi nonce bilan qayta yuborish ishlaydi", r3.status_code == 200, r3.status_code)

        # Nonce'siz so'rov rad etiladi
        no_nonce = sign("POST", full, body)
        del no_nonce["X-Nonce"]
        r4 = await client.post(
            full, content=body, headers=no_nonce | {"content-type": "application/json"}
        )
        check("nonce'siz so'rov rad etiladi", r4.status_code == 401, r4.status_code)

        # Query'ni imzodan keyin o'zgartirish — imzo buziladi
        signed = f"{PREFIX}/bot/profile?telegram_id=555001"
        tampered_headers = sign("GET", signed, b"")
        r5 = await client.get(f"{PREFIX}/bot/profile?telegram_id=555003", headers=tampered_headers)
        check("query'ni almashtirish aniqlanadi", r5.status_code == 401, r5.status_code)

    print("\n" + "=" * 60)
    print(f"  Muvaffaqiyatli: {passed}   Xato: {len(failed)}")
    if failed:
        for name in failed:
            print(f"    - {name}")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)

"""Demo uchun namunaviy restoranlar va sharhlar qo'shadi.

Ishlab turgan backendga bot nomidan (HMAC imzo bilan) murojaat qiladi —
ya'ni Telegram botdan kelgan ma'lumot bilan bir xil yo'ldan o'tadi.

    .venv\\Scripts\\python.exe scripts\\seed_demo.py [http://localhost:8000]

Namoyish oldidan bir marta ishga tushiring. Bir xil nomdagi restoran ikkinchi
marta yaratilmaydi, shuning uchun qayta chaqirish xavfsiz.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("API_URL", "http://localhost:8000")).rstrip("/")
PREFIX = "/api/v1"
SECRET = settings.BOT_HMAC_SECRET.encode()

DEMO = [
    {
        "telegram_id": 100004,
        "owner": "Nilufar Rasulova",
        "name": "Mega Market",
        "industry_key": "market",
        "category_key": "grocery",
        "description": "Oziq-ovqat va maishiy mahsulotlar. Har kuni yangi mahsulot.",
        "address": "Toshkent, Sergeli, Yangi Sergeli 4",
        "latitude": 41.2201,
        "longitude": 69.2154,
        "work_hours": "08:00-23:00",
        "phone": "+998901234501",
        "attributes": {"delivery": "Bor", "min_order": "50000", "payment": "Ikkalasi"},
        "menu": [],
        "reviews": [
            (200010, "Shahnoza", 5, "Narxlari arzon, yetkazib berish tez."),
            (200011, "Rustam", 4, "Tanlov keng, lekin kassada navbat bo'ladi."),
        ],
    },
    {
        "telegram_id": 100005,
        "owner": "Doktor Umarov",
        "name": "Salomat Klinika",
        "industry_key": "clinic",
        "category_key": "dental",
        "description": "Stomatologiya va umumiy tekshiruv. Zamonaviy uskunalar.",
        "address": "Toshkent, Mirobod, Shota Rustaveli 22",
        "latitude": 41.2915,
        "longitude": 69.2622,
        "work_hours": "09:00-19:00",
        "phone": "+998901234502",
        "attributes": {"appointment": "Oldindan yozilish", "emergency": "Yo'q",
                       "license": "LIC-2024-8891"},
        "menu": [],
        "reviews": [
            (200012, "Gulnora", 5, "Shifokor tushuntirib ishladi, og'riq sezmadim."),
        ],
    },
    {
        "telegram_id": 100006,
        "owner": "Sardor Nazarov",
        "name": "PowerFit",
        "industry_key": "gym",
        "category_key": "fitness",
        "description": "Zamonaviy fitnes zali, shaxsiy murabbiy va guruh mashg'ulotlari.",
        "address": "Toshkent, Chilonzor, Qatortol 60",
        "latitude": 41.2762,
        "longitude": 69.2043,
        "work_hours": "06:00-23:00",
        "phone": "+998901234503",
        "attributes": {"trial": "Bor", "monthly_fee": "450000", "age_group": "16+"},
        "menu": [],
        "reviews": [
            (200013, "Javohir", 5, "Uskunalar yangi, murabbiylar professional."),
            (200014, "Dilshod", 4, "Kechqurun gavjum bo'ladi."),
        ],
    },
    {
        "telegram_id": 100001,
        "owner": "Alisher Karimov",
        "name": "Osh Markazi",
        "industry_key": "restaurant",
        "description": "An'anaviy o'zbek oshxonasi. Har kuni yangi pishirilgan palov va somsa.",
        "address": "Toshkent, Chilonzor tumani, Bunyodkor 12",
        "latitude": 41.2856,
        "longitude": 69.2034,
        "work_hours": "09:00-23:00",
        "category_key": "national",
        "phone": "+998901112233",
        "menu": [
            ("Toy palov", "Qo'y go'shti, sabzi va guruchdan", 45000, "Asosiy taomlar"),
            ("Somsa", "Tandirda pishirilgan, go'shtli", 12000, "Asosiy taomlar"),
            ("Achichuk salat", "Pomidor, piyoz, ko'katlar", 15000, "Salatlar"),
            ("Ko'k choy", "Bir choynak", 8000, "Ichimliklar"),
        ],
        "reviews": [
            (200001, "Dilnoza", 5, "Palovi zo'r, xizmat tez. Oilaviy kelish uchun juda qulay."),
            (200002, "Bekzod", 4, "Taomlar mazali, lekin tushlik payti navbat bo'ladi."),
            (200003, "Kamola", 5, "Somsasi issiq va yumshoq. Narxi ham arzon."),
        ],
    },
    {
        "telegram_id": 100002,
        "owner": "Nodira Yusupova",
        "name": "Cafe Bahor",
        "description": "Yevropa va osiyo taomlari, tinch muhit, bepul Wi-Fi.",
        "address": "Toshkent, Mirzo Ulug'bek, Buyuk Ipak Yo'li 45",
        "latitude": 41.3251,
        "longitude": 69.3345,
        "work_hours": "08:00-22:00",
        "category_key": "european",
        "phone": "+998907778899",
        "menu": [
            ("Sezar salati", "Tovuq va parmezan bilan", 38000, "Salatlar"),
            ("Karbonara", "Klassik italyan retsepti", 52000, "Asosiy taomlar"),
            ("Cheesecake", "New York uslubida", 28000, "Shirinliklar"),
            ("Kapuchino", "Ikki porsiya espresso", 18000, "Ichimliklar"),
        ],
        "reviews": [
            (200004, "Sardor", 5, "Qahvasi ajoyib, ishlash uchun ham qulay joy."),
            (200005, "Malika", 4, "Cheesecake juda yaxshi. Musiqa biroz baland."),
        ],
    },
    {
        "telegram_id": 100003,
        "owner": "Jasur Tursunov",
        "name": "Burger Time",
        "description": "Tez va mazali fast-food. Yetkazib berish 30 daqiqada.",
        "address": "Toshkent, Yunusobod, Amir Temur 108",
        "latitude": 41.3489,
        "longitude": 69.2871,
        "work_hours": "10:00-02:00",
        "category_key": "fast_food",
        "phone": "+998933334455",
        "menu": [
            ("Double Cheese", "Ikki qavat go'sht va pishloq", 42000, "Burgerlar"),
            ("Chicken Burger", "Qarsildoq tovuq filesi", 35000, "Burgerlar"),
            ("Fri kartoshka", "Katta porsiya", 15000, "Garnir"),
        ],
        "reviews": [
            (200006, "Aziz", 4, "Burgeri katta va to'ydiradi. Yetkazish tez."),
            (200007, "Nigora", 3, "Mazali, lekin kechqurun kutish uzoq."),
        ],
    },
]


def sign(method: str, path_with_query: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(12)
    base = f"{timestamp}.{nonce}.{method.upper()}.{path_with_query}.{hashlib.sha256(body).hexdigest()}"
    signature = hmac.new(SECRET, base.encode(), hashlib.sha256).hexdigest()
    return {"X-Timestamp": timestamp, "X-Nonce": nonce, "X-Signature": signature}


async def call(client: httpx.AsyncClient, method: str, path: str, json_body: dict | None = None):
    request = client.build_request(method, PREFIX + path, json=json_body)
    body = request.read()
    request.headers.update(sign(method, request.url.raw_path.decode(), body))
    response = await client.send(request)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:200]}")
    return response.json()


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        try:
            health = await client.get("/health")
            health.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            print(f"Backend {BASE_URL} da javob bermayapti: {exc}")
            print("Avval backendni ishga tushiring.")
            return 1

        print(f"Backend: {BASE_URL}\n")

        for item in DEMO:
            registration = await call(
                client,
                "POST",
                "/bot/restaurants/register",
                {
                    "user": {
                        "telegram_id": item["telegram_id"],
                        "full_name": item["owner"],
                        "language": "uz",
                        "phone": item["phone"],
                    },
                    "name": item["name"],
                    "industry_key": item.get("industry_key", "restaurant"),
                    "description": item["description"],
                    "address": item["address"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "work_hours": item["work_hours"],
                    "phone": item["phone"],
                    "category_key": item["category_key"],
                    "attributes": item.get("attributes", {}),
                },
            )
            restaurant = registration["restaurant"]
            existed = registration.get("already_registered")
            icon = restaurant["industry"]["icon"]
            print(f"{'=' if existed else '+'} {icon} {restaurant['name']} (id {restaurant['id']})")
            if registration.get("password"):
                print(f"    login: {registration['username']}  parol: {registration['password']}")

            for telegram_id, name, rating, text in item["reviews"]:
                await call(
                    client,
                    "POST",
                    "/bot/users/sync",
                    {"telegram_id": telegram_id, "full_name": name, "language": "uz"},
                )
                await call(
                    client,
                    "POST",
                    "/bot/reviews",
                    {
                        "telegram_id": telegram_id,
                        "restaurant_id": restaurant["id"],
                        "rating": rating,
                        "text": text,
                    },
                )
            print(f"    {len(item['reviews'])} ta sharh qo'shildi")

        print("\nTayyor. Endi saytni oching va ro'yxatni ko'ring.")
        print("Menyu qo'shish uchun kabinetga kiring — login/parol yuqorida.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

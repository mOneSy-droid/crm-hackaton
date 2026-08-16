# Restaurant CRM — Backend

FastAPI backend: restoranlar Telegram bot orqali ro'yxatdan o'tadi, mijozlar sharh qoldiradi,
egalar saytdagi kabinetdan profil, menyu, sharhlar va shaxsiy botlarini boshqaradi.

## Tez ishga tushirish

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Ochiladi: <http://localhost:8000/docs> — interaktiv Swagger, hamma endpoint shu yerda.

Jadvallar va kategoriyalar birinchi ishga tushishda avtomatik yaratiladi. Migratsiya kerak emas.

Admin yaratish:

```bash
python scripts/create_admin.py admin ParolKamida8Belgi
```

## Tekshirish

```bash
python scripts/smoke_test.py
```

Butun oqimni uchdan-uchgacha yuradi (53 tekshiruv): bot imzosi, ro'yxatdan o'tish, avtomatik
kirish linki, sharh va reyting, moderatsiya, egalik chegaralari, BotBuilder, bildirishnoma
navbati, replay himoyasi. Vaqtinchalik SQLite bazasida ishlaydi, sizning bazangizga tegmaydi.

```bash
python scripts/verify_bot_client.py
```

`bot/crm_client.py` backend bilan to'g'ri tillashishini tasdiqlaydi (14 tekshiruv).

## Ko'p sohalilik

Tizim bitta biznes modeli bilan ishlaydi — **soha bu kod emas, ma'lumot.**
Hozir 4 ta soha bor: restoran 🍽, do'kon 🛒, klinika 🏥, sport va ta'lim 🏋.

```
Industry (soha)
  ├─ yorliqlar: "Taom" / "Mahsulot" / "Xizmat"  (uz/ru/en)
  ├─ field_schema: shu sohaga xos savollar (JSON)
  └─ Category (yo'nalishlar: milliy/fast-food yoki oziq-ovqat/kiyim)

Restaurant (biznes)
  ├─ industry_id
  └─ attributes: sohaga xos javoblar (JSON)
```

Bot ham, sayt ham yorliqni `GET /api/v1/industries` dan oladi. Shuning uchun
restoran egasiga "Taom qo'shish" deb ko'rinadigan tugma klinikaga
"Xizmat qo'shish" bo'ladi — kodda birorta `if` yozilmagan.

### Yangi soha qo'shish

[`app/services/seed.py`](app/services/seed.py) dagi `INDUSTRIES` ro'yxatiga
bitta yozuv qo'shing va backendni qayta ishga tushiring. Kod o'zgartirilmaydi:

```python
{
    "key": "beauty",
    "icon": "💇",
    "name": _label("Go'zallik salonlari", "Салоны красоты", "Beauty salons"),
    "entity": _label("salon", "салон", "salon"),
    "item": _label("Xizmat", "Услуга", "Service"),
    "catalog": _label("Xizmatlar", "Услуги", "Services"),
    "fields": [
        {"key": "booking", "type": "choice", "choices": ["Bor", "Yo'q"],
         "label": _label("Oldindan yozilish bormi?", "Есть запись?", "Booking?")},
    ],
    "categories": [("barber", "Sartaroshxona", "Барбершоп", "Barbershop")],
}
```

Seed idempotent — matnni tuzatib qayta ishga tushirsangiz mavjud yozuvlar
yangilanadi, dublikat yaratilmaydi.

> `key` bir marta qo'yilgach o'zgartirmang: bizneslar shunga bog'langan.
> Yo'nalish kalitlari soha ichida yagona, shuning uchun turli sohalarda
> `other` kabi kalitlar takrorlanishi mumkin.

## Arxitektura

```
app/
├── core/          config, security (JWT/HMAC/Fernet), logging (maxfiy ma'lumot filtri)
├── db/            SQLAlchemy engine, sessiya, Base
├── models/        barcha jadvallar bitta faylda — o'qish oson
├── schemas/       pydantic: so'rov/javob shakllari va validatsiya
├── services/      biznes-logika (ro'yxatdan o'tish, reyting, botlar, AI, storage)
└── api/
    ├── middleware.py   bot so'rovlari uchun HMAC tekshiruvi
    ├── deps.py         JWT, egalik tekshiruvi
    └── v1/             endpointlar
```

Ikkita mustaqil kirish yo'li:

| Kim | Yo'l | Autentifikatsiya |
|---|---|---|
| Sayt (React) | `/api/v1/*` | `Authorization: Bearer <JWT>` |
| Telegram bot | `/api/v1/bot/*` | HMAC-SHA256 imzo (`X-Timestamp`, `X-Nonce`, `X-Signature`) |

Bot hech qachon JWT ishlatmaydi, sayt hech qachon `/bot/*` ga kira olmaydi.

## Xavfsizlik

- **Parollar** — PBKDF2-HMAC-SHA256, 260k iteratsiya. Ochiq parol faqat ro'yxatdan o'tish
  javobida bir marta qaytariladi, keyin bazada faqat hash qoladi.
- **Bot tokenlari** — Fernet (AES-128-CBC + HMAC) bilan shifrlanadi. Ochiq token faqat
  `/bot/botbuilder/runners` orqali, faqat imzolangan so'rovda beriladi. Kabinet API'si
  tokenni hech qachon qaytarmaydi — faqat oxirgi 4 belgisi.
- **Telefon raqamlari** — API'da hech qachon to'liq qaytarilmaydi (`+9989****4567`).
  Log filtri raqam, bot tokeni va `Bearer ...` qatorlarini avtomatik o'chiradi.
- **Bot imzosi** — metod, to'liq yo'l *(query bilan birga)* va tana hash'i imzolanadi.
  ±5 daqiqalik vaqt oynasi + nonce takrorlanishini bloklash. Ushlab olingan so'rovni
  qayta yuborib bo'lmaydi, lekin botning o'zi bir xil so'rovni xohlagancha yubora oladi.
- **Egalik** — begona restoranga murojaat 403 emas, **404** qaytaradi: mavjudligini ham
  fosh qilmaslik uchun.
- **Bir martalik kirish linki** — 15 daqiqa yashaydi, bir marta ishlaydi, bazada faqat
  SHA-256 hash saqlanadi.
- **Fayl yuklash** — kengaytmaga emas, fayl imzosiga (magic bytes) qarab tekshiriladi.

## Railway'ga deploy

1. Railway'da yangi **Postgres** servis qo'shing — `DATABASE_URL` avtomatik ulanadi
   (`postgres://` prefiksi kod ichida asyncpg'ga o'giriladi).
2. Backend servisida **Root Directory** = `backend`.
3. Variables:

   | O'zgaruvchi | Qiymat |
   |---|---|
   | `ENV` | `prod` |
   | `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `BOT_HMAC_SECRET` | yana bitta tasodifiy qator — bot servisiga ham shu qiymat |
   | `TOKEN_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
   | `CORS_ORIGINS` | `https://<vercel-domeningiz>.vercel.app` |
   | `FRONTEND_URL` | `https://<vercel-domeningiz>.vercel.app` |
   | `PUBLIC_BASE_URL` | `https://<backend>.up.railway.app` |
   | `ANTHROPIC_API_KEY` | ixtiyoriy — BotBuilder AI uchun |

4. Rasm yuklamalari uchun `/app/media` ga **Volume** ulang. Aks holda har deployda
   yuklangan rasmlar yo'qoladi.

`TOKEN_ENCRYPTION_KEY` berilmasa `SECRET_KEY` dan hosil qilinadi — bu dev uchun qulay,
lekin productionda `SECRET_KEY` almashtirilsa saqlangan bot tokenlari o'qilmay qoladi.
Shuning uchun ikkalasini alohida qo'ying.

## Ma'lum cheklovlar

- Jadvallar `create_all` bilan yaratiladi (Alembic yo'q). Modelga yangi ustun qo'shsangiz
  mavjud bazada avtomatik paydo bo'lmaydi — hackaton davomida bazani o'chirib qayta
  yarating yoki ustunni qo'lda qo'shing.
- Nonce keshi xotirada — bir nechta instansiyaga ko'paytirilsa Redis kerak bo'ladi.
- Shaxsiy botlarni ishga tushiruvchi runner alohida servis: `/bot/botbuilder/runners`
  dan konfiguratsiyalarni olib, har bir botni alohida process qilib ko'taradi.

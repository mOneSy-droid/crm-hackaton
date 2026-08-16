# Restaurant CRM

Bizneslar uchun CRM: ro'yxatdan o'tish va sharh qoldirish Telegram bot orqali,
boshqaruv esa saytdagi kabinetdan.

Bitta tizim to'rt sohada ishlaydi — 🍽 restoran, 🛒 do'kon, 🏥 klinika,
🏋 sport va ta'lim. **Soha kodga yozilmagan, u ma'lumot:** yangi soha qo'shish
uchun bazaga bitta yozuv qo'shiladi, kod o'zgarmaydi. Batafsil:
[`backend/README.md`](backend/README.md#ko-sohalilik).

```
Hackaton/
├── frontend/   TanStack Start (React)  → Vercel
├── backend/    FastAPI + Postgres      → Railway
├── bot/        python-telegram-bot     → Railway (2 ta servis)
│   ├── main.py         asosiy bot
│   └── runner_main.py  mijozlarning shaxsiy botlari
└── docs/API.md API kontrakti
```

Bot: [@CrmHackaton_bot](https://t.me/CrmHackaton_bot)

**Asosiy farqimiz:** har bir mijoz o'ziga AI yasab bergan shaxsiy Telegram bot
oladi. Anketa to'ldiradi → @BotFather'dan token oladi → boti bir daqiqada
jonli ishlaydi. Kod yozilmaydi: bitta universal bot konfiguratsiya bilan
boshqariladi. Batafsil: [`bot/README.md`](bot/README.md).

Namoyish uchun namunaviy ma'lumot (to'rt sohada 6 ta biznes va sharhlar):

```bash
cd backend && .venv\Scripts\python.exe scripts\seed_demo.py
```

## Qaerdan boshlash

| Kim | Nima o'qiydi |
|---|---|
| Frontend | [`frontend/README.md`](frontend/README.md) + [`docs/API.md`](docs/API.md) 1-bo'lim |
| Bot | [`bot/README.md`](bot/README.md) + [`docs/API.md`](docs/API.md) 2-bo'lim |
| Backend | [`backend/README.md`](backend/README.md) |

## Uchalasini ishga tushirish

Har biri alohida terminalda. Tartib muhim: backend birinchi.

```bash
cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt && copy .env.example .env && uvicorn app.main:app --reload
```
```bash
cd bot && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt && copy .env.example .env && python main.py
```
```bash
cd frontend && npm install && copy .env.example .env && npm run dev
```

| Xizmat | Manzil |
|---|---|
| Sayt | <http://localhost:8080> |
| API hujjatlari | <http://localhost:8000/docs> |

Namoyish uchun namunaviy restoranlar va sharhlar:

```bash
cd backend && .venv\Scripts\python.exe scripts\seed_demo.py
```

## Ma'lumot oqimi

```
Telegram bot ──HMAC imzo──> /api/v1/bot/*  ┐
                                            ├─> FastAPI ─> Postgres
Sayt (React) ──JWT────────> /api/v1/*      ┘

Backend botga to'g'ridan-to'g'ri yozmaydi: bildirishnomalar navbatga
qo'yiladi, bot /bot/outbox dan olib yuboradi. Shu tufayli Telegram
tokeni faqat bot servisida qoladi.
```

Botdan saytga kirish: bot bir martalik token yasaydi va
`https://<sayt>/auth/telegram?token=...` linkini yuboradi. Sayt uni JWT'ga
almashtiradi — login/parol kiritish shart emas.

## Testlar

```bash
cd backend && .venv\Scripts\python.exe scripts\smoke_test.py
```
```bash
cd bot && .venv\Scripts\python.exe scripts\check_wiring.py
```
```bash
cd bot && .venv\Scripts\python.exe scripts\test_integration.py
```
```bash
cd bot && .venv\Scripts\python.exe scripts\test_runner.py
```
```bash
cd frontend && npx tsc --noEmit
```

Hech biriga Telegram tokeni yoki tashqi tarmoq kerak emas.

## Muhim sozlamalar

`BOT_HMAC_SECRET` backend va bot servislarida **aynan bir xil** bo'lishi shart.

Deploydan keyin backendda `CORS_ORIGINS` va `FRONTEND_URL` ni Vercel domeniga
o'zgartiring — aks holda sayt API'ga ulana olmaydi va botdagi kirish linki
noto'g'ri manzilga ishora qiladi.

`.env` fayllari `.gitignore` da — repoga hech qachon tushmaydi.

> Bitta bot tokeni bilan bir vaqtda faqat bitta process polling qila oladi.
> Ikkinchisini ishga tushirsangiz `Conflict: terminated by other getUpdates request`
> xatosi chiqadi. Railway'da `numReplicas` 1 bo'lib qolsin.

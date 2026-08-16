# Telegram bot

Bu papkada **ikkita mustaqil servis** bor:

| Servis | Fayl | Nima qiladi |
|---|---|---|
| Asosiy bot | `main.py` | @CrmHackaton_bot — ro'yxatdan o'tish, sharh, profil, BotBuilder |
| **Runner** | `runner_main.py` | Mijozlarning **shaxsiy botlarini** ko'taradi va boshqaradi |

Ikkalasi ham `crm_client.py` va `config.py` ni bo'lishadi, lekin alohida
process sifatida ishlaydi — biri yiqilsa ikkinchisi ishlayveradi.

Barcha ma'lumot backendda saqlanadi — botlar faqat interfeys.

## Ishga tushirish

```bash
cd bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env` da kamida ikkitasini to'ldiring:

```
TELEGRAM_BOT_TOKEN=<@BotFather bergan token>
BOT_HMAC_SECRET=<backenddagi qiymat bilan AYNAN bir xil>
```

Keyin backend ishlab turganiga ishonch hosil qiling va botni ishga tushiring:

```bash
python main.py
```

Bot ko'rinishini (nom, About, Description, botpic, buyruqlar) o'rnatish — bir marta:

```bash
python setup_profile.py
```

Shaxsiy botlar runnerini ishga tushirish (alohida terminalda):

```bash
python runner_main.py
```

Runnerga Telegram tokeni **kerak emas** — u har bir mijoz botining tokenini
backenddan shifrdan chiqarilgan holda oladi.

## Tekshirish

```bash
python scripts/check_wiring.py
```

Telegram tokeni kerak emas. Tekshiradi: uch tildagi matnlar to'liqmi, har bir
tugmaning `callback_data` si biror handlerga tushadimi (37 ta tugma), bazaga
ulanish. **Yangi tugma qo'shsangiz shuni ishga tushiring** — eski botdagi asosiy
nosozlik aynan "tugma bor, handler yo'q" edi.

```bash
python scripts/test_integration.py
```

Haqiqiy backendni ko'taradi va handlerlar yuboradigan aynan o'sha payloadlarni
jo'natadi (26 tekshiruv). Backend javobidagi maydon nomi o'zgarsa shu yerda ushlanadi.

```bash
python scripts/test_runner.py
```

Runner mantiqini tekshiradi (30 tekshiruv): botlarni ko'tarish/to'xtatish/qayta
yuklash, bitta bot yiqilganda qolganlari ishlashi, konfiguratsiya talqini va
backend zanjiri (anketa → runners → lead → egasiga bildirishnoma).
Telegram tokeni kerak emas.

## Tuzilma

```
bot/
├── main.py            asosiy bot
├── runner_main.py     shaxsiy botlar runneri
├── config.py          env sozlamalari (ikkala servis uchun)
├── crm_client.py      backend klienti (HMAC imzolash shu yerda)
├── i18n.py            uz / ru / en matnlar
├── keyboards.py       barcha klaviaturalar
├── storage.py         bot bazasi: til tanlovi + adminlar
├── outbox.py          backend bildirishnomalarini yetkazish
├── setup_profile.py   About / Description / botpic / buyruqlar
├── handlers/          asosiy botning oqimlari
│   ├── navigation.py   /start, /menu, /language, /help
│   ├── registration.py 7 bosqichli anketa
│   ├── reviews.py      sharh qoldirish
│   ├── profile.py      profilni tahrirlash
│   ├── botbuilder.py   shaxsiy bot yasash
│   └── admin.py        admin panel
└── tenant/            shaxsiy botlar
    ├── bot.py          konfiguratsiya bilan boshqariladigan universal bot
    └── supervisor.py   ko'tarish, kuzatish, qayta yuklash
```

## Shaxsiy botlar qanday ishlaydi

Mijoz uchun **kod yozilmaydi** — bitta `tenant/bot.py` hammasini yuritadi,
o'zgaradigani konfiguratsiya:

```
Egasi anketa to'ldiradi
      ↓
Backend (AI) JSON konfiguratsiya yasaydi: salomlashuv, tugmalar, savol oqimlari
      ↓
Egasi @BotFather tokenini beradi → backend uni shifrlab saqlaydi
      ↓
Runner har 30 soniyada GET /bot/botbuilder/runners qiladi
      ↓
Yangi bot ko'riladi → alohida asyncio vazifasida ishga tushadi
```

O'rnatilgan (built-in) tugmalar backend bilan ishlaydi:

| Tugma `id` | Nima qiladi |
|---|---|
| `menu` | Backenddan menyuni olib ko'rsatadi |
| `contact` | Manzil, ish vaqti, telefon + xarita nuqtasi |
| `review` | Reyting + matn → haqiqiy sharh sifatida backendga yoziladi |

Qolgan tugmalar `flows` dagi savol oqimini yuritadi (`ask_text`, `ask_phone`,
`ask_location`, `ask_choice`, `message`). Yig'ilgan javoblar
`POST /bot/tenant/lead` orqali backendga boradi va **restoran egasiga asosiy
bot orqali Telegramga yetkaziladi** — shaxsiy bot egasining chat ID'sini
bilishi shart emas.

Konfiguratsiya yoki token o'zgarsa `config_version` xeshi o'zgaradi va runner
o'sha botni qayta ko'taradi — qolganlariga tegmaydi.

### Nega alohida OS process emas

50 ta bot uchun 50 ta process ~2 GB xotira oladi. Bitta event loop'da ular
~150 MB da sig'adi. Izolyatsiya vazifa darajasida: har bir bot o'z xatosini
yutadi va ortib boruvchi kechikish bilan (5s → 300s) qayta ko'tariladi.
Haqiqiy process kerak bo'lsa `TenantRunner` ni `multiprocessing` ga o'tkazish
yetarli — interfeysi o'zgarmaydi.

## Yangi buyruq qo'shish

1. `handlers/` ichida handler yozing va `main.py` da ro'yxatdan o'tkazing
2. `setup_profile.py` dagi `COMMANDS` ga uch tilda qator qo'shing
3. `python scripts/check_wiring.py` — ulanganini tasdiqlang
4. `python setup_profile.py` — Telegram menyusini yangilang

Menyu tugmasi qo'shsangiz `keyboards.py` da tugmani, `main.py` da esa unga mos
`CallbackQueryHandler` ni qo'shing — `check_wiring.py` ikkalasi mos kelishini tekshiradi.

## Bildirishnomalar qanday ishlaydi

Backend Telegram'ga to'g'ridan-to'g'ri yozmaydi — xabarni navbatga qo'yadi,
bot esa har 5 soniyada `GET /bot/outbox` orqali olib, o'z tokeni bilan yuboradi.
Shu tufayli Telegram tokeni faqat shu servisda qoladi.

Yetkazilgani `ack` qilinmagan xabar keyingi pollashda yana keladi — xabar
yo'qolmaydi. Foydalanuvchi botni bloklagan bo'lsa xabar tashlab yuboriladi.

## Railway'ga deploy

Backend bilan bir xil Postgres'dan foydalanish mumkin — bot faqat `bot_users`
jadvalini yaratadi, backend jadvallariga tegmaydi.

| O'zgaruvchi | Qiymat |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather tokeni |
| `CRM_API_URL` | `https://<backend>.up.railway.app` |
| `BOT_HMAC_SECRET` | backenddagi qiymat bilan bir xil |
| `BOT_DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `BOT_SUPER_ADMINS` | o'z Telegram ID'ingiz (@userinfobot beradi) |

Servis **Root Directory** = `bot`. Bot polling rejimida ishlaydi, domen kerak emas.

**Runner uchun ikkinchi servis** — o'sha `bot` papkasidan:

- Root Directory: `bot`
- Config-as-code path: `railway.runner.json` (u `Dockerfile.runner` ga ishora qiladi)
- O'zgaruvchilar: `CRM_API_URL` va `BOT_HMAC_SECRET` (`TELEGRAM_BOT_TOKEN` **kerak emas**)

> Bitta bot tokeni bilan bir vaqtda faqat bitta process polling qila oladi.
> Railway'da `numReplicas` ni 1 dan oshirmang — aks holda `Conflict` xatosi chiqadi.
> Bu runner uchun ham amal qiladi: ikkita runner bir xil mijoz botlarini
> ko'tarsa, ularning hammasi `Conflict` beradi.

## Xavfsizlik

- @BotFather tokeni backendga yuboriladi va u yerda Fernet bilan shifrlanadi.
  Foydalanuvchi tokenni yozgan xabar **darhol o'chiriladi**.
- Log filtri bot tokeni va telefon raqamini avtomatik yashiradi.
- Admin faqat `BOT_SUPER_ADMINS` orqali yoki mavjud admin tomonidan qo'shiladi.
  (Eski kodda bot tokeni yuborgan har qanday odam avtomatik admin bo'lardi.)
- Telefon raqami faqat «Kontaktni yuborish» tugmasi orqali olinadi.

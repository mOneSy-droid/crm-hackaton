# Bizneslar uchun CRM — loyiha tavsifi

## Bir gapda

O'zbekistondagi kichik bizneslar Telegram bot orqali 2 daqiqada ro'yxatdan
o'tadi, mijozlar sharh qoldiradi, egasi esa saytdagi kabinetdan boshqaradi —
va har bir biznes o'ziga **AI yasab bergan shaxsiy Telegram bot** oladi.

## Muammo

Kichik biznes uchun CRM olish uchta to'siqqa uriladi:

1. **Ro'yxatdan o'tish og'ir.** SMS tasdiqlash uchun Eskiz kabi xizmatga pul
   to'lash, shartnoma tuzish kerak. Startap uchun bu birinchi kundanoq to'siq.
2. **Mijoz bilan aloqa yo'q.** Restoran sharh yig'ishni xohlaydi, lekin mijoz
   ilova yuklab olmaydi. Uzbekistonda hamma Telegramda — CRM esa Telegramda emas.
3. **Har bir soha o'ziga xos.** Restoranga menyu kerak, do'konga katalog,
   klinikaga qabul jadvali. Tayyor CRM'lar bitta sohaga qotib qolgan.

## Yechim

### 1. Telegram — bu identifikatsiya

SMS yo'q. Ro'yxatdan o'tish botda: til tanlanadi, telefon raqami Telegramning
«Kontaktni yuborish» tugmasi orqali olinadi (qo'lda yozib bo'lmaydi — bu ham
qulay, ham ishonchli), joylashuv xarita orqali yuboriladi.

Anketa tugagach tizim login/parol generatsiya qiladi **va** bir martalik
tokenli link beradi. Foydalanuvchi tugmani bosadi — parol kiritmasdan saytdagi
kabinetiga tushadi. Token 15 daqiqa yashaydi va bir marta ishlaydi.

### 2. Har bir mijozga o'z boti — AI yasaydi

Bu bizning asosiy farqimiz. Biznes egasi 4 ta savolga javob beradi:

- Bot nima uchun kerak?
- Qaysi tillarda ishlasin?
- Qanday funksiyalar kerak?
- Muloqot uslubi qanday?

Claude API javoblar asosida botning butun logikasini yasaydi: salomlashuv
matni, menyu tugmalari, savol-javob oqimlari — uch tilda. Egasi @BotFather'dan
token oladi, botga tashlaydi, va **bir daqiqada o'z boti jonli ishlaydi.**

Muhimi: har bir mijoz uchun kod yozilmaydi. Bitta universal bot
konfiguratsiya bilan boshqariladi. Shaxsiy bot mijozdan buyurtma yoki bron
qabul qilsa, u egasining Telegramiga yetib boradi.

### 3. Bitta tizim — to'rt soha

Soha kodga yozilmagan, u **ma'lumot**. Har bir soha o'z atamalarini olib yuradi:

| | 🍽 Restoran | 🛒 Do'kon | 🏥 Klinika | 🏋 Sport va ta'lim |
|---|---|---|---|---|
| Katalog | Menyu | Katalog | Xizmatlar | Mashg'ulotlar |
| Bitta yozuv | Taom | Mahsulot | Xizmat | Mashg'ulot |
| O'z savollari | yetkazib berish, joy soni | min. buyurtma, to'lov turi | qabul turi, litsenziya | sinov darsi, oylik to'lov |

Restoran egasiga «Taom qo'shish» deb ko'rinadigan tugma klinikaga «Xizmat
qo'shish» bo'ladi. Yangi soha qo'shish uchun bazaga bitta yozuv qo'shiladi —
kod o'zgarmaydi.

## Nima ishlaydi

**Telegram bot** — ko'p tilli (o'zbek, rus, ingliz), 9 ta buyruq:
ro'yxatdan o'tish, sharh qoldirish, profilni tahrirlash, o'z botini yasash,
admin panel.

**Sayt** — bizneslar katalogi (qidiruv, soha va yo'nalish bo'yicha filtr),
har bir biznesning ochiq sahifasi (menyu, sharhlar, xarita), va egasi uchun
kabinet: statistika, sharhlarni tasdiqlash va javob berish, katalog boshqaruvi,
profil, BotBuilder.

**Backend** — sayt uchun JWT, bot uchun HMAC-imzolangan so'rovlar.

## Xavfsizlik

- Telefon raqami API'da hech qachon to'liq qaytarilmaydi (`+9989****4567`).
  Log filtri raqam, bot tokeni va `Bearer` tokenlarni avtomatik o'chiradi.
- Mijozlarning bot tokenlari Fernet bilan shifrlanadi. Foydalanuvchi tokenni
  botga yozgach, xabari **darhol o'chiriladi**.
- Bot so'rovlari HMAC-SHA256 bilan imzolanadi: vaqt tamg'asi + nonce + to'liq
  yo'l (query bilan) + tana xeshi. Ushlab olingan so'rovni qayta yuborib
  bo'lmaydi, `?telegram_id=` ni almashtirib bo'lmaydi.
- Begona bizneslarga murojaat 403 emas, **404** qaytaradi — mavjudligini ham
  fosh qilmaslik uchun.
- Backend Telegram'ga to'g'ridan-to'g'ri yozmaydi: bildirishnomalar navbatga
  qo'yiladi, bot olib yuboradi. Telegram tokeni faqat bot servisida qoladi.

## Texnologiyalar

| Qism | Nima | Qayerda |
|---|---|---|
| Backend | Python, FastAPI, async SQLAlchemy, PostgreSQL | Railway |
| Bot va runner | python-telegram-bot | Railway |
| Sayt | TanStack Start, React 19, TypeScript | Vercel |
| AI | Claude API | — |

## Sifat

169 ta avtomatik tekshiruv, hammasi o'tadi. Hech biriga Telegram tokeni yoki
tashqi tarmoq kerak emas — CI'da ham ishlaydi.

| Tekshiruv | Nimani tekshiradi |
|---|---|
| 78 | Backend: auth, sharhlar, reyting, egalik chegaralari, replay himoyasi, sohalar |
| 37 | Bot ↔ backend: handlerlar yuboradigan aynan o'sha payloadlar |
| 30 | Runner: botlarni ko'tarish, yiqilganda tiklash, konfiguratsiya talqini |
| 14 | Bot klienti: imzolash va xato formatlari |
| 10 | Bot ulanishi: 43 ta tugmaning har biri handlerga tushadimi |

Oxirgisi alohida foydali: yangi tugma qo'shilib, handleri yozilmasa test
darhol ushlaydi.

## Keyingi qadamlar

- **QR orqali sharh** — stol yoki kassadagi QR to'g'ridan-to'g'ri sharh
  oqimini ochadi
- **AI sharh tahlili** — takrorlanuvchi shikoyatlarni topish, javob
  qoralamalari, egasiga haftalik hisobot
- Filiallar, tumanlararo reyting taqqoslash, Telegram Mini App kabinet

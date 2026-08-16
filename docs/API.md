# API kontrakti

Bu hujjat **frontend** va **bot** komandalari uchun. Jonli va har doim aniq versiya:
`http://localhost:8000/docs` (Swagger) yoki `/openapi.json`.

Baza manzil: `https://<backend>.up.railway.app/api/v1`

> Frontend uchun bularning hammasi allaqachon
> [`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts) da tipli holda yozilgan —
> qo'lda `fetch` yozish shart emas. Quyidagi bo'lim kontraktni tushuntiradi.

---

## 1. Frontend uchun (React)

### Autentifikatsiya

Barcha yopiq endpointlarga: `Authorization: Bearer <access_token>`

Ikki xil kirish yo'li bor:

**a) Botdagi "Saytga avtomatik kirish" tugmasi.** Bot foydalanuvchiga shunday link yuboradi:

```
https://<vercel-domen>/auth/telegram?token=<bir_martalik_token>&next=/dashboard
```

Frontendda `/auth/telegram` sahifasi shu tokenni JWT'ga almashtiradi:

```js
const res = await fetch(`${API}/auth/telegram/exchange`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ token }),
});
const { access_token, refresh_token } = await res.json();
// saqlab, `next` sahifasiga yo'naltiring
```

Token **bir martalik** va 15 daqiqa yashaydi. Ikkinchi urinishda 401 keladi —
foydalanuvchini "Botdan yangi link oling" degan xabar bilan qaytaring.

**b) Login/parol.** Bot ro'yxatdan o'tishda generatsiya qilgan login/parol:

```
POST /auth/login   { "username": "oshmarkazi_a7f2c", "password": "..." }
```

### Token yangilash

`access_token` 12 soat yashaydi. Muddati tugaganda 401 va
`{"detail": "Sessiya muddati tugadi, qaytadan kiring"}` keladi:

```
POST /auth/refresh   { "refresh_token": "..." }
```

Har `refresh` da eski refresh token bekor qilinadi va yangisi beriladi — javobdagi
ikkala tokenni ham saqlang.

### Endpointlar

| Metod | Yo'l | Kim | Nima qiladi |
|---|---|---|---|
| `POST` | `/auth/login` | ochiq | Login/parol bilan kirish |
| `POST` | `/auth/telegram/exchange` | ochiq | Bot linkidagi tokenni JWT'ga almashtirish |
| `POST` | `/auth/refresh` | ochiq | Access tokenni yangilash |
| `POST` | `/auth/logout` | user | Barcha sessiyalarni yopish |
| `GET` | `/auth/me` | user | Joriy foydalanuvchi + `restaurant_ids` |
| `POST` | `/auth/change-password` | user | Parolni o'zgartirish |
| `GET` | `/industries` | ochiq | **Sohalar, yorliqlar va sohaga xos savollar** |
| `GET` | `/categories?industry_key=` | ochiq | Yo'nalishlar (soha bo'yicha filtrlanadi) |
| `GET` | `/restaurants` | ochiq | Ro'yxat + qidiruv |
| `GET` | `/restaurants/my` | user | Mening restoranlarim |
| `GET` | `/restaurants/{id}` | ochiq | Profil |
| `GET` | `/restaurants/slug/{slug}` | ochiq | Profil (chiroyli URL uchun) |
| `PATCH` | `/restaurants/{id}` | egasi | Profilni tahrirlash |
| `GET` | `/restaurants/{id}/stats` | egasi | Kabinet statistikasi |
| `GET` | `/restaurants/{id}/menu` | ochiq | Menyu |
| `POST` | `/restaurants/{id}/menu` | egasi | Taom qo'shish |
| `PATCH` | `/restaurants/{id}/menu/{item_id}` | egasi | Taomni tahrirlash |
| `DELETE` | `/restaurants/{id}/menu/{item_id}` | egasi | Taomni o'chirish |
| `GET` | `/reviews?restaurant_id=` | ochiq | Sharhlar |
| `PATCH` | `/reviews/{id}/moderate` | egasi | Tasdiqlash / rad etish |
| `POST` | `/reviews/{id}/reply` | egasi | Sharhga javob |
| `DELETE` | `/reviews/{id}` | egasi | O'chirish |
| `POST` | `/uploads/image` | user | Rasm yuklash (multipart, `file`) |
| `GET` | `/restaurants/{id}/bots` | egasi | Shaxsiy botlar |
| `POST` | `/restaurants/{id}/bots/questionnaire` | egasi | Anketa → AI bot logikasi |
| `GET` | `/restaurants/{id}/bots/{bot_id}/config` | egasi | Generatsiya qilingan matnlar |
| `POST` | `/restaurants/{id}/bots/{bot_id}/token` | egasi | @BotFather tokenini ulash |
| `POST` | `/restaurants/{id}/bots/{bot_id}/start` | egasi | Ishga tushirish |
| `POST` | `/restaurants/{id}/bots/{bot_id}/stop` | egasi | To'xtatish |
| `POST` | `/restaurants/{id}/verify` | admin | Restoranni tasdiqlash |

### Ro'yxat javobi

Barcha ro'yxat endpointlari bir xil shaklda:

```json
{ "items": [ ... ], "total": 42, "limit": 20, "offset": 0 }
```

`GET /restaurants` filtrlari: `q`, `industry_key`, `category_id`, `category_key`,
`min_rating`, `sort` (`rating` | `new` | `name`), `limit`, `offset`.

### Ko'p sohalilik — yorliqlarni kodga yozmang

Tizim restoran, do'kon, klinika va sport markazlari bilan ishlaydi. Sohaga
bog'liq har qanday so'z (`Menyu` / `Katalog` / `Xizmatlar`, `Taom` / `Mahsulot`)
**backenddan keladi**:

```json
GET /industries →
[{
  "key": "market", "icon": "🛒",
  "name_uz": "Do'konlar",
  "item_label_uz": "Mahsulot",        ← bitta yozuv
  "catalog_label_uz": "Katalog",      ← katalogning o'zi
  "fields": [                          ← sohaga xos savollar
    {"key": "delivery", "type": "choice", "choices": ["Bor", "Yo'q"],
     "label": {"uz": "Yetkazib berish bormi?", "ru": "...", "en": "..."}}
  ],
  "categories": [{"key": "grocery", "name_uz": "Oziq-ovqat", ...}]
}]
```

Har bir biznes javobida `industry` (qisqartirilgan) va `attributes` bo'ladi:

```json
{
  "name": "Mega Market",
  "industry": {"key": "market", "icon": "🛒", "item_label_uz": "Mahsulot", ...},
  "attributes": {"delivery": "Bor", "min_order": "50000"}
}
```

Formani `fields` bo'yicha chizing — yangi soha qo'shilganda frontendga kod
yozish shart bo'lmaydi. Tayyor yordamchilar:
[`src/lib/labels.ts`](../frontend/src/lib/labels.ts) —
`itemLabel()`, `catalogLabel()`, `localized()`, `fieldLabel()`.

`attributes` qisman yangilanadi: bitta kalit yuborsangiz qolganlari saqlanadi.
Yo'nalish (`category_id`) biznes sohasiga tegishli bo'lishi shart, aks holda 422.

### Xatolar

```json
{ "detail": "Restoran topilmadi" }
```

Validatsiya xatosi (422) qo'shimcha `problems` beradi — to'g'ridan-to'g'ri forma
maydonlari tagida ko'rsatishga tayyor:

```json
{
  "detail": "Kiritilgan ma'lumotda xatolik bor",
  "problems": [
    { "field": "work_hours", "message": "ish vaqti 'HH:MM-HH:MM' ko'rinishida bo'lishi kerak, masalan 09:00-23:00" }
  ]
}
```

| Kod | Ma'nosi |
|---|---|
| 401 | Token yo'q / eskirgan → `/auth/refresh` yoki login sahifasi |
| 403 | Rolga ruxsat yo'q |
| 404 | Topilmadi **yoki** sizniki emas |
| 409 | Ziddiyat (masalan bot allaqachon band) |
| 413 | Fayl juda katta (8 MB) |
| 415 | Rasm formati qo'llab-quvvatlanmaydi |
| 422 | Validatsiya — `problems` ni ko'rsating |

### E'tibor bering

- Telefon raqami **hech qachon to'liq qaytmaydi** — faqat `phone_masked`.
- `POST /restaurants` yo'q: restoran faqat bot orqali yaratiladi.
- Yangi kirgan egada `must_change_password` bo'lishi mumkin — parol o'zgartirishni taklif qiling.

---

## 2. Bot uchun (python-telegram-bot)

**Tayyor klient bor: [`bot/crm_client.py`](../bot/crm_client.py)** — imzolashni o'zi qiladi,
qo'lda hech narsa hisoblash shart emas.

```python
from crm_client import CrmClient, CrmApiError

crm = CrmClient(os.environ["CRM_API_URL"], os.environ["BOT_HMAC_SECRET"])

try:
    result = await crm.register_restaurant({...})
except CrmApiError as e:
    await update.message.reply_text(e.message)   # xabar foydalanuvchiga tayyor
```

### Imzolash (agar qo'lda yozmoqchi bo'lsangiz)

Har bir `/api/v1/bot/*` so'rovida uchta sarlavha:

```
X-Timestamp: 1755331200
X-Nonce:     a3f9c2e18b7d4056
X-Signature: <hex>
```

```
base      = "{timestamp}.{nonce}.{METHOD}.{path?query}.{sha256_hex(body)}"
signature = hmac_sha256(BOT_HMAC_SECRET, base).hexdigest()
```

- `path?query` — `/api/v1/bot/profile?telegram_id=123` ko'rinishida, **query bilan birga**
- `body` — bo'sh bo'lsa `sha256(b"")`
- `nonce` — har so'rovda yangi tasodifiy qator (8–64 belgi)
- Timestamp oynasi ±5 daqiqa

### Endpointlar

| Metod | Yo'l | Nima uchun |
|---|---|---|
| `POST` | `/bot/users/sync` | Til tanlanganda, kontakt yuborilganda |
| `POST` | `/bot/restaurants/register` | Anketa "Tasdiqlash" bosilganda |
| `POST` | `/bot/login-link` | "Saytga kirish" tugmasi uchun link |
| `GET` | `/bot/profile?telegram_id=` | Tahrirlashdan oldin joriy ma'lumot |
| `PATCH` | `/bot/restaurants/{id}?telegram_id=` | Profilni tahrirlash |
| `GET` | `/bot/restaurants/search?q=` | Sharh uchun restoran tanlash |
| `POST` | `/bot/reviews` | Sharh yuborish |
| `POST` | `/bot/upload` | Rasmni yuklab, URL olish |
| `POST` | `/bot/botbuilder/questionnaire?telegram_id=` | BotBuilder anketasi |
| `POST` | `/bot/botbuilder/{bot_id}/token?telegram_id=` | @BotFather tokeni |
| `GET` | `/bot/botbuilder/runners` | Runner uchun bot konfiguratsiyalari |
| `GET` | `/bot/outbox` | Yuborilishi kerak bo'lgan xabarlar |
| `POST` | `/bot/outbox/ack` | Yetkazilganini tasdiqlash |

### Ro'yxatdan o'tish javobi

```json
{
  "restaurant": { "id": 1, "name": "Osh Markazi", "slug": "osh-markazi", ... },
  "username": "oshmarkazi_a7f2c",
  "password": "Kx7mNp2qRt4v",
  "login_url": "https://.../auth/telegram?token=...&next=/dashboard",
  "already_registered": false
}
```

> **`password` faqat shu bir marta keladi.** Bazada faqat hash saqlanadi — qayta olish
> imkoni yo'q. Foydalanuvchiga darhol yuboring.
>
> `already_registered: true` — bu nomdagi restoran allaqachon bor (masalan "Tasdiqlash"
> ikki marta bosilgan). Dublikat yaratilmaydi, `password` esa `null` bo'ladi.

`login_url` ni "Saytga avtomatik kirish" tugmasi sifatida yuboring.

### Bildirishnomalar (outbox)

Backend Telegram'ga o'zi yozmaydi — token faqat sizda qoladi. Har 5–10 soniyada pollang:

```python
while True:
    for msg in await crm.fetch_outbox():
        await send_by_kind(msg["kind"], msg["telegram_id"], msg["payload"], msg["language"])
    await crm.ack_outbox([m["id"] for m in messages])
    await asyncio.sleep(5)
```

`kind` qiymatlari va `payload` maydonlari:

| `kind` | payload | Qachon |
|---|---|---|
| `new_review` | `restaurant_name`, `rating`, `text`, `review_id` | Yangi sharh kelganda → egasiga |
| `review_moderated` | `review_id`, `status` | Sharh tasdiqlangan/rad etilganda → muallifga |
| `owner_reply` | `restaurant_name`, `reply`, `review_id` | Egasi javob yozganda → muallifga |
| `bot_status` | `bot_username`, `status` | Shaxsiy bot holati o'zgarganda → egasiga |

`language` (`uz`/`ru`/`en`) foydalanuvchining tanlagan tili — shablonni shunga qarab tanlang.
`ack` qilinmagan xabar keyingi pollashda **yana keladi**, shuning uchun faqat haqiqatan
yuborilganidan keyin tasdiqlang.

### Muhim eslatmalar

- **Bot tokenini hech qayerda log qilmang.** Foydalanuvchi tokenni chatga yozgach, uning
  xabarini `delete_message` bilan o'chirib qo'ying.
- Telefon raqamini faqat `KeyboardButton(request_contact=True)` orqali oling.
- Xatolarda `CrmApiError.message` allaqachon foydalanuvchiga ko'rsatishga yaroqli —
  uni to'g'ridan-to'g'ri yuboring, texnik tafsilot qo'shmang.

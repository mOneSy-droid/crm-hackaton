# Frontend

TanStack Start (React 19 + Vite) — restoranlar katalogi va restoran egasi kabineti.
Barcha ma'lumot backenddan keladi, mock ma'lumot yo'q.

## Ishga tushirish

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Ochiladi: <http://localhost:8080>

`.env` da backend manzilini ko'rsating:

```
VITE_API_URL=http://localhost:8000
```

> Backend boshqa portda bo'lsa (masalan 8000 band bo'lsa) shu qiymatni o'zgartiring
> **va** backenddagi `CORS_ORIGINS` ga `http://localhost:8080` borligiga ishonch hosil qiling.

## Sahifalar

| Yo'l | Kim uchun | Nima |
|---|---|---|
| `/` | hamma | Restoranlar katalogi, qidiruv, kategoriya filtri |
| `/r/:slug` | hamma | Restoranning ochiq sahifasi: menyu, sharhlar, xarita |
| `/login` | hamma | Login/parol bilan kirish |
| `/auth/telegram` | bot | **Botdagi «Saytga kirish» tugmasi shu yerga tushadi** |
| `/dashboard` | egasi | Reyting, yulduzlar taqsimoti, oxirgi sharhlar |
| `/reviews` | egasi | Moderatsiya, javob yozish, o'chirish |
| `/menu` | egasi | Taom qo'shish/tahrirlash, rasm yuklash, mavjudlik |
| `/profile` | egasi | Nom, manzil, ish vaqti, kategoriya, logotip |
| `/mybot` | egasi | BotBuilder anketasi va @BotFather tokenini ulash |

## Tuzilma

```
src/
├── lib/
│   ├── api.ts        backend klienti — barcha tiplar va endpointlar shu yerda
│   ├── session.ts    kirish holati, useRequireAuth, logout
│   └── labels.ts     enum -> o'zbekcha matn
├── components/
│   ├── AppLayout.tsx kabinet qobig'i (yon panel + yuqori panel)
│   └── Toast.tsx     xabar ko'rsatish
├── routes/           TanStack file-based routing
└── styles/crm.css    dizayn tizimi (tokenlar + komponentlar)
```

`routeTree.gen.ts` avtomatik generatsiya qilinadi — qo'lda tahrirlamang.
Yangi sahifa qo'shish: `src/routes/` ga `.tsx` fayl qo'ying, `npm run dev` uni o'zi ulaydi.

## Auth qanday ishlaydi

Ikki yo'l bilan kiriladi, ikkalasi ham bir xil JWT juftligini beradi:

1. **Telegram** — bot `/auth/telegram?token=...&next=/dashboard` linkini yuboradi.
   Token bir martalik, 15 daqiqa yashaydi. `api.exchangeTelegramToken` uni JWT'ga almashtiradi.
2. **Login/parol** — botda ro'yxatdan o'tishda generatsiya qilingan.

`access_token` 12 soat yashaydi. 401 kelganda `api.ts` avtomatik `refresh` qiladi va
so'rovni bir marta qaytadan yuboradi; refresh ham ishlamasa tokenlar tozalanadi va
foydalanuvchi `/login` ga yo'naltiriladi.

## Tekshirish

```bash
npx tsc --noEmit
```
```bash
npm run build
```

## Vercel'ga deploy

1. Vercel'da yangi loyiha, **Root Directory** = `frontend`
2. Environment Variables:

   | O'zgaruvchi | Qiymat |
   |---|---|
   | `VITE_API_URL` | `https://<backend>.up.railway.app` |
   | `NITRO_PRESET` | `vercel` |

   (`NITRO_PRESET` allaqachon `vercel.json` da yozilgan — u yerda qolsa ham bo'ladi.)

3. Backend tomonda `CORS_ORIGINS` va `FRONTEND_URL` ga Vercel domenini qo'shing —
   aks holda brauzer so'rovlarni bloklaydi va botdagi kirish linki noto'g'ri domenga
   ishora qiladi.

## Diqqat

- Bu SSR ilova (TanStack Start). `localStorage` faqat brauzerda mavjud, shuning uchun
  `api.ts` har safar `typeof window` ni tekshiradi. Yangi kod yozganda ham shunday qiling.
- Telefon raqamlari API'dan hech qachon to'liq kelmaydi — faqat `phone_masked`.

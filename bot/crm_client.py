"""Backend bilan ishlash uchun tayyor klient — Telegram bot shu faylni ishlatadi.

O'rnatish:
    pip install httpx

Ishlatish:
    from crm_client import CrmClient

    crm = CrmClient("https://<backend>.up.railway.app", os.environ["BOT_HMAC_SECRET"])

    await crm.sync_user(telegram_id=123, language="uz", phone="+998901112233")
    result = await crm.register_restaurant({...})
    await crm.close()

MUHIM: `BOT_HMAC_SECRET` backenddagi qiymat bilan bir xil bo'lishi shart va
faqat environment variable orqali beriladi — kodga yozilmaydi.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

import httpx


class CrmApiError(Exception):
    """Backend xato qaytardi. `.message` foydalanuvchiga ko'rsatishga yaroqli."""

    def __init__(self, status_code: int, message: str, problems: list[dict] | None = None):
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.message = message
        self.problems = problems or []


class CrmClient:
    """Barcha so'rovlarni HMAC-SHA256 bilan imzolaydigan async klient.

    Imzo formulasi (backend ham aynan shuni hisoblaydi):
        base = "{timestamp}.{nonce}.{METHOD}.{path_va_query}.{sha256_hex(body)}"
        signature = hex(hmac_sha256(secret, base))

    `path_va_query` — bu `/api/v1/bot/profile?telegram_id=123` ko'rinishidagi
    to'liq yo'l. Query ham imzoga kiradi, shuning uchun uni o'zgartirib
    bo'lmaydi. `nonce` har so'rovda yangi — bir xil so'rovni qayta yuborish
    mumkin, lekin ushlab olingan so'rovni takrorlab bo'lmaydi.
    """

    API_PREFIX = "/api/v1"

    def __init__(self, base_url: str, hmac_secret: str, timeout: float = 20.0):
        self._base_url = base_url.rstrip("/")
        self._secret = hmac_secret.encode()
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "CrmClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    # -- ichki qism ---------------------------------------------------------

    def _sign(self, method: str, path_with_query: str, body: bytes) -> dict[str, str]:
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(12)
        base = (
            f"{timestamp}.{nonce}.{method.upper()}.{path_with_query}."
            f"{hashlib.sha256(body).hexdigest()}"
        )
        signature = hmac.new(self._secret, base.encode(), hashlib.sha256).hexdigest()
        return {"X-Timestamp": timestamp, "X-Nonce": nonce, "X-Signature": signature}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        request = self._client.build_request(
            method, self.API_PREFIX + path, json=json, params=params, files=files
        )
        # Imzo aynan yuboriladigan URL va tana ustidan hisoblanadi.
        # `read()` kerak: multipart (rasm yuklash) so'rovi oqim ko'rinishida
        # tuziladi va oldindan o'qilmasa `request.content` mavjud bo'lmaydi.
        body = request.read()
        path_with_query = request.url.raw_path.decode()
        request.headers.update(self._sign(method, path_with_query, body))

        # Tarmoq xatosi ham CrmApiError bo'lib chiqadi — handlerlar bitta
        # tur bilan ishlaydi, foydalanuvchiga tushunarli xabar boradi va
        # xato yuqoriga otilib "Xatolik yuz berdi" kaskadini keltirmaydi.
        try:
            response = await self._client.send(request)
        except httpx.TimeoutException as exc:
            raise CrmApiError(
                0, "Server javob berishga ulgurmadi. Bir daqiqadan so'ng urinib ko'ring."
            ) from exc
        except httpx.HTTPError as exc:
            raise CrmApiError(
                0, "Server bilan hozircha aloqa yo'q. Birozdan keyin urinib ko'ring."
            ) from exc

        if response.status_code >= 400:
            raise self._to_error(response)
        return response.json() if response.content else None

    @staticmethod
    def _to_error(response: httpx.Response) -> CrmApiError:
        try:
            data = response.json()
        except ValueError:
            return CrmApiError(response.status_code, "Serverda kutilmagan xatolik")

        message = data.get("detail", "Xatolik yuz berdi")
        problems = data.get("problems", [])
        if problems:
            # Botda foydalanuvchiga ko'rsatish uchun qisqa va aniq matn
            message = "; ".join(f"{p['field']}: {p['message']}" for p in problems)
        return CrmApiError(response.status_code, message, problems)

    async def _public_get(self, path: str) -> Any:
        """Ochiq endpoint — imzo talab qilinmaydi (`/bot/*` dan tashqarida)."""
        response = await self._client.get(self.API_PREFIX + path)
        if response.status_code >= 400:
            raise self._to_error(response)
        return response.json()

    # -- ma'lumotnomalar ----------------------------------------------------

    async def get_industries(self) -> list[dict]:
        """Sohalar: yorliqlar, qo'shimcha savollar va yo'nalishlar bilan.

        Bot barcha sohaga bog'liq matnlarni shu yerdan oladi — kodda
        "restoran" yoki "taom" so'zi yozilmaydi.
        """
        return await self._public_get("/industries")

    async def get_categories(self, industry_key: str | None = None) -> list[dict]:
        """Yo'nalishlar — uz/ru/en nomlari bilan."""
        suffix = f"?industry_key={industry_key}" if industry_key else ""
        return await self._public_get(f"/categories{suffix}")

    async def get_restaurant(self, restaurant_id: int) -> dict:
        """Ochiq profil — manzil, ish vaqti, telefon."""
        return await self._public_get(f"/restaurants/{restaurant_id}")

    async def get_catalog(self, restaurant_id: int) -> list[dict]:
        """Menyu — faqat mavjud taomlar."""
        return await self._public_get(f"/restaurants/{restaurant_id}/menu?only_available=true")

    # -- foydalanuvchi ------------------------------------------------------

    async def sync_user(
        self,
        telegram_id: int,
        *,
        language: str = "uz",
        full_name: str | None = None,
        phone: str | None = None,
        telegram_username: str | None = None,
    ) -> dict:
        """Til tanlanganda va kontakt yuborilganda chaqiriladi."""
        return await self._request(
            "POST",
            "/bot/users/sync",
            json={
                "telegram_id": telegram_id,
                "language": language,
                "full_name": full_name,
                "phone": phone,
                "telegram_username": telegram_username,
            },
        )

    # -- ro'yxatdan o'tish --------------------------------------------------

    async def register_restaurant(self, payload: dict) -> dict:
        """Anketa tasdiqlangach chaqiriladi.

        Javobdagi `password` FAQAT bir marta keladi — foydalanuvchiga darhol
        yuboring, keyin uni qayta olishning imkoni yo'q.
        """
        return await self._request("POST", "/bot/restaurants/register", json=payload)

    async def login_link(self, telegram_id: int, next_path: str | None = "/dashboard") -> dict:
        """"Saytga avtomatik kirish" tugmasi uchun bir martalik link."""
        return await self._request(
            "POST", "/bot/login-link", json={"telegram_id": telegram_id, "next_path": next_path}
        )

    # -- profil -------------------------------------------------------------

    async def get_profile(self, telegram_id: int) -> dict:
        """Egasining restoranlari — tahrirlashdan oldin joriy ma'lumotni ko'rsatish uchun."""
        return await self._request("GET", "/bot/profile", params={"telegram_id": telegram_id})

    async def update_restaurant(self, telegram_id: int, restaurant_id: int, changes: dict) -> dict:
        """Faqat o'zgargan maydonlarni yuboring."""
        return await self._request(
            "PATCH",
            f"/bot/restaurants/{restaurant_id}",
            params={"telegram_id": telegram_id},
            json=changes,
        )

    # -- sharhlar -----------------------------------------------------------

    async def search_restaurants(self, query: str | None = None, limit: int = 10) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        return await self._request("GET", "/bot/restaurants/search", params=params)

    async def create_review(
        self,
        telegram_id: int,
        restaurant_id: int,
        rating: int,
        text: str | None = None,
        photo_urls: list[str] | None = None,
    ) -> dict:
        return await self._request(
            "POST",
            "/bot/reviews",
            json={
                "telegram_id": telegram_id,
                "restaurant_id": restaurant_id,
                "rating": rating,
                "text": text,
                "photo_urls": photo_urls or [],
            },
        )

    async def upload_photo(self, filename: str, content: bytes) -> str:
        """Telegramdan olingan rasm baytlarini yuklab, ochiq URL qaytaradi."""
        data = await self._request(
            "POST", "/bot/upload", files={"file": (filename, content, "image/jpeg")}
        )
        return data["url"]

    # -- BotBuilder ---------------------------------------------------------

    async def submit_bot_questionnaire(
        self,
        telegram_id: int,
        restaurant_id: int,
        purpose: str,
        languages: list[str],
        features: list[str],
        tone: str | None = None,
    ) -> dict:
        return await self._request(
            "POST",
            "/bot/botbuilder/questionnaire",
            params={"telegram_id": telegram_id},
            json={
                "restaurant_id": restaurant_id,
                "purpose": purpose,
                "languages": languages,
                "features": features,
                "tone": tone,
            },
        )

    async def submit_bot_token(self, telegram_id: int, bot_id: int, token: str) -> dict:
        """@BotFather tokenini backendga uzatadi — u shifrlab saqlanadi.

        Tokenni HECH QAYERDA log qilmang va chatda qoldirmang: yuborilgandan
        keyin foydalanuvchining xabarini o'chirib qo'yish tavsiya etiladi.
        """
        return await self._request(
            "POST",
            f"/bot/botbuilder/{bot_id}/token",
            params={"telegram_id": telegram_id},
            json={"token": token},
        )

    async def runner_configs(self) -> list[dict]:
        """Ishga tushirilishi kerak bo'lgan shaxsiy botlar ro'yxati (tokenlar bilan)."""
        return await self._request("GET", "/bot/botbuilder/runners")

    async def submit_lead(
        self,
        bot_id: int,
        telegram_id: int,
        flow_id: str,
        answers: dict[str, str],
        flow_label: str | None = None,
        customer_name: str | None = None,
    ) -> dict:
        """Shaxsiy bot yig'gan buyurtma/bron/savolni egasiga yuboradi."""
        return await self._request(
            "POST",
            "/bot/tenant/lead",
            json={
                "bot_id": bot_id,
                "telegram_id": telegram_id,
                "flow_id": flow_id,
                "flow_label": flow_label,
                "answers": answers,
                "customer_name": customer_name,
            },
        )

    # -- bildirishnomalar ---------------------------------------------------

    async def fetch_outbox(self, limit: int = 50) -> list[dict]:
        """Backend yubormoqchi bo'lgan xabarlar. Har 5-10 soniyada pollang."""
        return await self._request("GET", "/bot/outbox", params={"limit": limit})

    async def ack_outbox(self, ids: list[int]) -> None:
        if ids:
            await self._request("POST", "/bot/outbox/ack", json={"ids": ids})

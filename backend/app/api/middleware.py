from __future__ import annotations

import logging
import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.security import verify_bot_signature

logger = logging.getLogger(__name__)

#: Ushlab olingan so'rovni qayta yuborishni bloklash uchun ko'rilgan nonce'lar
_seen_nonces: dict[str, float] = {}


def _remember_nonce(nonce: str) -> bool:
    """Nonce birinchi marta ko'rilayotgan bo'lsa True qaytaradi."""
    now = time.time()
    ttl = settings.BOT_REQUEST_MAX_SKEW_SECONDS
    if len(_seen_nonces) > 20_000:
        for key, seen_at in list(_seen_nonces.items()):
            if now - seen_at > ttl:
                del _seen_nonces[key]
    if nonce in _seen_nonces and now - _seen_nonces[nonce] <= ttl:
        return False
    _seen_nonces[nonce] = now
    return True


class BotSignatureMiddleware:
    """Telegram bot xizmatidan kelgan so'rovlarni HMAC-SHA256 bo'yicha tekshiradi.

    Nega dependency emas, middleware: rasm yuklashda (multipart) FastAPI so'rov
    tanasini dependency'lardan oldin o'qib bo'ladi va keyin uni qayta o'qib
    bo'lmaydi. Middleware tanani marshrutlashdan oldin buferga oladi, imzoni
    tekshiradi va o'zgarmagan holda ilovaga uzatadi.

    Bot yuborishi kerak bo'lgan sarlavhalar:
        X-Timestamp: unix sekund
        X-Nonce:     har so'rovda yangi tasodifiy qator (8-64 belgi)
        X-Signature: hex(hmac_sha256(BOT_HMAC_SECRET,
                     "{ts}.{nonce}.{METHOD}.{path?query}.{sha256_hex(body)}"))

    Query string ham imzoga kiradi — `?telegram_id=...` ni yo'lda almashtirib
    bo'lmasin. Nonce tufayli bot bir xil so'rovni (masalan outbox pollash)
    xohlagancha yuborishi mumkin, lekin ushlab olingan so'rovni qayta yuborib
    bo'lmaydi.
    """

    def __init__(self, app: ASGIApp, protected_prefix: str) -> None:
        self.app = app
        self.protected_prefix = protected_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.protected_prefix):
            await self.app(scope, receive, send)
            return

        body = b""
        while True:
            message: Message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        signature = headers.get("x-signature", "")
        timestamp = headers.get("x-timestamp", "")
        nonce = headers.get("x-nonce", "")

        path = scope["path"]
        query = scope.get("query_string", b"").decode()
        if query:
            path = f"{path}?{query}"

        ok, reason = verify_bot_signature(
            signature, timestamp, nonce, scope["method"], path, body
        )
        if not ok:
            logger.warning("Bot imzosi rad etildi (%s): %s", reason, scope["path"])
            await JSONResponse({"detail": "Imzo noto'g'ri"}, status_code=401)(scope, receive, send)
            return

        if not _remember_nonce(nonce):
            logger.warning("Bot so'rovi takrorlandi: %s", scope["path"])
            await JSONResponse({"detail": "So'rov takrorlandi"}, status_code=409)(
                scope, receive, send
            )
            return

        # Tanani ilovaga qayta uzatamiz
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

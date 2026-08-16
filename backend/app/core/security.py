from __future__ import annotations

import hashlib
import hmac
import secrets
import string
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

# ---------------------------------------------------------------------------
# Parol hashlash — PBKDF2-HMAC-SHA256 (stdlib, Windowsda ham muammosiz o'rnatiladi)
# ---------------------------------------------------------------------------

_PBKDF2_ROUNDS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

TokenType = Literal["access", "refresh"]


def _create_token(subject: str, token_type: TokenType, expires: timedelta, **extra: Any) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
        "jti": secrets.token_urlsafe(12),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    return _create_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        role=role,
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        str(user_id), "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Tokenni tekshiradi. Xato bo'lsa `jwt.PyJWTError` ko'taradi."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return payload


# ---------------------------------------------------------------------------
# Bir martalik tokenlar (bot -> saytga avtomatik kirish, refresh token saqlash)
# ---------------------------------------------------------------------------


def generate_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_fingerprint(token: str) -> str:
    """Tokenni bazada ochiq saqlamaslik uchun SHA-256 barmoq izi."""
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Restoran uchun login/parol generatsiyasi
# ---------------------------------------------------------------------------

_LOGIN_ALPHABET = string.ascii_lowercase + string.digits
# I/l/0/O kabi chalkash belgilar yo'q — foydalanuvchi qo'lda ko'chirib yozadi
_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_login(prefix: str = "rest") -> str:
    clean = "".join(ch for ch in prefix.lower() if ch in string.ascii_lowercase)[:10] or "rest"
    suffix = "".join(secrets.choice(_LOGIN_ALPHABET) for _ in range(5))
    return f"{clean}_{suffix}"


def generate_password(length: int = 12) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


# ---------------------------------------------------------------------------
# Telegram bot tokenlarini shifrlash
# ---------------------------------------------------------------------------

_fernet = Fernet(settings.fernet_key)


def encrypt_secret(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt_secret(cipher: str) -> str:
    try:
        return _fernet.decrypt(cipher.encode()).decode()
    except InvalidToken as exc:  # kalit almashgan yoki ma'lumot buzilgan
        raise ValueError("could not decrypt stored secret") from exc


# ---------------------------------------------------------------------------
# Bot -> backend so'rovlari uchun HMAC imzo
# ---------------------------------------------------------------------------


def build_signature_base(
    timestamp: str, nonce: str, method: str, path: str, body: bytes
) -> str:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    return f"{timestamp}.{nonce}.{method.upper()}.{path}.{body_hash}"


def sign_request(timestamp: str, nonce: str, method: str, path: str, body: bytes) -> str:
    base = build_signature_base(timestamp, nonce, method, path, body)
    return hmac.new(
        settings.BOT_HMAC_SECRET.encode(), base.encode(), hashlib.sha256
    ).hexdigest()


def verify_bot_signature(
    signature: str, timestamp: str, nonce: str, method: str, path: str, body: bytes
) -> tuple[bool, str]:
    """(ok, sabab) qaytaradi. Sabab faqat logga yoziladi, mijozga emas.

    `nonce` har bir so'rovda yangi bo'ladi — shu tufayli bir xil so'rovni
    (masalan outbox pollash) takrorlash mumkin, lekin ushlangan so'rovni
    qayta yuborib bo'lmaydi.
    """
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False, "bad timestamp"

    if abs(int(time.time()) - ts) > settings.BOT_REQUEST_MAX_SKEW_SECONDS:
        return False, "timestamp outside allowed window"

    if not nonce or len(nonce) < 8 or len(nonce) > 64:
        return False, "missing or malformed nonce"

    expected = sign_request(timestamp, nonce, method, path, body)
    if not hmac.compare_digest(expected, signature or ""):
        return False, "signature mismatch"
    return True, ""

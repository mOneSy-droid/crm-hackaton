"""Runner testi — haqiqiy Telegram tokeni kerak emas.

    python scripts/test_runner.py

Tekshiriladi:
  1. Supervisor botlarni to'g'ri ko'taradi/to'xtatadi/qayta yuklaydi
  2. Yiqilgan bot qayta ko'tariladi va qo'shnilariga ta'sir qilmaydi
  3. Konfiguratsiya talqini (tugmalar, oqimlar, ko'p tillilik)
  4. Backend zanjiri: anketa -> runners -> lead -> egasiga bildirishnoma

Telegram qismi (`TenantBot.start`) testda almashtiriladi — biz tekshirayotgan
narsa nazorat mantiqi, Telegramning o'zi emas.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BOT_DIR.parent
sys.path.insert(0, str(BOT_DIR))
sys.path.insert(0, str(REPO_DIR / "backend"))

TMP = Path(tempfile.mkdtemp(prefix="runner_test_"))
SHARED_SECRET = "runner-test-secret"

os.environ.update(
    ENV="dev",
    SECRET_KEY="runner-test-secret-key-at-least-32-characters-long",
    BOT_HMAC_SECRET=SHARED_SECRET,
    DATABASE_URL=f"sqlite+aiosqlite:///{(TMP / 'runner.db').as_posix()}",
    MEDIA_ROOT=str(TMP / "media"),
    TELEGRAM_BOT_TOKEN="123456789:AAtest-token-for-runner-check-only-xxx",
    BOT_DATABASE_URL=f"sqlite+aiosqlite:///{(TMP / 'bot.db').as_posix()}",
)

import httpx  # noqa: E402

from app.main import app as backend_app  # noqa: E402
from crm_client import CrmClient  # noqa: E402
from outbox import _render  # noqa: E402
from tenant import bot as tenant_bot_module  # noqa: E402
from tenant.bot import TenantBot, pick  # noqa: E402
from tenant.supervisor import Supervisor, TenantRunner  # noqa: E402

passed, failed = 0, []


def check(name: str, condition: bool, extra: object = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  [ok]   {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


# ---------------------------------------------------------------------------
# Telegram o'rnini bosuvchi soxta bot
# ---------------------------------------------------------------------------

started_ids: list[int] = []
stopped_ids: list[int] = []
#: shu bot_id birinchi ishga tushishda yiqiladi
crash_once: set[int] = set()


class FakeTenantBot:
    def __init__(self, spec: dict, crm: CrmClient):
        self.spec = spec
        self.bot_id = spec["bot_id"]
        self.version = spec["config_version"]

    async def start(self) -> None:
        if self.bot_id in crash_once:
            crash_once.discard(self.bot_id)
            raise RuntimeError("Telegram tokeni rad etildi")
        started_ids.append(self.bot_id)

    async def stop(self) -> None:
        stopped_ids.append(self.bot_id)


def spec(bot_id: int, version: str) -> dict:
    return {
        "bot_id": bot_id,
        "restaurant_id": bot_id * 10,
        "restaurant_name": f"Test {bot_id}",
        "token": f"{bot_id}:token",
        "languages": ["uz"],
        "tone": None,
        "config": {},
        "config_version": version,
    }


class FakeCrm:
    """Faqat `runner_configs` kerak — qolganini supervisor ishlatmaydi."""

    def __init__(self, specs: list[dict]):
        self.specs = specs

    async def runner_configs(self) -> list[dict]:
        return self.specs


# ---------------------------------------------------------------------------
# 1-3: supervisor mantiqi
# ---------------------------------------------------------------------------


async def test_supervisor() -> None:
    print("\n1) Supervisor botlarni boshqaradi")
    tenant_bot_module.TenantBot = FakeTenantBot  # noqa: F811
    import tenant.supervisor as supervisor_module

    supervisor_module.TenantBot = FakeTenantBot

    started_ids.clear()
    stopped_ids.clear()

    crm = FakeCrm([spec(1, "v1"), spec(2, "v1")])
    supervisor = Supervisor(crm, poll_seconds=1)

    result = await supervisor.sync_once()
    await asyncio.sleep(0.3)
    check("ikkita bot ko'tarildi", result["started"] == 2, result)
    check("ikkalasi ham ishga tushdi", sorted(started_ids) == [1, 2], started_ids)

    print("\n2) O'zgarishlarni sezadi")
    crm.specs = [spec(1, "v1"), spec(2, "v2")]
    result = await supervisor.sync_once()
    await asyncio.sleep(0.3)
    check("konfiguratsiya o'zgargani aniqlandi", result["reloaded"] == 1, result)
    check("faqat #2 qayta ko'tarildi", started_ids.count(2) == 2 and started_ids.count(1) == 1,
          started_ids)

    crm.specs = [spec(1, "v1")]
    result = await supervisor.sync_once()
    await asyncio.sleep(0.3)
    check("to'xtatilgan bot olib tashlandi", result["stopped"] == 1, result)
    check("ishlayotganlar ro'yxati to'g'ri", supervisor.active_ids == [1], supervisor.active_ids)

    print("\n3) Bitta bot yiqilsa qolganlari ishlayveradi")
    crash_once.add(3)
    crm.specs = [spec(1, "v1"), spec(3, "v1")]
    await supervisor.sync_once()
    await asyncio.sleep(0.4)
    check("yiqilgan bot ro'yxatda qoladi (qayta urinadi)", 3 in supervisor.active_ids,
          supervisor.active_ids)
    check("qo'shnisi ishlab turibdi", 1 in supervisor.active_ids, supervisor.active_ids)

    # Qayta urinish BACKOFF_START (5s) dan keyin — testda kutmaymiz,
    # muhimi runner o'lib qolmagani
    await supervisor.shutdown()
    check("shutdown hammasini to'xtatdi", supervisor.active_ids == [], supervisor.active_ids)

    supervisor_module.TenantBot = TenantBot


# ---------------------------------------------------------------------------
# 4: konfiguratsiya talqini
# ---------------------------------------------------------------------------


async def test_config_interpretation() -> None:
    print("\n4) Konfiguratsiya talqini")

    config = {
        "welcome": {"uz": "Salom!", "ru": "Привет!"},
        "menu_buttons": [
            {"id": "menu", "label": {"uz": "📋 Menyu", "ru": "📋 Меню"}},
            {"id": "booking", "label": {"uz": "🪑 Bron", "ru": "🪑 Бронь"}},
        ],
        "flows": [
            {
                "id": "booking",
                "trigger": "booking",
                "steps": [
                    {"type": "ask_text", "text": {"uz": "Nechchi kishi?"}, "save_as": "odam"},
                    {"type": "ask_phone", "text": {"uz": "Raqamingiz?"}, "save_as": "telefon"},
                ],
            }
        ],
        "fallback": {"uz": "Tushunmadim."},
    }
    instance = TenantBot(
        {
            "bot_id": 7,
            "restaurant_id": 70,
            "restaurant_name": "Test",
            "token": "7:x",
            "languages": ["uz", "ru"],
            "tone": None,
            "config": config,
            "config_version": "v1",
        },
        crm=None,  # type: ignore[arg-type]
    )

    check("ikki til qabul qilindi", instance.languages == ["uz", "ru"], instance.languages)
    check("o'zbekcha salom", pick(config["welcome"], "uz") == "Salom!")
    check("ruscha salom", pick(config["welcome"], "ru") == "Привет!")
    check(
        "til yo'q bo'lsa birinchisiga tushadi",
        pick(config["welcome"], "en") == "Salom!",
        pick(config["welcome"], "en"),
    )

    keyboard = instance._menu_kb("ru")
    labels = [b.text for row in keyboard.inline_keyboard for b in row]
    check("tugmalar tanlangan tilda", labels == ["📋 Меню", "🪑 Бронь"], labels)

    check("mavjud oqim topildi", instance._find_flow("booking") is not None)
    check("yo'q oqim None qaytaradi", instance._find_flow("yoq") is None)

    empty = TenantBot(
        {**instance.spec, "config": {}, "config_version": "v0"}, crm=None  # type: ignore[arg-type]
    )
    check(
        "bo'sh konfiguratsiyada ham klaviatura yasaladi",
        len(empty._menu_kb("uz").inline_keyboard) >= 1,
    )


# ---------------------------------------------------------------------------
# 5: backend zanjiri
# ---------------------------------------------------------------------------


async def test_backend_chain() -> None:
    print("\n5) Backend zanjiri: anketa -> runners -> lead")

    crm = CrmClient("http://test", SHARED_SECRET)
    await crm._client.aclose()
    crm._client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=backend_app), base_url="http://test", timeout=30
    )

    owner_id = 810001
    await crm.sync_user(owner_id, language="uz", full_name="Runner Egasi")
    registration = await crm.register_restaurant(
        {
            "user": {"telegram_id": owner_id, "full_name": "Runner Egasi", "language": "uz"},
            "name": "Runner Kafe",
            "work_hours": "09:00-22:00",
        }
    )
    restaurant_id = registration["restaurant"]["id"]

    instance = await crm.submit_bot_questionnaire(
        owner_id, restaurant_id, "Buyurtma qabul qilish", ["uz"], ["menyu"], "do'stona"
    )
    bot_id = instance["id"]
    check("anketa saqlandi", instance["has_generated_config"])

    # Token ulanmagan bot runner ro'yxatiga tushmasligi kerak
    configs = await crm.runner_configs()
    check("tokensiz bot ro'yxatda yo'q", all(c["bot_id"] != bot_id for c in configs), configs)

    # Tokenni to'g'ridan-to'g'ri bazaga qo'yamiz (Telegram tekshiruvisiz)
    from sqlalchemy import select

    from app.core.security import encrypt_secret
    from app.db.session import SessionLocal
    from app.models import BotInstance, BotStatus

    async with SessionLocal() as db:
        row = await db.scalar(select(BotInstance).where(BotInstance.id == bot_id))
        row.token_encrypted = encrypt_secret("999888777:AAtest-tenant-token-xxxxxxxxxxxxxxx")
        row.token_hint = "xxxx"
        row.bot_username = "runner_test_bot"
        row.bot_user_id = 999888777
        row.status = BotStatus.ACTIVE
        await db.commit()

    configs = await crm.runner_configs()
    mine = next((c for c in configs if c["bot_id"] == bot_id), None)
    check("faollashgan bot ro'yxatga tushdi", mine is not None)
    check("token deshifrlandi", mine and mine["token"].startswith("999888777:"))
    check("config_version bor", bool(mine and mine.get("config_version")), mine)
    check("konfiguratsiya bo'sh emas", bool(mine and mine["config"].get("welcome")), mine)

    version_before = mine["config_version"]

    # Anketa yangilansa versiya ham o'zgarishi kerak — runner shunga qarab
    # botni qayta ko'taradi
    await asyncio.sleep(1.05)
    await crm.submit_bot_questionnaire(
        owner_id, restaurant_id, "Endi bron qilish uchun", ["uz", "ru"], ["bron"], "rasmiy"
    )
    configs = await crm.runner_configs()
    mine = next(c for c in configs if c["bot_id"] == bot_id)
    check("anketa o'zgargach versiya o'zgardi", mine["config_version"] != version_before,
          f"{version_before} -> {mine['config_version']}")

    print("\n6) Lead egasiga yetadi")
    await crm.submit_lead(
        bot_id=bot_id,
        telegram_id=850001,
        flow_id="booking",
        flow_label="Bron qilish",
        answers={"Nechchi kishi": "4", "Sana": "17-avgust 19:00"},
        customer_name="Mijoz Aliyev",
    )

    messages = await crm.fetch_outbox()
    lead = next((m for m in messages if m["kind"] == "tenant_lead"), None)
    check("outboxda lead bor", lead is not None, [m["kind"] for m in messages])
    check("egasiga yo'naltirilgan", lead and lead["telegram_id"] == owner_id, lead)

    rendered = _render("tenant_lead", lead["payload"], "uz") if lead else ""
    check("xabar matnga aylandi", "Bron qilish" in rendered, rendered)
    check("javoblar ro'yxati bor", "Nechchi kishi: 4" in rendered, rendered)
    check("mijoz ismi bor", "Mijoz Aliyev" in rendered, rendered)

    # Noto'g'ri bot_id
    try:
        await crm.submit_lead(bot_id=999999, telegram_id=1, flow_id="x", answers={})
        check("mavjud bo'lmagan bot rad etiladi", False, "xato ko'tarilmadi")
    except Exception as exc:  # noqa: BLE001
        check("mavjud bo'lmagan bot rad etiladi", getattr(exc, "status_code", None) == 404, exc)

    await crm.close()


async def main() -> int:
    async with backend_app.router.lifespan_context(backend_app):
        await test_supervisor()
        await test_config_interpretation()
        await test_backend_chain()

    print("\n" + "=" * 62)
    print(f"  Muvaffaqiyatli: {passed}   Xato: {len(failed)}")
    for name in failed:
        print(f"    - {name}")
    print("=" * 62)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Shaxsiy botlarni ko'taradi, kuzatadi va o'zgarganda qayta yuklaydi.

Har bir bot alohida asyncio vazifasi sifatida ishlaydi va o'z xatolarini o'zi
yutadi — bittasi yiqilsa qolganlari ishlab turaveradi. Yiqilgan bot ortib
boruvchi kechikish bilan qayta ko'tariladi.

Nega alohida OS process emas: 50 ta bot uchun 50 ta process ~2 GB xotira oladi
va Railway'da qimmat. Bitta event loop'da ular ~150 MB da sig'adi. Izolyatsiya
esa vazifa darajasida ta'minlanadi. Agar keyinchalik haqiqiy process kerak
bo'lsa, `TenantRunner` ni o'zgartirmasdan `multiprocessing` ga o'tkazish mumkin —
interfeys bir xil.
"""

from __future__ import annotations

import asyncio
import logging

from crm_client import CrmApiError, CrmClient
from tenant.bot import TenantBot

logger = logging.getLogger(__name__)

#: Yiqilgan botni qayta ko'tarishdan oldingi kutish (sekund)
BACKOFF_START = 5
BACKOFF_MAX = 300


class TenantRunner:
    """Bitta shaxsiy botni ushlab turadigan nazoratchi."""

    def __init__(self, spec: dict, crm: CrmClient):
        self.spec = spec
        self.crm = crm
        self.bot_id: int = spec["bot_id"]
        self.version: str = spec["config_version"]
        self.name: str = spec["restaurant_name"]
        self._task: asyncio.Task | None = None
        self._bot: TenantBot | None = None
        self._stopping = False

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"tenant-bot-{self.bot_id}")

    async def _run(self) -> None:
        delay = BACKOFF_START
        while not self._stopping:
            self._bot = TenantBot(self.spec, self.crm)
            try:
                await self._bot.start()
                logger.info("Bot #%s (%s) ishga tushdi", self.bot_id, self.name)
                delay = BACKOFF_START
                # Polling fonda ishlaydi — to'xtatilgunicha kutamiz
                while not self._stopping:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - bitta bot butun runnerni yiqitmasin
                logger.warning(
                    "Bot #%s (%s) yiqildi: %s: %s — %s soniyadan keyin qayta urinaman",
                    self.bot_id,
                    self.name,
                    type(exc).__name__,
                    exc,
                    delay,
                )
            finally:
                await self._safe_stop()

            if self._stopping:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, BACKOFF_MAX)

    async def _safe_stop(self) -> None:
        if self._bot is None:
            return
        try:
            await self._bot.stop()
        except Exception:  # noqa: BLE001
            logger.debug("Bot #%s to'xtatishda xatolik", self.bot_id)
        finally:
            self._bot = None

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
        await self._safe_stop()
        logger.info("Bot #%s (%s) to'xtatildi", self.bot_id, self.name)


class Supervisor:
    """Backenddan ro'yxatni olib, botlarni sinxronlashtiradi."""

    def __init__(self, crm: CrmClient, poll_seconds: int = 30):
        self.crm = crm
        self.poll_seconds = poll_seconds
        self._runners: dict[int, TenantRunner] = {}
        self._running = False

    @property
    def active_ids(self) -> list[int]:
        return sorted(self._runners)

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.sync_once()
            except CrmApiError as exc:
                logger.warning("Ro'yxat olinmadi: %s", exc.message)
            except Exception:  # noqa: BLE001 - sinxronlash sikli hech qachon to'xtamasin
                logger.exception("Sinxronlashda kutilmagan xatolik")
            await asyncio.sleep(self.poll_seconds)

    async def sync_once(self) -> dict[str, int]:
        """Backenddagi holat bilan ishlab turgan botlarni moslashtiradi."""
        specs = await self.crm.runner_configs()
        wanted = {spec["bot_id"]: spec for spec in specs}

        started = stopped = reloaded = 0

        # To'xtatilgan yoki o'chirilgan botlar
        for bot_id in list(self._runners):
            if bot_id not in wanted:
                await self._runners.pop(bot_id).stop()
                stopped += 1

        for bot_id, spec in wanted.items():
            runner = self._runners.get(bot_id)
            if runner is None:
                runner = TenantRunner(spec, self.crm)
                runner.start()
                self._runners[bot_id] = runner
                started += 1
            elif runner.version != spec["config_version"]:
                # Anketa yangilandi yoki token almashtirildi — qayta ko'taramiz
                logger.info("Bot #%s konfiguratsiyasi o'zgardi, qayta yuklanmoqda", bot_id)
                await runner.stop()
                runner = TenantRunner(spec, self.crm)
                runner.start()
                self._runners[bot_id] = runner
                reloaded += 1

        if started or stopped or reloaded:
            logger.info(
                "Sinxronlandi: +%d ta, -%d ta, qayta %d ta (jami %d ta bot ishlayapti)",
                started, stopped, reloaded, len(self._runners),
            )
        return {"started": started, "stopped": stopped, "reloaded": reloaded,
                "total": len(self._runners)}

    async def shutdown(self) -> None:
        self._running = False
        await asyncio.gather(*(runner.stop() for runner in self._runners.values()))
        self._runners.clear()

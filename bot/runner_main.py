"""Shaxsiy botlar runneri — alohida servis sifatida ishga tushadi.

    python runner_main.py

Asosiy botdan (main.py) mustaqil ishlaydi va o'z Telegram tokenini talab
qilmaydi: har bir mijoz botining tokenini backenddan shifrdan chiqarilgan
holda oladi.

Railway'da: shu papkadan ikkinchi servis yarating va start buyrug'ini
`python runner_main.py` qilib qo'ying.
"""

from __future__ import annotations

import asyncio
import logging
import re
import signal
import sys

from config import BOT_HMAC_SECRET, CRM_API_URL
from crm_client import CrmClient
from tenant.supervisor import Supervisor

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger("runner")

_TOKEN_RE = re.compile(r"\b\d{6,10}:[A-Za-z0-9_-]{30,}\b")


class RedactingFilter(logging.Filter):
    """Mijozlarning bot tokenlari logga tushmasin."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        if _TOKEN_RE.search(message):
            record.msg = _TOKEN_RE.sub("<bot-token>", message)
            record.args = ()
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(RedactingFilter())

POLL_SECONDS = 30


async def main() -> int:
    crm = CrmClient(CRM_API_URL, BOT_HMAC_SECRET)
    supervisor = Supervisor(crm, poll_seconds=POLL_SECONDS)

    stop_event = asyncio.Event()

    def request_stop(*_args: object) -> None:
        logger.info("To'xtatish signali qabul qilindi")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            # Windowsda add_signal_handler qo'llab-quvvatlanmaydi
            signal.signal(sig, request_stop)

    logger.info("Runner ishga tushdi | backend: %s | interval: %ds", CRM_API_URL, POLL_SECONDS)

    sync_task = asyncio.create_task(supervisor.run_forever())
    await stop_event.wait()

    logger.info("To'xtatilmoqda...")
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    await supervisor.shutdown()
    await crm.close()
    logger.info("Runner to'xtadi")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)

"""Локальний запуск (polling)."""

import asyncio
import logging

from bot.main import run_polling

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_polling())

from __future__ import annotations

import asyncio
import logging

from bot.config import MODE, require_config
from bot.factory import bootstrap, create_bot, create_dispatcher
from bot.jobs import jobs_loop


async def run_polling() -> None:
    require_config()
    bot = create_bot()
    dp = create_dispatcher()
    await bootstrap(bot)

    # Локально polling і webhook не сумісні — знімаємо webhook
    await bot.delete_webhook(drop_pending_updates=True)

    jobs_task = asyncio.create_task(jobs_loop(bot), name="kmmr-jobs")
    try:
        await dp.start_polling(bot)
    finally:
        jobs_task.cancel()
        try:
            await jobs_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if MODE == "webhook":
        # web.run_app керує event loop сам
        from bot.webhook_app import run_webhook_sync

        run_webhook_sync()
    else:
        await run_polling()


if __name__ == "__main__":
    if MODE == "webhook":
        from bot.webhook_app import run_webhook_sync

        run_webhook_sync()
    else:
        asyncio.run(run_polling())

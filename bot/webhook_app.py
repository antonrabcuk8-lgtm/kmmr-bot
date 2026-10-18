from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.config import (
    WEBAPP_HOST,
    WEBAPP_PORT,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    require_webhook_config,
    webhook_url,
)
from bot.factory import bootstrap, create_bot, create_dispatcher
from bot.jobs import jobs_loop

logger = logging.getLogger(__name__)


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "kmmr-bot"})


def build_app() -> web.Application:
    require_webhook_config()
    bot = create_bot()
    dp = create_dispatcher()

    async def on_startup(bot: Bot) -> None:
        await bootstrap(bot)
        url = webhook_url()
        await bot.set_webhook(
            url=url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        logger.info("Webhook встановлено: %s", url)

    async def on_shutdown(bot: Bot) -> None:
        logger.info("Зупинка webhook-режиму")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    ).register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    async def start_jobs(application: web.Application) -> None:
        application["jobs_task"] = asyncio.create_task(
            jobs_loop(application["bot"]),
            name="kmmr-jobs",
        )

    async def stop_jobs(application: web.Application) -> None:
        task = application.get("jobs_task")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app.on_startup.append(start_jobs)
    app.on_cleanup.append(stop_jobs)
    return app


def run_webhook_sync() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = build_app()
    logger.info(
        "Webhook server: %s:%s path=%s",
        WEBAPP_HOST,
        WEBAPP_PORT,
        WEBHOOK_PATH,
    )
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)


async def run_webhook() -> None:
    """Для сумісності з asyncio-входом; краще run_webhook_sync()."""
    run_webhook_sync()

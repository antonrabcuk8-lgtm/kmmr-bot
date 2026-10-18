from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config import ADMIN_IDS, BOT_TOKEN
from bot.db import db
from bot.handlers import setup_routers
from bot.jobs import maybe_run_jobs

logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Головне меню"),
            BotCommand(command="new", description="Залишити звернення"),
            BotCommand(command="my", description="Мої звернення"),
            BotCommand(command="help", description="Про бота"),
            BotCommand(command="cancel", description="Скасувати заповнення"),
            BotCommand(command="admin", description="Адмінка (лише для ради)"),
        ],
        scope=BotCommandScopeDefault(),
    )


def create_bot() -> Bot:
    return Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())

    @dp.update.outer_middleware()
    async def _jobs_on_update(handler, event, data):
        bot: Bot = data["bot"]
        # Не блокуємо відповідь користувачу
        asyncio.create_task(maybe_run_jobs(bot))
        return await handler(event, data)

    return dp


async def bootstrap(bot: Bot) -> None:
    await db.init()
    await setup_bot_commands(bot)
    me = await bot.get_me()
    logger.info("Бот готовий: @%s | адмінів: %s", me.username, len(ADMIN_IDS))

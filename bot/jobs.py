from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta

from aiogram import Bot

from bot.config import (
    DIGEST_DAY,
    DIGEST_HOUR,
    JOBS_INTERVAL_SEC,
    OVERDUE_DAYS,
)
from bot.backup import send_daily_backup
from bot.db import db
from bot.formatters import KYIV, format_digest, format_overdue
from bot.notify import notify_admins

logger = logging.getLogger(__name__)

_jobs_lock = asyncio.Lock()
_last_jobs_ts = 0.0


def _previous_month(now: datetime) -> tuple[int, int, str]:
    first = now.replace(day=1)
    prev = first - timedelta(days=1)
    return prev.year, prev.month, f"{prev.year:04d}-{prev.month:02d}"


async def send_monthly_digest(bot: Bot, *, force: bool = False) -> bool:
    now = datetime.now(KYIV)
    year, month, period = _previous_month(now)
    meta_key = f"digest_sent:{period}"

    if not force:
        if now.day != DIGEST_DAY or now.hour < DIGEST_HOUR:
            return False
        if await db.get_meta(meta_key):
            return False

    stats = await db.stats_month(year, month)
    text = format_digest(
        stats,
        title=f"Місячний дайджест КММР ({period})",
    )
    sent = await notify_admins(bot, text)
    if sent:
        await db.set_meta(meta_key, now.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("Дайджест %s надіслано %s адмінам", period, sent)
        return True
    logger.warning("Дайджест %s не доставлено жодному адміну", period)
    return False


async def send_overdue_reminders(bot: Bot, *, force: bool = False) -> bool:
    now = datetime.now(KYIV)
    today = now.strftime("%Y-%m-%d")
    meta_key = "overdue_reminded_day"

    if not force and await db.get_meta(meta_key) == today:
        return False

    # Нагадуємо раз на день після DIGEST_HOUR, щоб не будити вночі
    if not force and now.hour < DIGEST_HOUR:
        return False

    overdue = await db.list_overdue_new(OVERDUE_DAYS)
    if not overdue:
        if force:
            await notify_admins(
                bot,
                f"✅ Прострочених «нових» немає (поріг {OVERDUE_DAYS} днів).",
            )
        await db.set_meta(meta_key, today)
        return False

    text = format_overdue(overdue, days=OVERDUE_DAYS)
    sent = await notify_admins(bot, text)
    if sent:
        await db.set_meta(meta_key, today)
        logger.info("Нагадування про %s прострочених надіслано", len(overdue))
        return True
    return False


async def run_jobs_once(bot: Bot) -> None:
    await send_monthly_digest(bot)
    await send_overdue_reminders(bot)
    await send_daily_backup(bot)


async def maybe_run_jobs(bot: Bot) -> None:
    """Не частіше ніж раз на JOBS_INTERVAL_SEC; безпечно викликати з webhook."""
    global _last_jobs_ts
    now = time.monotonic()
    if now - _last_jobs_ts < JOBS_INTERVAL_SEC:
        return
    if _jobs_lock.locked():
        return
    async with _jobs_lock:
        now = time.monotonic()
        if now - _last_jobs_ts < JOBS_INTERVAL_SEC:
            return
        try:
            await run_jobs_once(bot)
        except Exception:
            logger.exception("Помилка у фонових задачах")
        finally:
            _last_jobs_ts = time.monotonic()


async def jobs_loop(bot: Bot) -> None:
    logger.info(
        "Фонові задачі: інтервал %ss, дайджест день=%s година=%s, overdue=%s днів",
        JOBS_INTERVAL_SEC,
        DIGEST_DAY,
        DIGEST_HOUR,
        OVERDUE_DAYS,
    )
    await asyncio.sleep(5)
    while True:
        try:
            await maybe_run_jobs(bot)
        except Exception:
            logger.exception("Помилка у циклі джобів")
        await asyncio.sleep(JOBS_INTERVAL_SEC)

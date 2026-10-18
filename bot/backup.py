from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot

from bot.db import db
from bot.formatters import KYIV
from bot.notify import notify_admins_document

logger = logging.getLogger(__name__)


async def build_backup_file() -> tuple[bytes, str, int]:
    content = await db.export_snapshot_bytes()
    count = await db.count_all()
    stamp = datetime.now(KYIV).strftime("%Y%m%d-%H%M")
    filename = f"kmmr-backup-{stamp}.json"
    return content, filename, count


async def send_daily_backup(bot: Bot, *, force: bool = False) -> bool:
    """Щоденний повний JSON-бекап усім адмінам (для збереження на ПК)."""
    now = datetime.now(KYIV)
    today = now.strftime("%Y-%m-%d")
    meta_key = "backup_sent_day"

    if not force:
        from bot.config import DIGEST_HOUR

        if now.hour < DIGEST_HOUR:
            return False
        if await db.get_meta(meta_key) == today:
            return False

    content, filename, count = await build_backup_file()
    caption = (
        f"💾 Бекап КММР за {today}\n"
        f"Звернень у файлі: {count}\n\n"
        "Збережи цей .json на ПК / у «Збережене».\n"
        "Після збою на Render відновити: /restore і надішли цей файл.\n"
        "Після відновлення /stats знову покаже ту саму статистику."
    )
    sent = await notify_admins_document(
        bot,
        content=content,
        filename=filename,
        caption=caption,
    )
    if sent:
        await db.set_meta(meta_key, today)
        logger.info("Бекап (%s звернень) надіслано %s адмінам", count, sent)
        return True
    logger.warning("Бекап не доставлено жодному адміну")
    return False

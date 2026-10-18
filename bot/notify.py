from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile

from bot.config import ADMIN_IDS

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot, text: str, *, reply_markup=None) -> int:
    """Надіслати повідомлення всім адмінам. Повертає скільки успішно."""
    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
            sent += 1
        except Exception:
            logger.warning("Не вдалося написати адміну %s", admin_id, exc_info=True)
    return sent


async def notify_admins_document(
    bot: Bot,
    *,
    content: bytes,
    filename: str,
    caption: str,
) -> int:
    """Надіслати файл усім адмінам."""
    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            document = BufferedInputFile(content, filename=filename)
            await bot.send_document(admin_id, document, caption=caption)
            sent += 1
        except Exception:
            logger.warning(
                "Не вдалося надіслати файл адміну %s", admin_id, exc_info=True
            )
    return sent

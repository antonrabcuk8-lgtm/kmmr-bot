from __future__ import annotations

import logging

from aiogram import Bot

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

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.constants import APPEAL_TYPES, DISTRICTS, STATUS_ORDER, STATUSES, TOPICS


def main_menu(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="✍️ Залишити звернення")
    builder.button(text="📂 Мої звернення")
    if is_admin:
        builder.button(text="🛠 Адмінка")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Скасувати")]],
        resize_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in APPEAL_TYPES.items():
        builder.button(text=label, callback_data=f"type:{key}")
    builder.adjust(1)
    return builder.as_markup()


def district_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name in DISTRICTS:
        builder.button(text=name, callback_data=f"district:{name}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="‹ Назад", callback_data="back:type"))
    return builder.as_markup()


def topic_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in TOPICS.items():
        builder.button(text=label, callback_data=f"topic:{key}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="‹ Назад", callback_data="back:district"))
    return builder.as_markup()


def reply_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Не потрібна відповідь", callback_data="reply:no")
    builder.button(text="Написати мені в Telegram", callback_data="reply:yes")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="‹ Назад", callback_data="back:text"))
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Надіслати", callback_data="confirm:yes")
    builder.button(text="‹ Назад", callback_data="back:reply")
    builder.button(text="Скасувати", callback_data="confirm:no")
    builder.adjust(2, 1)
    return builder.as_markup()


def admin_status_keyboard(appeal_id: int, current: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for status in STATUS_ORDER:
        if status == "new":
            continue
        mark = "✓ " if status == current else ""
        builder.button(
            text=f"{mark}{STATUSES[status]}",
            callback_data=f"status:{appeal_id}:{status}",
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text="Написати відповідь",
            callback_data=f"admin_reply:{appeal_id}",
        )
    )
    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Inbox (нові)", callback_data="admin:inbox")
    builder.button(text="📋 Останні 10", callback_data="admin:recent")
    builder.button(text="📊 Статистика місяця", callback_data="admin:stats")
    builder.adjust(1)
    return builder.as_markup()

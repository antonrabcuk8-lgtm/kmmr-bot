from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import ADMIN_IDS
from bot.constants import EMERGENCY_TEXT, HELP_EXTRA, WELCOME_TEXT
from bot.keyboards import main_menu

router = Router()


def _menu_for(user_id: int | None):
    return main_menu(is_admin=bool(user_id and user_id in ADMIN_IDS))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        WELCOME_TEXT,
        reply_markup=_menu_for(message.from_user.id if message.from_user else None),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        WELCOME_TEXT + HELP_EXTRA,
        reply_markup=_menu_for(message.from_user.id if message.from_user else None),
    )


@router.message(F.text == "🚨 Є загроза просто зараз")
@router.message(F.text == "Є загроза просто зараз")
async def emergency(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        EMERGENCY_TEXT,
        reply_markup=_menu_for(message.from_user.id if message.from_user else None),
    )


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "скасувати")
async def cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    menu = _menu_for(message.from_user.id if message.from_user else None)
    if current is None:
        await message.answer("Немає активного заповнення.", reply_markup=menu)
        return
    await state.clear()
    await message.answer("✖️ Скасовано.", reply_markup=menu)

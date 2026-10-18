from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import ADMIN_IDS, DAILY_LIMIT
from bot.db import db
from bot.formatters import (
    format_appeal_card,
    format_summary,
    format_user_appeal,
    h,
    label_topic,
    type_with_emoji,
)
from bot.notify import notify_admins
from bot.keyboards import (
    admin_status_keyboard,
    cancel_keyboard,
    confirm_keyboard,
    district_keyboard,
    main_menu,
    reply_keyboard,
    topic_keyboard,
    type_keyboard,
)
from bot.states import AppealForm

router = Router()

MAX_TEXT_LEN = 2000
MIN_TEXT_LEN = 20

MENU_TEXTS = {
    "✍️ Залишити звернення",
    "Залишити звернення",
    "📂 Мої звернення",
    "Мої звернення",
    "🛠 Адмінка",
    "Адмінка",
    "🚨 Є загроза просто зараз",
    "Є загроза просто зараз",
}


def _menu_for(user_id: int | None):
    return main_menu(is_admin=bool(user_id and user_id in ADMIN_IDS))


async def _start_form(message: Message, state: FSMContext) -> None:
    count = await db.count_today(message.from_user.id)
    if count >= DAILY_LIMIT:
        await message.answer(
            f"⏳ <b>Ліміт на сьогодні</b>\n"
            f"Максимум <b>{DAILY_LIMIT}</b> звернення на день.\n"
            "<i>Спробуй завтра.</i>",
            reply_markup=_menu_for(message.from_user.id),
        )
        return

    await state.clear()
    await state.set_state(AppealForm.choosing_type)
    await message.answer(
        "✍️ <b>Крок 1/5</b>\nОбери <b>тип</b> звернення.",
        reply_markup=cancel_keyboard(),
    )
    await message.answer("Тип:", reply_markup=type_keyboard())


@router.message(Command("new"))
@router.message(F.text.in_({"✍️ Залишити звернення", "Залишити звернення"}))
async def start_appeal(message: Message, state: FSMContext) -> None:
    await _start_form(message, state)


@router.message(Command("my"))
@router.message(F.text.in_({"📂 Мої звернення", "Мої звернення"}))
async def my_appeals(message: Message, state: FSMContext) -> None:
    await state.clear()
    appeals = await db.list_by_user(message.from_user.id, limit=10)
    menu = _menu_for(message.from_user.id)
    if not appeals:
        await message.answer(
            "📂 Поки немає збережених звернень з цього акаунта.\n"
            "Натисни <b>Залишити звернення</b>, щоб надіслати перше.",
            reply_markup=menu,
        )
        return

    await message.answer(
        f"📂 <b>Твої звернення</b> <i>({len(appeals)})</i>",
        reply_markup=menu,
    )
    for appeal in appeals:
        await message.answer(format_user_appeal(appeal))


@router.callback_query(AppealForm.choosing_type, F.data.startswith("type:"))
async def choose_type(callback: CallbackQuery, state: FSMContext) -> None:
    appeal_type = callback.data.split(":", 1)[1]
    await state.update_data(appeal_type=appeal_type)
    await state.set_state(AppealForm.choosing_district)
    await callback.message.edit_text(f"✅ Тип: <b>{h(type_with_emoji(appeal_type))}</b>")
    await callback.message.answer(
        "📍 <b>Крок 2/5</b>\nОбери <b>район</b> Києва.",
        reply_markup=district_keyboard(),
    )
    await callback.answer()


@router.callback_query(AppealForm.choosing_district, F.data.startswith("district:"))
async def choose_district(callback: CallbackQuery, state: FSMContext) -> None:
    district = callback.data.split(":", 1)[1]
    await state.update_data(district=district)
    await state.set_state(AppealForm.choosing_topic)
    await callback.message.edit_text(f"✅ Район: <b>{h(district)}</b>")
    await callback.message.answer(
        "🏷 <b>Крок 3/5</b>\nОбери <b>тему</b>.",
        reply_markup=topic_keyboard(),
    )
    await callback.answer()


@router.callback_query(AppealForm.choosing_topic, F.data.startswith("topic:"))
async def choose_topic(callback: CallbackQuery, state: FSMContext) -> None:
    topic = callback.data.split(":", 1)[1]
    await state.update_data(topic=topic)
    await state.set_state(AppealForm.entering_text)
    await callback.message.edit_text(f"✅ Тема: <b>{h(label_topic(topic))}</b>")
    await callback.message.answer(
        "📝 <b>Крок 4/5</b>\n"
        "Напиши текст звернення <b>одним повідомленням</b>\n"
        f"<i>(від {MIN_TEXT_LEN} до {MAX_TEXT_LEN} символів)</i>.\n\n"
        "Без особистих даних третіх осіб, якщо це не потрібно.",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(AppealForm.entering_text, F.text)
async def enter_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text.casefold() == "скасувати":
        return
    if len(text) < MIN_TEXT_LEN:
        await message.answer(
            f"✍️ Занадто коротко. Мінімум <b>{MIN_TEXT_LEN}</b> символів."
        )
        return
    if len(text) > MAX_TEXT_LEN:
        await message.answer(
            f"✂️ Занадто довго. Максимум <b>{MAX_TEXT_LEN}</b> символів."
        )
        return

    await state.update_data(text=text)
    await state.set_state(AppealForm.choosing_reply)
    await message.answer(
        "💬 <b>Крок 5/5</b>\n"
        "Чи потрібна відповідь у цей Telegram?\n"
        "<i>Якщо ні — звернення лишається анонімним для відповіді.</i>",
        reply_markup=reply_keyboard(),
    )


@router.message(AppealForm.entering_text)
async def enter_text_invalid(message: Message) -> None:
    await message.answer(
        "Надішли <b>текст</b> одним повідомленням або натисни «Скасувати»."
    )


@router.callback_query(AppealForm.choosing_reply, F.data.startswith("reply:"))
async def choose_reply(callback: CallbackQuery, state: FSMContext) -> None:
    wants_reply = callback.data.endswith(":yes")
    await state.update_data(wants_reply=wants_reply)
    data = await state.get_data()
    await state.set_state(AppealForm.confirming)
    await callback.message.edit_text(
        format_summary(data),
        reply_markup=confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("back:"))
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    target = callback.data.split(":", 1)[1]
    current = await state.get_state()
    if current is None:
        await callback.answer("Форма вже закрита", show_alert=True)
        return

    if target == "type":
        await state.set_state(AppealForm.choosing_type)
        await callback.message.edit_text(
            "✍️ <b>Крок 1/5</b>\nОбери <b>тип</b> звернення.",
            reply_markup=type_keyboard(),
        )
    elif target == "district":
        await state.set_state(AppealForm.choosing_district)
        await callback.message.edit_text(
            "📍 <b>Крок 2/5</b>\nОбери <b>район</b> Києва.",
            reply_markup=district_keyboard(),
        )
    elif target == "text":
        await state.set_state(AppealForm.entering_text)
        await callback.message.edit_text(
            "📝 <b>Крок 4/5</b>\nНапиши текст звернення ще раз одним повідомленням."
        )
        await callback.message.answer("Чекаю на текст:", reply_markup=cancel_keyboard())
    elif target == "reply":
        await state.set_state(AppealForm.choosing_reply)
        await callback.message.edit_text(
            "💬 <b>Крок 5/5</b>\nЧи потрібна відповідь у цей Telegram?",
            reply_markup=reply_keyboard(),
        )
    else:
        await callback.answer("Невідомий крок", show_alert=True)
        return
    await callback.answer()


@router.callback_query(AppealForm.confirming, F.data == "confirm:no")
async def confirm_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("✖️ Звернення скасовано.")
    await callback.message.answer(
        "Можеш почати знову.",
        reply_markup=_menu_for(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(AppealForm.confirming, F.data == "confirm:yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    user = callback.from_user

    count = await db.count_today(user.id)
    if count >= DAILY_LIMIT:
        await state.clear()
        await callback.message.edit_text(
            f"⏳ Ліміт на сьогодні вичерпано: <b>{DAILY_LIMIT}</b> звернення."
        )
        await callback.message.answer(
            "Спробуй завтра.",
            reply_markup=_menu_for(user.id),
        )
        await callback.answer()
        return

    appeal = await db.create_appeal(
        user_id=user.id,
        username=user.username,
        appeal_type=data["appeal_type"],
        district=data["district"],
        topic=data["topic"],
        text=data["text"],
        wants_reply=bool(data.get("wants_reply")),
    )
    await state.clear()

    reply_note = (
        "Ми напишемо сюди, коли статус зміниться або з’явиться відповідь."
        if appeal.wants_reply
        else "Ти все одно можеш дивитися статус у «Мої звернення»."
    )
    await callback.message.edit_text(
        f"✅ <b>Звернення прийнято</b>\n"
        f"Номер: <code>{h(appeal.public_id)}</code>\n\n"
        f"{h(reply_note)}\n"
        "⏱ Перша реакція ради — зазвичай <b>до 7 днів</b>."
    )
    await callback.message.answer(
        "Готово. Можеш надіслати ще одне або перевірити статус пізніше.",
        reply_markup=_menu_for(user.id),
    )
    await callback.answer("Надіслано")

    card = format_appeal_card(appeal, for_admin=True)
    await notify_admins(
        bot,
        "🔔 <b>Нове звернення</b>\n\n" + card,
        reply_markup=admin_status_keyboard(appeal.id, current=appeal.status),
    )


@router.message(StateFilter(AppealForm), F.text)
async def ignore_text_during_buttons(message: Message) -> None:
    if message.text and message.text.casefold() == "скасувати":
        return
    if message.text in MENU_TEXTS:
        return
    await message.answer(
        "Зараз потрібна відповідь <b>кнопкою</b> вище, або натисни «Скасувати»."
    )

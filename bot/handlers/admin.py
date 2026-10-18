from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.config import ADMIN_IDS, OVERDUE_DAYS
from bot.constants import STATUSES
from bot.db import db
from bot.formatters import (
    format_appeal_card,
    format_digest,
    format_overdue,
    format_stats,
    format_status_update,
    h,
    label_status,
    status_with_emoji,
)
from bot.jobs import send_monthly_digest
from bot.keyboards import admin_menu_keyboard, admin_status_keyboard, main_menu
from bot.states import AdminReply

router = Router()


class IsAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user and user.id in ADMIN_IDS)


def _normalize_public_id(raw: str) -> str:
    value = raw.strip()
    upper = value.upper()
    if upper.startswith("KMMR-"):
        return "КММР-" + value.split("-", 1)[1]
    if value.isdigit():
        return f"КММР-{int(value):04d}"
    return value


async def _send_appeals(target: Message, appeals: list, empty_text: str) -> None:
    if not appeals:
        await target.answer(empty_text)
        return
    for appeal in appeals:
        await target.answer(
            format_appeal_card(appeal, for_admin=True),
            reply_markup=admin_status_keyboard(appeal.id, current=appeal.status),
        )


@router.message(Command("admin"), IsAdmin())
@router.message(F.text.in_({"🛠 Адмінка", "Адмінка"}), IsAdmin())
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    open_new = await db.count_status("new")
    await message.answer(
        "🛠 <b>Адмінка КММР</b>\n\n"
        f"🆕 Зараз нових: <b>{open_new}</b>\n"
        f"👥 Адмінів у системі: <b>{len(ADMIN_IDS)}</b>\n\n"
        "<b>Команди</b>\n"
        "/inbox — лише нові\n"
        "/list — останні 10\n"
        "/stats — статистика місяця\n"
        "/export — CSV за місяць\n"
        "/get КММР-0001 — картка\n"
        "/reply КММР-0001 текст — відповідь\n"
        "/digest — надіслати дайджест за минулий місяць\n"
        "/overdue — нагадування про «нові» старше 7 днів\n"
        "/admins — хто в ADMIN_IDS",
        reply_markup=admin_menu_keyboard(),
    )
    await message.answer("Меню:", reply_markup=main_menu(is_admin=True))


@router.message(Command("stats"), IsAdmin())
@router.callback_query(F.data == "admin:stats", IsAdmin())
async def cmd_stats(event: Message | CallbackQuery) -> None:
    stats = await db.stats_month()
    text = format_stats(stats)
    if isinstance(event, CallbackQuery):
        await event.message.answer(text)
        await event.answer()
    else:
        await event.answer(text)


@router.message(Command("inbox"), IsAdmin())
@router.callback_query(F.data == "admin:inbox", IsAdmin())
async def cmd_inbox(event: Message | CallbackQuery) -> None:
    appeals = await db.list_by_status("new", limit=15)
    target = event.message if isinstance(event, CallbackQuery) else event
    await _send_appeals(
        target, appeals, "📭 Inbox порожній — нових звернень немає."
    )
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("list"), IsAdmin())
@router.callback_query(F.data == "admin:recent", IsAdmin())
async def cmd_list(event: Message | CallbackQuery) -> None:
    appeals = await db.list_recent(10)
    target = event.message if isinstance(event, CallbackQuery) else event
    await _send_appeals(target, appeals, "📭 Звернень ще немає.")
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("get"), IsAdmin())
async def cmd_get(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Використання: /get КММР-0001")
        return

    public_id = _normalize_public_id(parts[1])
    appeal = await db.get_by_public_id(public_id)
    if not appeal:
        await message.answer("Звернення не знайдено.")
        return

    await message.answer(
        format_appeal_card(appeal, for_admin=True),
        reply_markup=admin_status_keyboard(appeal.id, current=appeal.status),
    )


@router.message(Command("digest"), IsAdmin())
async def cmd_digest(message: Message, bot: Bot) -> None:
    """Примусово надіслати дайджест минулого місяця всім адмінам."""
    ok = await send_monthly_digest(bot, force=True)
    if ok:
        await message.answer("📬 Дайджест за минулий місяць розіслано всім адмінам.")
    else:
        # все одно покажемо локально, якщо розсилка впала
        from datetime import timedelta

        from bot.formatters import KYIV

        now = datetime.now(KYIV)
        prev = now.replace(day=1) - timedelta(days=1)
        stats = await db.stats_month(prev.year, prev.month)
        await message.answer(
            format_digest(
                stats,
                title=f"Дайджест КММР ({prev.year:04d}-{prev.month:02d})",
            )
        )
        await message.answer(
            "Розсилка іншим адмінам не пройшла "
            "(можливо, вони ще не натиснули /start)."
        )


@router.message(Command("overdue"), IsAdmin())
async def cmd_overdue(message: Message) -> None:
    overdue = await db.list_overdue_new(OVERDUE_DAYS)
    if not overdue:
        await message.answer(
            f"✅ Прострочених «нових» немає (поріг {OVERDUE_DAYS} днів)."
        )
        return
    await message.answer(format_overdue(overdue, days=OVERDUE_DAYS))


@router.message(Command("admins"), IsAdmin())
async def cmd_admins(message: Message) -> None:
    ids = sorted(ADMIN_IDS)
    lines = [
        "👥 <b>Адміни бота</b>",
        f"Усього: <b>{len(ids)}</b>",
        "",
        "Щоб додати колегу з комісії — у файлі <code>.env</code>:",
        "<code>ADMIN_IDS=твій_id,id_колеги</code>",
        "потім перезапусти бота.",
        "",
        "Список ID:",
    ]
    for admin_id in ids:
        mark = " ← ти" if message.from_user and admin_id == message.from_user.id else ""
        lines.append(f"• <code>{admin_id}</code>{mark}")
    await message.answer("\n".join(lines))


@router.message(Command("export"), IsAdmin())
async def cmd_export(message: Message) -> None:
    now = datetime.now(timezone.utc)
    csv_text = await db.export_csv(now.year, now.month)
    content = csv_text.encode("utf-8-sig")
    filename = f"kmmr-appeals-{now.year:04d}-{now.month:02d}.csv"
    document = BufferedInputFile(content, filename=filename)
    await message.answer_document(
        document,
        caption=f"Експорт звернень за {now.year:04d}-{now.month:02d}",
    )


@router.message(Command("reply"), IsAdmin())
async def cmd_reply(message: Message, bot: Bot) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Використання:\n/reply КММР-0001 Текст відповіді для людини"
        )
        return

    public_id = _normalize_public_id(parts[1])
    text = parts[2].strip()
    appeal = await db.get_by_public_id(public_id)
    if not appeal:
        await message.answer("Звернення не знайдено.")
        return
    if len(text) < 3:
        await message.answer("Текст відповіді занадто короткий.")
        return

    updated = await db.set_status(appeal.id, "answered", admin_note=text)
    assert updated is not None
    await message.answer(
        format_appeal_card(updated, for_admin=True),
        reply_markup=admin_status_keyboard(updated.id, current=updated.status),
    )

    if updated.user_id and updated.wants_reply:
        try:
            await bot.send_message(
                updated.user_id,
                format_status_update(updated, custom_text=text),
            )
            await message.answer("Відповідь надіслано користувачу.")
        except Exception:
            await message.answer(
                "Статус оновлено, але не вдалося написати користувачу "
                "(можливо, заблокував бота)."
            )
    else:
        await message.answer(
            "Статус оновлено. Користувач не просив відповідь у Telegram — "
            "текст збережено в нотатці."
        )


@router.callback_query(F.data.startswith("admin_reply:"), IsAdmin())
async def start_admin_reply(callback: CallbackQuery, state: FSMContext) -> None:
    appeal_id = int(callback.data.split(":")[1])
    appeal = await db.get_by_id(appeal_id)
    if not appeal:
        await callback.answer("Не знайдено", show_alert=True)
        return
    await state.set_state(AdminReply.waiting_text)
    await state.update_data(reply_appeal_id=appeal_id)
    await callback.message.answer(
        f"💬 Напиши текст відповіді для <code>{h(appeal.public_id)}</code> "
        "одним повідомленням.\n"
        "Після цього статус стане <b>Є відповідь</b>.\n"
        "<i>Або /cancel щоб скасувати.</i>"
    )
    await callback.answer()


@router.message(AdminReply.waiting_text, IsAdmin(), F.text)
async def receive_admin_reply(message: Message, state: FSMContext, bot: Bot) -> None:
    if (message.text or "").startswith("/"):
        return
    data = await state.get_data()
    appeal_id = data.get("reply_appeal_id")
    if not appeal_id:
        await state.clear()
        await message.answer("Сесію відповіді скинуто.")
        return

    text = (message.text or "").strip()
    if len(text) < 3:
        await message.answer("Занадто коротко. Напиши відповідь ще раз.")
        return

    updated = await db.set_status(int(appeal_id), "answered", admin_note=text)
    await state.clear()
    if not updated:
        await message.answer("Звернення не знайдено.")
        return

    await message.answer(
        format_appeal_card(updated, for_admin=True),
        reply_markup=admin_status_keyboard(updated.id, current=updated.status),
    )

    if updated.user_id and updated.wants_reply:
        try:
            await bot.send_message(
                updated.user_id,
                format_status_update(updated, custom_text=text),
            )
            await message.answer("Відповідь надіслано користувачу.")
        except Exception:
            await message.answer(
                "Збережено, але користувачу не вдалося написати."
            )
    else:
        await message.answer("Збережено в нотатці (користувач не просив відповідь).")


@router.callback_query(F.data.startswith("status:"), IsAdmin())
async def set_status(callback: CallbackQuery, bot: Bot) -> None:
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некоректні дані", show_alert=True)
        return

    try:
        appeal_id = int(parts[1])
    except ValueError:
        await callback.answer("Некоректний ID", show_alert=True)
        return

    status = parts[2]
    if status not in STATUSES:
        await callback.answer("Невідомий статус", show_alert=True)
        return

    appeal = await db.set_status(appeal_id, status)
    if not appeal:
        await callback.answer("Звернення не знайдено", show_alert=True)
        return

    await callback.message.edit_text(
        format_appeal_card(appeal, for_admin=True)
        + f"\n\n✅ Оновлено: <b>{h(status_with_emoji(status))}</b>",
        reply_markup=admin_status_keyboard(appeal.id, current=appeal.status),
    )
    await callback.answer(f"Статус: {label_status(status)}")

    if appeal.wants_reply and appeal.user_id:
        try:
            await bot.send_message(
                appeal.user_id,
                format_status_update(appeal),
            )
        except Exception:
            await callback.message.answer(
                f"Статус змінено, але не вдалося написати користувачу "
                f"по {appeal.public_id}."
            )


@router.message(Command("admin"))
@router.message(Command("stats"))
@router.message(Command("list"))
@router.message(Command("inbox"))
@router.message(Command("get"))
@router.message(Command("export"))
@router.message(Command("reply"))
@router.message(Command("digest"))
@router.message(Command("overdue"))
@router.message(Command("admins"))
@router.message(F.text.in_({"🛠 Адмінка", "Адмінка"}))
async def admin_denied(message: Message) -> None:
    await message.answer("⛔️ Ця команда лише для адміністраторів бота.")


@router.message(StateFilter(AdminReply.waiting_text))
async def admin_reply_non_admin(message: Message, state: FSMContext) -> None:
    if message.from_user and message.from_user.id in ADMIN_IDS:
        return
    await state.clear()

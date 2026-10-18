from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot.constants import (
    APPEAL_TYPES,
    STATUS_EMOJI,
    STATUS_USER_HINTS,
    STATUSES,
    TOPICS,
    TYPE_EMOJI,
)
from bot.db import Appeal


def _kyiv_tz():
    try:
        return ZoneInfo("Europe/Kyiv")
    except ZoneInfoNotFoundError:
        try:
            return ZoneInfo("Europe/Kiev")
        except ZoneInfoNotFoundError:
            return timezone(timedelta(hours=2))


KYIV = _kyiv_tz()


def h(value: object) -> str:
    return escape(str(value), quote=False)


def label_type(value: str) -> str:
    return APPEAL_TYPES.get(value, value)


def label_topic(value: str) -> str:
    return TOPICS.get(value, value)


def label_status(value: str) -> str:
    return STATUSES.get(value, value)


def type_with_emoji(value: str) -> str:
    return f"{TYPE_EMOJI.get(value, '📌')} {label_type(value)}"


def status_with_emoji(value: str) -> str:
    return f"{STATUS_EMOJI.get(value, '•')} {label_status(value)}"


def format_kyiv_time(utc_str: str) -> str:
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(KYIV).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return utc_str


def format_summary(data: dict) -> str:
    reply = "так, у Telegram" if data.get("wants_reply") else "не потрібна"
    return (
        "📝 <b>Перевір звернення</b>\n"
        "<i>перед надсиланням</i>\n\n"
        f"<b>Тип:</b> {h(type_with_emoji(data['appeal_type']))}\n"
        f"<b>Район:</b> {h(data['district'])}\n"
        f"<b>Тема:</b> {h(label_topic(data['topic']))}\n"
        f"<b>Відповідь:</b> {h(reply)}\n\n"
        f"<b>Текст:</b>\n{h(data['text'])}"
    )


def format_appeal_card(appeal: Appeal, *, for_admin: bool = False) -> str:
    reply = "так" if appeal.wants_reply else "ні"
    lines = [
        f"📬 <b>{h(appeal.public_id)}</b>",
        f"🗓 {h(format_kyiv_time(appeal.created_at))} <i>(Київ)</i>",
        f"<b>Тип:</b> {h(type_with_emoji(appeal.appeal_type))}",
        f"<b>Район:</b> {h(appeal.district)}",
        f"<b>Тема:</b> {h(label_topic(appeal.topic))}",
        f"<b>Статус:</b> {h(status_with_emoji(appeal.status))}",
        f"<b>Потрібна відповідь:</b> {h(reply)}",
        "",
        h(appeal.text),
    ]
    if for_admin:
        if appeal.username:
            lines.insert(2, f"👤 Telegram: @{h(appeal.username)}")
        elif appeal.wants_reply and appeal.user_id:
            lines.insert(2, f"👤 Telegram ID: <code>{appeal.user_id}</code>")
        else:
            lines.insert(2, "🔒 Контакт: <i>анонімно</i>")
        if appeal.admin_note:
            lines.extend(["", f"💬 <b>Відповідь / нотатка:</b>\n{h(appeal.admin_note)}"])
    return "\n".join(lines)


def format_user_appeal(appeal: Appeal) -> str:
    hint = STATUS_USER_HINTS.get(appeal.status, "")
    text = appeal.text if len(appeal.text) <= 280 else appeal.text[:277] + "..."
    lines = [
        f"📬 <b>{h(appeal.public_id)}</b>",
        f"🗓 {h(format_kyiv_time(appeal.created_at))}",
        f"{h(type_with_emoji(appeal.appeal_type))} · "
        f"{h(label_topic(appeal.topic))} · {h(appeal.district)}",
        f"<b>Статус:</b> {h(status_with_emoji(appeal.status))}",
    ]
    if hint:
        lines.append(f"<i>{h(hint)}</i>")
    lines.extend(["", h(text)])
    if appeal.admin_note and appeal.status in {"answered", "not_our_scope", "sent_to_city"}:
        lines.extend(["", f"💬 <b>Коментар ради:</b>\n{h(appeal.admin_note)}"])
    return "\n".join(lines)


def format_status_update(appeal: Appeal, *, custom_text: str | None = None) -> str:
    hint = STATUS_USER_HINTS.get(appeal.status, "")
    lines = [
        f"🔔 <b>Оновлення</b> по {h(appeal.public_id)}",
        f"<b>Статус:</b> {h(status_with_emoji(appeal.status))}",
    ]
    if hint:
        lines.append(f"<i>{h(hint)}</i>")
    if custom_text:
        lines.extend(["", f"💬 {h(custom_text)}"])
    elif appeal.admin_note and appeal.status in {"answered", "not_our_scope"}:
        lines.extend(["", f"💬 {h(appeal.admin_note)}"])
    lines.extend(
        ["", "Дякуємо, що звернулися до <b>Київської Міської Молодіжної Ради</b>."]
    )
    return "\n".join(lines)


def format_stats(stats: dict) -> str:
    lines = [
        f"📊 <b>Статистика</b> за <code>{h(stats['period'])}</code>",
        f"Усього: <b>{stats['total']}</b>",
        f"Нових зараз: <b>{stats.get('open_new', 0)}</b>",
        "",
        "<b>За типом</b>",
    ]
    if stats["by_type"]:
        for key, cnt in stats["by_type"]:
            lines.append(f"• {h(type_with_emoji(key))} — <b>{cnt}</b>")
    else:
        lines.append("• <i>немає даних</i>")

    lines.append("")
    lines.append("<b>За темою</b>")
    if stats["by_topic"]:
        for key, cnt in stats["by_topic"]:
            lines.append(f"• {h(label_topic(key))} — <b>{cnt}</b>")
    else:
        lines.append("• <i>немає даних</i>")

    lines.append("")
    lines.append("<b>За районом</b>")
    if stats["by_district"]:
        for name, cnt in stats["by_district"][:10]:
            lines.append(f"• {h(name)} — <b>{cnt}</b>")
    else:
        lines.append("• <i>немає даних</i>")

    lines.append("")
    lines.append("<b>За статусом</b>")
    if stats["by_status"]:
        for key, cnt in stats["by_status"]:
            lines.append(f"• {h(status_with_emoji(key))} — <b>{cnt}</b>")
    else:
        lines.append("• <i>немає даних</i>")

    return "\n".join(lines)


def format_digest(stats: dict, *, title: str | None = None) -> str:
    header = title or f"Автодайджест за {stats['period']}"
    lines = [
        f"🗞 <b>{h(header)}</b>",
        f"Період: <code>{h(stats['period'])}</code>",
        f"Усього звернень: <b>{stats['total']}</b>",
        "",
        "<b>Топ тем</b>",
    ]
    if stats["by_topic"]:
        for key, cnt in stats["by_topic"][:5]:
            lines.append(f"• {h(label_topic(key))} — <b>{cnt}</b>")
    else:
        lines.append("• <i>немає даних</i>")

    lines.append("")
    lines.append("<b>Топ районів</b>")
    if stats["by_district"]:
        for name, cnt in stats["by_district"][:5]:
            lines.append(f"• {h(name)} — <b>{cnt}</b>")
    else:
        lines.append("• <i>немає даних</i>")

    lines.append("")
    lines.append("<b>За типом</b>")
    if stats["by_type"]:
        for key, cnt in stats["by_type"]:
            lines.append(f"• {h(type_with_emoji(key))} — <b>{cnt}</b>")
    else:
        lines.append("• <i>немає даних</i>")

    lines.extend(
        [
            "",
            "<i>Можна взяти цей текст за основу для дайджесту ради / Instagram.</i>",
            "Деталі: /export · /stats",
        ]
    )
    return "\n".join(lines)


def format_overdue(appeals: list[Appeal], *, days: int) -> str:
    lines = [
        "⏰ <b>Нагадування</b>",
        f"Звернень зі статусом <b>Нове</b> довше {days} днів: "
        f"<b>{len(appeals)}</b>",
        "",
    ]
    for appeal in appeals[:20]:
        lines.append(
            f"• <code>{h(appeal.public_id)}</code> — "
            f"{h(label_topic(appeal.topic))} · {h(appeal.district)} · "
            f"{h(format_kyiv_time(appeal.created_at))}"
        )
    if len(appeals) > 20:
        lines.append(f"… і ще {len(appeals) - 20}")
    lines.extend(["", "Відкрий /inbox або /get КММР-0001"])
    return "\n".join(lines)

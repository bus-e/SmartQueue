"""Тексты и кнопки бота. Чистые функции — без Telegram и сети, поэтому проверяются модульными тестами.

Кнопка — пара (подпись, callback_data). callback_data короткая: «действие:аргумент».
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

Button = tuple[str, str]
Keyboard = list[list[Button]]


def ordinal(n: int) -> str:
    return f"{n}-й"


def people(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} человек"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} человека"
    return f"{n} человек"


def _due(iso: str | None, now: datetime) -> bool:
    return bool(iso) and datetime.fromisoformat(iso) <= now  # type: ignore[arg-type]


def card(queue: dict, me: dict | None, now: datetime | None = None) -> tuple[str, Keyboard]:
    """Карточка очереди для участника или оператора."""
    now = now or datetime.now(timezone.utc)
    code, title = queue["code"], escape(queue["title"])
    head = f"<b>{title}</b> · <code>{code}</code>"

    if queue["status"] == "closed":
        return f"{head}\n\nОчередь завершена.", []

    if queue.get("role") in ("owner", "operator"):
        text = f"{head}\n\nТы оператор. В очереди — {people(queue['waiting'])}."
        kb: Keyboard = [
            [("Вызвать следующего", f"c:{code}")],
            [("Кто в очереди", f"w:{code}"), ("Обновить", f"r:{code}")],
        ]
        if queue["role"] == "owner":
            kb.append([("Закрыть очередь", f"x:{code}")])
        return text, kb

    if me is None:
        text = f"{head}\n\nВ очереди — {people(queue['waiting'])}. Встанешь?"
        return text, [[("Встать в очередь", f"j:{code}")]]

    eid, pos = me["id"], me["position"]
    kb = [[("Кто в очереди", f"w:{code}"), ("Обновить", f"r:{code}")]]
    if me["status"] == "called":
        text = f"{head}\n\n🔔 <b>Тебя вызывают.</b> Подходи."
    elif pos == 1 and me.get("can_next"):
        text = f"{head}\n\n<b>Твоя очередь.</b> Зайди, а когда выйдешь — нажми «Следующий»."
        kb.insert(0, [("Следующий", f"n:{eid}")])
    elif pos == 1:
        text = f"{head}\n\n<b>Ты первый.</b> Тебя скоро вызовут."
    else:
        ahead = me["ahead"]
        text = f"{head}\n\nТы <b>{ordinal(pos)}</b>. Перед тобой — {people(ahead)}."
        if queue.get("now_serving"):
            text += f"\nСейчас у двери: {escape(queue['now_serving'])}."
        if pos == 2:
            text += "\nТы следующий — подходи к двери."
        if _due(me.get("take_over_at"), now):
            text += (
                "\n\nПервый не нажимает «Следующий» больше 10 минут. Если он уже прошёл — забери управление."
            )
            kb.insert(0, [("Забрать управление", f"t:{me['first_id']}")])
    kb.append([("Выйти из очереди", f"l:{eid}")])
    return text, kb


def who(queue: dict, entries: list[dict]) -> str:
    """Список очереди. Имена других видят только управляющие — остальным «участник»."""
    lines = [f"<b>{escape(queue['title'])}</b> · кто в очереди:"]
    for e in entries:
        name = escape(e["name"]) if e.get("name") else "участник"
        mark = " ← ты" if e.get("is_me") else ""
        state = " (вызван)" if e["status"] == "called" else ""
        lines.append(f"{e['position'] or '·'}. {name}{state}{mark}")
    if len(lines) == 1:
        lines.append("пока никого")
    return "\n".join(lines)


HELP = (
    "Я помогаю стоять в очереди, не стоя под дверью.\n\n"
    "• Отсканируй QR у двери или пришли код очереди — 6 символов, например <code>K7M2QX</code>.\n"
    "• /new — создать свою очередь.\n"
    "• /my — мои очереди."
)

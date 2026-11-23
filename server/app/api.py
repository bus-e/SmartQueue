"""API v1: гость, очереди, записи. Адреса и коды ответов — по документу «API SmartQueue».

Кто вызывает:
- сайт и приложение — заголовок X-Guest-Token (выдаёт POST /auth/guest);
- Telegram-бот — служебный ключ X-Bot-Key и X-Telegram-Id (имя — X-Telegram-Name).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from app.domain.model import (
    Conflict,
    DomainError,
    Entry,
    EntryStatus,
    Forbidden,
    Queue,
    QueueType,
    Source,
)
from app.store import MemoryStore, NotFound, User

router = APIRouter(prefix="/api/v1")


class Unauthorized(DomainError):
    """Нет или неверный токен (HTTP 401)."""


# ---------------------------------------------------------------- зависимости
def store(request: Request) -> MemoryStore:
    return request.app.state.store


def current_user(
    s: MemoryStore = Depends(store),
    x_guest_token: Optional[str] = Header(None),
    x_bot_key: Optional[str] = Header(None),
    x_telegram_id: Optional[int] = Header(None),
    x_telegram_name: Optional[str] = Header(None),
) -> User:
    with s.tx():
        if x_bot_key is not None:
            if x_bot_key != os.environ.get("BOT_KEY", "") or not x_bot_key or x_telegram_id is None:
                raise Unauthorized("Неверный ключ бота")
            return s.telegram_user(x_telegram_id, unquote(x_telegram_name or ""))
        if x_guest_token:
            user = s.by_token(x_guest_token)
            if user:
                return user
        raise Unauthorized("Нужен вход: POST /api/v1/auth/guest")


# ---------------------------------------------------------------- модели запросов
class GuestIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class QueueIn(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    type: QueueType = QueueType.REGULAR
    notify_before: int = Field(2, ge=1, le=10)
    source: Source = Source.SITE


class QueuePatch(BaseModel):
    status: Literal["closed"]


class EntryIn(BaseModel):
    source: Source = Source.SITE
    name: Optional[str] = Field(None, max_length=50)  # только для ручной записи оператором


class EntryPatch(BaseModel):
    status: Literal["served", "left", "removed"]


# ---------------------------------------------------------------- ответы
def queue_view(s: MemoryStore, q: Queue, user: User | None = None) -> dict:
    w = q.waiting()
    first = w[0] if w else None
    view = {
        "code": q.code.value,
        "title": q.title,
        "type": q.type.value,
        "status": q.status.value,
        "waiting": len(w),
        "notify_before": q.notify_before.value,
        "now_serving": _name(s, first) if first and q.type is QueueType.REGULAR else None,
    }
    if user:
        view["role"] = (
            q.staff[user.id].value if user.id in q.staff else ("creator" if q.creator == user.id else None)
        )
    return view


def entry_view(s: MemoryStore, q: Queue, e: Entry, user: User | None, show_names: bool) -> dict:
    pos = q.position(e)
    mine = user is not None and e.participant == user.id
    take_at: datetime | None = q.take_over_at()
    return {
        "id": s.entry_id(q, e),
        "code": q.code.value,
        "number": e.number,
        "status": e.status.value,
        "position": pos,
        "ahead": pos - 1 if pos else None,
        "name": _name(s, e) if show_names or mine else None,
        "source": e.source.value,
        "joined_at": e.joined_at.isoformat(),
        "is_me": mine,
        "can_next": mine and pos == 1 and q.type is QueueType.REGULAR,
        "take_over_at": take_at.isoformat() if mine and pos == 2 and take_at else None,
        "first_id": s.entry_id(q, q.waiting()[0]) if mine and pos == 2 and take_at else None,
    }


def _name(s: MemoryStore, e: Entry) -> str:
    u = s.user(e.participant)
    return e.guest_name or (u.name if u else "Участник")


def _is_manager(q: Queue, user: User) -> bool:
    return user.id in q.managers() or user.id in q.staff


# ---------------------------------------------------------------- гость
@router.post("/auth/guest", status_code=201, tags=["вход"])
def guest(body: GuestIn, s: MemoryStore = Depends(store)) -> dict:
    """Выдать токен гостя: вход без регистрации, только имя."""
    with s.tx():
        user, token = s.new_guest(body.name)
        return {"token": token, "user": {"id": user.id, "name": user.name}}


@router.get("/me/queues", tags=["вход"])
def my_queues(user: User = Depends(current_user), s: MemoryStore = Depends(store)) -> list[dict]:
    """Мои очереди: где я стою, управляю или которые создал."""
    with s.tx():
        out = []
        for q in s.queues_of(user):
            e = q.active_entry(user.id)
            out.append({**queue_view(s, q, user), "me": entry_view(s, q, e, user, False) if e else None})
        return out


# ---------------------------------------------------------------- очереди
@router.post("/queues", status_code=201, tags=["очереди"])
def create_queue(body: QueueIn, user: User = Depends(current_user), s: MemoryStore = Depends(store)) -> dict:
    """Создать очередь. Создатель обычной очереди сразу стоит первым, бизнес-очереди — владелец."""
    with s.tx():
        q = s.create_queue(body.title, body.type, user, body.source, body.notify_before)
        return queue_view(s, q, user)


@router.get("/queues/{code}", tags=["очереди"])
def get_queue(code: str, s: MemoryStore = Depends(store)) -> dict:
    """Очередь по коду: название, тип, статус, сколько ждут. Доступно без входа — для страницы по QR."""
    with s.tx():
        return queue_view(s, s.queue(code))


@router.patch("/queues/{code}", tags=["очереди"])
def patch_queue(
    code: str, body: QueuePatch, user: User = Depends(current_user), s: MemoryStore = Depends(store)
) -> dict:
    """Завершить очередь — создатель обычной или владелец бизнес-очереди."""
    with s.tx():
        q = s.queue(code)
        q.close(user.id)
        s.sync(q)
        return queue_view(s, q, user)


# ---------------------------------------------------------------- записи
@router.post("/queues/{code}/entries", status_code=201, tags=["записи"])
def join(
    code: str, body: EntryIn, user: User = Depends(current_user), s: MemoryStore = Depends(store)
) -> dict:
    """Встать в очередь. Повторный вход возвращает ту же запись.
    Оператор с полем name записывает человека вручную."""
    with s.tx():
        q = s.queue(code)
        if body.name and user.id in q.staff:
            e = q.add_manual(body.name, user.id)
        else:
            e = q.join(user.id, body.source)
        s.sync(q)
        return entry_view(s, q, e, user, True)


@router.get("/queues/{code}/entries", tags=["записи"])
def entries(code: str, user: User = Depends(current_user), s: MemoryStore = Depends(store)) -> list[dict]:
    """Кто в очереди: ждущие и вызванные по порядку. Имена видят управляющие и сам участник."""
    with s.tx():
        q = s.queue(code)
        show = _is_manager(q, user)
        called = [e for e in q.entries if e.status is EntryStatus.CALLED]
        return [entry_view(s, q, e, user, show) for e in called + q.waiting()]


@router.get("/queues/{code}/entries/me", tags=["записи"])
def my_entry(code: str, user: User = Depends(current_user), s: MemoryStore = Depends(store)) -> dict:
    """Моя запись и позиция."""
    with s.tx():
        q = s.queue(code)
        e = q.active_entry(user.id)
        if e is None:
            raise NotFound("Вы не стоите в этой очереди")
        return entry_view(s, q, e, user, True)


@router.patch("/entries/{entry_id}", tags=["записи"])
def patch_entry(
    entry_id: int, body: EntryPatch, user: User = Depends(current_user), s: MemoryStore = Depends(store)
) -> dict:
    """served — «Следующий» (первый в обычной очереди) или отметка оператора;
    left — выйти самому; removed — удалить не пришедшего или забрать управление у первого через 10 минут."""
    with s.tx():
        q, e = s.locate(entry_id)
        if body.status == "left":
            q.leave(e.id, user.id)
        elif body.status == "served":
            if q.type is QueueType.REGULAR:
                if e is not q.first_waiting():
                    raise Conflict("«Следующий» относится к первому в очереди")
                q.next(user.id)
            else:
                q.mark_served(e.id, user.id)
        else:
            w = q.waiting()
            if q.type is QueueType.REGULAR and len(w) > 1 and e is w[0] and w[1].participant == user.id:
                q.take_over(user.id)
            else:
                q.remove(e.id, user.id)
        s.sync(q)
        return entry_view(s, q, e, user, True)


@router.post("/queues/{code}/calls", status_code=201, tags=["бизнес-очередь"])
def call_next(code: str, user: User = Depends(current_user), s: MemoryStore = Depends(store)) -> dict:
    """Вызвать следующего (владелец или оператор бизнес-очереди)."""
    with s.tx():
        q = s.queue(code)
        e = q.call(user.id)
        if e is None:
            raise NotFound("В очереди никого нет")
        s.sync(q)
        return entry_view(s, q, e, user, True)


__all__ = ["router", "Unauthorized", "Forbidden"]

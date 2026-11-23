"""Хранилище очередей и пользователей.

Спринт 2: данные в памяти процесса — этого достаточно, чтобы сайт и бот работали с одной очередью.
Все изменения идут под одной блокировкой, поэтому одновременные запросы не ломают порядок (риск Р3).
Перенос в PostgreSQL по схеме из миграции 0001 — спринт 3, интерфейс хранилища при этом не меняется.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from app.domain.model import (
    DomainError,
    Entry,
    Notice,
    Queue,
    QueueCode,
    QueueStatus,
    QueueType,
    Source,
    clean_name,
    utcnow,
)


class NotFound(DomainError):
    """Очередь или запись не найдена (HTTP 404)."""


@dataclass
class User:
    id: str
    name: str
    telegram_id: int | None = None


@dataclass(frozen=True)
class Outgoing:
    """Уведомление для отправки: кому, по какой очереди, что случилось."""

    user_id: str | None
    code: str
    entry_id: int
    notice: Notice


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class MemoryStore:
    def __init__(self, clock: Callable[[], datetime] = utcnow):
        self.clock = clock
        self._lock = threading.RLock()
        self._users: dict[str, User] = {}
        self._by_token: dict[str, str] = {}
        self._by_telegram: dict[int, str] = {}
        self._queues: dict[str, Queue] = {}
        self._gid: dict[tuple[str, int], int] = {}  # (код, номер записи в очереди) -> id записи в API
        self._local: dict[int, tuple[str, int]] = {}
        self.outbox: list[Outgoing] = []

    @contextmanager
    def tx(self) -> Iterator[MemoryStore]:
        """Одна операция — одна «транзакция»: блокировка на время чтения и изменения."""
        with self._lock:
            yield self

    # ---------------------------------------------------------------- пользователи
    def new_guest(self, name: str) -> tuple[User, str]:
        user = self._new_user(clean_name(name))
        token = secrets.token_urlsafe(24)
        self._by_token[_hash(token)] = user.id
        return user, token

    def by_token(self, token: str) -> User | None:
        uid = self._by_token.get(_hash(token))
        return self._users.get(uid) if uid else None

    def telegram_user(self, telegram_id: int, name: str) -> User:
        uid = self._by_telegram.get(telegram_id)
        if uid:
            user = self._users[uid]
            user.name = clean_name(name) if name and name.strip() else user.name
            return user
        user = self._new_user(clean_name(name or "Гость"), telegram_id)
        self._by_telegram[telegram_id] = user.id
        return user

    def user(self, uid: str | None) -> User | None:
        return self._users.get(uid) if uid else None

    def _new_user(self, name: str, telegram_id: int | None = None) -> User:
        user = User(f"u{len(self._users) + 1}", name, telegram_id)
        self._users[user.id] = user
        return user

    # ---------------------------------------------------------------- очереди
    def create_queue(
        self, title: str, type: QueueType, creator: User, source: Source, notify_before: int
    ) -> Queue:
        while True:  # код уникален среди открытых очередей
            code = QueueCode.generate()
            old = self._queues.get(code.value)
            if old is None or old.status is QueueStatus.CLOSED:
                break
        q = Queue.create(title, type, creator.id, source, notify_before, code=code, clock=self.clock)
        self._queues[code.value] = q
        self.sync(q)
        return q

    def queue(self, raw_code: str) -> Queue:
        try:
            code = QueueCode.parse(raw_code)
        except ValueError as e:
            raise NotFound(str(e)) from None
        q = self._queues.get(code.value)
        if q is None:
            raise NotFound("Очередь с таким кодом не найдена")
        return q

    def queues_of(self, user: User) -> list[Queue]:
        return [
            q
            for q in self._queues.values()
            if q.active_entry(user.id) or user.id in q.staff or q.creator == user.id
        ]

    # ---------------------------------------------------------------- записи
    def entry_id(self, q: Queue, e: Entry) -> int:
        key = (q.code.value, e.id)
        if key not in self._gid:
            gid = len(self._gid) + 1
            self._gid[key], self._local[gid] = gid, key
        return self._gid[key]

    def locate(self, gid: int) -> tuple[Queue, Entry]:
        key = self._local.get(gid)
        if key is None:
            raise NotFound("Запись не найдена")
        q = self._queues[key[0]]
        return q, q.get(key[1])

    def sync(self, q: Queue) -> None:
        """После изменения: выдать id новым записям и забрать уведомления в журнал."""
        for e in q.entries:
            self.entry_id(q, e)
        for n in q.drain_notices():
            e = q.get(n.entry_id)
            self.outbox.append(Outgoing(e.participant, q.code.value, self.entry_id(q, e), n))

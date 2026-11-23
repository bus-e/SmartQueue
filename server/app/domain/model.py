"""Доменная модель SmartQueue: очередь, записи и правила.

Модуль не зависит от базы данных и веб-фреймворка — правила проверяются модульными тестами.
Соответствует документу «Модель предметной области» (КТ2).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum


# ---------------------------------------------------------------- ошибки
class DomainError(Exception):
    """Нарушено правило предметной области."""


class Forbidden(DomainError):
    """Нет прав на действие (HTTP 403)."""


class Conflict(DomainError):
    """Запись уже в другом состоянии (HTTP 409)."""


class QueueClosed(DomainError):
    """Очередь завершена (HTTP 410)."""


# ---------------------------------------------------------------- перечисления
class QueueType(str, Enum):
    REGULAR = "regular"
    BUSINESS = "business"


class QueueStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class EntryStatus(str, Enum):
    WAITING = "waiting"
    CALLED = "called"
    SERVED = "served"
    LEFT = "left"
    REMOVED = "removed"
    CLOSED = "closed"


ACTIVE = (EntryStatus.WAITING, EntryStatus.CALLED)


class Source(str, Enum):
    APP = "app"
    SITE = "site"
    BOT = "bot"
    OPERATOR = "operator"


class Role(str, Enum):
    OWNER = "owner"
    OPERATOR = "operator"


class NoticeType(str, Enum):
    N_AHEAD = "n_ahead"  # «Перед вами N человек»
    NEXT = "next"  # «Человек перед вами зашёл — вы следующий»
    FIRST = "first"  # «Вы первый» — управление обычной очередью
    CALLED = "called"  # «Вас вызывают»
    REMOVED = "removed"  # «Вас удалили из очереди»
    CLOSED = "closed"  # «Очередь завершена»


# ---------------------------------------------------------------- значения
@dataclass(frozen=True)
class QueueCode:
    """6 символов без похожих 0, O, 1, I."""

    value: str
    ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    def __post_init__(self):
        v = self.value
        if not isinstance(v, str) or len(v) != 6 or any(c not in self.ALPHABET for c in v):
            raise ValueError("Код очереди: 6 символов A–Z и 2–9, без 0, O, 1, I")

    @classmethod
    def generate(cls) -> QueueCode:
        return cls("".join(secrets.choice(cls.ALPHABET) for _ in range(6)))

    @classmethod
    def parse(cls, raw: str) -> QueueCode:
        """Код с экрана или голоса: без пробелов, регистр не важен."""
        return cls(raw.replace(" ", "").upper())


@dataclass(frozen=True)
class NotifyThreshold:
    """За сколько человек до участника присылать уведомление."""

    value: int = 2

    def __post_init__(self):
        if isinstance(self.value, bool) or not isinstance(self.value, int) or not 1 <= self.value <= 10:
            raise ValueError("Порог N: целое от 1 до 10")


def clean_name(raw: str) -> str:
    """Имя участника или название очереди: 1–50 символов после обрезки пробелов."""
    name = (raw or "").strip()
    if not 1 <= len(name) <= 50:
        raise ValueError("Имя: от 1 до 50 символов")
    return name


TAKEOVER_AFTER = timedelta(minutes=10)  # сколько первый может не нажимать «Следующий»


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- сущности
@dataclass
class Entry:
    id: int
    number: int
    participant: str | None  # id участника; None — ручная запись оператором
    guest_name: str | None
    source: Source
    joined_at: datetime  # время сервера — единственное основание порядка
    status: EntryStatus = EntryStatus.WAITING
    called_at: datetime | None = None
    served_at: datetime | None = None
    left_at: datetime | None = None

    def __post_init__(self):
        if self.participant is None and not self.guest_name:
            raise ValueError("Запись: нужен участник или имя")


@dataclass(frozen=True)
class Notice:
    entry_id: int
    type: NoticeType


@dataclass
class Queue:
    code: QueueCode
    title: str
    type: QueueType
    creator: str
    notify_before: NotifyThreshold = field(default_factory=NotifyThreshold)
    clock: Callable[[], datetime] = utcnow
    status: QueueStatus = QueueStatus.OPEN
    entries: list[Entry] = field(default_factory=list)
    staff: dict[str, Role] = field(default_factory=dict)
    _sent: set = field(default_factory=set, repr=False)
    _first: int | None = field(default=None, repr=False)  # кто сейчас первый
    _first_since: datetime | None = field(default=None, repr=False)  # и с какого момента
    _outbox: list[Notice] = field(default_factory=list, repr=False)

    # -------- создание
    @classmethod
    def create(
        cls,
        title: str,
        type: QueueType,
        creator: str,
        source: Source = Source.SITE,
        notify_before: int = 2,
        code: QueueCode | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> Queue:
        q = cls(
            code or QueueCode.generate(),
            clean_name(title),
            type,
            creator,
            NotifyThreshold(notify_before),
            clock,
        )
        if type is QueueType.REGULAR:
            q.join(creator, source)  # создатель обычной очереди стоит первым
        else:
            q.staff[creator] = Role.OWNER  # владелец бизнес-очереди управляет ей
        return q

    # -------- чтение
    def waiting(self) -> list[Entry]:
        return sorted(
            (e for e in self.entries if e.status is EntryStatus.WAITING),
            key=lambda e: (e.joined_at, e.number),
        )

    def first_waiting(self) -> Entry | None:
        w = self.waiting()
        return w[0] if w else None

    def position(self, entry: Entry) -> int | None:
        """Позиция вычисляется, а не хранится: 1 + число ждущих, вошедших раньше."""
        if entry.status is not EntryStatus.WAITING:
            return None
        return 1 + sum(1 for e in self.waiting() if (e.joined_at, e.number) < (entry.joined_at, entry.number))

    def active_entry(self, participant: str) -> Entry | None:
        return next((e for e in self.entries if e.participant == participant and e.status in ACTIVE), None)

    def managers(self) -> set[str]:
        if self.type is QueueType.BUSINESS:
            return set(self.staff)
        first = self.first_waiting()
        return {first.participant} if first and first.participant else set()

    def take_over_at(self) -> datetime | None:
        """С какого момента второй может забрать управление у первого (обычная очередь)."""
        if self.type is not QueueType.REGULAR or self._first_since is None or len(self.waiting()) < 2:
            return None
        return self._first_since + TAKEOVER_AFTER

    def get(self, entry_id: int) -> Entry:
        for e in self.entries:
            if e.id == entry_id:
                return e
        raise DomainError("Запись не найдена")

    # -------- действия участника
    def join(self, participant: str, source: Source) -> Entry:
        self._require_open()
        existing = self.active_entry(participant)
        if existing:
            return existing  # повторный вход не создаёт вторую запись
        return self._add(participant, None, source)

    def leave(self, entry_id: int, participant: str) -> None:
        e = self.get(entry_id)
        if e.participant != participant:
            raise Forbidden("Выйти можно только из своей записи")
        self._finish(e, EntryStatus.LEFT)
        self._after_change()

    # -------- управление обычной очередью
    def next(self, by: str) -> Entry | None:
        """«Следующий»: первый прошёл, управление переходит к новому первому."""
        if self.type is not QueueType.REGULAR:
            raise DomainError("В бизнес-очереди используется вызов следующего")
        self._require_open()
        if by not in self.managers():
            raise Forbidden("Управляет только первый в очереди")
        first = self.first_waiting()
        if first is None:
            raise DomainError("В очереди никого нет")
        first.status, first.served_at = EntryStatus.SERVED, self.clock()
        self._after_change()
        if not self.waiting():
            self.status = QueueStatus.CLOSED  # обычная очередь опустела
        return self.first_waiting()

    def take_over(self, by: str) -> Entry:
        """Первый не нажимает «Следующий» дольше 10 минут — второй забирает управление.
        Запись первого получает статус «удалён»: он не пришёл либо прошёл и забыл нажать."""
        if self.type is not QueueType.REGULAR:
            raise DomainError("Передача по времени есть только в обычной очереди")
        self._require_open()
        w = self.waiting()
        if len(w) < 2 or w[1].participant != by:
            raise Forbidden("Забрать управление может только второй в очереди")
        since = self._first_since or self.clock()
        if self.clock() - since < TAKEOVER_AFTER:
            raise Forbidden("Первый ещё может нажать «Следующий»: подождите 10 минут")
        self._finish(w[0], EntryStatus.REMOVED)
        self._notify(w[0], NoticeType.REMOVED)
        self._after_change()
        return w[1]  # второй стал первым

    # -------- управление бизнес-очередью
    def add_staff(self, user: str, by: str) -> None:
        if self.staff.get(by) is not Role.OWNER:
            raise Forbidden("Назначать операторов может только владелец")
        self.staff[user] = Role.OPERATOR

    def call(self, by: str) -> Entry | None:
        """Вызвать следующего: первая запись «ждёт» становится «вызван»."""
        if self.type is not QueueType.BUSINESS:
            raise DomainError("Вызов есть только в бизнес-очереди")
        self._require_open()
        if by not in self.staff:
            raise Forbidden("Вызывать могут только владелец и операторы")
        first = self.first_waiting()
        if first is None:
            return None
        first.status, first.called_at = EntryStatus.CALLED, self.clock()
        self._notify(first, NoticeType.CALLED)
        self._after_change()
        return first

    def mark_served(self, entry_id: int, by: str) -> None:
        """Отметить обслуженного: вызванного или — если гости подходят сами — первого ждущего."""
        if by not in self.staff:
            raise Forbidden("Отметить обслуженного могут только владелец и операторы")
        e = self.get(entry_id)
        if e.status is EntryStatus.WAITING and e is not self.first_waiting():
            raise Conflict("Без вызова отметить можно только первого в очереди")
        if e.status not in ACTIVE:
            raise Conflict("Запись уже не в очереди")
        was_waiting = e.status is EntryStatus.WAITING
        e.status, e.served_at = EntryStatus.SERVED, self.clock()
        if was_waiting:
            self._after_change()

    def add_manual(self, name: str, by: str) -> Entry:
        """Ручная запись человека без смартфона — стоит по общим правилам."""
        self._require_open()
        if by not in self.staff:
            raise Forbidden("Записывать вручную могут только владелец и операторы")
        return self._add(None, clean_name(name), Source.OPERATOR)

    # -------- общее управление
    def remove(self, entry_id: int, by: str) -> None:
        """Удалить не пришедшего."""
        if by not in self.managers():
            raise Forbidden("Удалять может только управляющий очередью")
        e = self.get(entry_id)
        if e.participant == by:
            raise Conflict("Себя не удаляют — для этого «Следующий» или «Выйти»")
        self._finish(e, EntryStatus.REMOVED)
        self._notify(e, NoticeType.REMOVED)
        self._after_change()

    def close(self, by: str) -> None:
        allowed = (
            {self.creator}
            if self.type is QueueType.REGULAR
            else {u for u, r in self.staff.items() if r is Role.OWNER}
        )
        if by not in allowed:
            raise Forbidden("Завершить может только создатель или владелец")
        for e in self.entries:
            if e.status in ACTIVE:
                e.status = EntryStatus.CLOSED
                self._notify(e, NoticeType.CLOSED)
        self.status = QueueStatus.CLOSED

    # -------- уведомления
    def drain_notices(self) -> list[Notice]:
        """Уведомления, появившиеся после последнего вызова (в сервере — в журнал той же транзакции)."""
        out, self._outbox = self._outbox, []
        return out

    # -------- внутреннее
    def _require_open(self) -> None:
        if self.status is QueueStatus.CLOSED:
            raise QueueClosed("Очередь завершена")

    def _add(self, participant, guest_name, source) -> Entry:
        number = len(self.entries) + 1
        e = Entry(
            id=number,
            number=number,
            participant=participant,
            guest_name=guest_name,
            source=source,
            joined_at=self.clock(),
        )
        self.entries.append(e)
        self._track_first()
        return e

    def _track_first(self) -> None:
        first = self.first_waiting()
        if (first.id if first else None) != self._first:
            self._first, self._first_since = (first.id, self.clock()) if first else (None, None)

    def _finish(self, e: Entry, status: EntryStatus) -> None:
        if e.status not in ACTIVE:
            raise Conflict("Запись уже не в очереди")
        e.status, e.left_at = status, self.clock()

    def _notify(self, e: Entry, t: NoticeType) -> None:
        key = (e.id, t)
        if key in self._sent:
            return  # каждое уведомление — один раз
        self._sent.add(key)
        self._outbox.append(Notice(e.id, t))

    def _after_change(self) -> None:
        """Очередь сдвинулась: кому пора сообщить."""
        self._track_first()
        n = self.notify_before.value
        for pos, e in enumerate(self.waiting(), 1):
            if pos == 1:
                self._notify(e, NoticeType.FIRST if self.type is QueueType.REGULAR else NoticeType.NEXT)
            elif pos - 1 == n:
                self._notify(e, NoticeType.N_AHEAD)

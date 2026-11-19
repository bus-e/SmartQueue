"""Модульные тесты доменной модели. Номера Т — из плана тестирования (КТ2)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.model import (
    Conflict,
    EntryStatus,
    Forbidden,
    NoticeType,
    NotifyThreshold,
    Queue,
    QueueClosed,
    QueueCode,
    QueueStatus,
    QueueType,
    Source,
    clean_name,
)


class Clock:
    """Управляемые часы: каждый вызов — на секунду позже."""

    def __init__(self):
        self.t = datetime(2026, 11, 12, 9, 15, tzinfo=timezone.utc)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


def regular(n=2):
    return Queue.create(
        "Зачёт, ауд. 214", QueueType.REGULAR, "anna", notify_before=n, code=QueueCode("K7M2QX"), clock=Clock()
    )


def business():
    return Queue.create("Кофейня", QueueType.BUSINESS, "owner", code=QueueCode("CAFE22"), clock=Clock())


def types(notices):
    return [(n.entry_id, n.type) for n in notices]


# ---------------------------------------------------------------- Т1. Создание
def test_t1_creator_stands_first_in_regular_queue():
    q = regular()
    assert q.position(q.active_entry("anna")) == 1
    assert q.managers() == {"anna"}


def test_t1_generated_code_is_valid():
    for _ in range(200):
        QueueCode.generate()  # не бросает исключение


def test_t1_business_queue_owner_is_manager_not_member():
    q = business()
    assert q.managers() == {"owner"} and q.waiting() == []


# ---------------------------------------------------------------- Т2. Код очереди
@pytest.mark.parametrize("raw", ["K7M2QX", "k7m 2qx"])
def test_t2_valid_codes(raw):
    assert QueueCode.parse(raw).value == "K7M2QX"


@pytest.mark.parametrize("raw", ["K7M2Q", "K7M2QXA", "K0M2QX", "KOM2QX", "K1M2QX", "KIM2QX", ""])
def test_t2_invalid_codes(raw):
    with pytest.raises(ValueError):
        QueueCode.parse(raw)


def test_t2_closed_queue_rejects_join():
    q = regular()
    q.close("anna")
    with pytest.raises(QueueClosed):
        q.join("boris", Source.BOT)


# ---------------------------------------------------------------- Т3. Повторный вход
def test_t3_second_join_returns_same_entry():
    q = regular()
    a = q.join("boris", Source.BOT)
    b = q.join("boris", Source.SITE)
    assert a is b and len(q.waiting()) == 2


# ---------------------------------------------------------------- порядок и позиция
def test_order_is_server_time_and_position_is_computed():
    q = regular()
    for p in ["boris", "vera", "gleb"]:
        q.join(p, Source.SITE)
    vera = q.active_entry("vera")
    assert q.position(vera) == 3
    q.leave(q.active_entry("boris").id, "boris")
    assert q.position(vera) == 2  # остальные сдвинулись сами


# ---------------------------------------------------------------- Т5, Т6. Передача управления
def test_t5_not_first_cannot_press_next():
    q = regular()
    q.join("boris", Source.BOT)
    with pytest.raises(Forbidden):
        q.next("boris")


def test_t6_next_passes_control_once():
    q = regular()
    q.join("boris", Source.BOT)
    q.next("anna")
    assert q.managers() == {"boris"}
    with pytest.raises(Forbidden):  # повторное нажатие прежнего первого
        q.next("anna")


def test_regular_queue_closes_when_empty():
    q = regular()
    q.next("anna")
    assert q.status is QueueStatus.CLOSED


def test_first_removes_no_show_next_person():
    q = regular()
    boris = q.join("boris", Source.BOT)
    q.join("vera", Source.BOT)
    with pytest.raises(Forbidden):
        q.remove(boris.id, "vera")  # vera не первая
    q.remove(boris.id, "anna")  # первый удаляет не пришедшего
    assert boris.status is EntryStatus.REMOVED
    assert q.position(q.active_entry("vera")) == 2


# ---------------------------------------------------------------- Т17. Первый не передал управление
def test_t17_second_takes_over_only_after_10_minutes():
    q = regular()
    q.join("boris", Source.BOT)
    q.join("vera", Source.BOT)
    with pytest.raises(Forbidden):  # 10 минут ещё не прошло
        q.take_over("boris")
    q.clock.t += timedelta(minutes=10)
    with pytest.raises(Forbidden):  # vera не вторая
        q.take_over("vera")
    q.take_over("boris")
    assert q.managers() == {"boris"}
    assert q.entries[0].status is EntryStatus.REMOVED


def test_t17_timer_restarts_for_new_first():
    q = regular()
    q.join("boris", Source.BOT)
    q.join("vera", Source.BOT)
    q.clock.t += timedelta(minutes=10)
    q.next("anna")  # boris стал первым только сейчас
    with pytest.raises(Forbidden):
        q.take_over("vera")


# ---------------------------------------------------------------- Т7, Т8. Уведомления
def test_t7_n_ahead_and_first_notices():
    q = regular(n=2)
    for p in ["boris", "vera", "gleb"]:
        q.join(p, Source.SITE)  # позиции: anna 1, boris 2, vera 3, gleb 4
    q.next("anna")  # boris первый, у gleb впереди 2
    got = types(q.drain_notices())
    assert (q.active_entry("boris").id, NoticeType.FIRST) in got
    assert (q.active_entry("gleb").id, NoticeType.N_AHEAD) in got
    assert len(got) == 2


@pytest.mark.parametrize("n", [1, 2, 10])
def test_t7_threshold_valid(n):
    assert NotifyThreshold(n).value == n


@pytest.mark.parametrize("n", [0, 11, "abc", True])
def test_t7_threshold_invalid(n):
    with pytest.raises(ValueError):
        NotifyThreshold(n)


def test_t8_notice_is_sent_only_once():
    q = regular(n=1)
    for p in ["boris", "vera", "gleb"]:
        q.join(p, Source.SITE)
    q.next("anna")
    first = types(q.drain_notices())
    q.leave(q.active_entry("gleb").id, "gleb")  # очередь снова изменилась
    again = types(q.drain_notices())
    assert not set(first) & set(again)


# ---------------------------------------------------------------- Т10–Т12. Бизнес-очередь
def test_t10_two_calls_call_different_people():
    q = business()
    q.add_staff("op", "owner")
    q.join("boris", Source.APP)
    q.join("vera", Source.BOT)
    a, b = q.call("owner"), q.call("op")
    assert a.participant == "boris" and b.participant == "vera"
    assert a.status is b.status is EntryStatus.CALLED


def test_t11_outsider_cannot_call_or_remove():
    q = business()
    e = q.join("boris", Source.APP)
    with pytest.raises(Forbidden):
        q.call("boris")
    with pytest.raises(Forbidden):
        q.remove(e.id, "stranger")
    with pytest.raises(Forbidden):
        q.add_staff("x", "boris")


def test_t12_manual_entry_stands_by_time():
    q = business()
    q.join("boris", Source.APP)
    m = q.add_manual("Мария Петровна", "owner")
    q.join("vera", Source.BOT)
    assert [e.guest_name or e.participant for e in q.waiting()] == ["boris", "Мария Петровна", "vera"]
    assert m.source is Source.OPERATOR


def test_called_person_gets_notice_and_served_mark():
    q = business()
    e = q.join("boris", Source.APP)
    q.call("owner")
    assert (e.id, NoticeType.CALLED) in types(q.drain_notices())
    q.mark_served(e.id, "owner")
    assert e.status is EntryStatus.SERVED
    with pytest.raises(Conflict):
        q.mark_served(e.id, "owner")


# ---------------------------------------------------------------- Т18. Гости подходят сами
def test_t18_operator_marks_first_served_without_call():
    q = business()
    boris = q.join("boris", Source.APP)
    vera = q.join("vera", Source.BOT)
    with pytest.raises(Conflict):  # не первого без вызова отметить нельзя
        q.mark_served(vera.id, "owner")
    q.mark_served(boris.id, "owner")
    assert boris.status is EntryStatus.SERVED and q.position(vera) == 1
    assert (vera.id, NoticeType.NEXT) in types(q.drain_notices())


# ---------------------------------------------------------------- Т13. Имя
@pytest.mark.parametrize("name", ["М", "М" * 50, "  Мария  "])
def test_t13_valid_names(name):
    assert 1 <= len(clean_name(name)) <= 50


@pytest.mark.parametrize("name", ["", "   ", "М" * 51])
def test_t13_invalid_names(name):
    with pytest.raises(ValueError):
        clean_name(name)


# ---------------------------------------------------------------- завершение
def test_close_notifies_everyone_and_only_creator_can_close():
    q = regular()
    q.join("boris", Source.BOT)
    with pytest.raises(Forbidden):
        q.close("boris")
    q.close("anna")
    got = types(q.drain_notices())
    assert sum(1 for _, t in got if t is NoticeType.CLOSED) == 2
    assert all(e.status is EntryStatus.CLOSED for e in q.entries)

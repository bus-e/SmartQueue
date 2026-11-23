"""Интеграционные тесты API: сценарии из плана тестирования (Т1, Т3, Т4, Т5) и правила очереди через HTTP."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import MemoryStore


class Clock:
    def __init__(self):
        self.t = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)

    def __call__(self):
        self.t += timedelta(milliseconds=1)  # каждое действие — чуть позже предыдущего
        return self.t

    def wait(self, minutes):
        self.t += timedelta(minutes=minutes)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(clock, monkeypatch):
    monkeypatch.setenv("BOT_KEY", "test-bot-key")
    return TestClient(create_app(MemoryStore(clock)))


def guest(client, name):
    r = client.post("/api/v1/auth/guest", json={"name": name})
    assert r.status_code == 201
    return {"X-Guest-Token": r.json()["token"]}


def tg(telegram_id, name):
    return {
        "X-Bot-Key": "test-bot-key",
        "X-Telegram-Id": str(telegram_id),
        "X-Telegram-Name": quote(name),
    }  # только ASCII


def create(client, who, title="Зачёт", type="regular"):
    r = client.post("/api/v1/queues", json={"title": title, "type": type}, headers=who)
    assert r.status_code == 201, r.text
    return r.json()["code"]


def me(client, code, who):
    return client.get(f"/api/v1/queues/{code}/entries/me", headers=who).json()


# ---------------------------------------------------------------- Т1
def test_t1_create_regular_queue_creator_is_first(client):
    egor = guest(client, "Егор")
    code = create(client, egor)
    assert len(code) == 6
    mine = me(client, code, egor)
    assert mine["position"] == 1 and mine["can_next"] is True
    q = client.get(f"/api/v1/queues/{code}").json()
    assert q["title"] == "Зачёт" and q["waiting"] == 1 and q["status"] == "open"


# ---------------------------------------------------------------- Т3
def test_t3_second_join_returns_same_entry(client):
    egor, igor = guest(client, "Егор"), guest(client, "Игорь")
    code = create(client, egor)
    first = client.post(f"/api/v1/queues/{code}/entries", json={}, headers=igor).json()
    again = client.post(f"/api/v1/queues/{code}/entries", json={}, headers=igor).json()
    assert first["id"] == again["id"] and again["position"] == 2
    assert client.get(f"/api/v1/queues/{code}").json()["waiting"] == 2


# ---------------------------------------------------------------- Т4
def test_t4_site_and_bot_see_one_queue(client):
    egor = guest(client, "Егор")  # создаёт на сайте
    code = create(client, egor)
    igor = guest(client, "Игорь")  # встаёт на сайте
    anna = tg(1001, "Анна")  # встаёт через бота
    client.post(f"/api/v1/queues/{code}/entries", json={"source": "bot"}, headers=anna)
    client.post(f"/api/v1/queues/{code}/entries", json={"source": "site"}, headers=igor)
    assert me(client, code, igor)["position"] == 3

    # Анна выходит в боте — позиция Игоря на сайте сразу меняется
    anna_entry = me(client, code, anna)["id"]
    r = client.patch(f"/api/v1/entries/{anna_entry}", json={"status": "left"}, headers=anna)
    assert r.status_code == 200 and r.json()["status"] == "left"
    assert me(client, code, igor)["position"] == 2

    order = [e["source"] for e in client.get(f"/api/v1/queues/{code}/entries", headers=egor).json()]
    assert order == ["site", "site"]


# ---------------------------------------------------------------- Т5
def test_t5_next_by_not_first_is_forbidden(client):
    egor, igor = guest(client, "Егор"), guest(client, "Игорь")
    code = create(client, egor)
    client.post(f"/api/v1/queues/{code}/entries", json={}, headers=igor)
    first = me(client, code, egor)["id"]
    r = client.patch(f"/api/v1/entries/{first}", json={"status": "served"}, headers=igor)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "Forbidden"


def test_next_moves_queue_and_gives_control(client):
    egor, igor = guest(client, "Егор"), guest(client, "Игорь")
    code = create(client, egor)
    client.post(f"/api/v1/queues/{code}/entries", json={}, headers=igor)
    r = client.patch(
        f"/api/v1/entries/{me(client, code, egor)['id']}", json={"status": "served"}, headers=egor
    )
    assert r.status_code == 200
    assert me(client, code, igor)["position"] == 1 and me(client, code, igor)["can_next"] is True


def test_take_over_after_ten_minutes(client, clock):
    egor, igor = guest(client, "Егор"), guest(client, "Игорь")
    code = create(client, egor)
    client.post(f"/api/v1/queues/{code}/entries", json={}, headers=igor)
    first = me(client, code, egor)["id"]
    assert me(client, code, igor)["take_over_at"] is not None

    early = client.patch(f"/api/v1/entries/{first}", json={"status": "removed"}, headers=igor)
    assert early.status_code == 403  # первый ещё может нажать «Следующий»

    clock.wait(10)
    r = client.patch(f"/api/v1/entries/{first}", json={"status": "removed"}, headers=igor)
    assert r.status_code == 200 and r.json()["status"] == "removed"
    assert me(client, code, igor)["position"] == 1


def test_names_hidden_from_regular_participants(client):
    egor, igor, anna = guest(client, "Егор"), guest(client, "Игорь"), guest(client, "Анна")
    code = create(client, egor)
    for who in (igor, anna):
        client.post(f"/api/v1/queues/{code}/entries", json={}, headers=who)
    seen_by_anna = client.get(f"/api/v1/queues/{code}/entries", headers=anna).json()
    assert [e["name"] for e in seen_by_anna] == [None, None, "Анна"]
    seen_by_first = client.get(f"/api/v1/queues/{code}/entries", headers=egor).json()
    assert [e["name"] for e in seen_by_first] == ["Егор", "Игорь", "Анна"]


def test_business_queue_call_and_manual_entry(client):
    owner, guest1 = guest(client, "Кофейня"), guest(client, "Анна")
    code = create(client, owner, "Кофейня", "business")
    client.post(f"/api/v1/queues/{code}/entries", json={}, headers=guest1)
    manual = client.post(f"/api/v1/queues/{code}/entries", json={"name": "Гость у стойки"}, headers=owner)
    assert manual.status_code == 201 and manual.json()["source"] == "operator"

    called = client.post(f"/api/v1/queues/{code}/calls", headers=owner)
    assert called.status_code == 201 and called.json()["status"] == "called"
    served = client.patch(f"/api/v1/entries/{called.json()['id']}", json={"status": "served"}, headers=owner)
    assert served.json()["status"] == "served"
    assert client.post(f"/api/v1/queues/{code}/calls", headers=guest1).status_code == 403


def test_close_queue(client):
    egor, igor = guest(client, "Егор"), guest(client, "Игорь")
    code = create(client, egor)
    assert client.patch(f"/api/v1/queues/{code}", json={"status": "closed"}, headers=igor).status_code == 403
    assert (
        client.patch(f"/api/v1/queues/{code}", json={"status": "closed"}, headers=egor).json()["status"]
        == "closed"
    )
    assert client.post(f"/api/v1/queues/{code}/entries", json={}, headers=igor).status_code == 410


def test_errors_have_one_format(client):
    r = client.get("/api/v1/queues/K0M2QX")
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message"}
    assert client.post("/api/v1/queues", json={"title": "x"}).status_code == 401
    assert client.post("/api/v1/auth/guest", json={"name": ""}).status_code == 422
    assert (
        client.post("/api/v1/queues", json={}, headers=tg(1, "x") | {"X-Bot-Key": "wrong"}).status_code == 401
    )


def test_my_queues(client):
    egor, igor = guest(client, "Егор"), guest(client, "Игорь")
    code = create(client, egor)
    client.post(f"/api/v1/queues/{code}/entries", json={}, headers=igor)
    mine = client.get("/api/v1/me/queues", headers=igor).json()
    assert [(q["code"], q["me"]["position"]) for q in mine] == [(code, 2)]


def test_simultaneous_joins_keep_unique_positions(client):
    """Риск Р3: 30 человек встают одновременно — у всех разные места, без пропусков."""
    owner = guest(client, "Егор")
    code = create(client, owner)
    people = [guest(client, f"Участник {i}") for i in range(30)]
    barrier = threading.Barrier(len(people))

    def join(who):
        barrier.wait()
        client.post(f"/api/v1/queues/{code}/entries", json={}, headers=who)

    threads = [threading.Thread(target=join, args=(p,)) for p in people]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    positions = sorted(me(client, code, p)["position"] for p in people)
    assert positions == list(range(2, 32))


def test_notifications_go_to_outbox(client):
    store = client.app.state.store
    egor, igor, anna, ilya = (guest(client, n) for n in ("Егор", "Игорь", "Анна", "Илья"))
    code = create(client, egor)
    for who in (igor, anna, ilya):
        client.post(f"/api/v1/queues/{code}/entries", json={}, headers=who)
    client.patch(f"/api/v1/entries/{me(client, code, egor)['id']}", json={"status": "served"}, headers=egor)
    kinds = [(o.notice.type.value, o.entry_id) for o in store.outbox]
    assert ("first", me(client, code, igor)["id"]) in kinds
    assert ("n_ahead", me(client, code, ilya)["id"]) in kinds  # N = 2: перед Ильёй двое

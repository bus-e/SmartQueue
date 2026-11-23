"""Бот: тексты и кнопки (модульно) и обращения к настоящему API в одном процессе (интеграционно)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import MemoryStore
from smartqueue_bot.client import Api, ApiError
from smartqueue_bot.views import card, people, who

NOW = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)
Q = {"code": "K7M2QX", "title": "Очередь к 304 ауд.", "status": "open", "waiting": 4, "now_serving": "Максим"}


def entry(**kw):
    base = {"id": 7, "position": 3, "ahead": 2, "status": "waiting", "can_next": False, "take_over_at": None}
    return base | kw


# ---------------------------------------------------------------- тексты
def test_people_forms():
    assert [people(n) for n in (1, 2, 5, 11, 22)] == [
        "1 человек",
        "2 человека",
        "5 человек",
        "11 человек",
        "22 человека",
    ]


def test_card_waiting():
    text, kb = card(Q, entry(), NOW)
    assert "Ты <b>3-й</b>" in text and "Перед тобой — 2 человека" in text and "Максим" in text
    assert kb[-1] == [("Выйти из очереди", "l:7")]


def test_card_first_has_next_button():
    text, kb = card(Q, entry(position=1, ahead=0, can_next=True), NOW)
    assert "Твоя очередь" in text and kb[0] == [("Следующий", "n:7")]


def test_take_over_button_only_after_ten_minutes():
    later = (NOW + timedelta(minutes=3)).isoformat()
    _, kb = card(Q, entry(position=2, ahead=1, take_over_at=later, first_id=5), NOW)
    assert all("t:" not in d for row in kb for _, d in row)
    due = (NOW - timedelta(seconds=1)).isoformat()
    text, kb = card(Q, entry(position=2, ahead=1, take_over_at=due, first_id=5), NOW)
    assert kb[0] == [("Забрать управление", "t:5")] and "больше 10 минут" in text


def test_card_operator_and_closed():
    _, kb = card(Q | {"role": "owner"}, None, NOW)
    assert kb[0] == [("Вызвать следующего", "c:K7M2QX")] and kb[-1] == [("Закрыть очередь", "x:K7M2QX")]
    text, kb = card(Q | {"status": "closed"}, None, NOW)
    assert "завершена" in text and kb == []


def test_card_not_joined_and_escaping():
    text, kb = card(Q | {"title": "<b>Зачёт</b>"}, None, NOW)
    assert "&lt;b&gt;Зачёт" in text and kb == [[("Встать в очередь", "j:K7M2QX")]]


def test_who_hides_other_names():
    es = [entry(id=1, position=1, name=None), entry(id=2, position=2, name="Егор", is_me=True)]
    text = who(Q, es)
    assert "1. участник" in text and "2. Егор ← ты" in text


# ---------------------------------------------------------------- бот + настоящий API
@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("BOT_KEY", "k")
    return create_app(MemoryStore())


def bot_api(server, key="k"):
    return Api("http://test", key, transport=httpx.ASGITransport(app=server))


def test_t4_site_and_bot_share_one_queue(server):
    site = TestClient(server)
    token = site.post("/api/v1/auth/guest", json={"name": "Егор"}).json()["token"]
    egor = {"X-Guest-Token": token}
    code = site.post("/api/v1/queues", json={"title": "Зачёт"}, headers=egor).json()["code"]

    async def scenario():
        a = bot_api(server)
        anna = await a.join(code, 1001, "Анна")  # Анна встаёт через бота
        ilya = await a.join(code, 1002, "Илья")
        assert (anna["position"], ilya["position"]) == (2, 3)
        await a.set_status(anna["id"], "left", 1001, "Анна")  # Анна выходит в боте
        me = await a.me(code, 1002, "Илья")
        assert me["position"] == 2
        assert await a.me(code, 1001, "Анна") is None
        await a.close()

    asyncio.run(scenario())
    # сайт видит ту же очередь
    seen = site.get(f"/api/v1/queues/{code}/entries", headers=egor).json()
    assert [(e["name"], e["source"]) for e in seen] == [("Егор", "site"), ("Илья", "bot")]


def test_bot_creates_queue_and_calls(server):
    async def scenario():
        a = bot_api(server)
        q = await a.create("Кофейня", "business", 1, "Оператор")
        await a.join(q["code"], 2, "Гость")
        called = await a.call_next(q["code"], 1, "Оператор")
        assert called["status"] == "called"
        with pytest.raises(ApiError) as e:
            await a.call_next(q["code"], 2, "Гость")
        assert e.value.status == 403
        await a.close()

    asyncio.run(scenario())


def test_wrong_bot_key_is_rejected(server):
    async def scenario():
        a = bot_api(server, key="wrong")
        with pytest.raises(ApiError) as e:
            await a.create("Зачёт", "regular", 1, "Егор")
        assert e.value.status == 401
        await a.close()

    asyncio.run(scenario())

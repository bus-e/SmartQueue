"""Обработчики бота целиком: /start с кодом из QR, создание очереди, кнопки «Следующий» и «Выйти».

Вместо Telegram — простые заглушки, вместо сети — настоящий API в том же процессе.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx

from app.main import create_app
from app.store import MemoryStore
from smartqueue_bot import main as bot
from smartqueue_bot.client import Api


class Chat:
    def __init__(self):
        self.sent: list[tuple[str, object]] = []

    async def send_message(self, text, parse_mode=None, reply_markup=None):
        self.sent.append((text, reply_markup))


class Callback:
    def __init__(self, data):
        self.data, self.answers, self.edits = data, [], []

    async def answer(self, text=None, show_alert=False):
        self.answers.append(text)

    async def edit_message_text(self, text, parse_mode=None, reply_markup=None):
        self.edits.append((text, reply_markup))


def user(uid, name):
    return SimpleNamespace(id=uid, full_name=name, username=None)


def buttons(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row] if markup else []


def setup(monkeypatch):
    monkeypatch.setenv("BOT_KEY", "k")
    server = create_app(MemoryStore())
    api = Api("http://test", "k", transport=httpx.ASGITransport(app=server))
    app = SimpleNamespace(bot_data={"api": api})
    return server, api, app


def ctx(app, args=None, data=None):
    return SimpleNamespace(application=app, args=args or [], user_data=data if data is not None else {})


def test_create_join_next_leave(monkeypatch):
    server, api, app = setup(monkeypatch)

    async def scenario():
        # Егор создаёт очередь: /new → название → «Обычная»
        egor, egor_chat, egor_data = user(1, "Егор"), Chat(), {}
        await bot.new(
            SimpleNamespace(effective_user=egor, effective_chat=egor_chat), ctx(app, data=egor_data)
        )
        msg = SimpleNamespace(text="Зачёт")
        await bot.text(
            SimpleNamespace(effective_user=egor, effective_chat=egor_chat, message=msg),
            ctx(app, data=egor_data),
        )
        cb = Callback("nt:regular")
        await bot.button(
            SimpleNamespace(effective_user=egor, effective_chat=egor_chat, callback_query=cb),
            ctx(app, data=egor_data),
        )
        code = cb.edits[0][0].split("<code>")[1][:6]
        assert "Твоя очередь" in cb.edits[-1][0]

        # Анна переходит по ссылке из QR: /start CODE
        anna, anna_chat = user(2, "Анна"), Chat()
        await bot.start(
            SimpleNamespace(effective_user=anna, effective_chat=anna_chat, callback_query=None),
            ctx(app, [code]),
        )
        text, markup = anna_chat.sent[-1]
        assert "Ты <b>2-й</b>" in text and any(d.startswith("l:") for d in buttons(markup))

        # Егор нажимает «Следующий» — Анна становится первой
        next_btn = next(d for d in buttons(cb.edits[-1][1]) if d.startswith("n:"))
        cb2 = Callback(next_btn)
        await bot.button(
            SimpleNamespace(effective_user=egor, effective_chat=egor_chat, callback_query=cb2), ctx(app)
        )
        assert cb2.answers == ["Очередь сдвинулась"]
        me = await api.me(code, 2, "Анна")
        assert me["position"] == 1 and me["can_next"]

        # Анна выходит кнопкой
        cb3 = Callback(f"l:{me['id']}")
        await bot.button(
            SimpleNamespace(effective_user=anna, effective_chat=anna_chat, callback_query=cb3), ctx(app)
        )
        assert cb3.answers == ["Ты вышел из очереди"]
        await api.close()

    asyncio.run(scenario())


def test_plain_code_and_errors(monkeypatch):
    server, api, app = setup(monkeypatch)

    async def scenario():
        chat = Chat()
        u = SimpleNamespace(effective_user=user(5, "Илья"), effective_chat=chat, callback_query=None)
        await bot.text(SimpleNamespace(**vars(u), message=SimpleNamespace(text="K7M2QX")), ctx(app))
        assert "не найдена" in chat.sent[-1][0]  # такой очереди нет — понятный текст
        await bot.text(SimpleNamespace(**vars(u), message=SimpleNamespace(text="привет")), ctx(app))
        assert "QR" in chat.sent[-1][0]  # непонятный текст — подсказка
        await api.close()

    asyncio.run(scenario())

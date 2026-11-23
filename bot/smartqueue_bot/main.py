"""Telegram-бот SmartQueue.

Вход по ссылке из QR: t.me/<бот>?start=K7M2QX → /start K7M2QX. Код можно прислать и просто текстом.
Карточка очереди — одно сообщение: кнопки его обновляют, а не присылают новые.

Переменные окружения: TELEGRAM_BOT_TOKEN, BOT_KEY (тот же, что у сервера), API_URL (по умолчанию http://api:8000).
"""

from __future__ import annotations

import logging
import os
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from smartqueue_bot.client import Api, ApiError
from smartqueue_bot.views import HELP, Keyboard, card, who

log = logging.getLogger("smartqueue.bot")
CODE = re.compile(r"^\s*([A-HJ-NP-Za-hj-np-z2-9]{6})\s*$")


def markup(kb: Keyboard) -> InlineKeyboardMarkup | None:
    if not kb:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in row] for row in kb])


def ident(update: Update) -> tuple[int, str]:
    u: User | None = update.effective_user
    assert u is not None
    return u.id, u.full_name or u.username or "Гость"


def state(ctx: ContextTypes.DEFAULT_TYPE) -> dict:
    assert ctx.user_data is not None
    return ctx.user_data


async def say(update: Update, text: str, kb: Keyboard | None = None) -> None:
    chat = update.effective_chat
    assert chat is not None
    await chat.send_message(text, parse_mode=ParseMode.HTML, reply_markup=markup(kb or []))


def api(ctx: ContextTypes.DEFAULT_TYPE) -> Api:
    return ctx.application.bot_data["api"]


async def show(update: Update, ctx: ContextTypes.DEFAULT_TYPE, code: str, join: bool = False) -> None:
    """Показать карточку очереди; при join — сначала встать."""
    tg_id, name = ident(update)
    a = api(ctx)
    try:
        if join:
            await a.join(code, tg_id, name)
        q = await a.queue(code, tg_id, name)
        q.update(next((x for x in await a.my_queues(tg_id, name) if x["code"] == q["code"]), {}))
        me = await a.me(code, tg_id, name)
        text, kb = card(q, me)
    except ApiError as e:
        text, kb = f"⚠️ {e.message}", []
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup(kb)
        )
    else:
        await say(update, text, kb)


# ---------------------------------------------------------------- команды
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if ctx.args and CODE.match(ctx.args[0]):
        await show(update, ctx, ctx.args[0].upper(), join=True)
    else:
        await say(update, HELP)


async def new(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    state(ctx)["await"] = "title"
    await say(update, "Как назвать очередь? Например: «Очередь к 304 ауд.»")


async def my(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id, name = ident(update)
    qs = await api(ctx).my_queues(tg_id, name)
    if not qs:
        await say(update, "Ты пока не в очереди. Пришли код или /new.")
        return
    kb = [[(f"{q['title']} · {q['code']}", f"r:{q['code']}")] for q in qs]
    await say(update, "Твои очереди:", kb)


async def text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message.text if update.message and update.message.text else ""
    st = state(ctx)
    if st.get("await") == "title":
        st["await"], st["title"] = None, msg.strip()[:50]
        kb = [[("Обычная", "nt:regular"), ("Бизнес", "nt:business")]]
        await say(
            update,
            "Какая очередь?\n• Обычная — управляет первый в очереди.\n• Бизнес — вызывает оператор.",
            kb,
        )
    elif m := CODE.match(msg):
        await show(update, ctx, m.group(1).upper(), join=True)
    else:
        await say(update, HELP)


# ---------------------------------------------------------------- кнопки
async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cq = update.callback_query
    assert cq is not None
    action, _, arg = (cq.data or "").partition(":")
    tg_id, name = ident(update)
    a = api(ctx)
    try:
        if action == "nt":
            q = await a.create(state(ctx).get("title") or "Очередь", arg, tg_id, name)
            await cq.answer("Очередь создана")
            await cq.edit_message_text(
                f"Готово. Код очереди: <code>{q['code']}</code>", parse_mode=ParseMode.HTML
            )
            await show(update, ctx, q["code"])
            return
        if action == "w":
            q = await a.queue(arg, tg_id, name)
            await cq.answer()
            await say(update, who(q, await a.entries(arg, tg_id, name)))
            return
        if action in ("l", "n", "t"):
            status = {"l": "left", "n": "served", "t": "removed"}[action]
            entry = await a.set_status(int(arg), status, tg_id, name)
            await cq.answer(
                {"l": "Ты вышел из очереди", "n": "Очередь сдвинулась", "t": "Управление у тебя"}[action]
            )
            code = entry["code"]
        elif action == "c":
            called = await a.call_next(arg, tg_id, name)
            await cq.answer(f"Вызван №{called['number']}")
            code = arg
        elif action == "x":
            await a.close_queue(arg, tg_id, name)
            await cq.answer("Очередь закрыта")
            code = arg
        else:  # r, j
            await cq.answer()
            code = arg
        await show(update, ctx, code, join=action == "j")
    except ApiError as e:
        await cq.answer(e.message, show_alert=True)


def build(token: str, api_url: str, bot_key: str) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["api"] = Api(api_url, bot_key)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new))
    app.add_handler(CommandHandler("my", my))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = build(token, os.environ.get("API_URL", "http://api:8000"), os.environ["BOT_KEY"])
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

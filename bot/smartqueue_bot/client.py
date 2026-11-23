"""Обращения бота к API SmartQueue от имени пользователя Telegram.

Бот не хранит очереди сам: всё состояние на сервере, поэтому сайт, приложение и бот видят одну очередь.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Api:
    def __init__(self, base_url: str, bot_key: str, transport: httpx.AsyncBaseTransport | None = None):
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/api/v1", transport=transport, timeout=10
        )
        self._key = bot_key

    async def close(self) -> None:
        await self._http.aclose()

    def _headers(self, telegram_id: int, name: str) -> dict[str, str]:
        # заголовки HTTP — только ASCII, поэтому имя кодируется
        return {
            "X-Bot-Key": self._key,
            "X-Telegram-Id": str(telegram_id),
            "X-Telegram-Name": quote(name or ""),
        }

    async def _call(self, method: str, path: str, tg_id: int, name: str, json: Any = None) -> Any:
        r = await self._http.request(method, path, headers=self._headers(tg_id, name), json=json)
        body = r.json() if r.content else None
        if r.status_code >= 400:
            err = (body or {}).get("error", {}) if isinstance(body, dict) else {}
            raise ApiError(r.status_code, err.get("code", "unknown"), err.get("message", "Ошибка сервера"))
        return body

    # --- очереди
    async def queue(self, code: str, tg_id: int, name: str) -> dict:
        return await self._call("GET", f"/queues/{code}", tg_id, name)

    async def create(self, title: str, type: str, tg_id: int, name: str) -> dict:
        return await self._call(
            "POST", "/queues", tg_id, name, {"title": title, "type": type, "source": "bot"}
        )

    async def close_queue(self, code: str, tg_id: int, name: str) -> dict:
        return await self._call("PATCH", f"/queues/{code}", tg_id, name, {"status": "closed"})

    async def my_queues(self, tg_id: int, name: str) -> list[dict]:
        return await self._call("GET", "/me/queues", tg_id, name)

    # --- записи
    async def join(self, code: str, tg_id: int, name: str) -> dict:
        return await self._call("POST", f"/queues/{code}/entries", tg_id, name, {"source": "bot"})

    async def me(self, code: str, tg_id: int, name: str) -> dict | None:
        try:
            return await self._call("GET", f"/queues/{code}/entries/me", tg_id, name)
        except ApiError as e:
            if e.status == 404:
                return None
            raise

    async def entries(self, code: str, tg_id: int, name: str) -> list[dict]:
        return await self._call("GET", f"/queues/{code}/entries", tg_id, name)

    async def set_status(self, entry_id: int, status: str, tg_id: int, name: str) -> dict:
        return await self._call("PATCH", f"/entries/{entry_id}", tg_id, name, {"status": status})

    async def call_next(self, code: str, tg_id: int, name: str) -> dict:
        return await self._call("POST", f"/queues/{code}/calls", tg_id, name)

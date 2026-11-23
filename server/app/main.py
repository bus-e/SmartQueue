"""API-сервер SmartQueue: проверка работы, вход гостя, очереди и записи. Описание API — на /docs."""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import Unauthorized, router
from app.domain.model import Conflict, DomainError, Forbidden, QueueClosed, QueueCode
from app.store import MemoryStore, NotFound

# Ошибка правила -> HTTP-код. Остальные нарушения правил — 400.
STATUS = [(Unauthorized, 401), (Forbidden, 403), (NotFound, 404), (Conflict, 409), (QueueClosed, 410)]


def error(status: int, code: str, message: str) -> JSONResponse:
    """Единый формат ошибки: {error: {code, message}} — его разбирают сайт, приложение и бот."""
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def create_app(store: MemoryStore | None = None) -> FastAPI:
    app = FastAPI(
        title="SmartQueue API", version="0.2.0", docs_url="/docs", openapi_url="/api/v1/openapi.json"
    )
    app.state.store = store or MemoryStore()
    app.include_router(router)

    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, e: DomainError) -> JSONResponse:
        status = next((code for cls, code in STATUS if isinstance(e, cls)), 400)
        return error(status, type(e).__name__, str(e))

    @app.exception_handler(ValueError)
    async def value_error(_: Request, e: ValueError) -> JSONResponse:
        return error(422, "ValueError", str(e))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, e: RequestValidationError) -> JSONResponse:
        first = e.errors()[0] if e.errors() else {}
        where = ".".join(str(x) for x in first.get("loc", [])[1:])
        return error(422, "ValidationError", f"{where}: {first.get('msg', 'неверные данные')}".strip(": "))

    @app.get("/api/v1/health", tags=["служебное"])
    def health() -> dict:
        """Сервер запущен."""
        return {"status": "ok", "version": app.version}

    @app.get("/api/v1/codes/{raw}/check", tags=["служебное"])
    def check_code(raw: str) -> dict:
        """Проверка формата кода очереди (6 символов без 0, O, 1, I)."""
        try:
            return {"code": QueueCode.parse(raw).value, "valid": True}
        except ValueError as e:
            return {"code": raw, "valid": False, "message": str(e)}

    return app


app = create_app()

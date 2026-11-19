"""API-сервер SmartQueue. Спринт 1: каркас, проверка работы, описание API на /docs."""

from fastapi import FastAPI

from app.domain.model import QueueCode

app = FastAPI(title="SmartQueue API", version="0.1.0", docs_url="/docs", openapi_url="/api/v1/openapi.json")


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

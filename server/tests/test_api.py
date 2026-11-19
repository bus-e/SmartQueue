from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_openapi_is_published():
    assert client.get("/api/v1/openapi.json").status_code == 200


def test_code_check():
    assert client.get("/api/v1/codes/k7m 2qx/check").json() == {"code": "K7M2QX", "valid": True}
    assert client.get("/api/v1/codes/K0M2QX/check").json()["valid"] is False

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("UPI_DEV_MODE", "0")
    monkeypatch.setenv("SITE_ACCESS_PASSWORD", "segredo-teste")
    monkeypatch.setenv("SITE_AUTH_SECRET", "test-secret")

    from app.config import settings

    monkeypatch.setattr(settings, "UPI_DEV_MODE", False)
    monkeypatch.setattr(settings, "SITE_ACCESS_PASSWORD", "segredo-teste")
    monkeypatch.setattr(settings, "SITE_AUTH_SECRET", "test-secret")

    from app.main import app

    return TestClient(app)


def test_auth_config_required_in_prod(auth_client):
    r = auth_client.get("/auth/config")
    assert r.status_code == 200
    assert r.json()["required"] is True


def test_login_wrong_password(auth_client):
    r = auth_client.post("/auth/login", json={"password": "errada"})
    assert r.status_code == 401


def test_chat_requires_token(auth_client):
    r = auth_client.post("/chat", json={"message": "oi"})
    assert r.status_code == 401


def test_chat_with_valid_token(auth_client):
    login = auth_client.post("/auth/login", json={"password": "segredo-teste"})
    token = login.json()["token"]

    with pytest.MonkeyPatch.context() as mp:
        from unittest.mock import AsyncMock, patch

        with patch(
            "app.main.ai_service.get_response",
            new_callable=AsyncMock,
            return_value={"response": "ok", "emotion": "happy", "audio": ""},
        ):
            r = auth_client.post(
                "/chat",
                json={"message": "oi"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json()["response"] == "ok"

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """Cliente de teste com auth desativada (UPI_DEV_MODE=True)."""
    from app.config import settings

    monkeypatch.setattr(settings, "UPI_DEV_MODE", True)
    monkeypatch.setattr(settings, "SITE_ACCESS_PASSWORD", "")

    with patch(
        "app.main.ai_service.get_response",
        new_callable=AsyncMock,
        return_value={
            "response": "Oi do teste!",
            "emotion": "happy",
            "audio": "",
        },
    ):
        from app.main import app

        yield TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["status"] == "healthy"


def test_api_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_chat_direct(client):
    r = client.post("/chat", json={"message": "Olá"})
    assert r.status_code == 200
    body = r.json()
    assert body["response"] == "Oi do teste!"
    assert body["emotion"] == "happy"


def test_chat_api_route(client):
    r = client.post("/api/chat", json={"message": "Oi"})
    assert r.status_code == 200
    assert "response" in r.json()


def test_chat_forwards_history(client):
    with patch(
        "app.main.ai_service.get_response",
        new_callable=AsyncMock,
        return_value={"response": "ok", "emotion": "happy", "audio": ""},
    ) as get_response:
        from app.main import app

        test_client = TestClient(app)
        r = test_client.post(
            "/chat",
            json={
                "message": "E o horário?",
                "chat_history": [
                    {"role": "user", "content": "Onde fica o NAPSI?"},
                    {"role": "assistant", "content": "Bloco A, Sala 12."},
                ],
            },
        )
        assert r.status_code == 200
        get_response.assert_awaited_once()
        history = get_response.await_args.kwargs.get("chat_history") or []
        assert len(history) == 2


def test_ingest(client):
    with patch("app.main.ai_service.add_document", new_callable=AsyncMock) as add:
        r = client.post("/ingest", json={"text": "NAPSI sala 12", "metadata": {}})
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        add.assert_awaited_once()

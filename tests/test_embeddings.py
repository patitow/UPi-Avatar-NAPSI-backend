"""Testes de seleção de provider de embeddings (OpenAI vs Ollama)."""

from unittest.mock import patch

import pytest

from app.services.ai_service import AIService


def test_embeddings_backend_auto_prefers_openai_with_key():
    with patch.object(AIService, "_openai_api_key", return_value="sk-test"):
        assert AIService._embeddings_backend() == "openai"


def test_embeddings_backend_auto_falls_back_to_ollama_without_key():
    with patch.object(AIService, "_openai_api_key", return_value=""):
        assert AIService._embeddings_backend() == "ollama"


def test_embeddings_backend_forced_ollama():
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.EMBEDDINGS_PROVIDER = "ollama"
        with patch.object(AIService, "_openai_api_key", return_value="sk-test"):
            assert AIService._embeddings_backend() == "ollama"


def test_embeddings_backend_forced_openai():
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.EMBEDDINGS_PROVIDER = "openai"
        with patch.object(AIService, "_openai_api_key", return_value=""):
            assert AIService._embeddings_backend() == "openai"


def test_init_embeddings_uses_openai_when_configured():
    service = AIService.__new__(AIService)
    service.embeddings_provider = "none"
    mock_embeddings = object()

    def fake_openai(self):
        self.embeddings_provider = "openai"
        return mock_embeddings

    with patch.object(AIService, "_embeddings_backend", return_value="openai"), \
         patch.object(AIService, "_init_openai_embeddings", fake_openai):
        result = AIService._init_embeddings(service)

    assert result is mock_embeddings
    assert service.embeddings_provider == "openai"


def test_init_embeddings_falls_back_to_ollama():
    service = AIService.__new__(AIService)
    service.embeddings_provider = "none"
    mock_embeddings = object()

    with patch.object(AIService, "_embeddings_backend", return_value="openai"), \
         patch.object(AIService, "_init_openai_embeddings", return_value=None), \
         patch.object(AIService, "_init_ollama_embeddings", return_value=mock_embeddings):
        result = AIService._init_embeddings(service)

    assert result is mock_embeddings

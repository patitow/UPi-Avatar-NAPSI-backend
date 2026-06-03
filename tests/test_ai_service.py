import json

import pytest
from unittest.mock import MagicMock, patch
from app.services.ai_service import AIService


@pytest.fixture
def mock_service():
    mock_emb = MagicMock()
    mock_emb.embed_query.return_value = [0.0] * 16
    mock_llm = MagicMock()
    mock_vs = MagicMock()
    mock_vs.similarity_search.return_value = [
        MagicMock(page_content="Contexto de teste")
    ]

    with patch.object(AIService, "_init_embeddings", return_value=mock_emb), \
         patch.object(AIService, "_init_llm", return_value=mock_llm), \
         patch.object(AIService, "init_knowledge_base"), \
         patch("app.services.ai_service.create_semantic_cache", return_value=None):
        service = AIService()
        service.vector_store = mock_vs
        service.using_fallback = False
        yield service


@pytest.mark.asyncio
async def test_get_response(mock_service):
    mock_service.llm.invoke.return_value.content = (
        '{"response": "O NAPSI fica no Bloco A, Sala 12.", "emotion": "happy"}'
    )
    with patch.object(mock_service, "_lookup_semantic_cache", return_value=None), \
         patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await mock_service.get_response("Onde fica o NAPSI?")
    assert out["emotion"] == "happy"
    assert "Bloco" in out["response"] or "Sala" in out["response"]
    mock_service.llm.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_cache_hit(mock_service):
    with patch.object(
        mock_service,
        "_lookup_semantic_cache",
        return_value={"response": "Do cache", "emotion": "calm"},
    ), patch("app.services.ai_service.synthesize_speech", return_value="audio"):
        out = await mock_service.get_response("Como agendar atendimento?")
    assert out["response"] == "Do cache"
    mock_service.llm.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_greeting_oi_lindo_no_intimate_in_response(mock_service):
    mock_service.llm.invoke.return_value.content = (
        '{"response": "Oi! Sou o UPi do NAPSI. Quer saber sobre atendimento ou localização?", '
        '"emotion": "happy"}'
    )
    with patch.object(mock_service, "_lookup_semantic_cache", return_value=None), \
         patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await mock_service.get_response("oi lindo")
    assert "UPi" in out["response"] or "NAPSI" in out["response"]
    assert "bem-vindo" not in out["response"].lower()
    assert "saúde mental" not in out["response"].lower()
    lower = out["response"].lower()
    assert "lindo" not in lower
    assert "linda" not in lower
    mock_service.llm.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_sanitize_strips_intimate_terms(mock_service):
    raw = mock_service._sanitize_response_tone(
        "Oi lindo! Massa demais, querida, visse?"
    )
    assert "lindo" not in raw.lower()
    assert "linda" not in raw.lower()
    assert "querida" not in raw.lower()


@pytest.mark.asyncio
async def test_cache_skip_wrong_intent(mock_service):
    mock_cache = MagicMock()
    mock_cache.lookup.return_value = json.dumps(
        {
            "response": "Para agendar, envie e-mail para napsi@poli.br.",
            "emotion": "neutral",
        },
        ensure_ascii=False,
    )
    mock_service.semantic_cache = mock_cache
    mock_service.llm.invoke.return_value.content = (
        '{"response": "O NAPSI fica no Bloco A, Sala 12.", "emotion": "happy"}'
    )
    with patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await mock_service.get_response("Onde fica o NAPSI?")
    assert "Bloco" in out["response"] or "Sala" in out["response"]
    mock_service.llm.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_llm_fallback(mock_service):
    mock_service.llm.invoke.side_effect = Exception("down")
    with patch.object(mock_service, "_lookup_semantic_cache", return_value=None), \
         patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await mock_service.get_response("onde fica o napsi")
    assert "NAPSI" in out["response"] or "UPi" in out["response"]

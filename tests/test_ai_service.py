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
        '{"response": "Oi!", "emotion": "happy"}'
    )
    with patch.object(mock_service, "_lookup_semantic_cache", return_value=None), \
         patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await mock_service.get_response("Olá")
    assert out["emotion"] == "happy"
    mock_service.llm.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_cache_hit(mock_service):
    with patch.object(
        mock_service,
        "_lookup_semantic_cache",
        return_value={"response": "Do cache", "emotion": "calm"},
    ), patch("app.services.ai_service.synthesize_speech", return_value="audio"):
        out = await mock_service.get_response("Oi")
    assert out["response"] == "Do cache"
    mock_service.llm.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_llm_fallback(mock_service):
    mock_service.llm.invoke.side_effect = Exception("down")
    with patch.object(mock_service, "_lookup_semantic_cache", return_value=None), \
         patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await mock_service.get_response("oi")
    assert "NAPSI" in out["response"] or "UPi" in out["response"]

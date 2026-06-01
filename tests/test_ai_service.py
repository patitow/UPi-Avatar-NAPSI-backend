import pytest
from unittest.mock import MagicMock, patch
from app.services.ai_service import AIService


@pytest.fixture
def mock_service():
    """AIService com todas as dependências externas substituídas por mocks."""
    mock_emb = MagicMock()
    mock_emb.embed_query.return_value = [0.0] * 10

    mock_llm = MagicMock()

    mock_vs = MagicMock()
    mock_vs.get_by_ids.return_value = []
    mock_vs.similarity_search.return_value = [MagicMock(page_content="Contexto de teste")]

    with patch.object(AIService, "_init_embeddings", return_value=mock_emb), \
         patch.object(AIService, "_init_llm", return_value=mock_llm), \
         patch("app.services.ai_service.PGVector", return_value=mock_vs):
        service = AIService(connection_string="postgresql://mock")
        service.using_fallback = False
        yield service


@pytest.mark.asyncio
async def test_ai_service_initialization(mock_service):
    assert mock_service.system_instructions is not None
    assert mock_service.vector_store is not None


@pytest.mark.asyncio
async def test_get_response_logic(mock_service):
    mock_service.llm.invoke.return_value.content = '{"response": "Massa demais, UPi aqui!", "emotion": "happy"}'

    with patch.object(mock_service, "_try_connect_cache_index", return_value=None):
        response = await mock_service.get_response("Oi UPi")

    assert "response" in response
    assert response["emotion"] == "happy"
    mock_service.llm.invoke.assert_called_once()
    mock_service.vector_store.similarity_search.assert_called_once_with("Oi UPi", k=3)


@pytest.mark.asyncio
async def test_fallback_logic(mock_service):
    """Testa se o fallback para Ollama é acionado quando o LLM principal falha."""
    mock_service.llm.invoke.side_effect = Exception("OpenAI Down")

    with patch("app.services.ai_service.ChatOllama") as mock_ollama_cls, \
         patch.object(mock_service, "_try_connect_cache_index", return_value=None):
        mock_ollama_instance = MagicMock()
        mock_ollama_instance.invoke.return_value.content = "Resposta via Ollama"
        mock_ollama_cls.return_value = mock_ollama_instance

        response = await mock_service.get_response("Dúvida")

    assert response.get("response") == "Resposta via Ollama"
    mock_ollama_instance.invoke.assert_called_once()

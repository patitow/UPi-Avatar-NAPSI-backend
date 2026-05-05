import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.services.ai_service import AIService

@pytest.fixture
def mock_embeddings():
    with patch('app.services.ai_service.HuggingFaceEmbeddings') as mock:
        yield mock

@pytest.fixture
def mock_vector_store():
    with patch('app.services.ai_service.PGVector') as mock:
        instance = mock.return_value
        instance.similarity_search.return_value = [
            MagicMock(page_content="Contexto de teste")
        ]
        yield instance

@pytest.mark.asyncio
async def test_ai_service_initialization(mock_embeddings, mock_vector_store):
    # Testa se o serviço inicia corretamente com mocks
    service = AIService(connection_string="postgresql://mock")
    assert service.system_instructions is not None
    assert service.vector_store is not None

@pytest.mark.asyncio
async def test_get_response_logic(mock_embeddings, mock_vector_store):
    # Testa a lógica de geração de resposta
    service = AIService(connection_string="postgresql://mock")
    
    # Mock do LLM
    service.llm = MagicMock()
    service.llm.invoke.return_value.content = "Resposta do UPi massa!"
    
    response = await service.get_response("Oi UPi")
    
    assert "UPi" in response
    service.llm.invoke.assert_called_once()
    service.vector_store.similarity_search.assert_called_once_with("Oi UPi", k=2)

@pytest.mark.asyncio
async def test_fallback_logic(mock_embeddings, mock_vector_store):
    # Testa se o fallback é chamado em caso de erro no LLM principal
    service = AIService(connection_string="postgresql://mock")
    service.using_fallback = False # Simula que estamos usando OpenAI
    
    # Mock que falha na primeira e passa na segunda (fallback)
    service.llm.invoke.side_effect = Exception("OpenAI Down")
    
    with patch('app.services.ai_service.ChatOllama') as mock_ollama:
        mock_ollama_instance = mock_ollama.return_value
        mock_ollama_instance.invoke.return_value.content = "Resposta via Ollama"
        
        response = await service.get_response("Dúvida")
        
        assert response == "Resposta via Ollama"
        mock_ollama_instance.invoke.assert_called_once()

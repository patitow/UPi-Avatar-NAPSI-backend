import pytest
from unittest.mock import MagicMock, patch

from app.services.ai_service import AIService


@pytest.fixture
def mock_service():
    with patch.object(AIService, "_init_embeddings", return_value=None), \
         patch.object(AIService, "_init_llm", return_value=None), \
         patch.object(AIService, "init_knowledge_base"), \
         patch("app.services.ai_service.create_semantic_cache", return_value=None):
        yield AIService()


@pytest.mark.parametrize(
    "user_input",
    ["oi", "oi lindo", "Olá!!", "e aí"],
)
@pytest.mark.asyncio
async def test_greetings_never_use_intimate_terms(mock_service, user_input):
    with patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await mock_service.get_response(user_input)
    lower = out["response"].lower()
    for banned in ("lindo", "linda", "querido", "querida", "amor"):
        assert banned not in lower, out["response"]


@pytest.mark.asyncio
async def test_llm_output_sanitized(mock_service):
    mock_service.llm = MagicMock()
    mock_service.llm.invoke.return_value.content = (
        '{"response": "Oi linda! Massa demais!", "emotion": "happy"}'
    )
    mock_service.vector_store = MagicMock()
    mock_service.vector_store.similarity_search.return_value = []

    with patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await mock_service.get_response("Como funciona o NAPSI?")

    assert "linda" not in out["response"].lower()
    assert "lindo" not in out["response"].lower()

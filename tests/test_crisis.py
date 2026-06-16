import pytest
from unittest.mock import patch

from app.services.ai_service import AIService
from app.services.intent import classify_intent, is_crisis_message, is_distress_message


@pytest.mark.parametrize(
    "message",
    [
        "Penso em me machucar",
        "Não aguento mais, quero desistir de tudo",
        "Quero morrer",
    ],
)
def test_crisis_intent(message):
    assert classify_intent(message) == "crisis"
    assert is_crisis_message(message)
    assert not is_distress_message(message)


def test_panic_is_distress_not_crisis():
    msg = "Estou em crise de pânico agora"
    assert classify_intent(msg) == "distress"
    assert is_distress_message(msg)
    assert not is_crisis_message(msg)


@pytest.mark.asyncio
async def test_crisis_response_includes_cvv():
    from unittest.mock import MagicMock

    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = (
        '{"response": "Fora da minha área.", "emotion": "neutral"}'
    )
    with patch.object(AIService, "_init_embeddings", return_value=None), \
         patch.object(AIService, "_init_llm", return_value=mock_llm), \
         patch.object(AIService, "init_knowledge_base"), \
         patch("app.services.ai_service.create_semantic_cache", return_value=None):
        service = AIService()
    service.vector_store = MagicMock()
    service.vector_store.similarity_search_with_score.return_value = []

    with patch.object(service, "_lookup_semantic_cache", return_value=None), \
         patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await service.get_response("Penso em me machucar")

    lower = out["response"].lower()
    assert "188" in lower or "cvv" in lower
    assert "napsi" in lower
    assert "fora da minha área" not in lower

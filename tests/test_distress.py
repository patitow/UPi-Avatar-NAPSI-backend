import pytest
from unittest.mock import MagicMock, patch

from app.services.ai_service import AIService
from app.services.intent import classify_intent, is_distress_message


@pytest.mark.parametrize(
    "message",
    [
        "Estou me sentindo mal, me ajude",
        "Preciso de ajuda, estou ansioso",
        "Não estou bem",
        "Estou passando mal",
    ],
)
def test_distress_intent_detected(message):
    assert is_distress_message(message)
    assert classify_intent(message) == "distress"


@pytest.mark.asyncio
async def test_distress_never_out_of_scope():
    with patch.object(AIService, "_init_embeddings", return_value=None), \
         patch.object(AIService, "_init_llm", return_value=None), \
         patch.object(AIService, "init_knowledge_base"), \
         patch("app.services.ai_service.create_semantic_cache", return_value=None):
        service = AIService()

    with patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await service.get_response("Estou me sentindo mal, me ajude")

    lower = out["response"].lower()
    assert "fora da minha área" not in lower
    assert "napsi" in lower or "napsi@poli" in lower
    assert out["emotion"] == "calm"


@pytest.mark.asyncio
async def test_llm_out_of_scope_replaced_for_distress():
    with patch.object(AIService, "_init_embeddings", return_value=None), \
         patch.object(AIService, "_init_llm", return_value=MagicMock()), \
         patch.object(AIService, "init_knowledge_base"), \
         patch("app.services.ai_service.create_semantic_cache", return_value=None):
        service = AIService()
    service.vector_store = MagicMock()
    service.vector_store.similarity_search_with_score.return_value = []
    service.llm.invoke.return_value.content = (
        '{"response": "Oxe, isso está fora da minha área, visse? '
        'Só posso ajudar com assuntos do NAPSI/UPE.", "emotion": "neutral"}'
    )

    with patch.object(service, "_lookup_semantic_cache", return_value=None), \
         patch("app.services.ai_service.synthesize_speech", return_value=""):
        out = await service.get_response("Estou me sentindo mal")

    assert "fora da minha área" not in out["response"].lower()

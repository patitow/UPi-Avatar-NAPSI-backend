"""Base de conhecimento e expectativas ACI."""
import os

from app.services.ai_service import AIService
from app.services.intent import classify_intent, is_distress_message


def test_load_seed_texts_includes_aci_knowledge():
    svc = AIService.__new__(AIService)
    texts = svc._load_seed_texts()
    joined = "\n".join(texts).lower()
    assert "napsi" in joined
    assert "semana de provas" in joined or "tempo adicional" in joined
    assert "calour" in joined or "calouros" in joined
    assert "escolaridade" in joined


def test_aci_distress_and_services_intents():
    assert classify_intent("Preciso de acolhimento psicológico") == "distress"
    assert classify_intent("Me ajude a entender os serviços do NAPSI") == "services"
    assert not is_distress_message("Me ajude a entender os serviços do NAPSI")
    assert classify_intent("Como pedir tempo adicional na prova?") == "services"
    assert classify_intent("Sofro bullying na faculdade") == "distress"


def test_knowledge_files_exist():
    base = os.path.join(
        os.path.dirname(__file__), "..", "data"
    )
    assert os.path.isfile(os.path.join(base, "napsi_info.txt"))
    assert os.path.isfile(
        os.path.join(base, "knowledge", "napsi_expectativas_aci.txt")
    )

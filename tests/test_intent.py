from app.services.intent import (
    classify_intent,
    rag_search_query,
    response_matches_intent,
)


def test_classify_intent_samples():
    assert classify_intent("Onde fica o NAPSI?") == "location"
    assert classify_intent("Como agendar um atendimento?") == "scheduling"
    assert classify_intent("Quais serviços o NAPSI oferece?") == "services"
    assert classify_intent("O NAPSI apoia alunos com TEA?") == "tea"


def test_rag_query_adds_hints():
    q = rag_search_query("Onde fica o NAPSI?")
    assert "Bloco" in q or "localização" in q.lower()


def test_response_matches_intent_tea():
    assert response_matches_intent(
        "Sim, apoiamos alunos com TEA (Transtorno do Espectro Autista).",
        "tea",
    )
    assert not response_matches_intent(
        "Para agendar, envie e-mail para napsi@poli.br.",
        "tea",
    )


def test_response_matches_intent_location():
    assert response_matches_intent("Fica no Bloco A, Sala 12.", "location")
    assert not response_matches_intent("Só agendar por e-mail.", "location")

"""Classificação leve de intenção para RAG e cache semântico."""
from __future__ import annotations

import re
from typing import Literal

Intent = Literal["location", "scheduling", "services", "tea", "general"]

_RULES: list[tuple[Intent, re.Pattern[str]]] = [
    ("tea", re.compile(r"\b(tea|autis|espectro\s+autis|tdah|dislexia)\b", re.I)),
    (
        "location",
        re.compile(
            r"\b(onde|fica|localiza|endere[cç]o|sala\s+\d|bloco\s+[a-z]|como\s+chegar)\b",
            re.I,
        ),
    ),
    (
        "scheduling",
        re.compile(
            r"\b(agendar|marca(r|ção|ção)|hor[aá]rio|formul[aá]rio|solicitar\s+atendimento)\b",
            re.I,
        ),
    ),
    (
        "services",
        re.compile(
            r"\b(servi[cç]os?|oferece|atendimentos|psicoped|psicol[oó]g|acolhimento|equipe)\b",
            re.I,
        ),
    ),
]

_RAG_HINTS: dict[Intent, str] = {
    "location": "localização Bloco A Sala 12 horário funcionamento",
    "scheduling": "agendar atendimento formulário e-mail napsi@poli.br",
    "services": "serviços psicopedagógico psicológico social inclusão",
    "tea": "TEA Transtorno do Espectro Autista apoio inclusão",
}

_INTENT_SNIPPETS: dict[Intent, str] = {
    "location": (
        "LOCALIZAÇÃO: NAPSI no Bloco A, Sala 12, POLI/UPE. "
        "Segunda a sexta, 8h às 17h. Contato: napsi@poli.br."
    ),
    "scheduling": (
        "AGENDAMENTO: formulário no site da POLI (seção NAPSI) ou e-mail napsi@poli.br "
        "com nome, matrícula e demanda; também presencial no Bloco A, Sala 12."
    ),
    "services": (
        "SERVIÇOS: apoio psicopedagógico, psicológico e social; adaptação acadêmica; "
        "orientação a estudantes com deficiência, TEA, TDAH, dislexia e vulnerabilidade."
    ),
    "tea": (
        "TEA: o NAPSI apoia alunos com TEA (Transtorno do Espectro Autista), "
        "com plano de apoio individualizado e inclusão educacional."
    ),
}

_RESPONSE_CHECKS: dict[Intent, re.Pattern[str]] = {
    "location": re.compile(r"\b(bloco|sala\s+\d|localiz|8h|17h)\b", re.I),
    "scheduling": re.compile(r"\b(agendar|e-?mail|formul[aá]rio|napsi@)\b", re.I),
    "services": re.compile(
        r"\b(psicoped|psicol[oó]g|acolhimento|servi[cç]o|apoio)\b", re.I
    ),
    "tea": re.compile(r"\b(tea|autis|espectro)\b", re.I),
}


def classify_intent(text: str) -> Intent:
    if not text or not text.strip():
        return "general"
    for name, pattern in _RULES:
        if pattern.search(text):
            return name
    return "general"


def rag_search_query(user_input: str) -> str:
    intent = classify_intent(user_input)
    hint = _RAG_HINTS.get(intent, "")
    if not hint:
        return user_input.strip()
    return f"{user_input.strip()} {hint}"


_DEFAULT_SNIPPET = (
    "O NAPSI (Núcleo de Apoio Psicopedagógico e Social Inclusivo) da POLI/UPE "
    "oferece apoio psicopedagógico, psicológico e social no Bloco A, Sala 12."
)


def fallback_context(intent: str) -> str:
    return _INTENT_SNIPPETS.get(intent, _DEFAULT_SNIPPET)  # type: ignore[arg-type]


def response_matches_intent(response: str, intent: Intent) -> bool:
    if intent == "general":
        return True
    pattern = _RESPONSE_CHECKS.get(intent)
    if not pattern:
        return True
    return bool(pattern.search(response))

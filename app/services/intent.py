"""Classificação leve de intenção para RAG e cache semântico."""

from __future__ import annotations



import re

from typing import Literal



Intent = Literal[

    "crisis", "distress", "location", "scheduling", "services", "tea", "general"

]



_RULES: list[tuple[Intent, re.Pattern[str]]] = [

    (

        "crisis",

        re.compile(

            r"(penso\s+em\s+me\s+machucar|quero\s+me\s+machucar|me\s+machucar|"

            r"auto[- ]?les[aã]o|suic[ií]d|quero\s+morrer|n[aã]o\s+quero\s+viv|"

            r"tirar\s+(?:a\s+)?minha\s+vida|me\s+matar|"

            r"quero\s+desistir\s+de\s+tudo|acabar\s+com\s+(?:a\s+)?minha\s+vida|"

            r"n[aã]o\s+aguento\s+mais.{0,40}(?:viv|vida|tudo|fim))",

            re.I,

        ),

    ),

    (

        "distress",

        re.compile(

            r"(sentindo\s+mal|me\s+sinto|estou\s+mal|n[aã]o\s+estou\s+bem|"

            r"passando\s+mal|mal[- ]estar|"

            r"(?:estou|to)\s+(?:triste|ansios|deprim)|"

            r"ansiedade|depress|desesper|"

            r"crise\s+de\s+p[aâ]nico|crise\s+ansios|"

            r"semana\s+de\s+prova|"

            r"n[aã]o\s+aguento|sofrimento|bullying|assen[aã]o|"

            r"sa[uú]de\s+mental|preciso\s+de\s+acolhimento|"

            r"(?:me\s+)?ajud(?:e|em)(?!ar\b)(?!\s+(?:a|no|com|sobre|entender|saber|inform))|"

            r"preciso\s+de\s+ajuda)",

            re.I,

        ),

    ),

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

            r"\b(servi[cç]os?|oferece|atendimentos|psicoped|psicol[oó]g|equipe|"

            r"tempo\s+adicional|ambiente\s+separado|adapta[cç][aã]o|"

            r"segunda\s+chamada|abono|calour|nivelamento|provas?|"

            r"vulnerabilidade|aux[ií]lio\s+estudant)\b",

            re.I,

        ),

    ),

]



_RAG_HINTS: dict[Intent, str] = {

    "crisis": "CVV 188 SAMU 192 emergência saúde mental risco vida NAPSI",

    "distress": "acolhimento psicológico saúde mental ansiedade semana de provas NAPSI",

    "location": "localização Bloco A Sala 12 horário funcionamento",

    "scheduling": "agendar atendimento formulário e-mail napsi@poli.br",

    "services": "serviços tempo adicional ambiente separado provas adaptação acadêmica",

    "tea": "TEA Transtorno do Espectro Autista ruído comunicação PAI inclusão",

}



_INTENT_SNIPPETS: dict[Intent, str] = {

    "crisis": (

        "CRISE/RISCO: CVV 188 (24h), SAMU 192 se urgência médica, CAPS da região. "

        "NAPSI: napsi@poli.br, Bloco A Sala 12 (8h–17h). Não substitui emergência."

    ),

    "distress": (

        "ACOLHIMENTO: NAPSI oferece atendimento psicológico e psicossocial para ansiedade, "

        "estresse e crises frequentes na semana de provas. Agende por napsi@poli.br ou "

        "presencial Bloco A, Sala 12 (seg–sex, 8h–17h). Atendimentos são confidenciais."

    ),

    "location": (

        "LOCALIZAÇÃO: NAPSI no Bloco A, Sala 12, POLI/UPE. "

        "Segunda a sexta, 8h às 17h. Contato: napsi@poli.br."

    ),

    "scheduling": (

        "AGENDAMENTO: formulário no site da POLI (seção NAPSI) ou e-mail napsi@poli.br "

        "com nome, matrícula e demanda; também presencial no Bloco A, Sala 12."

    ),

    "services": (

        "SERVIÇOS: apoio psicopedagógico, psicológico e social; adaptações como tempo "

        "adicional e ambiente separado em provas (com laudo quando exigido); nivelamento "

        "para calouros; orientação a estudantes com deficiência, TEA, TDAH, dislexia."

    ),

    "tea": (

        "TEA: NAPSI apoia alunos com TEA (Transtorno do Espectro Autista) com PAI, "

        "ambiente com menos ruído e comunicação clara; articula conscientização com docentes."

    ),

}



_RESPONSE_CHECKS: dict[Intent, re.Pattern[str]] = {

    "crisis": re.compile(r"\b(188|cvv|192|samu|napsi|caps)\b", re.I),

    "distress": re.compile(

        r"\b(napsi|acolh|psicol[oó]g|napsi@|bloco|sala|ajud|samu|192)\b", re.I

    ),

    "location": re.compile(r"\b(bloco|sala\s+\d|localiz|8h|17h)\b", re.I),

    "scheduling": re.compile(r"\b(agendar|e-?mail|formul[aá]rio|napsi@)\b", re.I),

    "services": re.compile(

        r"\b(psicoped|psicol[oó]g|acolhimento|servi[cç]o|apoio)\b", re.I

    ),

    "tea": re.compile(r"\b(tea|autis|espectro)\b", re.I),

}





def is_crisis_message(text: str) -> bool:

    if not text or not text.strip():

        return False

    return classify_intent(text) == "crisis"





def is_distress_message(text: str) -> bool:

    if not text or not text.strip():

        return False

    return classify_intent(text) == "distress"





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



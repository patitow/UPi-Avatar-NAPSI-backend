"""Revisão leve de ortografia e norma culta (pt-BR) nas respostas do UPi."""
from __future__ import annotations

import re

_WRONG_TEA = re.compile(
    r"Transtorno\s+do\s+Tempo\s+Extraordin[aá]rio",
    re.IGNORECASE,
)
_CORRECT_TEA = "Transtorno do Espectro Autista"

_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bde\s+seg\s+a\s+sex\b", re.I), "de segunda a sexta"),
    (re.compile(r"\bseg\s+a\s+sex\b", re.I), "segunda a sexta"),
    (re.compile(r"\bdas\s+8h\s+as\s+17h\b", re.I), "das 8h às 17h"),
    (re.compile(r"\b8h\s+as\s+17h\b", re.I), "8h às 17h"),
    (re.compile(r"\bvoce\b", re.I), "você"),
    (re.compile(r"\bnao\b", re.I), "não"),
    (re.compile(r"\bPoli\b"), "POLI"),
    (re.compile(r"\bemail\b", re.I), "e-mail"),
    (re.compile(r"\b[Pp]ra\b"), "para"),
    (re.compile(r"\b[Tt][áa]\b"), "está"),
    (re.compile(r"\b[Tt][ôo]\b"), "estou"),
    (re.compile(r"\bprobleminha\b", re.I), "problema"),
]


def _capitalize_after_punctuation(text: str) -> str:
    def upper_first(m: re.Match[str]) -> str:
        return m.group(1) + m.group(2).upper()

    text = re.sub(
        r"(^|[.!?]\s+)(para|está|estou|não|oxe|oi|eita)\b",
        upper_first,
        text,
        flags=re.IGNORECASE,
    )
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def polish_portuguese(text: str) -> str:
    if not text or not text.strip():
        return text

    out = _WRONG_TEA.sub(_CORRECT_TEA, text)
    for pattern, repl in _REPLACEMENTS:
        out = pattern.sub(repl, out)
    out = _capitalize_after_punctuation(out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    return out

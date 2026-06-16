from app.services.portuguese import polish_portuguese


def test_fixes_informal_spellings():
    raw = "Pra agendar, voce pode mandar email. Isso tá fora, nao?"
    out = polish_portuguese(raw)
    assert "Para" in out or out.lower().startswith("para")
    assert "você" in out
    assert "está" in out
    assert "não" in out
    assert "e-mail" in out.lower() or "email" not in out.lower()


def test_fixes_tea_hallucination():
    raw = "Apoio para TEA (Transtorno do Tempo Extraordinário)."
    out = polish_portuguese(raw)
    assert "Espectro Autista" in out
    assert "Tempo Extraordinário" not in out


def test_fixes_schedule_abbreviations():
    out = polish_portuguese("De seg a sex, das 8h as 17h.")
    assert "segunda a sexta" in out
    assert "às 17h" in out


def test_para_not_fully_uppercased_after_punctuation():
    out = polish_portuguese("pra agendar, preencha o formulário. para comparecer, vá ao bloco a.")
    assert "PARA" not in out
    assert out.startswith("Para")
    assert ". Para comparecer" in out or ". para comparecer" not in out

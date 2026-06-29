"""Testes do serviço de TTS (app/services/tts.py)."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.tts import clean_text_for_tts, synthesize_speech


# ─── clean_text_for_tts ───────────────────────────────────────────────────────

def test_clean_removes_markdown_bold():
    # NAPSI é transformado para "Náp-si" pelo mapa fonético — correto.
    result = clean_text_for_tts("O **NAPSI** fica na Sala 12.")
    assert "**" not in result
    assert "Sala" in result  # verifica que o restante do texto foi preservado


def test_clean_removes_markdown_italic():
    result = clean_text_for_tts("Ligue *agora* para o CVV.")
    assert "*" not in result
    assert "Ligue" in result


def test_clean_removes_markdown_heading():
    result = clean_text_for_tts("## Servicos do NAPSI")
    assert "#" not in result
    assert "Servicos" in result


def test_clean_removes_markdown_link():
    result = clean_text_for_tts("Veja [mais informacoes](http://napsi.poli.br).")
    assert "[" not in result
    assert "]" not in result
    assert "mais informacoes" in result


def test_clean_phonetic_upe():
    result = clean_text_for_tts("Bem-vindo a UPE!")
    assert "U. P. E." in result


def test_clean_phonetic_napsi():
    result = clean_text_for_tts("O NAPSI esta disponivel.")
    assert "Náp-si" in result


def test_clean_empty_string():
    assert clean_text_for_tts("") == ""


def test_clean_collapses_whitespace():
    result = clean_text_for_tts("Texto  com   espacos   extras.")
    assert "  " not in result


# ─── synthesize_speech ────────────────────────────────────────────────────────

def test_synthesize_speech_none_provider():
    """Provider 'none' deve retornar string vazia sem chamar nenhum TTS."""
    with patch("app.services.tts.settings") as mock_settings:
        mock_settings.TTS_PROVIDER = "none"
        result = synthesize_speech("Ola, mundo!")
    assert result == ""


def test_synthesize_speech_empty_text():
    """Texto vazio apos limpeza deve retornar string vazia."""
    with patch("app.services.tts.settings") as mock_settings:
        mock_settings.TTS_PROVIDER = "gtts"
        # Texto com apenas caracteres removidos pelo cleaner vira string vazia
        result = synthesize_speech("   ")
    assert result == ""


def test_synthesize_speech_gtts_path():
    """Provider gtts deve chamar _synthesize_gtts e retornar data URL."""
    fake_data_url = "data:audio/mp3;base64,AAAA"
    with patch("app.services.tts.settings") as mock_settings, \
         patch("app.services.tts._synthesize_gtts", return_value=fake_data_url) as mock_fn:
        mock_settings.TTS_PROVIDER = "gtts"
        result = synthesize_speech("O NAPSI fica no Bloco A.")
    mock_fn.assert_called_once()
    assert result == fake_data_url


def test_synthesize_speech_gtts_exception_returns_empty():
    """Erro no gTTS deve ser capturado e retornar string vazia."""
    with patch("app.services.tts.settings") as mock_settings, \
         patch("app.services.tts._synthesize_gtts", side_effect=Exception("network error")):
        mock_settings.TTS_PROVIDER = "gtts"
        result = synthesize_speech("Texto qualquer")
    assert result == ""


def test_synthesize_speech_openai_path():
    """Provider openai deve chamar _synthesize_openai e retornar data URL."""
    fake_data_url = "data:audio/mp3;base64,BBBB"
    with patch("app.services.tts.settings") as mock_settings, \
         patch("app.services.tts._synthesize_openai", return_value=fake_data_url) as mock_fn:
        mock_settings.TTS_PROVIDER = "openai"
        result = synthesize_speech("Texto para OpenAI TTS")
    mock_fn.assert_called_once()
    assert result == fake_data_url


def test_synthesize_speech_openai_fallback_to_gtts_on_error():
    """Se openai falhar, deve tentar gTTS como fallback."""
    fake_data_url = "data:audio/mp3;base64,CCCC"
    with patch("app.services.tts.settings") as mock_settings, \
         patch("app.services.tts._synthesize_openai", side_effect=Exception("api down")), \
         patch("app.services.tts._synthesize_gtts", return_value=fake_data_url) as gtts_fn:
        mock_settings.TTS_PROVIDER = "openai"
        result = synthesize_speech("Texto fallback")
    gtts_fn.assert_called_once()
    assert result == fake_data_url

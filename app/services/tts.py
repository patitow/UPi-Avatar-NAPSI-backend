"""Síntese de voz — providers intercambiáveis (gTTS, OpenAI, none)."""
import base64
import io
import re

from app.config import settings


def clean_text_for_tts(text: str) -> str:
    if not text:
        return ""

    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    clean = re.sub(r"\*([^*]+)\*", r"\1", clean)
    clean = re.sub(r"__([^_]+)__", r"\1", clean)
    clean = re.sub(r"_([^_]+)_", r"\1", clean)
    clean = re.sub(r"#+\s+", "", clean)
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
    clean = re.sub(
        r"[^\w\s,.:!?;áéíóúâêîôûàèìòùãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ\-]",
        "",
        clean,
    )

    phonetic_map = {
        r"\bUPE\b": "U. P. E.",
        r"\bPOLI\b": "Póli",
        r"\bNAPSI\b": "Náp-si",
        r"\bOxe\b": "Óxe",
        r"\bvisse\b": "vísse",
        r"\bemail\b": "e-mail",
        r"\b@\b": " arroba ",
    }
    for pattern, replacement in phonetic_map.items():
        clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", clean).strip()


def _to_data_url_mp3(raw: bytes) -> str:
    return f"data:audio/mp3;base64,{base64.b64encode(raw).decode('utf-8')}"


def _synthesize_gtts(text: str) -> str:
    from gtts import gTTS

    fp = io.BytesIO()
    gTTS(text=text, lang="pt", tld="com.br", slow=False).write_to_fp(fp)
    fp.seek(0)
    return _to_data_url_mp3(fp.read())


def _synthesize_openai(text: str) -> str:
    import os
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY ausente para TTS OpenAI")

    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(
        model="tts-1",
        voice=settings.TTS_OPENAI_VOICE,
        input=text,
    )
    return _to_data_url_mp3(response.content)


def synthesize_speech(text: str) -> str:
    """
    Retorna data URL de áudio ou string vazia se desativado / falha.
    Provider via TTS_PROVIDER (gtts | openai | none).
    """
    provider = (settings.TTS_PROVIDER or "gtts").lower().strip()
    if provider == "none":
        return ""

    clean = clean_text_for_tts(text)
    if not clean:
        return ""

    try:
        if provider == "openai":
            return _synthesize_openai(clean)
        return _synthesize_gtts(clean)
    except Exception as e:
        print(f"[TTS] Falha com provider={provider}: {e}", flush=True)
        if provider != "gtts":
            try:
                return _synthesize_gtts(clean)
            except Exception as e2:
                print(f"[TTS] Fallback gTTS falhou: {e2}", flush=True)
        return ""

import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "true" if default else "false").lower()
    return raw in ("1", "true", "yes", "on")


class Settings(BaseSettings):
    APP_NAME: str = "UPi AI Backend"
    DEBUG: bool = False

    # true = Chroma + cache JSON em disco, sem Postgres/Redis (desenvolvimento local)
    UPI_DEV_MODE: bool = _env_bool("UPI_DEV_MODE")

    # true (padrão) = sem atalhos por regex; tudo via LLM + RAG. Use 0 para reativar atalhos.
    UPI_DISABLE_REGEX_ROUTES: bool = _env_bool(
        "UPI_DISABLE_REGEX_ROUTES", default=True
    )

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-5-nano"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    # auto = OpenAI se OPENAI_API_KEY existir; senão Ollama. Valores: auto | openai | ollama
    EMBEDDINGS_PROVIDER: str = os.getenv("EMBEDDINGS_PROVIDER", "auto")
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    COLLECTION_NAME: str = "upi_knowledge"
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    DEV_CACHE_PATH: str = os.getenv(
        "DEV_CACHE_PATH", "./data/dev_semantic_cache.json"
    )

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://upi_user:upi_password@localhost:5432/upi_db",
    )

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    SEMANTIC_CACHE_DISTANCE: float = float(
        os.getenv("SEMANTIC_CACHE_DISTANCE", "0.12")
    )

    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "gtts")
    TTS_OPENAI_VOICE: str = os.getenv("TTS_OPENAI_VOICE", "nova")

    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    )

    # Produção: senha simples para fechar o site (ignorada em UPI_DEV_MODE=1)
    SITE_ACCESS_PASSWORD: Optional[str] = os.getenv("SITE_ACCESS_PASSWORD")
    SITE_AUTH_SECRET: str = os.getenv("SITE_AUTH_SECRET", "upi-site-auth")

    # Saudações sem LLM (mais rápido); crise/sofrimento sempre têm fast-path
    UPI_FAST_GREETINGS: bool = _env_bool("UPI_FAST_GREETINGS", default=True)
    UPI_LOG_TIMINGS: bool = _env_bool("UPI_LOG_TIMINGS", default=False)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

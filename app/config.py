import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "UPi AI Backend"
    DEBUG: bool = False

    OPENAI_MODEL: str = "gpt-4o-mini"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://upi_user:upi_password@localhost:5432/upi_db",
    )
    COLLECTION_NAME: str = "upi_knowledge"

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    SEMANTIC_CACHE_DISTANCE: float = 0.12

    # TTS: gtts | none | openai (openai exige OPENAI_API_KEY)
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "gtts")
    TTS_OPENAI_VOICE: str = os.getenv("TTS_OPENAI_VOICE", "nova")

    # CORS: lista separada por vírgula ou * (ex.: http://localhost:5173,https://upi.upe.br)
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    )

    class Config:
        env_file = ".env"


settings = Settings()

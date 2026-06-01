import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "UPi AI Backend"
    DEBUG: bool = False
    
    # LLM Models
    OPENAI_MODEL: str = "gpt-4o-mini"
    OLLAMA_MODEL: str = "llama3.2:3b"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMS: int = 3072  # llama3.2:1b → 2048 | llama3.2:3b → 3072
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+psycopg2://upi_user:upi_password@localhost:5432/upi_db"
    )
    COLLECTION_NAME: str = "upi_knowledge"
    
    # Cache
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    SEMANTIC_CACHE_THRESHOLD: float = 0.25

    # Vector store local (fallback sem PostgreSQL)
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")

    # Fallback
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    class Config:
        env_file = ".env"

settings = Settings()

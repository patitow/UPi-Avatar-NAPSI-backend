import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Definições da Aplicação
    APP_NAME: str = "UPi AI Backend"
    DEBUG: bool = False
    
    # Modelos de LLM
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Modelo local correto que tem descarregado no seu computador
    OLLAMA_MODEL: str = "llama3.2:1b"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # Dimensões corretas para o modelo llama3.2:1b (2048)
    EMBEDDING_DIMS: int = 384
    
    # Base de Dados (Garante que o DATABASE_URL exista para evitar AttributeError!)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+psycopg2://upi_user:upi_password@localhost:5432/upi_db"
    )
    COLLECTION_NAME: str = "upi_knowledge"
    
    # Cache Semântico
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    SEMANTIC_CACHE_THRESHOLD: float = 0.25

    # Diretório local do banco ChromaDB para persistência segura fora do Docker
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")

    # Endereço base do seu Ollama local
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    class Config:
        env_file = ".env"

settings = Settings()
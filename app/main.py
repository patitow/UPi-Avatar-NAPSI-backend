# Evita conflito entre Keras 3 e transformers (deve vir antes de qualquer import de ML)
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="UPi API", description="Backend para o Avatar Inteligente NAPSI/UPE")

# Configuração de CORS para permitir o frontend (Vite costuma usar porta 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restringir ao domínio do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.services.ai_service import ai_service
from app.config import settings

class ChatMessage(BaseModel):
    message: str
    user_id: str = "default_user"

@app.get("/")
async def root():
    return {"status": "online", "message": "UPi API está funcionando!"}

@app.get("/health")
async def health():
    """Retorna o estado operacional e quais serviços de IA estão ativos."""
    return {
        "status": "online",
        "llm_provider": "ollama" if ai_service.using_fallback else "openai",
        "llm_model": settings.OLLAMA_MODEL if ai_service.using_fallback else settings.OPENAI_MODEL,
        "embedding_model": settings.OLLAMA_MODEL,
        "vector_store": ai_service.vector_store_type,
    }

@app.post("/chat")
async def chat(payload: ChatMessage):
    response = await ai_service.get_response(payload.message, user_id=payload.user_id)
    return response

class IngestData(BaseModel):
    text: str
    metadata: dict = {}

@app.post("/ingest")
async def ingest(payload: IngestData):
    await ai_service.add_document(payload.text, payload.metadata)
    return {"status": "success", "message": "Documento ingerido com sucesso!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

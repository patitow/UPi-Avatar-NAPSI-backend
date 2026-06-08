from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import pydantic

from app.config import settings
from app.services.ai_service import ai_service

app = FastAPI(
    title="UPi Avatar Backend",
    description="Servidor central do UPi - Suporte Psicopedagógico",
    version="1.0.0"
)

# Configuração de CORS para permitir que o Frontend local (porta 5173) comunique sem bloqueios
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(pydantic.BaseModel):
    message: str
    user_id: Optional[str] = None
    chat_history: Optional[List[dict]] = []

# ==================== ROTAS DE VERIFICAÇÃO DE ESTADO (HEALTH) ====================

@app.get("/health")
def health_check():

    provider = "ollama" if getattr(ai_service, "using_fallback", False) else "openai"

    model = (
        settings.OLLAMA_MODEL
        if provider == "ollama"
        else settings.OPENAI_MODEL
    )

    return {
        "status": "healthy",
        "ok": True,
        "llm_provider": provider,
        "llm_model": model,
        "vector_store": ai_service.vector_store_type
    }

@app.get("/api/health")
def api_health_check():
    """Rota de verificação alternativa para manter a compatibilidade com o frontend."""
    return health_check()


# ==================== ROTAS DE INTERAÇÃO DO CHAT ====================

async def handle_chat_interaction(payload: ChatRequest):
    """Encaminha o diálogo do utilizador para o processamento de inteligência artificial e síntese de voz."""
    try:
        formatted_history = []
        if payload.chat_history:
            from langchain_core.messages import HumanMessage, AIMessage
            for msg in payload.chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    formatted_history.append(HumanMessage(content=content))
                elif role in ["assistant", "ai"]:
                    formatted_history.append(AIMessage(content=content))

        response_data = await ai_service.get_response(
            user_input=payload.message,
            chat_history=formatted_history,
            user_id=payload.user_id
        )
        return response_data
    except Exception as e:
        print(f"[API ERROR]: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

# Rota direta: Utilizada quando a regra de reescrita do proxy do Vite remove o prefixo '/api'
@app.post("/chat")
async def chat_interaction_direct(payload: ChatRequest):
    """Processa o chat na rota base /chat."""
    return await handle_chat_interaction(payload)

# Rota com o prefixo: Utilizada em chamadas diretas de desenvolvimento
@app.post("/api/chat")
async def chat_interaction_api(payload: ChatRequest):
    """Processa o chat na rota /api/chat."""
    return await handle_chat_interaction(payload)
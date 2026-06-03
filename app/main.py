import os
from typing import List, Optional

import pydantic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.ai_service import ai_service

app = FastAPI(
    title="UPi Avatar Backend",
    description="Servidor central do UPi - Suporte Psicopedagógico",
    version="1.0.0",
)


def _parse_cors_origins() -> list[str]:
    raw = (settings.CORS_ORIGINS or "").strip()
    if raw == "*":
        return ["*"]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:5173"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(pydantic.BaseModel):
    message: str
    user_id: Optional[str] = None
    chat_history: Optional[List[dict]] = []


class IngestRequest(pydantic.BaseModel):
    text: str
    metadata: dict = {}


@app.get("/health")
def health_check():
    """Liveness para o front — sem detalhes de stack (LLM, DB, TTS)."""
    return {"status": "healthy", "ok": True}


@app.get("/api/health")
def api_health_check():
    return health_check()


async def handle_chat_interaction(payload: ChatRequest):
    try:
        formatted_history = []
        if payload.chat_history:
            from langchain_core.messages import HumanMessage, AIMessage

            for msg in payload.chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    formatted_history.append(HumanMessage(content=content))
                elif role in ("assistant", "ai"):
                    formatted_history.append(AIMessage(content=content))

        return await ai_service.get_response(
            user_input=payload.message,
            chat_history=formatted_history,
            user_id=payload.user_id,
        )
    except Exception as e:
        print(f"[API ERROR]: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@app.post("/chat")
async def chat_direct(payload: ChatRequest):
    return await handle_chat_interaction(payload)


@app.post("/api/chat")
async def chat_api(payload: ChatRequest):
    return await handle_chat_interaction(payload)


@app.post("/ingest")
async def ingest(payload: IngestRequest):
    await ai_service.add_document(payload.text, payload.metadata)
    return {"status": "success", "message": "Documento indexado."}


@app.post("/api/ingest")
async def ingest_api(payload: IngestRequest):
    return await ingest(payload)

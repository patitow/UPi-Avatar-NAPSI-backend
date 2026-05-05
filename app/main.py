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

class ChatMessage(BaseModel):
    message: str
    user_id: str = "default_user"

@app.get("/")
async def root():
    return {"status": "online", "message": "UPi API está funcionando!"}

@app.post("/chat")
async def chat(payload: ChatMessage):
    response = await ai_service.get_response(payload.message)
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

#!/usr/bin/env bash
# UPi — desenvolvimento sem Docker (Chroma + cache JSON + Ollama + uvicorn)
set -e
cd "$(dirname "$0")"

export UPI_DEV_MODE=1
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"

echo "╔══════════════════════════════════════╗"
echo "║   UPi — DEV local (sem Docker)       ║"
echo "╚══════════════════════════════════════╝"

if ! command -v ollama &>/dev/null; then
  echo "✗ Instale Ollama: https://ollama.com"
  exit 1
fi

if ! curl -sf --max-time 2 http://127.0.0.1:11434/ >/dev/null; then
  echo "→ Iniciando ollama serve..."
  ollama serve &>/tmp/ollama.log &
  sleep 3
fi

MODEL="${OLLAMA_MODEL}"
if ! ollama list | grep -q "$MODEL"; then
  echo "→ Baixando $MODEL..."
  ollama pull "$MODEL"
fi

if ! python3 -c "import fastapi" &>/dev/null; then
  pip install -r requirements-dev.txt
elif ! python3 -c "import chromadb" &>/dev/null; then
  pip install chromadb
fi

mkdir -p data data/chroma_db

echo ""
echo "  Vector:  Chroma (./data/chroma_db)"
echo "  Cache:   ./data/dev_semantic_cache.json"
echo "  API:     http://localhost:8000"
echo ""

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# UPi — Inicialização 100% local (sem Docker, sem chave OpenAI)
# Requer: Python 3.10+, Ollama instalado (https://ollama.com)
# ─────────────────────────────────────────────────────────────────────────────

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════╗${NC}"
echo -e "${BLUE}║   UPi — Modo Local (Ollama)      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════╝${NC}"

# 1. Verifica Ollama
if ! command -v ollama &> /dev/null; then
  echo -e "${RED}✗ Ollama não encontrado.${NC}"
  echo "  Instale em: https://ollama.com  (macOS: brew install ollama)"
  exit 1
fi
echo -e "${GREEN}✓ Ollama encontrado${NC}"

# 2. Inicia servidor Ollama (se não estiver rodando)
if ! curl -s http://localhost:11434/ &> /dev/null; then
  echo -e "${YELLOW}→ Iniciando Ollama em background...${NC}"
  ollama serve &> /tmp/ollama.log &
  sleep 3
fi
echo -e "${GREEN}✓ Ollama rodando em http://localhost:11434${NC}"

# 3. Verifica/baixa o modelo
MODEL="llama3.2:3b"
if ! ollama list | grep -q "$MODEL"; then
  echo -e "${YELLOW}→ Baixando modelo $MODEL (~2 GB, apenas na primeira vez)...${NC}"
  ollama pull "$MODEL"
fi
echo -e "${GREEN}✓ Modelo $MODEL disponível${NC}"

# 4. Verifica dependências Python
if ! python3 -c "import fastapi" &> /dev/null; then
  echo -e "${YELLOW}→ Instalando dependências Python...${NC}"
  pip install -r requirements.txt
fi
echo -e "${GREEN}✓ Dependências Python ok${NC}"

# 5. Cria diretório de dados locais
mkdir -p data/chroma_db
echo -e "${GREEN}✓ Diretório data/chroma_db pronto${NC}"

# 6. Inicia o backend (sem OPENAI_API_KEY → usa Ollama automaticamente)
echo ""
echo -e "${BLUE}▶ Iniciando UPi backend em modo local...${NC}"
echo -e "  LLM:        Ollama ($MODEL)"
echo -e "  Embeddings: Ollama ($MODEL)"
echo -e "  Vector DB:  ChromaDB local (./data/chroma_db)"
echo -e "  Redis:      desativado (cache semântico off)"
echo ""
echo -e "${YELLOW}  API disponível em: http://localhost:8000${NC}"
echo -e "${YELLOW}  Pressione Ctrl+C para encerrar.${NC}"
echo ""

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

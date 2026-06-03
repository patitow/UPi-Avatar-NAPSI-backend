# UPi - Backend Inteligente (NAPSI/UPE)

Este é o motor de inteligência do UPi, um assistente virtual projetado para apoiar alunos da POLI/UPE, com foco especial em acessibilidade para estudantes com TEA.

## 🚀 Tecnologias e Otimizações

- **FastAPI**: API de alta performance.
- **LangChain**: Orquestração de RAG e LLMs.
- **RAG (Retrieval-Augmented Generation)**: Respostas baseadas em documentos reais.
- **PGVector (PostgreSQL)**: Armazenamento vetorial robusto para conhecimento institucional.
- **Redis Semantic Cache**: Cache inteligente que entende o significado das perguntas, economizando tokens e reduzindo latência.
- **Local Embeddings (Ollama `llama3.2:3b`)**: Embeddings gerados localmente via Ollama, sem envio de dados para APIs externas.
- **Ollama Fallback**: Suporte nativo ao modelo `llama3.2:3b` para operação offline ou caso a API principal falhe.

## 📋 Pré-requisitos

- Python 3.10+
- [Ollama](https://ollama.com/) — LLM e embeddings locais
- **Desenvolvimento:** só isso (sem Docker)
- **Produção / integração:** Docker (`compose-up`) com Postgres + Redis

## 🛠️ Desenvolvimento local (sem Docker)

Ativa `UPI_DEV_MODE=1`: **ChromaDB** em `data/chroma_db` + **cache semântico** em RAM/arquivo `data/dev_semantic_cache.json`. Sem Postgres, sem Redis.

```powershell
# Windows
.\start_dev.ps1
```

```bash
# Linux/macOS
bash start_local.sh
```

Ou manualmente:

```bash
export UPI_DEV_MODE=1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Front (outro terminal): `npm run dev` em `UPi-Avatar-NAPSI` — proxy em `http://localhost:5173`.

## 🐳 Produção / stack completa (Docker)

Para o modo de produção com PostgreSQL, Redis e OpenAI:

1. **Instale as dependências**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Suba a infraestrutura** (detecta Ollama na máquina):
   ```powershell
   # Windows
   .\compose-up.ps1
   ```
   ```bash
   # Linux/macOS
   bash compose-up.sh
   ```
   - Se **Ollama já estiver rodando** em `http://localhost:11434` (app ou `ollama serve`), sobem só **db**, **redis** e **api** — a API usa `host.docker.internal:11434`.
   - Se **não** houver Ollama no host, o script acrescenta o container **`upi_ollama`**. Na primeira vez: `docker exec -it upi_ollama ollama pull llama3.2:3b`.
   - Rebuild: `.\compose-up.ps1 -Build` ou `bash compose-up.sh --build`.

3. **Variáveis de Ambiente** — copie `.env.example` para `.env` (o repositório **nunca** apaga nem sobrescreve o seu `.env`):
   - `TTS_PROVIDER=gtts` | `openai` | `none`
   - `CORS_ORIGINS` — URLs do front separadas por vírgula (ou `*` em dev)
   - `OLLAMA_MODEL=llama3.2:3b` no `.env` (ou outro modelo, ex.: `qwen2.5:7b`, só na tua máquina)

## 📂 Como Alimentar o UPi (Ingestão)

O UPi aprende a partir de documentos na pasta `data/`.
1. Coloque seus arquivos `.pdf`, `.txt` ou `.md` em `data/`.
2. Execute o script de ingestão:
   ```bash
   python ingest_docs.py
   ```
   *O script utiliza `RecursiveCharacterTextSplitter` para manter a coerência semântica dos parágrafos.*

Após trocar de modelo Ollama ou atualizar documentos, apague `data/chroma_db` e `data/dev_semantic_cache.json` (modo dev) para o RAG e o cache refletirem o conteúdo novo.

**Qualidade das respostas:** o cache semântico agrupa por **intenção** (local, agendamento, serviços, TEA). Rode `python scripts/evaluate_ollama_models.py` com `EVAL_MODELS=seu_modelo` para validar os quatro cenários NAPSI.

## ⚙️ Execução

Inicie o servidor de desenvolvimento:
```bash
python app/main.py
```
A API estará disponível em `http://localhost:8000`.

## 🧪 Testes

**Unitários e API (Python):**
```bash
pytest
python scripts/validate_dev_stack.py
```

**E2E no browser:** no repositório do front (`UPi-Avatar-NAPSI`), com a API já rodando aqui em `:8000` — ver `e2e/README.md` no front.

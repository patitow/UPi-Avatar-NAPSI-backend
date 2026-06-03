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
- [Ollama](https://ollama.com/) — necessário para embeddings e LLM local
- Docker & Docker Compose (opcional — modo completo com PostgreSQL e Redis)

## 🚀 Modo Local (sem Docker, sem chave OpenAI)

A forma mais rápida de rodar o UPi sem nenhuma dependência externa:

```bash
# 1. Instale o Ollama (macOS)
brew install ollama   # ou baixe em https://ollama.com

# 2. Execute o script de inicialização automática
bash start_local.sh
```

O script verifica/instala tudo automaticamente:
- Inicia o Ollama se não estiver rodando
- Baixa o modelo `llama3.2:3b` se necessário (~2 GB, só na primeira vez)
- Usa **ChromaDB local** como vector store (sem PostgreSQL)
- Inicia o backend sem precisar de `OPENAI_API_KEY`

> O frontend exibirá **"IA Local · llama3.2:3b"** em roxo quando esse modo estiver ativo.

## 🐳 Modo Completo (Docker + OpenAI)

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

3. **Variáveis de Ambiente**:
   Crie um arquivo `.env` na raiz:
   ```env
   OPENAI_API_KEY=sua_chave_aqui
   DATABASE_URL=postgresql+psycopg2://upi_user:upi_password@localhost:5432/upi_db
   REDIS_URL=redis://localhost:6379
   ```

## 📂 Como Alimentar o UPi (Ingestão)

O UPi aprende a partir de documentos na pasta `data/`.
1. Coloque seus arquivos `.pdf`, `.txt` ou `.md` em `data/`.
2. Execute o script de ingestão:
   ```bash
   python ingest_docs.py
   ```
   *O script utiliza `RecursiveCharacterTextSplitter` para manter a coerência semântica dos parágrafos.*

## ⚙️ Execução

Inicie o servidor de desenvolvimento:
```bash
python app/main.py
```
A API estará disponível em `http://localhost:8000`.

## 🧪 Testes

Execute a suíte de testes unitários:
```bash
pytest
```

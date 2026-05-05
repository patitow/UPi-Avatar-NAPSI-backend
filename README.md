# UPi - Backend Inteligente (NAPSI/UPE)

Este é o motor de inteligência do UPi, um assistente virtual projetado para apoiar alunos da POLI/UPE, com foco especial em acessibilidade para estudantes com TEA.

## 🚀 Tecnologias e Otimizações

- **FastAPI**: API de alta performance.
- **LangChain**: Orquestração de RAG e LLMs.
- **RAG (Retrieval-Augmented Generation)**: Respostas baseadas em documentos reais.
- **PGVector (PostgreSQL)**: Armazenamento vetorial robusto para conhecimento institucional.
- **Redis Semantic Cache**: Cache inteligente que entende o significado das perguntas, economizando tokens e reduzindo latência.
- **Local Embeddings (`all-MiniLM-L6-v2`)**: Processamento de vetores 100% local (custo zero e alta velocidade).
- **Ollama Fallback**: Suporte nativo ao modelo `llama3.2:3b` para operação offline ou caso a API principal falhe.

## 📋 Pré-requisitos

- Python 3.10+
- Docker & Docker Compose
- [Ollama](https://ollama.com/) (opcional, para fallback local)

## 🛠️ Configuração

1. **Instale as dependências**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Suba a infraestrutura**:
   ```bash
   docker-compose up -d
   ```
   *Isso iniciará o PostgreSQL com pgvector e o Redis Stack.*

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

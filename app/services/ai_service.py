import os
import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from app.prompts.upi_prompts import UPI_SYSTEM_PROMPT
from app.config import settings

class AIService:
    """
    Serviço central de IA para o UPi.
    Gerencia Embeddings, Busca Semântica (RAG) e chamadas aos LLMs.
    """
    def __init__(self, connection_string: str = None):
        self.embeddings = self._init_embeddings()
        self.llm = self._init_llm()
        self.system_instructions = UPI_SYSTEM_PROMPT
        
        # Configuração do banco de dados
        self.connection_string = connection_string or settings.DATABASE_URL
        self.collection_name = settings.COLLECTION_NAME
        
        self.vector_store = None
        
        # Configuração do Redis (Cache Semântico)
        self._init_redis_cache()
        
        self.init_knowledge_base()

    def _init_embeddings(self):
        """Inicializa o modelo de embedding local."""
        return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)

    def _init_llm(self):
        """Inicializa o LLM principal com fallback automático."""
        try:
            self.using_fallback = False
            return ChatOpenAI(model_name=settings.OPENAI_MODEL, temperature=0.7)
        except Exception:
            ollama_url = settings.OLLAMA_BASE_URL
            print(f"Aviso: OpenAI não disponível. Usando Ollama ({ollama_url}) como fallback.")
            self.using_fallback = True
            return ChatOllama(
                model=settings.OLLAMA_MODEL, 
                temperature=0.7,
                base_url=ollama_url
            )

    def _init_redis_cache(self):
        """Inicializa o cache semântico no Redis com rigor máximo."""
        try:
            import langchain_core.globals
            from langchain_redis import RedisSemanticCache
            from langchain_core.outputs import Generation
            
            redis_url = settings.REDIS_URL
            # Threshold de 0.02 para ser extremamente rigoroso (evita falsos positivos)
            cache = RedisSemanticCache(
                redis_url=redis_url,
                embeddings=self.embeddings,
                distance_threshold=0.02 
            )
            
            # Garante que o índice existe fazendo um write de teste
            try:
                cache.update("init_check", "upi_ready", [Generation(text="ok")])
            except Exception as e:
                print(f"Aviso na inicialização do índice: {e}", flush=True)

            langchain_core.globals.set_llm_cache(cache)
            print("Cache semântico REATIVADO e OTIMIZADO (Threshold: 0.02).", flush=True)
        except Exception as e:
            print(f"Erro ao ativar Redis Cache: {e}. Prosseguindo em tempo real.", flush=True)

    def init_knowledge_base(self):
        """Configura o Vector Store (Postgres ou Chroma fallback)."""
        initial_data = [
            "O NAPSI oferece suporte aos alunos com TEA. Contato: napsi@poli.upe.br.",
            "A POLI/UPE atende no campus de Garanhuns das 08:00 às 17:00.",
            "Matrículas são realizadas via portal do estudante."
        ]
        
        try:
            self.vector_store = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=self.connection_string,
                use_jsonb=True,
            )
            self._populate_if_empty(initial_data)
        except Exception as e:
            self._init_chroma_fallback(initial_data, e)

    def _populate_if_empty(self, data: list):
        """Adiciona dados iniciais se a coleção estiver vazia."""
        try:
            if not self.vector_store.get_by_ids(["initial_check"]):
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
                docs = text_splitter.create_documents(data)
                self.vector_store.add_documents(docs)
        except Exception:
            pass # Silencia erros de população se já existir

    def _init_chroma_fallback(self, data: list, error: Exception):
        """Inicia ChromaDB como fallback para desenvolvimento local sem Docker."""
        print(f"Erro no Postgres: {error}. Usando Chroma fallback.")
        from langchain_community.vectorstores import Chroma
        self.vector_store = Chroma.from_texts(
            texts=data,
            embedding=self.embeddings,
            persist_directory="db"
        )

    async def get_response(self, user_input: str, chat_history: List[BaseMessage] = None):
        """Processa a entrada do usuário e retorna uma resposta estruturada."""
        try:
            # 1. Tenta o Cache Semântico Manualmente para Debug/Controle
            import langchain_core.globals
            cache = langchain_core.globals.get_llm_cache()
            if cache:
                # O cache do langchain-redis armazena como lista de Generation
                # Adiciona log da busca semântica para controle de threshold
                cached_val = cache.lookup(user_input, "upi")
                if cached_val:
                    print(f"[CACHE HIT] Respondendo via Redis para: {user_input}", flush=True)
                    return self._parse_structured_response(cached_val[0].text)

            # 2. Se não houver cache, segue o fluxo normal
            print(f"[LLM] Processando nova pergunta: {user_input}", flush=True)
            
            # Recupera documentos relevantes do PGVector
            docs = self.vector_store.similarity_search(user_input, k=3)
            context = "\n".join([doc.page_content for doc in docs])
            
            # Prepara a mensagem do sistema com o contexto
            system_msg = UPI_SYSTEM_PROMPT.format(context=context)
            
            # Constrói a lista de mensagens
            messages = [SystemMessage(content=system_msg)]
            if chat_history:
                messages.extend(chat_history[-5:]) # Últimas 5 mensagens para contexto
            messages.append(HumanMessage(content=user_input))
            
            # Chama o LLM
            response = self.llm.invoke(messages)
            
            # Parse e Retorno
            return self._parse_structured_response(response.content)
            
        except Exception as e:
            print(f"Erro crítico no AIService: {e}", flush=True)
            return {
                "response": "Eita! Tive um probleminha aqui pra te responder. Tenta de novo em instantes!",
                "emotion": "neutral"
            }

    async def _call_llm_structured(self, messages: list) -> str:
        """Executa a chamada ao LLM usando mensagens estruturadas (System/Human)."""
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            print(f"Erro no LLM: {e}. Tentando fallback...", flush=True)
            if not self.using_fallback:
                fallback_llm = ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    base_url=settings.OLLAMA_BASE_URL
                )
                return fallback_llm.invoke(messages).content
            raise e

    def _parse_structured_response(self, raw: str) -> dict:
        """Tenta parsear a resposta como JSON, fallback para texto puro se falhar."""
        import json
        try:
            # Limpa possíveis blocos de código markdown
            clean_raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_raw)
            return data
        except Exception:
            return {"response": raw, "emotion": "neutral"}

    async def add_document(self, text: str, metadata: dict = None):
        """Adiciona um novo documento à base de conhecimento."""
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = text_splitter.create_documents([text], metadatas=[metadata or {}])
        self.vector_store.add_documents(docs)

# Singleton para uso na aplicação
ai_service = AIService()

import os
import json
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
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
        """Inicializa o modelo de embedding usando Ollama (Eficiente para 4GB RAM)."""
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL
        )

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
        """Cache Semântico Manual ativado via RedisVL (Configurado no get_response)."""
        # Desativamos o set_llm_cache global para evitar conflitos e economizar memória
        print("Mecanismo de Cache Semântico Manual (RedisVL) pronto.", flush=True)

    def init_knowledge_base(self):
        """Configura o Vector Store com dados do arquivo napsi_info.txt."""
        initial_data = []
        try:
            info_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "napsi_info.txt")
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        initial_data = [content]
            
            # Fallback se o arquivo estiver vazio ou não existir
            if not initial_data:
                initial_data = ["O NAPSI/UPE oferece suporte psicopedagógico no Bloco A, Sala 12, das 08h às 17h."]
        except Exception as e:
            print(f"Erro ao ler arquivo de conhecimento: {e}")
            initial_data = ["Erro ao carregar base de conhecimento."]
        
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
        """Processa a entrada do usuário com Busca por Similaridade Semântica manual via RedisVL."""
        try:
            from redisvl.index import SearchIndex
            from redisvl.query import VectorQuery
            import numpy as np

            # 1. Configuração do Índice Semântico
            index_schema = {
                "index": {"name": "upi_cache", "prefix": "cache"},
                "fields": [
                    {"name": "prompt", "type": "text"},
                    {"name": "response", "type": "text"},
                    {
                        "name": "prompt_vector",
                        "type": "vector",
                        "attrs": {
                            "dims": 3072,
                            "distance_metric": "cosine",
                            "algorithm": "flat",
                            "datatype": "float32",
                        },
                    },
                ],
            }
            
            # Inicializa o índice (conecta ao Redis)
            try:
                idx = SearchIndex.from_dict(index_schema, redis_url=settings.REDIS_URL)
                # Tenta criar o índice se não existir
                if not idx.exists():
                    idx.create(overwrite=False)
            except Exception as e:
                print(f"Erro ao conectar ao RedisVL: {e}", flush=True)
                idx = None

            # 2. Busca por Similaridade no Cache
            query_vector = self.embeddings.embed_query(user_input)
            query_vector_np = np.array(query_vector, dtype=np.float32).tobytes()
            
            # Fingerprint para debug
            vector_fp = query_vector[:5]
            print(f"[DEBUG VECTOR] Pergunta: {user_input} | FP: {vector_fp}", flush=True)
            
            if idx:
                # Busca o vizinho mais próximo
                query = VectorQuery(
                    vector=query_vector,
                    vector_field_name="prompt_vector",
                    return_fields=["prompt", "response"],
                    num_results=1
                )
                
                results = idx.query(query)
                
                if results:
                    hit = results[0]
                    distance = float(hit.get('vector_distance', 1.0))
                    print(f"[DEBUG CACHE] Pergunta: {user_input} | Hit: {hit.get('prompt')} | Distância: {distance:.4f}", flush=True)
                    
                    # Threshold de 0.12 (Ajuste fino para máxima precisão com Llama 3.2)
                    if distance < 0.12:
                        print(f"[SEMANTIC HIT] Similaridade: {1-distance:.2%} | Usando Cache.", flush=True)
                        return self._parse_structured_response(hit['response'])

            # 3. Cache Miss - Processa via LLM
            print(f"[LLM] Pensando: {user_input}", flush=True)
            docs = self.vector_store.similarity_search(user_input, k=3)
            context = "\n".join([doc.page_content for doc in docs])
            print(f"[DEBUG CONTEXT] Encontrado: {len(docs)} docs | Contexto: {context[:100]}...", flush=True)
            
            system_msg = UPI_SYSTEM_PROMPT.format(context=context)
            messages = [SystemMessage(content=system_msg)]
            if chat_history:
                messages.extend(chat_history[-5:])
            messages.append(HumanMessage(content=user_input))
            
            response = self.llm.invoke(messages)
            response_text = response.content

            # 4. Salva no Cache Semântico
            if idx:
                try:
                    idx.load([
                        {
                            "prompt": user_input,
                            "response": response_text,
                            "prompt_vector": query_vector_np
                        }
                    ])
                    print(f"[CACHE STORE] Indexado: {user_input}", flush=True)
                except Exception as e:
                    print(f"Erro ao indexar no cache: {e}", flush=True)
            
            return self._parse_structured_response(response_text)
            
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
            # Limpa possíveis blocos de código markdown e prefixos "JSON:"
            clean_raw = raw.replace("```json", "").replace("```", "").replace("JSON:", "").strip()
            data = json.loads(clean_raw)
            return data
        except Exception:
            # Se falhar o parse, tenta limpar o texto e retornar como resposta
            clean_text = raw.replace("JSON:", "").replace("```json", "").replace("```", "").strip()
            return {"response": clean_text, "emotion": "neutral"}

    async def add_document(self, text: str, metadata: dict = None):
        """Adiciona um novo documento à base de conhecimento."""
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = text_splitter.create_documents([text], metadatas=[metadata or {}])
        self.vector_store.add_documents(docs)

# Singleton para uso na aplicação
ai_service = AIService()

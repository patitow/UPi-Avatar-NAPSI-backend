import os
import json
import base64
import re
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from langchain_ollama import ChatOllama
from app.prompts.upi_prompts import UPI_SYSTEM_PROMPT
from app.config import settings


class AIService:
    """Serviço central de IA para o UPi: Embeddings, RAG, LLMs e Síntese de Voz."""

    def __init__(self, connection_string: str = None):
        self.embeddings = self._init_embeddings()
        self.llm = self._init_llm()
        self.system_instructions = UPI_SYSTEM_PROMPT
        self.connection_string = connection_string or settings.DATABASE_URL
        self.collection_name = settings.COLLECTION_NAME
        self.vector_store = None
        self.init_knowledge_base()

    def _init_embeddings(self):
        """Inicializa embeddings locais via Ollama."""
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )

    def _init_llm(self):
        """Inicializa o LLM principal (OpenAI) com fallback automático para Ollama."""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.using_fallback = False
                return ChatOpenAI(model_name=settings.OPENAI_MODEL, temperature=0.7)
            except Exception as e:
                print(f"Erro ao inicializar OpenAI: {e}. Ativando fallback Ollama.", flush=True)

        print(f"Usando Ollama ({settings.OLLAMA_BASE_URL}) como LLM.", flush=True)
        self.using_fallback = True
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            temperature=0.7,
            base_url=settings.OLLAMA_BASE_URL
        )

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
            pass

    def _init_chroma_fallback(self, data: list, error: Exception):
        """Inicia ChromaDB como fallback para desenvolvimento local sem Docker."""
        print(f"Erro no Postgres: {error}. Usando ChromaDB local.", flush=True)
        from langchain_community.vectorstores import Chroma
        persist_dir = settings.CHROMA_PERSIST_DIR
        try:
            self.vector_store = Chroma(
                embedding_function=self.embeddings,
                persist_directory=persist_dir,
                collection_name=self.collection_name,
            )
            if not self.vector_store.get()["ids"]:
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
                docs = text_splitter.create_documents(data)
                self.vector_store.add_documents(docs)
        except Exception:
            self.vector_store = Chroma.from_texts(
                texts=data,
                embedding=self.embeddings,
                persist_directory=persist_dir,
                collection_name=self.collection_name,
            )

    @property
    def vector_store_type(self) -> str:
        from langchain_community.vectorstores import Chroma
        return "chroma" if isinstance(self.vector_store, Chroma) else "pgvector"

    def _try_connect_cache_index(self):
        """Tenta inicializar o índice Redis para cache semântico."""
        try:
            from redisvl.index import SearchIndex
            index_schema = {
                "index": {"name": "upi_cache", "prefix": "cache"},
                "fields": [
                    {"name": "prompt", "type": "text"},
                    {"name": "response", "type": "text"},
                    {
                        "name": "prompt_vector",
                        "type": "vector",
                        "attrs": {
                            "dims": settings.EMBEDDING_DIMS,
                            "distance_metric": "cosine",
                            "algorithm": "flat",
                            "datatype": "float32",
                        },
                    },
                ],
            }
            idx = SearchIndex.from_dict(index_schema, redis_url=settings.REDIS_URL)
            if not idx.exists():
                idx.create(overwrite=False)
            return idx
        except Exception as e:
            print(f"Cache semântico indisponível: {e}", flush=True)
            return None

    def _lookup_cache(self, idx, user_input: str, query_vector: list):
        """Busca resposta no cache semântico."""
        try:
            from redisvl.query import VectorQuery
            query = VectorQuery(
                vector=query_vector,
                vector_field_name="prompt_vector",
                return_fields=["prompt", "response"],
                num_results=1
            )
            results = idx.query(query)
            if results:
                hit = results[0]
                distance = float(hit.get("vector_distance", 1.0))
                if distance < 0.12:
                    return self._parse_structured_response(hit["response"])
        except Exception as e:
            print(f"Erro na busca de cache: {e}", flush=True)
        return None

    def _store_cache(self, idx, user_input: str, response_text: str, query_vector_np: bytes):
        """Persiste a resposta no cache semântico."""
        try:
            idx.load([{
                "prompt": user_input,
                "response": response_text,
                "prompt_vector": query_vector_np
            }])
        except Exception as e:
            print(f"Erro ao indexar no cache: {e}", flush=True)

    def _generate_tts_audio(self, text: str) -> str:
        """
        APRIMORAMENTO 1: Gera áudio de voz neural de alta qualidade via Google Cloud TTS.
        Retorna o áudio convertido em uma string Base64 para envio prático ao Frontend.
        """
        try:
            from google.cloud import texttospeech
            
            # Inicializa o cliente da API do Google (Requer GOOGLE_APPLICATION_CREDENTIALS configurado)
            client = texttospeech.TextToSpeechClient()
            
            input_text = texttospeech.SynthesisInput(text=text)
            
            # Configura uma voz em Português Brasileiro de altíssima qualidade (Neural2)
            voice = texttospeech.VoiceSelectionParams(
                language_code="pt-BR",
                name="pt-BR-Neural2-A" # Voz feminina fluida e natural
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0, # Velocidade confortável
                pitch=0.0
            )
            
            response = client.synthesize_speech(
                input=input_text, voice=voice, audio_config=audio_config
            )
            
            # Transforma os bytes do áudio em string Base64 para trafegar facilmente via JSON
            audio_base64 = base64.b64encode(response.audio_content).decode("utf-8")
            return audio_base64
            
        except Exception as e:
            print(f"[TTS ERROR] Falha ao gerar áudio neural: {e}", flush=True)
            return "" # Retorna vazio se falhar, permitindo que o chat em texto continue funcionando

    async def get_response(self, user_input: str, chat_history: List[BaseMessage] = None, user_id: str = None):
        """Processa a entrada do usuário com RAG, cache semântico e injeta o áudio neural."""
        try:
            query_vector = self.embeddings.embed_query(user_input)
            idx = self._try_connect_cache_index()

            if idx:
                import numpy as np
                query_vector_np = np.array(query_vector, dtype=np.float32).tobytes()
                cached = self._lookup_cache(idx, user_input, query_vector)
                if cached:
                    # Gera áudio para a resposta recuperada do cache
                    cached["audio"] = self._generate_tts_audio(cached["response"])
                    return cached
            else:
                query_vector_np = None

            # Filtro semântico de escopo
            docs_scored = self.vector_store.similarity_search_with_score(user_input, k=1)
            if docs_scored:
                _top_doc, top_score = docs_scored[0]
                if top_score > 1.05:
                    off_topic_text = "Oxe, isso tá fora da minha área, visse? Só posso ajudar com assuntos do NAPSI/UPE — serviços, atendimento e apoio estudantil."
                    return {
                        "response": off_topic_text,
                        "emotion": "calm", # Mudado para 'calm' para passar acolhimento
                        "audio": self._generate_tts_audio(off_topic_text)
                    }

            # Cache miss — consulta o LLM
            docs = self.vector_store.similarity_search(user_input, k=5)
            context = "\n".join([doc.page_content for doc in docs])

            system_msg = UPI_SYSTEM_PROMPT.format(context=context)
            messages = [SystemMessage(content=system_msg)]
            if chat_history:
                messages.extend(chat_history[-5:])
            messages.append(HumanMessage(content=user_input))

            response_text = await self._call_llm_structured(messages)

            if idx and query_vector_np:
                self._store_cache(idx, user_input, response_text, query_vector_np)

            # Estrutura o resultado de texto e emoção
            result = self._parse_structured_response(response_text)
            
            # GERAÇÃO DO ÁUDIO: Adiciona o áudio em formato Base64 no pacote de resposta
            result["audio"] = self._generate_tts_audio(result["response"])

            return result

        except Exception as e:
            print(f"Erro crítico no AIService: {e}", flush=True)
            error_text = "Eita! Tive um probleminha aqui pra te responder. Tenta de novo em instantes!"
            return {
                "response": error_text,
                "emotion": "calm",
                "audio": self._generate_tts_audio(error_text)
            }

    async def _call_llm_structured(self, messages: list) -> str:
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            if not self.using_fallback:
                fallback_llm = ChatOllama(model=settings.OLLAMA_MODEL, base_url=settings.OLLAMA_BASE_URL)
                return fallback_llm.invoke(messages).content
            raise e

    def _parse_structured_response(self, raw: str) -> dict:
        """Parseia resposta como JSON com suporte ao novo catálogo expandido de emoções."""
        # APRIMORAMENTO 1: Adicionadas novas emoções (calm, surprised, confused)
        VALID_EMOTIONS = {"happy", "neutral", "sad", "excited", "thinking", "calm", "surprised", "confused"}

        def clean_text(t):
            if not isinstance(t, str): return None
            return t.strip().strip('"').strip()

        def extract(data: dict):
            text = data.get("response") or data.get("resposta") or data.get("text") or data.get("message")
            text = clean_text(text)
            emo = data.get("emotion") or data.get("emocao") or "neutral"
            if not isinstance(emo, str) or emo not in VALID_EMOTIONS:
                emo = "neutral"
            return text, emo

        # Correção contra quebra de linha mal formatada: limpamos o texto de forma incremental e segura
        clean = raw
        for block in ["```json", "```", "JSON:"]:
            clean = clean.replace(block, "")
        clean = clean.strip()

        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(clean[start:end + 1])
                text, emo = extract(data)
                if isinstance(text, str) and text:
                    return {"response": text.strip(), "emotion": emo}
            except Exception:
                pass

        m = re.search(r'"response"\s*:\s*"([^"]+)"', clean)
        if m:
            emo_m = re.search(r'"emotion"\s*:\s*"([^"]+)"', clean)
            emo = emo_m.group(1) if emo_m else "neutral"
            if emo not in VALID_EMOTIONS: emo = "neutral"
            return {"response": m.group(1).strip(), "emotion": emo}

        return {"response": clean[:500], "emotion": "neutral"}

    async def add_document(self, text: str, metadata: dict = None):
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = text_splitter.create_documents([text], metadatas=[metadata or {}])
        self.vector_store.add_documents(docs)


ai_service = AIService()
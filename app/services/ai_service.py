import os
import json
import re
import time
from typing import List, Optional

from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from app.config import settings
from app.services.semantic_cache import create_semantic_cache
from app.services.intent import (
    classify_intent,
    fallback_context,
    is_crisis_message,
    is_distress_message,
    rag_search_query,
    response_matches_intent,
)
from app.services.portuguese import polish_portuguese
from app.services.tts import synthesize_speech

DEFAULT_UPI_PROMPT = """Você é o UPi, o assistente virtual oficial do NAPSI (Núcleo de Apoio Psicopedagógico e Suporte Estudantil) da POLI/UPE.
Sua personalidade é acolhedora e simpática. Use "oxe", "visse", "eita", "massa" com moderação. Escreva em português brasileiro correto (está, para, você, às) — nunca "tá", "pra", "tô". Em saudações, responda curto, sem discurso institucional.

Sempre responda estritamente em formato JSON com as chaves abaixo (não use nenhuma outra chave e não coloque textos fora do bloco JSON):
{
  "response": "Sua resposta carinhosa e direta aqui (máximo 3 frases curtas para ser fácil de ouvir)",
  "emotion": "uma destas: happy, neutral, sad, excited, thinking, calm, surprised, confused"
}

Responda usando estritamente as informações fornecidas no contexto abaixo. Se não souber a resposta, diga que não sabe de forma gentil e sugira que entrem em contato pelo e-mail napsi@poli.br ou visitem a sala 12 no Bloco A.

Contexto de Conhecimento:
{context}
"""

try:
    from app.prompts.upi_prompts import UPI_SYSTEM_PROMPT

    if not UPI_SYSTEM_PROMPT:
        UPI_SYSTEM_PROMPT = DEFAULT_UPI_PROMPT
except Exception:
    UPI_SYSTEM_PROMPT = DEFAULT_UPI_PROMPT

VALID_EMOTIONS = {
    "happy",
    "neutral",
    "sad",
    "excited",
    "thinking",
    "calm",
    "surprised",
    "confused",
}

_INTENT_FALLBACK_KEY: dict[str, tuple[str, str]] = {
    "crisis": ("crise", "calm"),
    "distress": ("acolhimento", "calm"),
    "location": ("onde fica", "calm"),
    "scheduling": ("agendar", "calm"),
    "tea": ("tea", "happy"),
    "services": ("serviço", "calm"),
}

FALLBACK_ANSWERS = {
    "onde fica": (
        "Oxe, o NAPSI fica no Bloco A, Sala 12, visse? "
        "O atendimento é de segunda a sexta, das 8h às 17h."
    ),
    "agendar": (
        "Para agendar seu atendimento, envie um e-mail para napsi@poli.br "
        "ou procure a equipe no Bloco A, Sala 12."
    ),
    "tea": (
        "O NAPSI oferece suporte psicopedagógico especializado para todos os estudantes, "
        "incluindo alunos com TEA (Transtorno do Espectro Autista)."
    ),
    "serviço": (
        "Oferecemos apoio psicopedagógico, acolhimento psicossocial, "
        "adaptações em provas (tempo adicional, ambiente separado, com laudo quando necessário) "
        "e orientação aos estudantes da POLI, visse?"
    ),
    "acolhimento": (
        "Sinto muito que você esteja passando por isso. O NAPSI acolhe estudantes "
        "em sofrimento com atendimento psicológico e psicossocial — escreva para napsi@poli.br "
        "ou procure o Bloco A, Sala 12, de segunda a sexta, das 8h às 17h. "
        "Se a angústia for muito forte agora, ligue 188 (CVV, 24h); em emergência médica, 192 (SAMU)."
    ),
    "crise": (
        "Sinto muito que você esteja passando por um momento tão difícil — sua vida importa. "
        "Ligue agora ao CVV 188 (24h, gratuito) ou ao SAMU 192 se houver risco imediato. "
        "O NAPSI também acolhe estudantes: napsi@poli.br ou Bloco A, Sala 12, de segunda a sexta, das 8h às 17h."
    ),
}

_OUT_OF_SCOPE_PHRASE = "fora da minha área"

_GREETING_RE = re.compile(
    r"^\s*(oi|olá|ola|e\s*a[ií]|eai|hey|bom\s+dia|boa\s+tarde|boa\s+noite)\b",
    re.IGNORECASE,
)
_GREETING_EXTRA = frozenset(
    {"oi", "ola", "olá", "eai", "hey", "lindo", "linda", "tudo", "bem", "beleza"}
)



import re
# ==================================================
# INÍCIO - TTS (ElevenLabs + Edge-TTS Fallback)
# ==================================================

import tempfile
import base64
from elevenlabs.client import ElevenLabs
import edge_tts

# ==================================================
# FIM - TTS
# ==================================================

class AIService:
    """Dev: Chroma + cache JSON. Produção: PGVector + Redis."""

    def __init__(self, connection_string: Optional[str] = None):
        self.dev_mode = settings.UPI_DEV_MODE
        self.using_fallback = False
        self.embeddings_provider = "none"
        self.embeddings = self._init_embeddings()
        self.llm = self._init_llm()
        self.connection_string = connection_string or settings.DATABASE_URL
        self.collection_name = settings.COLLECTION_NAME
        self.vector_store = None

        raw = UPI_SYSTEM_PROMPT or DEFAULT_UPI_PROMPT
        self.system_instructions = (
            " ".join(str(x) for x in raw)
            if isinstance(raw, tuple)
            else str(raw)
        )

        mode = "DEV (Chroma + cache JSON)" if self.dev_mode else "PROD (PGVector + Redis)"
        print(
            f"[INFO] AIService — {mode} | embeddings: {self.embeddings_provider}",
            flush=True,
        )

        self.semantic_cache = create_semantic_cache(
            dev_mode=self.dev_mode,
            embeddings=self.embeddings,
            redis_url=settings.REDIS_URL,
            cache_path=settings.DEV_CACHE_PATH,
            distance_threshold=settings.SEMANTIC_CACHE_DISTANCE,
        )
        self.init_knowledge_base()

    @staticmethod
    def _openai_api_key() -> str:
        return (settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY") or "").strip()

    @staticmethod
    def _embeddings_backend() -> str:
        provider = (settings.EMBEDDINGS_PROVIDER or "auto").strip().lower()
        if provider == "openai":
            return "openai"
        if provider == "ollama":
            return "ollama"
        return "openai" if AIService._openai_api_key() else "ollama"

    def _init_openai_embeddings(self):
        api_key = self._openai_api_key()
        if not api_key:
            return None
        try:
            from langchain_openai import OpenAIEmbeddings

            self.embeddings_provider = "openai"
            print(
                f"[INFO] Embeddings via OpenAI ({settings.OPENAI_EMBEDDING_MODEL}).",
                flush=True,
            )
            return OpenAIEmbeddings(
                model=settings.OPENAI_EMBEDDING_MODEL,
                api_key=api_key,
            )
        except Exception as e:
            print(f"[AVISO] Embeddings OpenAI indisponíveis: {e}", flush=True)
            return None

    def _init_ollama_embeddings(self):
        try:
            from langchain_ollama import OllamaEmbeddings

            self.embeddings_provider = "ollama"
            print(
                f"[INFO] Embeddings via Ollama ({settings.OLLAMA_MODEL}).",
                flush=True,
            )
            return OllamaEmbeddings(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
            )
        except Exception as e:
            print(f"[AVISO] Embeddings Ollama indisponíveis: {e}", flush=True)
            return None

    def _init_embeddings(self):
        backend = self._embeddings_backend()
        if backend == "openai":
            embeddings = self._init_openai_embeddings()
            if embeddings:
                return embeddings
            print("[AVISO] OpenAI embeddings falhou — tentando Ollama.", flush=True)

        embeddings = self._init_ollama_embeddings()
        if embeddings:
            return embeddings

        self.embeddings_provider = "none"
        return None

    def _init_llm(self):
        api_key = self._openai_api_key()
        if api_key:
            try:
                from langchain_openai import ChatOpenAI

                self.using_fallback = False
                return ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    temperature=0.7,
                    api_key=api_key,
                )
            except Exception as e:
                print(
                    f"[AVISO] OpenAI indisponível: {e}. Usando Ollama.",
                    flush=True,
                )

        print(
            f"[INFO] LLM via Ollama ({settings.OLLAMA_BASE_URL}).",
            flush=True,
        )
        self.using_fallback = True
        try:
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=settings.OLLAMA_MODEL,
                temperature=0.7,
                base_url=settings.OLLAMA_BASE_URL,
            )
        except Exception as e:
            print(f"[ERRO] Ollama LLM: {e}", flush=True)
            return None

    def _knowledge_data_dir(self) -> str:
        return os.path.join(
            os.path.dirname(__file__), "..", "..", "data"
        )

    def _load_seed_texts(self) -> List[str]:
        seeds = [
            "O NAPSI/UPE oferece suporte psicopedagógico e acolhimento no Bloco A, Sala 12, das 08h às 17h.",
            "Para agendar atendimentos no NAPSI, envie um e-mail para napsi@poli.br.",
        ]
        data_dir = self._knowledge_data_dir()
        paths: list[str] = []
        info_path = os.path.join(data_dir, "napsi_info.txt")
        if os.path.isfile(info_path):
            paths.append(info_path)
        knowledge_dir = os.path.join(data_dir, "knowledge")
        if os.path.isdir(knowledge_dir):
            for name in sorted(os.listdir(knowledge_dir)):
                if name.lower().endswith(".txt"):
                    paths.append(os.path.join(knowledge_dir, name))

        texts: list[str] = []
        for path in paths:
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        texts.append(content)
                        print(f"[INFO] Base de conhecimento: {os.path.basename(path)}", flush=True)
            except Exception as e:
                print(f"[AVISO] {path}: {e}", flush=True)
        return texts if texts else seeds

    def _seed_vector_store_if_empty(self) -> None:
        try:
            if self.vector_store.similarity_search("NAPSI UPE", k=1):
                return
        except Exception:
            pass
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=500, chunk_overlap=50
            )
            docs = splitter.create_documents(self._load_seed_texts())
            self.vector_store.add_documents(docs)
            print("[INFO] Base NAPSI semeada.", flush=True)
        except Exception as e:
            print(f"[AVISO] Seed vector store: {e}", flush=True)

    def init_knowledge_base(self):
        if not self.embeddings:
            print("[AVISO] Sem embeddings — RAG desativado.", flush=True)
            return

        if self.dev_mode:
            self._init_chroma()
        else:
            self._init_pgvector()

    def _init_chroma(self):
        persist_dir = settings.CHROMA_PERSIST_DIR
        os.makedirs(persist_dir, exist_ok=True)
        try:
            from langchain_community.vectorstores import Chroma

            self.vector_store = Chroma(
                embedding_function=self.embeddings,
                persist_directory=persist_dir,
                collection_name=self.collection_name,
            )
            existing = self.vector_store.get().get("ids") or []
            if not existing:
                from langchain_text_splitters import RecursiveCharacterTextSplitter

                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=500, chunk_overlap=50
                )
                docs = splitter.create_documents(self._load_seed_texts())
                self.vector_store.add_documents(docs)
            print(f"[INFO] ChromaDB em {persist_dir}", flush=True)
        except Exception as e:
            print(f"[AVISO] ChromaDB: {e}", flush=True)
            self.vector_store = None

    def _init_pgvector(self):
        try:
            from langchain_postgres import PGVector

            self.vector_store = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=self.connection_string,
                use_jsonb=True,
            )
            self._seed_vector_store_if_empty()
            print("[INFO] PGVector inicializado.", flush=True)
        except Exception as e:
            print(f"[AVISO] PGVector: {e}", flush=True)
            self.vector_store = None

    @property
    def vector_store_type(self) -> str:
        if not self.vector_store:
            return "direto"
        if self.dev_mode:
            return "chroma"
        return "pgvector"

    def _embed_query(self, user_input: str) -> Optional[List[float]]:
        if not self.embeddings:
            return None
        return self.embeddings.embed_query(user_input)

    def _lookup_semantic_cache(
        self, user_input: str, query_vector: Optional[List[float]] = None
    ) -> Optional[dict]:
        if not self.semantic_cache:
            return None
        raw = self.semantic_cache.lookup(user_input, query_vector)
        if not raw:
            return None
        parsed = self._parse_structured_response(raw)
        intent = classify_intent(user_input)
        response_text = str(parsed.get("response", ""))
        if response_text and response_matches_intent(response_text, intent):
            return parsed
        print(
            f"[CACHE SKIP] resposta não combina com intenção '{intent}'",
            flush=True,
        )
        return None

    def _store_semantic_cache(self, user_input: str, response_text: str) -> None:
        if self.semantic_cache:
            self.semantic_cache.store(user_input, response_text)

    def _rag_context(
        self, user_input: str, query_vector: Optional[List[float]] = None
    ) -> str:
        intent = classify_intent(user_input)
        default = fallback_context(intent)
        if not self.vector_store:
            return default
        max_distance = float(os.getenv("RAG_MAX_DISTANCE", "0.65"))
        rag_k = int(os.getenv("RAG_TOP_K", "3"))
        try:
            search_fn = getattr(
                self.vector_store, "similarity_search_with_score", None
            )
            search_by_vector = getattr(
                self.vector_store, "similarity_search_by_vector_with_score", None
            )
            query = rag_search_query(user_input)
            if query_vector is not None and search_by_vector:
                scored = search_by_vector(query_vector, k=rag_k)
            elif search_fn:
                scored = search_fn(query, k=rag_k)
                chunks = [
                    doc.page_content
                    for doc, dist in scored
                    if dist <= max_distance and doc.page_content.strip()
                ]
            else:
                docs = self.vector_store.similarity_search(query, k=3)
                chunks = [d.page_content for d in docs if d.page_content.strip()]
            if chunks:
                return "\n\n".join(chunks[:2])
        except Exception as e:
            print(f"[AVISO] RAG: {e}", flush=True)
        return default

    def _build_messages(
        self, user_input: str, context: str, chat_history: Optional[List[BaseMessage]]
    ) -> list:
        instructions = str(self.system_instructions or DEFAULT_UPI_PROMPT)
        system_msg = instructions.replace("{context}", context)
        messages: list = [SystemMessage(content=system_msg)]
        if chat_history:
            messages.extend(chat_history[-5:])
        messages.append(HumanMessage(content=user_input))
        return messages

    def _is_greeting(self, user_input: str) -> bool:
        text = user_input.strip()
        if not text or len(text) > 80:
            return False
        if _GREETING_RE.match(text):
            return True
        tokens = re.findall(r"[a-zà-ú0-9]+", text.lower())
        if not tokens or len(tokens) > 6:
            return False
        return all(t in _GREETING_EXTRA for t in tokens)

    def _greeting_response(self, user_input: str) -> dict:
        text = (
            "Oi! Sou o UPi, assistente do NAPSI na POLI/UPE — massa falar com você, visse! "
            "Quer saber sobre atendimento, localização ou serviços do núcleo?"
        )
        return {"response": text, "emotion": "happy"}

    def _distress_response(self, user_input: str) -> dict:
        return {
            "response": FALLBACK_ANSWERS["acolhimento"],
            "emotion": "calm",
        }

    def _crisis_response(self, user_input: str) -> dict:
        return {
            "response": FALLBACK_ANSWERS["crise"],
            "emotion": "calm",
        }

    def _block_out_of_scope_for_distress(self, user_input: str, result: dict) -> dict:
        """Evita que o LLM recuse quem pede ajuda em sofrimento ou crise."""
        if not (is_crisis_message(user_input) or is_distress_message(user_input)):
            return result
        text = str(result.get("response", "")).lower()
        if _OUT_OF_SCOPE_PHRASE in text:
            tag = "CRISIS" if is_crisis_message(user_input) else "DISTRESS"
            print(f"[{tag}] Substituindo resposta fora do escopo.", flush=True)
            if is_crisis_message(user_input):
                return self._crisis_response(user_input)
            return self._distress_response(user_input)
        return result

    def _sanitize_response_tone(self, text: str) -> str:
        """Evita apelidos íntimos na resposta (lindo, linda, amor, etc.)."""
        if not text:
            return text
        banned = re.compile(
            r"\b(lindo|linda|amor|mozão|mozao|bb|bebê|bebe|querid[oa]|gatinh[oa])\b",
            re.IGNORECASE,
        )
        cleaned = banned.sub("", text)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
        return cleaned or text

    def _apply_intent_fallback(self, user_input: str, result: dict) -> dict:
        intent = classify_intent(user_input)
        text = str(result.get("response", ""))
        if response_matches_intent(text, intent):
            return result
        mapped = _INTENT_FALLBACK_KEY.get(intent)
        if mapped:
            fb_key, emotion = mapped
            if fb_key in FALLBACK_ANSWERS:
                print(
                    f"[INTENT FALLBACK] LLM/cache fora do tema '{intent}', usando resposta segura.",
                    flush=True,
                )
                return {"response": FALLBACK_ANSWERS[fb_key], "emotion": emotion}
        return result

    def _keyword_fallback(self, user_input: str) -> dict:
        if is_crisis_message(user_input):
            return self._crisis_response(user_input)
        if is_distress_message(user_input):
            return self._distress_response(user_input)
        lower = user_input.lower()
        for key, val in FALLBACK_ANSWERS.items():
            if key in lower:
                return {"response": val, "emotion": "calm"}
        return {
            "response": (
                "Oxe, tive um problema ao conectar com a IA agora, mas o NAPSI "
                "segue no Bloco A, Sala 12, para acolher você!"
            ),
            "emotion": "calm",
        }

    async def _finalize(self, result: dict) -> dict:
        if isinstance(result, str):
            result = {"response": result, "emotion": "neutral"}
        elif not isinstance(result, dict):
            result = {"response": str(result), "emotion": "neutral"}

        if not result.get("response"):
            result["response"] = (
                "Oxe, não consegui entender agora, mas estou por aqui!"
            )
        if result.get("emotion") not in VALID_EMOTIONS:
            result["emotion"] = "neutral"

        result["response"] = polish_portuguese(
            self._sanitize_response_tone(str(result.get("response", "")))
        )
        if not result.get("audio"):
            result["audio"] = await self.generate_audio(result["response"])
        return result

    async def _invoke_llm(self, messages: list):
        if not self.llm:
            raise RuntimeError("LLM não inicializado")
        if hasattr(self.llm, "ainvoke"):
            return await self.llm.ainvoke(messages)
        return self.llm.invoke(messages)

    def _log_timings(self, label: str, timings: dict[str, float]) -> None:
        if not settings.UPI_LOG_TIMINGS:
            return
        parts = ", ".join(f"{key}={ms:.0f}ms" for key, ms in timings.items())
        print(f"[LATENCY] {label} | {parts}", flush=True)

    async def get_response(
        self,
        user_input: str,
        chat_history: List[BaseMessage] = None,
        user_id: str = None,
    ):
        started = time.perf_counter()
        timings: dict[str, float] = {}

        if is_crisis_message(user_input):
            self._log_timings("crisis-fast-path", timings)
            return await self._finalize(self._crisis_response(user_input))

        if is_distress_message(user_input):
            self._log_timings("distress-fast-path", timings)
            return await self._finalize(self._distress_response(user_input))

        if settings.UPI_FAST_GREETINGS and self._is_greeting(user_input):
            self._log_timings("greeting-fast-path", timings)
            return await self._finalize(self._greeting_response(user_input))

        t_embed = time.perf_counter()
        query_vector = self._embed_query(user_input)
        timings["embed"] = (time.perf_counter() - t_embed) * 1000

        t_cache = time.perf_counter()
        cached = self._lookup_semantic_cache(user_input, query_vector)
        timings["cache"] = (time.perf_counter() - t_cache) * 1000
        if cached and cached.get("response"):
            timings["total"] = (time.perf_counter() - started) * 1000
            self._log_timings("cache-hit", timings)
            return await self._finalize(cached)

        t_rag = time.perf_counter()
        context = self._rag_context(user_input, query_vector)
        timings["rag"] = (time.perf_counter() - t_rag) * 1000
        messages = self._build_messages(user_input, context, chat_history)

        try:
            t_llm = time.perf_counter()
            raw = await self._invoke_llm(messages)
            timings["llm"] = (time.perf_counter() - t_llm) * 1000
            response_text = (
                raw.content if hasattr(raw, "content") else str(raw)
            )
            result = self._parse_structured_response(response_text)
            result = self._block_out_of_scope_for_distress(user_input, result)
            result = self._apply_intent_fallback(user_input, result)
        except Exception as e:
            print(f"[LLM OFFLINE] {e}", flush=True)
            result = self._keyword_fallback(user_input)

        timings["total"] = (time.perf_counter() - started) * 1000
        self._log_timings("llm-path", timings)
        
        final_result = await self._finalize(result)
        
        if response_matches_intent(
            str(final_result.get("response", "")), classify_intent(user_input)
        ):
            self._store_semantic_cache(
                user_input,
                json.dumps(final_result, ensure_ascii=False),
            )
            
        return final_result

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

    # ==================================================
    # INÍCIO - TTS (ElevenLabs + Edge-TTS Fallback)
    # ==================================================

    async def _generate_audio_elevenlabs(self, text: str):
        """
        Gera áudio usando ElevenLabs.
        """

        client = ElevenLabs(
            api_key=settings.ELEVEN_LABS_API_KEY
        )

        audio_generator = client.text_to_speech.convert(
            voice_id=settings.ELEVENLABS_VOICE_ID,
            text=text,
            model_id="eleven_multilingual_v2"
        )

        audio_bytes = b"".join(audio_generator)

        return (
            "data:audio/mpeg;base64,"
            + base64.b64encode(audio_bytes).decode("utf-8")
        )


    async def _generate_audio_edge(self, text: str):
        """
        Fallback Edge-TTS.
        """

        with tempfile.NamedTemporaryFile(
            suffix=".mp3",
            delete=False
        ) as tmp:

            output_file = tmp.name

        clean_text = re.sub(r"[*_#`]", "", text)
        clean_text = re.sub(r"\n+", " ", clean_text)
        clean_text = clean_text.replace("/", "")
        clean_text = clean_text.strip()

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice="pt-BR-FranciscaNeural"
        )

        await communicate.save(output_file)

        with open(output_file, "rb") as f:
            audio_bytes = f.read()

        os.remove(output_file)

        return (
            "data:audio/mpeg;base64,"
            + base64.b64encode(audio_bytes).decode("utf-8")
        )


    TTS_CACHE: dict = {}

    async def generate_audio(self, text: str):
        """
        Primeiro tenta ElevenLabs.
        Se falhar, usa Edge-TTS.
        Possui cache em memória para não gastar tokens com a mesma string (fast-paths).
        """
        if text in self.TTS_CACHE:
            return self.TTS_CACHE[text]

        try:
            if settings.ELEVEN_LABS_API_KEY:
                print("[TTS] Usando ElevenLabs", flush=True)
                audio = await self._generate_audio_elevenlabs(text)
                self.TTS_CACHE[text] = audio
                return audio
        except Exception as e:
            print(f"[TTS] ElevenLabs falhou: {e}", flush=True)

        print("[TTS] Fallback Edge-TTS", flush=True)
        audio = await self._generate_audio_edge(text)
        self.TTS_CACHE[text] = audio
        return audio

    # ==================================================
    # FIM - TTS
    # ==================================================



    async def _call_llm_structured(self, messages: list) -> str:
        """Executa a chamada ao LLM usando mensagens estruturadas (System/Human)."""
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            print(f"Erro no LLM: {e}. Tentando fallback...", flush=True)
            if not getattr(self, 'using_fallback', False):
                from langchain_ollama import ChatOllama
                fallback_llm = ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    base_url=settings.OLLAMA_BASE_URL
                )
                return fallback_llm.invoke(messages).content
            raise e
        

    

    def _parse_structured_response(self, raw: str) -> dict:
        def clean_text(t):
            if not isinstance(t, str):
                return None
            return t.strip().strip('"').strip()

        clean = raw
        for block in ["```json", "```", "JSON:"]:
            clean = clean.replace(block, "")
        clean = clean.strip()

        start, end = clean.find("{"), clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(clean[start : end + 1])
                text = clean_text(
                    data.get("response") or data.get("resposta") or data.get("text")
                )
                emo = data.get("emotion") or data.get("emocao") or "neutral"
                if emo not in VALID_EMOTIONS:
                    emo = "neutral"
                return {"response": text or clean[:500], "emotion": emo}
            except json.JSONDecodeError:
                pass

        m = re.search(r'"response"\s*:\s*"([^"]+)"', clean)
        if m:
            emo_m = re.search(r'"emotion"\s*:\s*"([^"]+)"', clean)
            emo = emo_m.group(1) if emo_m else "neutral"
            if emo not in VALID_EMOTIONS:
                emo = "neutral"
            return {"response": m.group(1).strip(), "emotion": emo}

        return {"response": clean[:500], "emotion": "neutral"}

    async def add_document(self, text: str, metadata: dict = None):
        if not self.vector_store:
            return
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=500, chunk_overlap=50
            )
            docs = splitter.create_documents(
                [text], metadatas=[metadata or {}]
            )
            self.vector_store.add_documents(docs)
        except Exception as e:
            print(f"[ERRO] Ingestão: {e}", flush=True)


ai_service = AIService()

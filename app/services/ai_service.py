import os
import json
import base64
import re
import io
from typing import List

# Importações de base do LangChain
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from app.config import settings

# =====================================================================
# PROMPT DE CONTINGÊNCIA GLOBAL (Segurança de Escopo)
# =====================================================================
DEFAULT_UPI_PROMPT = """Você é o UPi, o assistente virtual oficial do NAPSI (Núcleo de Apoio Psicopedagógico e Suporte Estudantil) da POLI/UPE.
Sua personalidade é extremamente acolhedora, empática, paciente e muito simpática. Como você está em Pernambuco, use expressões regionais como "oxe", "visse", "massa", "eita" de forma natural e carinhosa.

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


class AIService:
    """
    Serviço central de IA para o UPi.
    Totalmente blindado contra NameError, TypeError de dicionário/string,
    erros de tuplas no prompt e com o processador fonético gTTS calibrado.
    """

    def __init__(self, connection_string: str = None):
        self.embeddings = self._init_embeddings()
        self.llm = self._init_llm()
        
        # BLINDAGEM DE TUPLA NO PROMPT
        raw_instructions = UPI_SYSTEM_PROMPT or DEFAULT_UPI_PROMPT
        if isinstance(raw_instructions, tuple):
            self.system_instructions = " ".join(str(x) for x in raw_instructions)
        else:
            self.system_instructions = str(raw_instructions)
            
        self.connection_string = connection_string or settings.DATABASE_URL
        self.collection_name = settings.COLLECTION_NAME
        self.vector_store = None
        self.init_knowledge_base()

    def _init_embeddings(self):
        """Inicializa os embeddings locais."""
        try:
            from langchain_huggingface import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL
            )

        except Exception as e:
            print(
                f"[AVISO] Não foi possível carregar os embeddings: {e}",
                flush=True
            )
            return None

    def _init_llm(self):
        """Inicializa o LLM principal (OpenAI) com recurso automático para o Ollama local."""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from langchain_openai import ChatOpenAI
                self.using_fallback = False
                return ChatOpenAI(model_name=settings.OPENAI_MODEL, temperature=0.7)
            except Exception as e:
                print(f"[AVISO] Falha ao iniciar OpenAI: {e}. Tentando Ollama local.", flush=True)

        print(f"A usar o Ollama ({settings.OLLAMA_BASE_URL}) como LLM.", flush=True)
        self.using_fallback = True
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.OLLAMA_MODEL,
                temperature=0.7,
                base_url=settings.OLLAMA_BASE_URL
            )
        except Exception as e:
            print(f"[ERRO CRÍTICO] Falha ao importar ou inicializar ChatOllama: {e}", flush=True)
            return None

    def init_knowledge_base(self):
        """Configura o banco de dados de vetores com tratamento de erros de importação."""
        initial_data = [
            "O NAPSI/UPE oferece suporte psicopedagógico e acolhimento no Bloco A, Sala 12, das 08h às 17h.",
            "Para agendar atendimentos no NAPSI, envie um e-mail para napsi@poli.br."
        ]
        
        try:
            from langchain_postgres import PGVector
            self.vector_store = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=self.connection_string,
                use_jsonb=True,
            )
            self._populate_if_empty(initial_data)
            print("[INFO] Banco de dados PGVector inicializado com sucesso.", flush=True)
        except Exception as e_postgres:
            print(f"[AVISO] Postgres indisponível ou módulo ausente: {e_postgres}. Ativando ChromaDB.", flush=True)
            self._init_chroma_fallback(initial_data, e_postgres)

    def _populate_if_empty(self, data: list):
        """Popula a base de conhecimento se estiver vazia."""
        try:
            if self.vector_store and not self.vector_store.get_by_ids(["initial_check"]):
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
                docs = text_splitter.create_documents(data)
                self.vector_store.add_documents(docs)
        except Exception:
            pass

    def _init_chroma_fallback(self, data: list, error: Exception):
        """Inicializa o ChromaDB local de forma dinâmica para evitar erros de importação globais."""
        persist_dir = settings.CHROMA_PERSIST_DIR
        try:
            from langchain_community.vectorstores import Chroma
            self.vector_store = Chroma(
                embedding_function=self.embeddings,
                persist_directory=persist_dir,
                collection_name=self.collection_name,
            )
            if not self.vector_store.get()["ids"]:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
                docs = text_splitter.create_documents(data)
                self.vector_store.add_documents(docs)
            print("[INFO] Banco de dados local ChromaDB ativado com sucesso.", flush=True)
        except Exception as e_chroma:
            print(f"[AVISO] Não foi possível iniciar o ChromaDB: {e_chroma}. O UPi funcionará em modo direto.", flush=True)
            self.vector_store = None

    @property
    def vector_store_type(self) -> str:
        if not self.vector_store:
            return "direto (sem banco)"
        try:
            from langchain_community.vectorstores import Chroma
            return "chroma" if isinstance(self.vector_store, Chroma) else "pgvector"
        except Exception:
            return "vetorial"

    def _clean_text_for_tts(self, text: str) -> str:
        """
        Higienização e polimento fonético para áudio ultra humano e natural.
        """
        if not text:
            return ""

        # Remove negritos, itálicos e cabeçalhos do Markdown
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        clean = re.sub(r'\*([^*]+)\*', r'\1', clean)
        clean = re.sub(r'__([^_]+)__', r'\1', clean)
        clean = re.sub(r'_([^_]+)_', r'\1', clean)
        clean = re.sub(r'#+\s+', '', clean)
        clean = re.sub(r'-\s+', '', clean)
        clean = re.sub(r'\d+\.\s+', '', clean)

        # Remove links do Markdown
        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)

        # Remove caracteres especiais e emojis, preservando acentuação
        clean = re.sub(r'[^\w\s,.:!?;áéíóúâêîôûàèìòùãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ\-]', '', clean)

        # MAPA FONÉTICO: Ajusta regionalismos e siglas acadêmicas para o gTTS pronunciar perfeitamente
        phonetic_map = {
            r'\bUPE\b': 'U. P. E.',
            r'\bUpe\b': 'U. P. E.',
            r'\bPOLI\b': 'Póli',
            r'\bPoli\b': 'Póli',
            r'\bNAPSI\b': 'Náp-si',
            r'\bNapsi\b': 'Náp-si',
            r'\bOxe\b': 'Óxe',
            r'\boxe\b': 'óxe',
            r'\bvisse\b': 'vísse',
            r'\bvisse\?\b': 'vísse?',
            r'\bemail\b': 'e-mail',
            r'\b@\b': ' arroba ',
        }

        for pattern, replacement in phonetic_map.items():
            clean = re.sub(pattern, replacement, clean)

        # Adiciona micropausas de respiração estratégica
        clean = clean.replace(",", ", ...")
        clean = clean.replace(".", ". ...")
        clean = clean.replace("!", "! ...")
        clean = clean.replace("?", "? ...")
        
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _generate_tts_audio(self, text: str) -> str:
        """Gera o áudio usando gTTS com o texto higienizado."""
        try:
            from gtts import gTTS
            
            clean_text = self._clean_text_for_tts(text)
            if not clean_text:
                return ""

            tts = gTTS(text=clean_text, lang='pt', tld='com.br', slow=False)
            
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            
            audio_base64 = base64.b64encode(fp.read()).decode("utf-8")
            return f"data:audio/mp3;base64,{audio_base64}"
            
        except Exception as e:
            print(f"[TTS ERROR] Falha na síntese de voz gTTS: {e}", flush=True)
            return ""

    async def get_response(self, user_input: str, chat_history: List[BaseMessage] = None, user_id: str = None):
        """Processa a mensagem com busca de contexto (RAG) e síntese de voz calibrada."""
        fallback_answers = {
            "onde fica": "Oxe, o NAPSI fica no Bloco A, Sala 12, visse? Pode passar lá de segunda a sexta, das 8h às 17h!",
            "agendar": "Pra agendar seu atendimento, você pode mandar um e-mail para napsi@poli.br ou falar diretamente na coordenação do Bloco A, Sala 12!",
            "tea": "O NAPSI oferece suporte psicopedagógico especializado e adaptado para todos os estudantes, incluindo alunos com TEA (Transtorno do Espectro Autista).",
            "serviço": "Oferecemos apoio psicopedagógico, acolhimento psicossocial, auxílio na adaptação acadêmica e orientação aos estudantes da Poli!",
            "oi": "Oi! Sou o UPi, assistente virtual do NAPSI aqui na POLI/UPE! Massa demais ter você aqui, visse? Como posso te ajudar hoje?"
        }

        context = "O NAPSI oferece atendimento psicopedagógico no Bloco A, Sala 12, de segunda a sexta, das 8h às 17h."
        
        if self.vector_store:
            try:
                docs = self.vector_store.similarity_search(user_input, k=3)
                if docs:
                    context = "\n".join([doc.page_content for doc in docs])
            except Exception as e_rag:
                print(f"[AVISO] Falha ao realizar busca semântica: {e_rag}", flush=True)

        # BLINDAGEM DE TUPLA NO PROMPT
        instructions = self.system_instructions if self.system_instructions else DEFAULT_UPI_PROMPT
        if isinstance(instructions, tuple):
            instructions = " ".join(str(x) for x in instructions)
        else:
            instructions = str(instructions)
            
        system_msg = instructions.replace("{context}", context)
        
        messages = [SystemMessage(content=system_msg)]
        if chat_history:
            messages.extend(chat_history[-5:])
        messages.append(HumanMessage(content=user_input))

        try:
            if not self.llm:
                raise Exception("LLM não está inicializado localmente ou na nuvem.")
            
            response = self.llm.invoke(messages)
            
            # BLINDAGEM DE RETORNO DO LLM: Trata se o retorno vier como objeto ou string pura
            if hasattr(response, "content"):
                response_text = response.content
            else:
                response_text = str(response)
                
            result = self._parse_structured_response(response_text)
        except Exception as e_llm:
            print(f"[LLM OFFLINE] Ativando contingência de respostas integradas: {e_llm}", flush=True)
            
            matched_response = None
            user_lower = user_input.lower()
            for key, val in fallback_answers.items():
                if key in user_lower:
                    matched_response = val
                    break
            
            if not matched_response:
                matched_response = "Oxe, tive um pequeno problema ao conectar com a inteligência artificial agora, mas posso adiantar que o NAPSI está ativo no Bloco A, Sala 12, para te acolher!"
            
            result = {
                "response": matched_response,
                "emotion": "calm"
            }

        # =====================================================================
        # BLINDAGEM MÁXIMA CONTRA TYPE_ERROR (Converte string pura para dict)
        # =====================================================================
        if isinstance(result, str):
            result = {
                "response": result,
                "emotion": "neutral"
            }
        elif not isinstance(result, dict):
            result = {
                "response": str(result),
                "emotion": "neutral"
            }

        # Garante que as chaves obrigatórias sempre existam para evitar novos erros de chave
        if "response" not in result or not result["response"]:
            result["response"] = "Oxe, não consegui entender muito bem agora, mas estou por aqui!"
        if "emotion" not in result:
            result["emotion"] = "neutral"

        # Gera o áudio da voz em base64 com segurança
        result["audio"] = self._generate_tts_audio(result["response"])
        return result

    def _parse_structured_response(self, raw: str) -> dict:
        """Extrai as informações de texto e emoção retornadas pelo modelo."""
        VALID_EMOTIONS = {"happy", "neutral", "sad", "excited", "thinking", "calm", "surprised", "confused"}

        def clean_text(t):
            if not isinstance(t, str): return None
            return t.strip().strip('"').strip()

        clean = raw
        for block in ["```json", "```", "JSON:"]:
            clean = clean.replace(block, "")
        clean = clean.strip()

        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(clean[start:end + 1])
                text = clean_text(data.get("response") or data.get("resposta") or data.get("text"))
                emo = data.get("emotion") or data.get("emocao") or "neutral"
                if emo not in VALID_EMOTIONS: emo = "neutral"
                return {"response": text, "emotion": emo}
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
        """Adiciona e indexa novos conhecimentos em tempo real na base local."""
        if not self.vector_store:
            return
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            docs = text_splitter.create_documents([text], metadatas=[metadata or {}])
            self.vector_store.add_documents(docs)
        except Exception as e:
            print(f"[ERRO] Falha ao adicionar novo documento: {e}", flush=True)


ai_service = AIService()
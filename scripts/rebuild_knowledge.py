#!/usr/bin/env python3
"""
Reindexa a base de conhecimento (Chroma dev) a partir de data/napsi_info.txt e data/knowledge/*.txt.
Remove cache semântico para evitar respostas antigas.

Uso:
  python scripts/rebuild_knowledge.py
"""
from __future__ import annotations

import os
import shutil
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.config import settings  # noqa: E402


def main() -> int:
    chroma_dir = settings.CHROMA_PERSIST_DIR
    cache_path = settings.DEV_CACHE_PATH

    if os.path.isdir(chroma_dir):
        try:
            shutil.rmtree(chroma_dir)
            print(f"[OK] Removido Chroma: {chroma_dir}")
        except OSError as e:
            print(
                f"[AVISO] Não foi possível apagar {chroma_dir} ({e}). "
                "Pare o uvicorn e rode de novo para reindexação limpa. "
                "Indexando trechos adicionais na base atual...",
                flush=True,
            )

    if os.path.isfile(cache_path):
        os.remove(cache_path)
        print(f"[OK] Removido cache semântico: {cache_path}")

    print("[INFO] Semeando base de conhecimento (pode levar alguns minutos)...")
    from app.services.ai_service import AIService  # noqa: E402

    service = AIService()
    if not service.vector_store:
        print("[ERRO] Vector store não inicializado (verifique Ollama/embeddings).")
        return 1

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = splitter.create_documents(service._load_seed_texts())
        existing = []
        try:
            existing = service.vector_store.get().get("ids") or []
        except Exception:
            pass
        if not existing:
            service.vector_store.add_documents(docs)
        else:
            service.vector_store.add_documents(docs)
            print(
                f"[INFO] Base já tinha {len(existing)} trechos; "
                f"+{len(docs)} trechos das fontes atuais.",
                flush=True,
            )
        n = len(docs)
        print(f"[OK] {n} trechos processados na coleção '{settings.COLLECTION_NAME}'.")
    except Exception as e:
        print(f"[ERRO] Indexação: {e}")
        return 1

    print("\nPróximo passo: reinicie o servidor uvicorn para carregar a base nova.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

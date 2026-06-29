import os
import asyncio
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.ai_service import ai_service


def _load_pdf(file_path: Path) -> list[dict]:
    """Carrega um PDF usando pypdf diretamente (sem langchain-community)."""
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"text": text, "page": i + 1})
    return pages


def _load_text(file_path: Path) -> list[dict]:
    """Carrega um arquivo de texto ou markdown."""
    content = file_path.read_text(encoding="utf-8")
    return [{"text": content, "page": 1}]


async def ingest_folder(folder_path: str):
    """
    Lê todos os arquivos PDF, TXT e MD de uma pasta e os adiciona à base de conhecimento do UPi.
    """
    data_path = Path(folder_path)
    if not data_path.exists():
        print(f"Erro: A pasta {folder_path} não existe.")
        return

    print(f"Iniciando ingestão de documentos em: {folder_path}...")

    paths = list(data_path.glob("*")) + list(data_path.glob("knowledge/*"))
    for file_path in paths:
        if file_path.suffix.lower() == ".pdf":
            loader = _load_pdf
        elif file_path.suffix.lower() in (".txt", ".md"):
            loader = _load_text
        else:
            continue

        print(f"Processando: {file_path.name}...")
        try:
            pages = loader(file_path)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=100
            )

            total_chunks = 0
            for page_data in pages:
                chunks = text_splitter.create_documents(
                    texts=[page_data["text"]],
                    metadatas=[{"source": file_path.name, "page": page_data["page"]}],
                )
                for chunk in chunks:
                    await ai_service.add_document(
                        text=chunk.page_content,
                        metadata=chunk.metadata,
                    )
                    total_chunks += 1

            print(f"Sucesso: {total_chunks} trechos adicionados.")
        except Exception as e:
            print(f"Erro ao processar {file_path.name}: {e}")


if __name__ == "__main__":
    # Cria a pasta data se não existir
    os.makedirs("data", exist_ok=True)

    # Se houver arquivos na pasta, processa
    asyncio.run(ingest_folder("data"))
    print("\nIngestão concluída! O UPi agora conhece seus documentos.")

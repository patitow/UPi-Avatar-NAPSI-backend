import os
import asyncio
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.ai_service import ai_service
from pathlib import Path

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
            loader = PyPDFLoader(str(file_path))
        elif file_path.suffix.lower() == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
        elif file_path.suffix.lower() == ".md":
            loader = TextLoader(str(file_path), encoding="utf-8")
        else:
            continue

        print(f"Processando: {file_path.name}...")
        try:
            # Carrega e divide o documento
            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            chunks = text_splitter.split_documents(documents)
            
            # Adiciona ao vector store (pgvector)
            for chunk in chunks:
                await ai_service.add_document(
                    text=chunk.page_content, 
                    metadata={"source": file_path.name, **chunk.metadata}
                )
            print(f"Sucesso: {len(chunks)} trechos adicionados.")
        except Exception as e:
            print(f"Erro ao processar {file_path.name}: {e}")

if __name__ == "__main__":
    # Cria a pasta data se não existir
    os.makedirs("data", exist_ok=True)
    
    # Se houver arquivos na pasta, processa
    asyncio.run(ingest_folder("data"))
    print("\nIngestão concluída! O UPi agora conhece seus documentos.")

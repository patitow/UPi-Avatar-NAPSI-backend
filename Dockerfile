# Usar uma imagem Python leve
FROM python:3.11-slim

# Definir o diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema necessárias para algumas libs (como psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar apenas os requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instalar as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do código
COPY . .

# Expor a porta que a FastAPI usa
EXPOSE 8000

# Comando para iniciar a aplicação
# 2 workers async = suficiente para VPS 4GB com Postgres + Redis + Caddy rodando juntos
# FastAPI e async por natureza, 2 workers suportam bem a carga sem desperdicar ~430MB de RAM
# --timeout-keep-alive 75 evita que conexoes caiam antes do LLM responder
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-keep-alive", "75"]

# ==============================================================================
# ARQUIVO: backend/Dockerfile
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo descreve como montar a "caixa" (imagem Docker) que roda o
# backend do Agente Comercial SDR — tanto o servidor da API (FastAPI/
# Uvicorn) quanto os processos do Celery (worker e beat), que reaproveitam
# esta mesma imagem, apenas com um comando de inicialização diferente
# (ver docker-compose.yml).
# ==============================================================================

FROM python:3.11-slim

# Evita que o Python crie arquivos .pyc e garante que os logs apareçam em
# tempo real no terminal (importante para acompanhar o container rodando).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /aplicativo

# Instala as dependências do sistema necessárias para compilar algumas
# bibliotecas Python (ex.: psycopg, usada para falar com o PostgreSQL) e o
# ffmpeg, usado para extrair um frame de vídeos recebidos no WhatsApp (ver
# integracoes_externas/video.py) — a OpenAI não aceita vídeo como entrada
# direta, só imagem, então descrevemos um frame extraído dele.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copia só o requirements.txt primeiro — assim o Docker reaproveita esta
# camada em builds futuros enquanto as dependências não mudarem, deixando
# o build bem mais rápido no dia a dia.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agora copia o resto do código da aplicação.
COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

# Comando padrão: sobe o servidor da API. Os containers de worker/beat do
# Celery sobrescrevem este comando no docker-compose.yml.
CMD ["uvicorn", "app.main:aplicativo", "--host", "0.0.0.0", "--port", "8000"]

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Esta imagem Docker instala as dependências do backend, copia o código-
# fonte e, por padrão, sobe o servidor da API com Uvicorn na porta 8000.
# A mesma imagem é reaproveitada pelos containers "worker" e "beat" do
# Celery, apenas trocando o comando executado.
# ==============================================================================

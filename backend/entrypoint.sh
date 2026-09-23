#!/bin/sh
# ==============================================================================
# ARQUIVO: backend/entrypoint.sh
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este script roda automaticamente toda vez que o container do backend (ou
# do worker/beat do Celery) inicia. Antes de executar o comando principal,
# ele aplica as migrações pendentes do banco de dados (alembic upgrade
# head) — assim, implantar um cliente novo ou atualizar a plataforma nunca
# exige rodar um comando manual à parte: basta subir os containers.
# ==============================================================================
set -e

echo "Aplicando migrações do banco de dados..."
alembic upgrade head

echo "Iniciando: $@"
exec "$@"

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este script garante que o banco de dados esteja sempre com o esquema
# atualizado antes de qualquer processo do backend (API, worker ou beat)
# começar a rodar, e depois entrega a execução para o comando real do
# container (uvicorn ou celery).
# ==============================================================================

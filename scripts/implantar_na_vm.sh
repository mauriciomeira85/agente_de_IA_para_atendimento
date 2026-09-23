#!/bin/bash
# ==============================================================================
# ARQUIVO: scripts/implantar_na_vm.sh
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este script automatiza a implantação do Agente Comercial SDR em uma VM
# Linux (Ubuntu) do zero: instala o Docker e sobe todos os containers da
# aplicação com um único comando — incluindo o túnel do Cloudflare, que
# publica o endereço na internet com HTTPS automático, sem precisar abrir
# portas na VM nem ter domínio próprio.
#
# COMO USAR (rode isto DENTRO da VM, depois de copiar o repositório para
# lá, por exemplo com "git clone" ou "scp"):
#
#   cd agente-comercial-sdr
#   cp .env.exemplo .env
#   nano .env                     # preencha os valores reais (ver README)
#   chmod +x scripts/implantar_na_vm.sh
#   ./scripts/implantar_na_vm.sh
# ==============================================================================
set -e

DIRETORIO_DO_PROJETO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIRETORIO_DO_PROJETO"

echo "==> Verificando arquivo .env"
if [ ! -f .env ]; then
  echo "Arquivo .env não encontrado. Copiando o modelo .env.exemplo..."
  cp .env.exemplo .env
  echo "!! Edite o arquivo .env com os valores reais antes de continuar (nano .env) e rode este script de novo."
  exit 1
fi

echo "==> Instalando o Docker (caso ainda não esteja instalado)"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  echo "Docker instalado. Talvez seja necessário sair e entrar de novo na sessão SSH para usar o Docker sem sudo."
fi

echo "==> Subindo os containers (build + start)"
docker compose up -d --build

echo "==> Pronto! Containers no ar:"
docker compose ps

echo "==> Aguardando o túnel do Cloudflare publicar o endereço (pode levar alguns segundos)..."
sleep 8
ENDERECO_PUBLICO="$(docker compose logs tunnel 2>&1 | grep -oE 'https://[a-zA-Z0-9.-]*\.trycloudflare\.com' | tail -n 1)"

echo ""
echo "Próximos passos:"
if [ -n "$ENDERECO_PUBLICO" ]; then
  echo "  1. Acesse: ${ENDERECO_PUBLICO}"
else
  echo "  1. Rode 'docker compose logs tunnel' e procure a URL https://*.trycloudflare.com gerada."
fi
echo "  2. No Worker do Cloudflare (infra/cloudflare-webhook), configure:"
echo "       BACKEND_WEBHOOK_URL = ${ENDERECO_PUBLICO:-<endereco-do-tunel>}/api/webhooks/whatsapp"
echo "  3. Crie a primeira conta da plataforma acessando a URL acima e clicando em 'Cadastre sua empresa'."
echo "  4. Atenção: o endereço do túnel muda se o container 'tunnel' for reiniciado. Para um endereço fixo,"
echo "     configure um domínio próprio em DOMINIO_PUBLICO (ver .env.exemplo) e libere as portas 80/443 na VM."

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este script prepara uma VM Ubuntu do zero (instala o Docker) e sobe toda
# a aplicação com "docker compose up -d --build", incluindo o túnel do
# Cloudflare que publica o endereço na internet. Ao final, ele lê os logs
# do túnel para descobrir e imprimir a URL pública gerada, junto com o
# próximo passo manual que só o dono da conta Cloudflare pode fazer
# (apontar o Worker para essa URL).
# ==============================================================================

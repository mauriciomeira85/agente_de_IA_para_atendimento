# ==============================================================================
# ARQUIVO: frontend/Dockerfile
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo descreve como montar a imagem Docker da interface (Next.js)
# do Agente Comercial SDR. Ele usa um build em DUAS ETAPAS ("multi-stage
# build"): a primeira etapa instala as dependências e compila a
# aplicação; a segunda etapa copia só o resultado final (a pasta gerada
# pelo modo "standalone" do Next.js, ver next.config.ts), deixando a
# imagem final bem mais enxuta — sem o node_modules de desenvolvimento.
# ==============================================================================

# --- Etapa 1: instalar dependências e compilar ---
FROM node:22-slim AS construtor
WORKDIR /aplicativo

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# O endereço público da API precisa existir no momento do build, porque o
# Next.js incorpora variáveis "NEXT_PUBLIC_*" diretamente no código do
# navegador. O valor real é passado pelo docker-compose.yml.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# --- Etapa 2: imagem final, só com o necessário para rodar ---
FROM node:22-slim AS executor
WORKDIR /aplicativo
ENV NODE_ENV=production

COPY --from=construtor /aplicativo/public ./public
COPY --from=construtor /aplicativo/.next/standalone ./
COPY --from=construtor /aplicativo/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Esta imagem compila o frontend em uma etapa separada (com todas as
# dependências de desenvolvimento) e monta a imagem final apenas com o
# resultado do build "standalone" do Next.js — mais rápida de subir e bem
# menor do que copiar o projeto inteiro.
# ==============================================================================

// ==============================================================================
// ARQUIVO: next.config.ts
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Configuração do Next.js. A única opção não-padrão aqui é
// "output: standalone", que faz o "next build" gerar uma pasta enxuta
// (.next/standalone) com só o necessário para rodar em produção — usada
// pelo Dockerfile do frontend para montar uma imagem bem mais leve do que
// copiar o node_modules inteiro.
// ==============================================================================

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo ativa o modo "standalone" de build do Next.js, usado para
// gerar uma imagem Docker de produção enxuta (ver frontend/Dockerfile).
// ==============================================================================

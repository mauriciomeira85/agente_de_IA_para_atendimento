// ==============================================================================
// ARQUIVO: app/layout.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Este é o "molde" (layout raiz) que envolve TODAS as páginas da
// aplicação Next.js — é aqui que ficam coisas que aparecem em toda tela,
// como o idioma do documento HTML, a fonte usada e o provedor de
// autenticação (que deixa os dados da empresa logada disponíveis para
// qualquer componente da árvore).
// ==============================================================================

import type { Metadata } from "next";
import "./globals.css";
import { ProvedorDeAutenticacao } from "@/biblioteca/autenticacao";

export const metadata: Metadata = {
  title: "Agente de Atendimento",
  description: "Plataforma de agente de IA para atendimento receptivo a clientes via WhatsApp.",
};

export default function LayoutRaiz({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="antialiased bg-slate-50 text-marca-escuro">
        <ProvedorDeAutenticacao>{children}</ProvedorDeAutenticacao>
      </body>
    </html>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo define o HTML base de toda a aplicação (idioma português,
// estilo de fundo) e envolve todas as páginas com o
// ProvedorDeAutenticacao, para que a sessão da empresa logada esteja
// disponível em qualquer tela.
// ==============================================================================

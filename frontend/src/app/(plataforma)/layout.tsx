"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/layout.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Este é o layout compartilhado por TODAS as telas internas da
// plataforma (Dashboard, Base de Atendimentos, Conversas, Setores, Base
// de Conhecimento, Configuração do Agente, Canais, Integrações e
// Configurações) — o grupo de rotas "(plataforma)"
// não aparece na URL, ele só serve para agrupar essas páginas sob o
// mesmo layout com a barra lateral.
//
// Este layout também é o responsável por PROTEGER essas rotas: antes de
// mostrar qualquer conteúdo, ele confere se existe uma sessão válida (ver
// useProtecaoDeRota em biblioteca/autenticacao.tsx) e manda para o login
// quem não estiver autenticado.
// ==============================================================================

import MenuLateral from "@/componentes/MenuLateral";
import { useProtecaoDeRota } from "@/biblioteca/autenticacao";

export default function LayoutDaPlataforma({ children }: { children: React.ReactNode }) {
  useProtecaoDeRota();

  return (
    <div className="flex min-h-screen">
      <MenuLateral />
      <main className="flex-1 min-w-0 px-8 py-8">{children}</main>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo monta o esqueleto visual de toda a área logada (barra
// lateral + conteúdo da página) e garante que só usuários autenticados
// consigam ver o que está dentro dele.
// ==============================================================================

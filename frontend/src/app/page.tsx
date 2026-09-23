"use client";

// ==============================================================================
// ARQUIVO: app/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a página de entrada da aplicação (o endereço "/"). Ela não tem
// nenhum conteúdo próprio — sua única função é decidir para onde mandar
// o visitante: se já existe um token de acesso salvo, direto para o
// Dashboard; caso contrário, para a tela de Login.
// ==============================================================================

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { estaAutenticado } from "@/biblioteca/api";

export default function PaginaInicial() {
  const roteador = useRouter();

  useEffect(() => {
    roteador.replace(estaAutenticado() ? "/painel" : "/login");
  }, [roteador]);

  return null;
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo apenas redireciona automaticamente para /painel (usuário já
// logado) ou /login (usuário novo/deslogado), assim que a página é
// carregada.
// ==============================================================================

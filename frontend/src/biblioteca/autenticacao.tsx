"use client";

// ==============================================================================
// ARQUIVO: biblioteca/autenticacao.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Este arquivo guarda, em memória (um "Context" do React), os dados
// básicos da empresa logada (nome da empresa e nome do agente) depois do
// login ou cadastro, para que a barra lateral e o cabeçalho da plataforma
// não precisem buscar essa informação de novo em toda troca de página.
//
// A "fonte da verdade" de quem está logado, de fato, é o token guardado
// no localStorage do navegador (ver biblioteca/api.ts) — este arquivo só
// cuida da parte de exibição (nome da empresa) e da proteção de rota
// (redirecionar para o login quando não há token válido).
// ==============================================================================

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { estaAutenticado } from "./api";

interface DadosDaSessao {
  nomeFantasia: string;
  nomeDoAgente: string;
}

interface ContextoDeAutenticacao {
  sessao: DadosDaSessao | null;
  definirSessao: (dados: DadosDaSessao) => void;
  sair: () => void;
}

const Contexto = createContext<ContextoDeAutenticacao | null>(null);

export function ProvedorDeAutenticacao({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<DadosDaSessao | null>(null);

  // Ao carregar a aplicação, tenta recuperar os dados da sessão salvos
  // anteriormente (evita "esquecer" o nome da empresa ao atualizar a página).
  useEffect(() => {
    const salvo = window.localStorage.getItem("sessao_agente_atendimento");
    if (salvo) setSessao(JSON.parse(salvo));
  }, []);

  function definirSessao(dados: DadosDaSessao) {
    setSessao(dados);
    window.localStorage.setItem("sessao_agente_atendimento", JSON.stringify(dados));
  }

  function sair() {
    setSessao(null);
    window.localStorage.removeItem("sessao_agente_atendimento");
    window.localStorage.removeItem("token_agente_atendimento");
    window.location.href = "/login";
  }

  return <Contexto.Provider value={{ sessao, definirSessao, sair }}>{children}</Contexto.Provider>;
}

export function useAutenticacao(): ContextoDeAutenticacao {
  const contexto = useContext(Contexto);
  if (!contexto) throw new Error("useAutenticacao precisa estar dentro de <ProvedorDeAutenticacao>.");
  return contexto;
}

/**
 * Hook usado no layout das telas protegidas: se não houver token salvo,
 * manda o usuário de volta para a tela de login antes mesmo de tentar
 * carregar qualquer dado da API.
 */
export function useProtecaoDeRota(): void {
  const roteador = useRouter();
  useEffect(() => {
    if (!estaAutenticado()) {
      roteador.replace("/login");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo define o ProvedorDeAutenticacao (guarda nome da empresa e
// do agente em memória + localStorage), o hook useAutenticacao (para
// qualquer componente ler esses dados) e useProtecaoDeRota (redireciona
// para /login quando não há sessão válida) — usado no layout de todas as
// telas internas da plataforma.
// ==============================================================================

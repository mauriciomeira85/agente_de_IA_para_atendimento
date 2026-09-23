"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/configuracoes/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Configurações" — diferente da aba "Configuração do
// Agente" (que trata do COMPORTAMENTO do agente), esta aba reúne dados
// gerais DA CONTA da empresa na plataforma: nome da conta, e-mail
// principal e a opção de encerrar a sessão.
// ==============================================================================

import { useAutenticacao } from "@/biblioteca/autenticacao";

export default function PaginaDeConfiguracoes() {
  const { sessao, sair } = useAutenticacao();

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-2xl font-semibold text-marca-escuro mb-6">Configurações</h1>

      <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <h2 className="text-base font-semibold text-marca-escuro">Sua conta</h2>

        <div>
          <p className="text-xs text-slate-500">Nome da empresa</p>
          <p className="text-sm text-slate-800">{sessao?.nomeFantasia || "-"}</p>
        </div>

        <div>
          <p className="text-xs text-slate-500">Nome do agente configurado</p>
          <p className="text-sm text-slate-800">{sessao?.nomeDoAgente || "-"}</p>
        </div>

        <p className="text-xs text-slate-400 pt-2 border-t border-slate-100">
          Para alterar o comportamento, o produto ou as regras de conversa do agente, use a aba
          &quot;Configuração do Agente&quot;. Esta aba trata apenas dos dados da sua conta na plataforma.
        </p>

        <div className="pt-2">
          <button onClick={sair} className="px-4 py-2 text-sm rounded-lg border border-slate-300 hover:bg-slate-50">
            Sair da conta
          </button>
        </div>
      </section>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a aba Configurações: um resumo simples dos
// dados da conta da empresa na plataforma e a opção de logout — mantida
// separada da aba Configuração do Agente, que trata do comportamento do
// agente em si.
// ==============================================================================

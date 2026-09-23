"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/integracoes/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Integrações": serve SÓ para enviar os dados do Dashboard
// (aba Painel — cartões de quantidade/taxa e o funil) para um CRM ou
// aplicação externa da empresa usuária, sob demanda (botão "Enviar
// agora"). Diferente dos outros dois projetos da linhagem, não existe
// aqui uma metade de ENTRADA (trazer contatos de um CRM externo) — este
// agente é receptivo, todo Atendimento nasce da própria mensagem do
// cliente no WhatsApp (ver Informacoes/Arquitetura.md, seção 2). A
// conexão do WhatsApp fica na aba "Canais" (ver
// app/(plataforma)/canais/page.tsx).
// ==============================================================================

import { useEffect, useState } from "react";
import {
  cadastrarIntegracaoDeSaida,
  enviarDadosDoDashboardAgora,
  listarIntegracoesDeSaida,
  removerIntegracaoDeSaida,
} from "@/biblioteca/api";
import type { IntegracaoSaida } from "@/biblioteca/tipos";

export default function PaginaDeIntegracoes() {
  const [conexoes, setConexoes] = useState<IntegracaoSaida[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [enviandoId, setEnviandoId] = useState<number | null>(null);
  const [mensagem, setMensagem] = useState<string | null>(null);

  async function recarregar() {
    const dados = await listarIntegracoesDeSaida();
    setConexoes(dados);
    setCarregando(false);
  }

  useEffect(() => {
    recarregar();
  }, []);

  async function aoEnviarAgora(id: number) {
    setEnviandoId(id);
    try {
      const atualizada = await enviarDadosDoDashboardAgora(id);
      setConexoes((atual) => atual.map((c) => (c.id === id ? atualizada : c)));
      setMensagem(
        atualizada.ultimo_envio_com_sucesso
          ? `Dados do Dashboard enviados com sucesso para "${atualizada.nome_da_conexao}".`
          : `O destino "${atualizada.nome_da_conexao}" não aceitou o envio. Confira a URL e a chave de acesso.`
      );
    } finally {
      setEnviandoId(null);
    }
  }

  async function aoRemover(id: number) {
    await removerIntegracaoDeSaida(id);
    setConexoes((atual) => atual.filter((c) => c.id !== id));
  }

  if (carregando) return <p className="text-sm text-slate-500">Carregando integrações...</p>;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-marca-escuro">Integrações</h1>
        <button
          onClick={() => setMostrarFormulario(true)}
          className="px-3 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700"
        >
          Conectar destino de envio
        </button>
      </div>

      {mensagem && (
        <div className="text-sm bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg px-4 py-2">{mensagem}</div>
      )}

      <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <div>
          <h2 className="text-base font-semibold text-marca-escuro">Enviar dados do Dashboard</h2>
          <p className="text-sm text-slate-500">
            Cada conexão aqui recebe, por POST, os cartões de quantidade/taxa e o funil do Dashboard sempre que você
            clicar em &quot;Enviar agora&quot;. Nenhum dado de cliente é enviado por aqui — só os números agregados
            do Dashboard.
          </p>
        </div>

        {conexoes.length === 0 && <p className="text-sm text-slate-400">Nenhum destino de envio cadastrado ainda.</p>}

        {conexoes.map((conexao) => (
          <div key={conexao.id} className="flex items-center justify-between border border-slate-100 rounded-lg px-4 py-2.5">
            <div>
              <p className="text-sm font-medium text-slate-800">{conexao.nome_da_conexao}</p>
              <p className="text-xs text-slate-400">{conexao.url_webhook}</p>
              <p className="text-xs text-slate-400">
                {conexao.ultimo_envio_em
                  ? `Último envio em ${new Date(conexao.ultimo_envio_em).toLocaleString("pt-BR")} — ${
                      conexao.ultimo_envio_com_sucesso ? "sucesso" : "falhou"
                    }`
                  : "Ainda sem nenhum envio"}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => aoEnviarAgora(conexao.id)}
                disabled={enviandoId === conexao.id}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-50"
              >
                {enviandoId === conexao.id ? "Enviando..." : "Enviar agora"}
              </button>
              <button onClick={() => aoRemover(conexao.id)} className="text-xs text-slate-400 hover:text-red-600">
                Remover
              </button>
            </div>
          </div>
        ))}
      </section>

      {mostrarFormulario && (
        <FormularioDeConexaoDeSaida
          aoFechar={() => setMostrarFormulario(false)}
          aoConectar={async (nome, url, chave) => {
            await cadastrarIntegracaoDeSaida({ nome_da_conexao: nome, url_webhook: url, chave_api: chave || undefined });
            setMostrarFormulario(false);
            recarregar();
          }}
        />
      )}
    </div>
  );
}

/** Pequeno formulário (modal) para cadastrar um novo destino de envio dos dados do Dashboard. */
function FormularioDeConexaoDeSaida({
  aoFechar,
  aoConectar,
}: {
  aoFechar: () => void;
  aoConectar: (nome: string, url: string, chave: string) => Promise<void>;
}) {
  const [nome, setNome] = useState("");
  const [url, setUrl] = useState("");
  const [chave, setChave] = useState("");

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md p-6">
        <h2 className="text-lg font-semibold text-marca-escuro mb-1">Conectar destino de envio</h2>
        <p className="text-sm text-slate-500 mb-4">
          Os dados do Dashboard passam a poder ser enviados para esta URL sempre que você clicar em &quot;Enviar agora&quot;.
        </p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            await aoConectar(nome, url, chave);
          }}
          className="space-y-3"
        >
          <input
            required
            placeholder="Nome da conexão (ex.: RD Station, Pipedrive)"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm"
          />
          <input
            required
            placeholder="URL do webhook"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm"
          />
          <input
            placeholder="Chave de acesso (API key) — opcional"
            value={chave}
            onChange={(e) => setChave(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm"
          />
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={aoFechar} className="px-4 py-2 text-sm text-slate-600">
              Cancelar
            </button>
            <button type="submit" className="px-4 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700">
              Conectar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a aba Integrações por completo: cadastrar,
// listar, remover e disparar sob demanda ("Enviar agora") o envio dos
// dados do Dashboard para destinos externos (IntegracaoSaida). Sem
// metade de entrada (CRM externo) — ver introdução.
// ==============================================================================

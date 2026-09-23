"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/atendimentos/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Base de Atendimentos": a tabela completa, com filtros de
// status e busca, e a edição/exclusão manual de um atendimento.
//
// Diferente da Base de Leads do Agente Comercial SDR (e da Base de Casos
// do Agente de Cobrança), não existe aqui nenhum botão de criação,
// importação de arquivo nem conexão com CRM externo — um Atendimento só
// nasce de um jeito, automaticamente, na primeira mensagem recebida de um
// cliente no WhatsApp (ver Informacoes/Arquitetura.md, seção 2); esta
// tela só mostra o que já aconteceu.
// ==============================================================================

import { useEffect, useState } from "react";
import { editarAtendimento, excluirAtendimento, listarAtendimentos, listarSetores } from "@/biblioteca/api";
import type { Atendimento, Setor, StatusAtendimento } from "@/biblioteca/tipos";
import ModalDeAtendimento from "@/componentes/ModalDeAtendimento";

const RÓTULOS_DE_STATUS: Record<StatusAtendimento, string> = {
  recebido: "Recebido",
  em_atendimento: "Em atendimento",
  encaminhado: "Encaminhado",
  resolvido: "Resolvido",
};

const CORES_DE_STATUS: Record<StatusAtendimento, string> = {
  recebido: "bg-slate-100 text-slate-600",
  em_atendimento: "bg-blue-100 text-blue-700",
  encaminhado: "bg-amber-100 text-amber-700",
  resolvido: "bg-emerald-100 text-emerald-700",
};

export default function PaginaDeAtendimentos() {
  const [atendimentos, setAtendimentos] = useState<Atendimento[]>([]);
  const [setores, setSetores] = useState<Setor[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [filtroStatus, setFiltroStatus] = useState<StatusAtendimento | "">("");
  const [busca, setBusca] = useState("");
  const [atendimentoEmEdicao, setAtendimentoEmEdicao] = useState<Atendimento | null>(null);

  async function recarregar() {
    setCarregando(true);
    const dados = await listarAtendimentos({
      status: filtroStatus || undefined,
      busca: busca || undefined,
    });
    setAtendimentos(dados);
    setCarregando(false);
  }

  useEffect(() => {
    listarSetores().then(setSetores);
  }, []);

  useEffect(() => {
    recarregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroStatus]);

  async function aoBuscar(evento: React.FormEvent) {
    evento.preventDefault();
    recarregar();
  }

  async function aoSalvarAtendimento(dados: Partial<Atendimento>) {
    if (!atendimentoEmEdicao) return;
    await editarAtendimento(atendimentoEmEdicao.id, dados);
    setAtendimentoEmEdicao(null);
    recarregar();
  }

  async function aoExcluir(id: number) {
    if (!confirm("Excluir este atendimento da base? Esta ação não pode ser desfeita.")) return;
    await excluirAtendimento(id);
    recarregar();
  }

  function nomeDoSetor(idSetor: number | null): string {
    if (idSetor === null) return "-";
    return setores.find((s) => s.id === idSetor)?.nome || "-";
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-marca-escuro">Base de Atendimentos</h1>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <form onSubmit={aoBuscar} className="flex gap-2">
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome, e-mail ou telefone"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-64"
          />
          <button type="submit" className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50">
            Buscar
          </button>
        </form>

        <select
          value={filtroStatus}
          onChange={(e) => setFiltroStatus(e.target.value as StatusAtendimento | "")}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
        >
          <option value="">Todos os status</option>
          {Object.entries(RÓTULOS_DE_STATUS).map(([valor, rotulo]) => (
            <option key={valor} value={valor}>
              {rotulo}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-auto" style={{ maxHeight: "calc(100vh - 280px)" }}>
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white z-10">
            <tr className="text-left text-slate-500 border-b border-slate-100">
              <th className="p-3 whitespace-nowrap">Nome</th>
              <th className="p-3 whitespace-nowrap">E-mail</th>
              <th className="p-3 whitespace-nowrap">Telefone</th>
              <th className="p-3 whitespace-nowrap">WhatsApp</th>
              <th className="p-3 whitespace-nowrap">Setor</th>
              <th className="p-3 whitespace-nowrap">Resumo</th>
              <th className="p-3 whitespace-nowrap">Última atividade</th>
              <th className="p-3 whitespace-nowrap">Status</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr>
                <td colSpan={9} className="p-4 text-center text-slate-400">
                  Carregando...
                </td>
              </tr>
            )}
            {!carregando && atendimentos.length === 0 && (
              <tr>
                <td colSpan={9} className="p-4 text-center text-slate-400">
                  Nenhum atendimento encontrado.
                </td>
              </tr>
            )}
            {atendimentos.map((atendimento) => (
              <tr key={atendimento.id} className="border-b border-slate-50 hover:bg-slate-50">
                <td className="p-3 font-medium text-marca-escuro whitespace-nowrap">{atendimento.nome}</td>
                <td className="p-3 text-slate-500 whitespace-nowrap">{atendimento.email || "-"}</td>
                <td className="p-3 text-slate-500 whitespace-nowrap">{atendimento.telefone || "-"}</td>
                <td className="p-3 text-slate-500 whitespace-nowrap">{atendimento.whatsapp || "-"}</td>
                <td className="p-3 text-slate-500 whitespace-nowrap">{nomeDoSetor(atendimento.id_setor)}</td>
                <td className="p-3 text-slate-500 max-w-xs truncate" title={atendimento.resumo_do_atendimento || ""}>
                  {atendimento.resumo_do_atendimento || "-"}
                </td>
                <td className="p-3 text-slate-500 whitespace-nowrap">
                  {atendimento.ultima_atividade_em ? new Date(atendimento.ultima_atividade_em).toLocaleString("pt-BR") : "-"}
                </td>
                <td className="p-3 whitespace-nowrap">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${CORES_DE_STATUS[atendimento.status]}`}>
                    {RÓTULOS_DE_STATUS[atendimento.status]}
                  </span>
                  {atendimento.numero_de_reaberturas > 0 && (
                    <span
                      className="ml-1.5 px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700"
                      title={`Reaberto ${atendimento.numero_de_reaberturas}x depois de marcado resolvido — cada reabertura é um novo ciclo de custo (mensagens/tokens)`}
                    >
                      ↺ {atendimento.numero_de_reaberturas}x
                    </span>
                  )}
                </td>
                <td className="p-3 text-right whitespace-nowrap">
                  <button onClick={() => setAtendimentoEmEdicao(atendimento)} className="text-slate-400 hover:text-marca-700 mr-3">
                    Editar
                  </button>
                  <button onClick={() => aoExcluir(atendimento.id)} className="text-slate-400 hover:text-red-600">
                    Excluir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {atendimentoEmEdicao && (
        <ModalDeAtendimento
          atendimentoParaEditar={atendimentoEmEdicao}
          aoFechar={() => setAtendimentoEmEdicao(null)}
          aoSalvar={aoSalvarAtendimento}
        />
      )}
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a aba Base de Atendimentos por completo: tabela
// com filtros de status/busca (incluindo o setor de destino, resolvido a
// partir da lista carregada de /api/setores) e edição/exclusão manual.
// Sem criação, importação nem conexão com CRM — todo atendimento nasce
// sozinho na primeira mensagem recebida (ver
// backend/app/agente/orquestrador.py).
// ==============================================================================

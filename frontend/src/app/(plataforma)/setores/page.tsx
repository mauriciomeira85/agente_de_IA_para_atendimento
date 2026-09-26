"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/setores/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Setores" — NOVA neste projeto, sem equivalente no Agente
// Comercial SDR nem no Agente de Cobrança. É aqui que a empresa cadastra
// os departamentos humanos (ex.: Vendas, Financeiro, Suporte Técnico),
// cada um com seu próprio contato de WhatsApp — a lista real de destinos
// que a ferramenta encaminhar_para_setor (agente do backend) usa para
// decidir para onde rotear um atendimento, e que o guardrail
// (backend/app/agente/guardrails_de_atendimento.py) confere para garantir
// que o modelo nunca "invente" um setor que a empresa não cadastrou.
//
// Substitui o bloco "Desfecho da Venda" que o Agente Comercial SDR e o
// Agente de Cobrança têm na aba Configuração do Agente: lá a empresa
// configura UM destino fixo para todos os casos; aqui ela cadastra quantos
// setores quiser, e o próprio agente decide, atendimento por atendimento,
// qual é o certo.
// ==============================================================================

import { useEffect, useState } from "react";
import { cadastrarSetor, editarSetor, listarSetores, removerSetor } from "@/biblioteca/api";
import type { Setor } from "@/biblioteca/tipos";

const campo = "w-full rounded-lg border border-slate-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600";

export default function PaginaDeSetores() {
  const [setores, setSetores] = useState<Setor[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [setorEmEdicao, setSetorEmEdicao] = useState<Setor | null | undefined>(undefined);

  async function recarregar() {
    setCarregando(true);
    setSetores(await listarSetores());
    setCarregando(false);
  }

  useEffect(() => {
    recarregar();
  }, []);

  async function aoSalvar(dados: { nome: string; contato_nome: string; contato_telefone: string }) {
    if (setorEmEdicao) {
      await editarSetor(setorEmEdicao.id, dados);
    } else {
      await cadastrarSetor(dados);
    }
    setSetorEmEdicao(undefined);
    recarregar();
  }

  async function aoRemover(id: number) {
    if (!confirm("Remover este setor? Atendimentos já encaminhados para ele mantêm o histórico.")) return;
    await removerSetor(id);
    recarregar();
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-marca-escuro">Setores</h1>
          <p className="text-sm text-slate-500 mt-1">
            Os departamentos humanos para onde o agente pode encaminhar um atendimento.
          </p>
        </div>
        <button
          onClick={() => setSetorEmEdicao(null)}
          className="px-3 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700"
        >
          Novo setor
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100">
        {carregando && <p className="p-4 text-sm text-slate-400">Carregando...</p>}
        {!carregando && setores.length === 0 && (
          <p className="p-4 text-sm text-slate-400">Nenhum setor cadastrado ainda. Cadastre pelo menos um para o agente poder encaminhar atendimentos.</p>
        )}
        {setores.map((setor) => (
          <div key={setor.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <p className="text-sm font-medium text-marca-escuro">{setor.nome}</p>
              <p className="text-xs text-slate-400">
                {setor.contato_nome} — {setor.contato_telefone}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => setSetorEmEdicao(setor)} className="text-xs text-slate-400 hover:text-marca-700">
                Editar
              </button>
              <button onClick={() => aoRemover(setor.id)} className="text-xs text-slate-400 hover:text-red-600">
                Remover
              </button>
            </div>
          </div>
        ))}
      </div>

      {setorEmEdicao !== undefined && (
        <ModalDeSetor setorParaEditar={setorEmEdicao} aoFechar={() => setSetorEmEdicao(undefined)} aoSalvar={aoSalvar} />
      )}
    </div>
  );
}

/** Janela (modal) usada para cadastrar um novo setor ou editar um já existente. */
function ModalDeSetor({
  setorParaEditar,
  aoFechar,
  aoSalvar,
}: {
  setorParaEditar: Setor | null;
  aoFechar: () => void;
  aoSalvar: (dados: { nome: string; contato_nome: string; contato_telefone: string }) => Promise<void>;
}) {
  const [nome, setNome] = useState(setorParaEditar?.nome || "");
  const [contatoNome, setContatoNome] = useState(setorParaEditar?.contato_nome || "");
  const [contatoTelefone, setContatoTelefone] = useState(setorParaEditar?.contato_telefone || "");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function aoSubmeter(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setSalvando(true);
    try {
      await aoSalvar({ nome, contato_nome: contatoNome, contato_telefone: contatoTelefone });
    } catch (falha) {
      // O backend valida o WhatsApp de quem recebe (DDD + número) — mostra o motivo em vez de falhar em silêncio.
      setErro(falha instanceof Error ? falha.message : "Não foi possível salvar o setor.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md p-6">
        <h2 className="text-lg font-semibold text-marca-escuro mb-4">
          {setorParaEditar ? "Editar setor" : "Novo setor"}
        </h2>
        <form onSubmit={aoSubmeter} className="space-y-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Nome do setor</label>
            <input required value={nome} onChange={(e) => setNome(e.target.value)} className={campo} placeholder="Ex.: Vendas, Financeiro, Suporte Técnico" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Nome de quem recebe</label>
            <input required value={contatoNome} onChange={(e) => setContatoNome(e.target.value)} className={campo} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">WhatsApp de quem recebe</label>
            <input
              required
              value={contatoTelefone}
              onChange={(e) => setContatoTelefone(e.target.value)}
              className={campo}
              placeholder="5511999999999"
            />
          </div>

          {erro && (
            <p className="text-sm bg-red-50 text-red-700 border border-red-200 rounded-lg px-3 py-2">{erro}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={aoFechar} className="px-4 py-2 text-sm text-slate-600 hover:text-marca-700">
              Cancelar
            </button>
            <button
              type="submit"
              disabled={salvando}
              className="px-4 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700 disabled:opacity-60"
            >
              {salvando ? "Salvando..." : "Salvar"}
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
// Este arquivo implementa o CRUD completo da aba Setores: listar,
// cadastrar, editar e remover — a lista real de destinos de encaminhamento
// que o agente usa e que o guardrail confere antes de agir.
// ==============================================================================

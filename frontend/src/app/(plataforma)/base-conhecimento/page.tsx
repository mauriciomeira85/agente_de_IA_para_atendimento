"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/base-conhecimento/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Base de Conhecimento" — NOVA neste projeto, a peça
// tecnicamente mais nova de toda a linhagem SDR → Cobrança → Atendimento.
// É aqui que a empresa cadastra os itens (FAQ, políticas de atendimento,
// descrição de produtos/serviços) que o agente consulta para responder
// dúvidas dos clientes — ver
// backend/app/agente/ferramentas.py:_ferramenta_consultar_base_de_conhecimento.
//
// Ao salvar um item, o backend gera automaticamente um "embedding" (um
// vetor que representa o SIGNIFICADO do texto, via Together AI) e o usa
// para busca por similaridade (pgvector) — nada disso aparece aqui, é um
// detalhe interno; esta tela só lida com título e conteúdo em texto
// livre, exatamente como a empresa os escreve.
// ==============================================================================

import { useEffect, useState } from "react";
import {
  cadastrarItemDeConhecimento,
  editarItemDeConhecimento,
  listarItensDeConhecimento,
  removerItemDeConhecimento,
} from "@/biblioteca/api";
import type { ItemDeConhecimento } from "@/biblioteca/tipos";

const campo = "w-full rounded-lg border border-slate-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600";

export default function PaginaDeBaseDeConhecimento() {
  const [itens, setItens] = useState<ItemDeConhecimento[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [itemEmEdicao, setItemEmEdicao] = useState<ItemDeConhecimento | null | undefined>(undefined);

  async function recarregar() {
    setCarregando(true);
    setItens(await listarItensDeConhecimento());
    setCarregando(false);
  }

  useEffect(() => {
    recarregar();
  }, []);

  async function aoSalvar(dados: { titulo: string; conteudo: string }) {
    if (itemEmEdicao) {
      await editarItemDeConhecimento(itemEmEdicao.id, dados);
    } else {
      await cadastrarItemDeConhecimento(dados);
    }
    setItemEmEdicao(undefined);
    recarregar();
  }

  async function aoRemover(id: number) {
    if (!confirm("Remover este item da Base de Conhecimento?")) return;
    await removerItemDeConhecimento(id);
    recarregar();
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-marca-escuro">Base de Conhecimento</h1>
          <p className="text-sm text-slate-500 mt-1">
            FAQ, políticas de atendimento e descrição de produtos/serviços que o agente consulta para responder.
          </p>
        </div>
        <button
          onClick={() => setItemEmEdicao(null)}
          className="px-3 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700"
        >
          Novo item
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100">
        {carregando && <p className="p-4 text-sm text-slate-400">Carregando...</p>}
        {!carregando && itens.length === 0 && (
          <p className="p-4 text-sm text-slate-400">
            Nenhum item cadastrado ainda. Sem itens aqui, o agente não tem de onde tirar respostas sobre a empresa.
          </p>
        )}
        {itens.map((item) => (
          <div key={item.id} className="flex items-start justify-between gap-4 px-4 py-3">
            <div className="min-w-0">
              <p className="text-sm font-medium text-marca-escuro">{item.titulo}</p>
              <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{item.conteudo}</p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <button onClick={() => setItemEmEdicao(item)} className="text-xs text-slate-400 hover:text-marca-700">
                Editar
              </button>
              <button onClick={() => aoRemover(item.id)} className="text-xs text-slate-400 hover:text-red-600">
                Remover
              </button>
            </div>
          </div>
        ))}
      </div>

      {itemEmEdicao !== undefined && (
        <ModalDeItem itemParaEditar={itemEmEdicao} aoFechar={() => setItemEmEdicao(undefined)} aoSalvar={aoSalvar} />
      )}
    </div>
  );
}

/** Janela (modal) usada para cadastrar um novo item ou editar um já existente. */
function ModalDeItem({
  itemParaEditar,
  aoFechar,
  aoSalvar,
}: {
  itemParaEditar: ItemDeConhecimento | null;
  aoFechar: () => void;
  aoSalvar: (dados: { titulo: string; conteudo: string }) => Promise<void>;
}) {
  const [titulo, setTitulo] = useState(itemParaEditar?.titulo || "");
  const [conteudo, setConteudo] = useState(itemParaEditar?.conteudo || "");
  const [salvando, setSalvando] = useState(false);

  async function aoSubmeter(evento: React.FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    try {
      await aoSalvar({ titulo, conteudo });
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-lg p-6">
        <h2 className="text-lg font-semibold text-marca-escuro mb-4">
          {itemParaEditar ? "Editar item" : "Novo item"}
        </h2>
        <form onSubmit={aoSubmeter} className="space-y-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Título</label>
            <input
              required
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              className={campo}
              placeholder="Ex.: Política de troca e devolução"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Conteúdo</label>
            <textarea
              required
              value={conteudo}
              onChange={(e) => setConteudo(e.target.value)}
              className={campo}
              rows={8}
              placeholder="Descreva o conteúdo completo — quanto mais claro e específico, melhor a resposta do agente."
            />
          </div>

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
// Este arquivo implementa o CRUD completo da aba Base de Conhecimento:
// listar, cadastrar, editar e remover itens de título + conteúdo em texto
// livre — o embedding usado na busca por similaridade é gerado e
// gravado pelo backend, nunca manipulado aqui.
// ==============================================================================

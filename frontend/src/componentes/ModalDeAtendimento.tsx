"use client";

// ==============================================================================
// ARQUIVO: componentes/ModalDeAtendimento.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Janela (modal) usada para EDITAR os dados cadastrais de um atendimento
// já existente na Base de Atendimentos (ex.: corrigir um nome ou e-mail
// digitado errado). Diferente do ModalDeLead do Agente Comercial SDR, não
// existe modo de CRIAÇÃO aqui — um Atendimento só nasce de um jeito,
// automaticamente, na primeira mensagem recebida de um cliente (ver
// Informacoes/Arquitetura.md, seção 2) — e sem os campos de
// redes sociais/localização, que não existem neste domínio simplificado.
// ==============================================================================

import { useState } from "react";
import type { Atendimento } from "@/biblioteca/tipos";

interface Propriedades {
  atendimentoParaEditar: Atendimento;
  aoFechar: () => void;
  aoSalvar: (dados: Partial<Atendimento>) => Promise<void>;
}

export default function ModalDeAtendimento({ atendimentoParaEditar, aoFechar, aoSalvar }: Propriedades) {
  const [nome, setNome] = useState(atendimentoParaEditar.nome);
  const [email, setEmail] = useState(atendimentoParaEditar.email || "");
  const [telefone, setTelefone] = useState(atendimentoParaEditar.telefone || "");
  const [whatsapp, setWhatsapp] = useState(atendimentoParaEditar.whatsapp || "");
  const [salvando, setSalvando] = useState(false);

  async function aoSubmeter(evento: React.FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    try {
      await aoSalvar({
        nome,
        email: email || null,
        telefone: telefone || null,
        whatsapp: whatsapp || null,
      });
    } finally {
      setSalvando(false);
    }
  }

  const campo = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600";

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md p-6">
        <h2 className="text-lg font-semibold text-marca-escuro mb-4">Editar atendimento</h2>
        <form onSubmit={aoSubmeter} className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="block text-xs text-slate-500 mb-1">Nome</label>
            <input required value={nome} onChange={(e) => setNome(e.target.value)} className={campo} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">E-mail</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} className={campo} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Telefone</label>
            <input value={telefone} onChange={(e) => setTelefone(e.target.value)} className={campo} />
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-slate-500 mb-1">WhatsApp</label>
            <input value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} className={campo} placeholder="5511999999999" />
          </div>

          <div className="col-span-2 flex justify-end gap-2 mt-2">
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
// Este componente é o formulário (em modal) de correção manual de um
// atendimento já existente. Recebe o atendimento a editar e devolve os
// dados preenchidos através da função aoSalvar, passada pela página que o
// abriu — sem modo de criação, sem campos de redes sociais/localização.
// ==============================================================================

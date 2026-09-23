"use client";

// ==============================================================================
// ARQUIVO: componentes/CampoDeTags.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Componente de seleção múltipla simples: a pessoa digita um valor
// (ex.: o nome de um país ou de um município) e aperta Enter (ou clica em
// "Adicionar") para incluí-lo em uma lista de "etiquetas" (tags), cada
// uma removível com um clique no "x". É usado no bloco "Área de Atuação"
// da Configuração do Agente, tanto para Países quanto para Municípios —
// listas grandes e variáveis demais para virarem uma lista fixa de
// caixinhas de seleção (isso é feito para Estados, que têm uma lista fixa
// de 27 opções — ver componentes/SeletorDeEstados.tsx).
// ==============================================================================

import { useState } from "react";

interface Propriedades {
  rotulo: string;
  marcadorDeExemplo: string;
  valores: string[];
  aoAlterar: (novosValores: string[]) => void;
}

export default function CampoDeTags({ rotulo, marcadorDeExemplo, valores, aoAlterar }: Propriedades) {
  const [valorDigitado, setValorDigitado] = useState("");

  function adicionar() {
    const valorLimpo = valorDigitado.trim();
    if (valorLimpo && !valores.includes(valorLimpo)) {
      aoAlterar([...valores, valorLimpo]);
    }
    setValorDigitado("");
  }

  function remover(valor: string) {
    aoAlterar(valores.filter((v) => v !== valor));
  }

  return (
    <div>
      <label className="block text-xs text-slate-500 mb-1">{rotulo}</label>
      <div className="flex gap-2">
        <input
          value={valorDigitado}
          onChange={(e) => setValorDigitado(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              adicionar();
            }
          }}
          placeholder={marcadorDeExemplo}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={adicionar}
          className="px-3 py-2 text-sm rounded-lg border border-slate-300 hover:bg-slate-50"
        >
          Adicionar
        </button>
      </div>
      {valores.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {valores.map((valor) => (
            <span
              key={valor}
              className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 text-xs px-2 py-1 rounded-full"
            >
              {valor}
              <button type="button" onClick={() => remover(valor)} className="text-slate-400 hover:text-marca-700">
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este componente implementa um campo de "várias etiquetas": digitar +
// Enter adiciona um valor à lista, e cada etiqueta pode ser removida
// individualmente. Usado para Países e Municípios na Área de Atuação.
// ==============================================================================

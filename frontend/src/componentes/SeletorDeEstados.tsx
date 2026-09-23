"use client";

// ==============================================================================
// ARQUIVO: componentes/SeletorDeEstados.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Componente de seleção múltipla dos 27 estados brasileiros (as 26
// unidades federativas + o Distrito Federal), cada um com sua própria
// caixinha de seleção (checkbox) — exatamente como pedido para o bloco
// "Área de Atuação" da Configuração do Agente. Como a lista de estados é
// fixa e pequena, faz sentido mostrá-la inteira, ao contrário de Países e
// Municípios (listas grandes demais — ver componentes/CampoDeTags.tsx).
// ==============================================================================

const ESTADOS_BRASILEIROS = [
  "Acre", "Alagoas", "Amapá", "Amazonas", "Bahia", "Ceará", "Distrito Federal",
  "Espírito Santo", "Goiás", "Maranhão", "Mato Grosso", "Mato Grosso do Sul",
  "Minas Gerais", "Pará", "Paraíba", "Paraná", "Pernambuco", "Piauí",
  "Rio de Janeiro", "Rio Grande do Norte", "Rio Grande do Sul", "Rondônia",
  "Roraima", "Santa Catarina", "São Paulo", "Sergipe", "Tocantins",
];

interface Propriedades {
  selecionados: string[];
  aoAlterar: (novosSelecionados: string[]) => void;
}

export default function SeletorDeEstados({ selecionados, aoAlterar }: Propriedades) {
  function alternar(estado: string) {
    if (selecionados.includes(estado)) {
      aoAlterar(selecionados.filter((e) => e !== estado));
    } else {
      aoAlterar([...selecionados, estado]);
    }
  }

  return (
    <div>
      <label className="block text-xs text-slate-500 mb-2">Estados atendidos</label>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-48 overflow-y-auto border border-slate-200 rounded-lg p-3">
        {ESTADOS_BRASILEIROS.map((estado) => (
          <label key={estado} className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={selecionados.includes(estado)} onChange={() => alternar(estado)} />
            {estado}
          </label>
        ))}
      </div>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este componente mostra os 27 estados brasileiros como caixinhas de
// seleção independentes, permitindo marcar quantos a empresa atender.
// ==============================================================================

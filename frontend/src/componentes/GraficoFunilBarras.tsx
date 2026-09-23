// ==============================================================================
// ARQUIVO: componentes/GraficoFunilBarras.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Gráfico de barras HORIZONTAIS do funil de atendimento (Atendimentos ->
// Finalizados -> Resolvidos sem humano — ver backend/app/esquemas/painel.py):
// cada etapa vira uma barra, com o rótulo à esquerda e o comprimento
// proporcional à quantidade — substitui o gráfico de pirâmide anterior
// (GraficoFunilPiramide, removido), a pedido do usuário.
//
// O desenho é feito com SVG puro (sem depender de biblioteca externa de
// gráficos), mesma escolha do componente anterior.
// ==============================================================================

import type { EtapaDoFunil } from "@/biblioteca/tipos";

interface Propriedades {
  etapas: EtapaDoFunil[];
}

const CORES = ["#171a33", "#333999", "#5560d9", "#7b85e8", "#a5abef"];

export default function GraficoFunilBarras({ etapas }: Propriedades) {
  const larguraTotal = 560;
  const alturaDeCadaBarra = 36;
  const espacamento = 22;
  const larguraDoRotulo = 168;
  const larguraMaximaDaBarra = larguraTotal - larguraDoRotulo - 48;
  const maiorQuantidade = Math.max(...etapas.map((e) => e.quantidade), 1);

  return (
    <svg
      viewBox={`0 0 ${larguraTotal} ${(alturaDeCadaBarra + espacamento) * etapas.length}`}
      width="100%"
      role="img"
      aria-label="Gráfico de barras horizontais do funil de atendimento"
    >
      {etapas.map((etapa, indice) => {
        const proporcao = etapa.quantidade / maiorQuantidade;
        const largura = Math.max(larguraMaximaDaBarra * proporcao, 4);
        const y = indice * (alturaDeCadaBarra + espacamento);

        return (
          <g key={etapa.etapa}>
            <text
              x={larguraDoRotulo - 12}
              y={y + alturaDeCadaBarra / 2 + 4}
              textAnchor="end"
              fill="#334155"
              fontSize="13"
              fontWeight={600}
            >
              {etapa.etapa}
            </text>
            <rect
              x={larguraDoRotulo}
              y={y}
              width={largura}
              height={alturaDeCadaBarra}
              rx={6}
              fill={CORES[indice % CORES.length]}
            />
            <text
              x={larguraDoRotulo + largura + 8}
              y={y + alturaDeCadaBarra / 2 + 4}
              textAnchor="start"
              fill="#171a33"
              fontSize="13"
              fontWeight={700}
            >
              {etapa.quantidade}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este componente recebe a lista de etapas do funil (nome + quantidade, já
// calculada pelo backend) e desenha, em SVG, uma barra horizontal por
// etapa — rótulo à esquerda, comprimento proporcional à quantidade,
// valor numérico ao final da barra.
// ==============================================================================

// ==============================================================================
// ARQUIVO: componentes/GraficoVolumePorDia.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Gráfico de barras VERTICAIS mostrando quantos atendimentos novos
// chegaram por dia — o gráfico mais comum em dashboards de atendimento
// (Octadesk, Zenvia, Intercom etc.), mostra tendência de crescimento/
// queda e picos de volume. Cobre os últimos 14 dias por padrão, ou o
// período escolhido no filtro do Dashboard (ver backend/app/rotas/
// painel.py, até NUMERO_MAXIMO_DE_DIAS_NO_GRAFICO_COM_PERIODO dias).
//
// Cada barra tem LARGURA FIXA (não divide o espaço disponível pelo
// número de dias) — com um período longo (30/60 dias), espremer tudo na
// largura do cartão deixaria cada barra ilegível. Em vez disso, o SVG
// cresce (largura = quantidade de dias x largura da barra) e fica dentro
// de um contêiner com rolagem horizontal — o usuário arrasta/rola pra
// ver os dias mais antigos, os mais recentes já aparecem visíveis.
//
// Mesma escolha dos outros gráficos do Dashboard: SVG puro, sem depender
// de biblioteca externa.
// ==============================================================================

import type { PontoDeVolumePorDia } from "@/biblioteca/tipos";

interface Propriedades {
  pontos: PontoDeVolumePorDia[];
}

/** "2026-09-22" -> "22/09" — rótulo curto o bastante pra caber embaixo de cada barra. */
function formatarDataCurta(data: string): string {
  const [, mes, dia] = data.split("-");
  return `${dia}/${mes}`;
}

const LARGURA_FIXA_DA_BARRA = 28;
const ESPACO_ENTRE_BARRAS = 10;
const ALTURA_DO_GRAFICO = 160;
const ALTURA_TOTAL = ALTURA_DO_GRAFICO + 28;

export default function GraficoVolumePorDia({ pontos }: Propriedades) {
  const larguraDoSvg = Math.max(pontos.length * (LARGURA_FIXA_DA_BARRA + ESPACO_ENTRE_BARRAS), 1);
  const maiorQuantidade = Math.max(...pontos.map((p) => p.quantidade), 1);

  return (
    <div className="overflow-x-auto">
      <svg
        width={larguraDoSvg}
        height={ALTURA_TOTAL}
        viewBox={`0 0 ${larguraDoSvg} ${ALTURA_TOTAL}`}
        role="img"
        aria-label="Gráfico de volume de atendimentos por dia, role para o lado para ver mais dias"
        className="block"
      >
        {pontos.map((ponto, indice) => {
          const alturaDaBarra = Math.max(
            (ponto.quantidade / maiorQuantidade) * (ALTURA_DO_GRAFICO - 20),
            ponto.quantidade > 0 ? 4 : 0
          );
          const x = indice * (LARGURA_FIXA_DA_BARRA + ESPACO_ENTRE_BARRAS);
          const y = ALTURA_DO_GRAFICO - alturaDaBarra;

          return (
            <g key={ponto.data}>
              {ponto.quantidade > 0 && (
                <text x={x + LARGURA_FIXA_DA_BARRA / 2} y={y - 4} textAnchor="middle" fill="#171a33" fontSize="10" fontWeight={700}>
                  {ponto.quantidade}
                </text>
              )}
              <rect x={x} y={y} width={LARGURA_FIXA_DA_BARRA} height={alturaDaBarra} rx={3} fill="#5560d9" />
              <text
                x={x + LARGURA_FIXA_DA_BARRA / 2}
                y={ALTURA_DO_GRAFICO + 16}
                textAnchor="middle"
                fill="#64748b"
                fontSize="9"
                transform={`rotate(-40 ${x + LARGURA_FIXA_DA_BARRA / 2} ${ALTURA_DO_GRAFICO + 16})`}
              >
                {formatarDataCurta(ponto.data)}
              </text>
            </g>
          );
        })}
        <line x1={0} y1={ALTURA_DO_GRAFICO} x2={larguraDoSvg} y2={ALTURA_DO_GRAFICO} stroke="#e2e8f0" strokeWidth={1} />
      </svg>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Recebe a série de pontos (data + quantidade, já calculada pelo backend)
// e desenha, em SVG de largura fixa por barra (não elástica), uma barra
// vertical por dia, com o valor acima da barra (quando > 0) e a data
// (dia/mês, rotacionada) abaixo do eixo — dentro de um contêiner com
// rolagem horizontal, pra continuar legível mesmo com muitos dias.
// ==============================================================================

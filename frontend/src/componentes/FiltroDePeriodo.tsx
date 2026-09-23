// ==============================================================================
// ARQUIVO: componentes/FiltroDePeriodo.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Filtro de período do Dashboard: atalhos rápidos (Hoje, 7 dias, 30 dias,
// Tudo) mais um intervalo personalizado (dois campos de data nativos do
// navegador, sem biblioteca externa). Este componente só sabe "qual
// período está selecionado" e avisa o pai (app/(plataforma)/painel/
// page.tsx) quando muda — quem decide o que cada cartão faz com essas
// datas é o backend (ver rotas/painel.py, INTRODUÇÃO: cada grupo de
// cartão usa a data — criação ou desfecho — que faz sentido pra ele).
// ==============================================================================

interface PeriodoSelecionado {
  dataInicio?: string;
  dataFim?: string;
}

interface Propriedades {
  periodo: PeriodoSelecionado;
  aoMudar: (periodo: PeriodoSelecionado) => void;
}

function formatarData(data: Date): string {
  return data.toISOString().slice(0, 10);
}

function calcularAtalho(diasAtras: number): PeriodoSelecionado {
  const hoje = new Date();
  const inicio = new Date(hoje);
  inicio.setDate(hoje.getDate() - diasAtras);
  return { dataInicio: formatarData(inicio), dataFim: formatarData(hoje) };
}

const ATALHOS: { rotulo: string; periodo: PeriodoSelecionado }[] = [
  { rotulo: "Hoje", periodo: calcularAtalho(0) },
  { rotulo: "7 dias", periodo: calcularAtalho(6) },
  { rotulo: "30 dias", periodo: calcularAtalho(29) },
  { rotulo: "Tudo", periodo: {} },
];

export default function FiltroDePeriodo({ periodo, aoMudar }: Propriedades) {
  const atalhoAtivo = ATALHOS.find(
    (atalho) => atalho.periodo.dataInicio === periodo.dataInicio && atalho.periodo.dataFim === periodo.dataFim
  );

  return (
    <div className="flex flex-wrap items-center gap-2 mb-6">
      {ATALHOS.map((atalho) => (
        <button
          key={atalho.rotulo}
          type="button"
          onClick={() => aoMudar(atalho.periodo)}
          className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
            atalho === atalhoAtivo
              ? "bg-marca-600 text-white border-marca-600"
              : "bg-white text-slate-600 border-slate-200 hover:border-marca-300"
          }`}
        >
          {atalho.rotulo}
        </button>
      ))}

      <div className="flex items-center gap-1.5 ml-1">
        <input
          type="date"
          value={periodo.dataInicio ?? ""}
          max={periodo.dataFim || undefined}
          onChange={(evento) => aoMudar({ ...periodo, dataInicio: evento.target.value || undefined })}
          className="text-sm border border-slate-200 rounded-lg px-2 py-1.5 text-slate-700"
          aria-label="Início do período"
        />
        <span className="text-slate-400 text-sm">até</span>
        <input
          type="date"
          value={periodo.dataFim ?? ""}
          min={periodo.dataInicio || undefined}
          onChange={(evento) => aoMudar({ ...periodo, dataFim: evento.target.value || undefined })}
          className="text-sm border border-slate-200 rounded-lg px-2 py-1.5 text-slate-700"
          aria-label="Fim do período"
        />
      </div>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Renderiza os atalhos de período (Hoje/7 dias/30 dias/Tudo) e um
// intervalo personalizado (dois <input type="date">). Não busca nem
// calcula nada do Dashboard em si — só controla o par
// dataInicio/dataFim e avisa o componente pai via `aoMudar`.
// ==============================================================================

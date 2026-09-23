"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/painel/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Dashboard": a primeira coisa que a empresa vê ao entrar
// na plataforma. Mostra um filtro de período (FiltroDePeriodo), duas
// fileiras de cartões (quantidades e taxas), dois gráficos de barras
// horizontais lado a lado (Volume e Desfechos — um termina em
// Encaminhados, o outro em Resolvidos sem humano), o gráfico de volume
// de atendimentos por dia e, quando houver dados, o ranking de setores
// mais acionados. Todos os números vêm prontos do backend (rota GET
// /api/painel, que recebe data_inicio/data_fim opcionais) — esta página
// só busca (de novo, a cada troca de período) e exibe, sem calcular nada
// sozinha.
//
// Diferente dos outros dois projetos da linhagem, o status de um
// Atendimento não é uma cadeia linear — ele termina em ENCAMINHADO OU
// RESOLVIDO (nunca os dois — ver backend/app/esquemas/painel.py). Por
// isso NÃO existe um único "funil": são dois gráficos de barras
// independentes, compartilhando a mesma base (Atendimentos / Em
// atendimento), cada um terminando num desfecho diferente — pensados
// pra comparar lado a lado quanto a IA resolveu sozinha versus quanto
// precisou de um humano.
// ==============================================================================

import { useEffect, useState } from "react";
import { obterPainel } from "@/biblioteca/api";
import type { PainelDados } from "@/biblioteca/tipos";
import Cartao from "@/componentes/Cartao";
import FiltroDePeriodo from "@/componentes/FiltroDePeriodo";
import GraficoFunilBarras from "@/componentes/GraficoFunilBarras";
import GraficoVolumePorDia from "@/componentes/GraficoVolumePorDia";

interface PeriodoSelecionado {
  dataInicio?: string;
  dataFim?: string;
}

export default function PaginaDoPainel() {
  const [dados, setDados] = useState<PainelDados | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [periodo, setPeriodo] = useState<PeriodoSelecionado>({});

  useEffect(() => {
    setCarregando(true);
    obterPainel(periodo)
      .then(setDados)
      .finally(() => setCarregando(false));
  }, [periodo]);

  if (carregando && !dados) return <p className="text-sm text-slate-500">Carregando painel...</p>;
  if (!dados) return <p className="text-sm text-red-600">Não foi possível carregar o painel.</p>;

  const { cartoes_de_quantidade, cartoes_de_taxa, funil_de_encaminhamento, funil_de_resolucao, volume_por_dia, setores_mais_acionados } =
    dados;

  return (
    <div>
      <h1 className="text-2xl font-semibold text-marca-escuro mb-1">Dashboard</h1>
      <p className="text-sm text-slate-500 mb-4">
        &ldquo;Total&rdquo; e &ldquo;Em atendimento&rdquo; contam pela data em que a conversa começou; &ldquo;Encaminhados&rdquo; e
        &ldquo;Resolvidos&rdquo; contam pela data em que o atendimento terminou — os dois podem incluir atendimentos que começaram
        fora do período escolhido.
      </p>
      <FiltroDePeriodo periodo={periodo} aoMudar={setPeriodo} />

      {/* Primeira fileira: cartões de quantidade absoluta */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <Cartao rotulo="Total de atendimentos" valor={String(cartoes_de_quantidade.total_de_atendimentos)} />
        <Cartao rotulo="Em atendimento" valor={String(cartoes_de_quantidade.em_atendimento)} />
        <Cartao rotulo="Encaminhados" valor={String(cartoes_de_quantidade.encaminhados)} />
        <Cartao rotulo="Resolvidos sem humano" valor={String(cartoes_de_quantidade.resolvidos)} destaque="positivo" />
      </div>

      {/* Segunda fileira: cartões de taxa percentual */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-10 max-w-2xl">
        <Cartao rotulo="Taxa de encaminhamento" valor={`${cartoes_de_taxa.taxa_de_encaminhamento}%`} />
        <Cartao rotulo="Taxa de resolução automática" valor={`${cartoes_de_taxa.taxa_de_resolucao_automatica}%`} destaque="positivo" />
        <Cartao rotulo="Taxa de reabertura" valor={`${cartoes_de_taxa.taxa_de_reabertura}%`} destaque="negativo" />
      </div>

      {/* Dois gráficos de barras horizontais, lado a lado: mesma base
          (Atendimentos / Em atendimento), terceiro degrau diferente. */}
      <div className="grid md:grid-cols-2 gap-6 mb-10">
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-bold text-black mb-4 text-center">Volume e Encaminhamentos</h2>
          <GraficoFunilBarras etapas={funil_de_encaminhamento} />
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-bold text-black mb-4 text-center">Volume e Resoluções</h2>
          <GraficoFunilBarras etapas={funil_de_resolucao} />
        </div>
      </div>

      {/* Volume de atendimentos por dia (últimos 14 dias) */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 mb-10">
        <h2 className="text-lg font-bold text-black mb-4 text-center">Volume de Atendimentos por Dia</h2>
        <GraficoVolumePorDia pontos={volume_por_dia} />
      </div>

      {/* Setores mais acionados — só aparece quando já existe pelo menos
          1 encaminhamento; um setor cadastrado mas nunca usado não gera
          um gráfico vazio. */}
      {setores_mais_acionados.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 max-w-xl mx-auto">
          <h2 className="text-lg font-bold text-black mb-4 text-center">Setores Mais Acionados</h2>
          <GraficoFunilBarras etapas={setores_mais_acionados} />
        </div>
      )}
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a aba Dashboard: mantém o estado do período
// selecionado (FiltroDePeriodo), busca os dados prontos da rota
// /api/painel pra esse período e os distribui entre os cartões de
// quantidade (4), os cartões de taxa (3: encaminhamento, resolução
// automática, reabertura), os dois gráficos de barras horizontais lado a
// lado (encaminhamento e resolução), o gráfico de volume por dia e,
// quando houver dados, o ranking de setores mais acionados.
// ==============================================================================

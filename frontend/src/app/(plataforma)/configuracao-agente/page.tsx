"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/configuracao-agente/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Configuração do Agente" — o formulário que molda como o
// agente se apresenta e se comporta. Tudo que é salvo aqui é lido pelo
// backend a cada mensagem recebida no WhatsApp (ver
// backend/app/agente/orquestrador.py).
//
// Versão bem mais simples, para o Agente de Atendimento, do que a mesma
// aba nos outros dois projetos da linhagem: SEM bloco de "Desfecho da
// Venda" (o destino de um atendimento é dinâmico, por Setor — cadastrado
// na aba própria "Setores") e SEM follow-up/critérios de qualificação
// (este agente é receptivo, nunca inicia contato). No lugar entra o bloco
// "Regras de Atendimento": o guardrail que trava a FONTE das respostas do
// agente (ver Informacoes/Arquitetura.md, seção 4.3). Os detalhes de
// produto/política em si não ficam aqui — ficam na aba "Base de
// Conhecimento"; este formulário só cobre a apresentação geral da
// empresa e como o agente deve se comportar.
//
// Os QUATRO templates Meta deste projeto (notificação, reencaminhamento,
// atenção, reengajamento) ficam na aba "Canais", junto com a conexão do
// WhatsApp — não aqui.
// ==============================================================================

import { useEffect, useState } from "react";
import { obterConfiguracaoDoAgente, salvarConfiguracaoDoAgente } from "@/biblioteca/api";
import type { ConfiguracaoAgente } from "@/biblioteca/tipos";
import CampoDeTags from "@/componentes/CampoDeTags";
import SeletorDeEstados from "@/componentes/SeletorDeEstados";

const CONFIGURACAO_VAZIA: ConfiguracaoAgente = {
  nome_do_agente: "",
  contexto_da_empresa: "",
  area_atuacao: { paises: [], estados: [], municipios: [] },
  endereco_cep: "",
  endereco_rua: "",
  endereco_bairro: "",
  endereco_numero: "",
  endereco_complemento: "",
  endereco_detalhes_adicionais: "",
  nome_do_template_encaminhamento: "notificacao_atendimento_padrao",
  nome_do_template_reengajamento: "reengajamento_padrao",
  nome_do_template_reencaminhamento: "reencaminhamento_atendimento_padrao",
  nome_do_template_atencao: "atencao_manipulacao_padrao",
  roteiro_conversa: "",
  responder_apenas_com_base_no_conhecimento: true,
  mensagem_fora_do_escopo: "Não tenho essa informação no momento, mas vou encaminhar sua dúvida para o setor responsável.",
};

const campo = "w-full rounded-lg border border-slate-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600";
const rotuloDaSecao = "text-base font-semibold text-marca-escuro";

export default function PaginaDeConfiguracaoDoAgente() {
  const [dados, setDados] = useState<ConfiguracaoAgente>(CONFIGURACAO_VAZIA);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);

  useEffect(() => {
    obterConfiguracaoDoAgente()
      .then(setDados)
      .finally(() => setCarregando(false));
  }, []);

  function atualizar<K extends keyof ConfiguracaoAgente>(campo: K, valor: ConfiguracaoAgente[K]) {
    setDados((atual) => ({ ...atual, [campo]: valor }));
  }

  async function aoSalvar(evento: React.FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    setMensagem(null);
    try {
      const salvo = await salvarConfiguracaoDoAgente(dados);
      setDados(salvo);
      setMensagem("Configuração salva. O agente já está usando essas informações nas próximas conversas.");
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) return <p className="text-sm text-slate-500">Carregando configuração...</p>;

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold text-marca-escuro mb-6">Configurações do Agente</h1>

      <form onSubmit={aoSalvar} className="space-y-10">
        {/* --- Bloco 1: Perfil da Empresa --- */}
        <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
          <h2 className={rotuloDaSecao}>Perfil da Empresa</h2>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Nome do Agente</label>
            <input
              required
              value={dados.nome_do_agente}
              onChange={(e) => atualizar("nome_do_agente", e.target.value)}
              className={campo}
              placeholder="Ex.: Sofia"
            />
            <p className="text-xs text-slate-400 mt-1">Esse nome aparece para o cliente quando o agente responde no WhatsApp.</p>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Contexto da Empresa</label>
            <textarea
              value={dados.contexto_da_empresa}
              onChange={(e) => atualizar("contexto_da_empresa", e.target.value)}
              className={campo}
              rows={6}
              placeholder="Quem é a empresa, o que ela faz, em poucas linhas — os detalhes de produtos/políticas específicos ficam na aba Base de Conhecimento."
            />
          </div>

          {/* --- Área de Atuação --- */}
          <div className="pt-4 border-t border-slate-100 space-y-4">
            <h3 className="text-sm font-semibold text-slate-800">Área de Atuação</h3>
            <CampoDeTags
              rotulo="Países atendidos"
              marcadorDeExemplo="Ex.: Brasil"
              valores={dados.area_atuacao.paises}
              aoAlterar={(v) => atualizar("area_atuacao", { ...dados.area_atuacao, paises: v })}
            />
            <SeletorDeEstados
              selecionados={dados.area_atuacao.estados}
              aoAlterar={(v) => atualizar("area_atuacao", { ...dados.area_atuacao, estados: v })}
            />
            <CampoDeTags
              rotulo="Municípios atendidos"
              marcadorDeExemplo="Ex.: São Paulo"
              valores={dados.area_atuacao.municipios}
              aoAlterar={(v) => atualizar("area_atuacao", { ...dados.area_atuacao, municipios: v })}
            />
          </div>

          {/* --- Endereço de referência --- */}
          <div className="pt-4 border-t border-slate-100 space-y-4">
            <h3 className="text-sm font-semibold text-slate-800">Endereço de Referência do Negócio</h3>
            <div className="grid grid-cols-2 gap-3">
              <input placeholder="CEP" value={dados.endereco_cep || ""} onChange={(e) => atualizar("endereco_cep", e.target.value)} className={campo} />
              <input placeholder="Rua ou Avenida" value={dados.endereco_rua || ""} onChange={(e) => atualizar("endereco_rua", e.target.value)} className={campo} />
              <input placeholder="Bairro" value={dados.endereco_bairro || ""} onChange={(e) => atualizar("endereco_bairro", e.target.value)} className={campo} />
              <input placeholder="Número" value={dados.endereco_numero || ""} onChange={(e) => atualizar("endereco_numero", e.target.value)} className={campo} />
              <input placeholder="Complemento" value={dados.endereco_complemento || ""} onChange={(e) => atualizar("endereco_complemento", e.target.value)} className={campo} />
            </div>
            <textarea
              placeholder="Detalhes adicionais da área atendida"
              value={dados.endereco_detalhes_adicionais || ""}
              onChange={(e) => atualizar("endereco_detalhes_adicionais", e.target.value)}
              className={campo}
              rows={3}
            />
          </div>
        </section>

        {/* --- Bloco 2: Roteiro da Conversa --- */}
        <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-3">
          <h2 className={rotuloDaSecao}>Roteiro da Conversa</h2>
          <p className="text-sm text-slate-500">Descreva como você quer que o agente se comporte durante a conversa.</p>
          <textarea
            value={dados.roteiro_conversa}
            onChange={(e) => atualizar("roteiro_conversa", e.target.value)}
            className={campo}
            rows={10}
            placeholder="Ex.: Seja cordial e direto, sempre confirme o nome do cliente antes de encaminhar..."
          />
        </section>

        {/* --- Bloco 3: Regras de Atendimento --- */}
        <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
          <div>
            <h2 className={rotuloDaSecao}>Regras de Atendimento</h2>
            <p className="text-sm text-slate-500">
              O guardrail deste projeto: trava de onde vêm as respostas do agente sobre produtos, serviços e
              políticas da empresa.
            </p>
          </div>

          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={dados.responder_apenas_com_base_no_conhecimento}
              onChange={(e) => atualizar("responder_apenas_com_base_no_conhecimento", e.target.checked)}
            />
            <span>
              Responder apenas com base na Base de Conhecimento — qualquer pergunta sobre produtos, serviços ou
              políticas da empresa PRECISA vir de um item cadastrado na aba &quot;Base de Conhecimento&quot;,
              nunca respondida &quot;de memória&quot; pelo agente.
            </span>
          </label>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Mensagem para pergunta fora do escopo</label>
            <textarea
              value={dados.mensagem_fora_do_escopo}
              onChange={(e) => atualizar("mensagem_fora_do_escopo", e.target.value)}
              className={campo}
              rows={3}
            />
            <p className="text-xs text-slate-400 mt-1">
              Usada quando a busca na Base de Conhecimento não encontra nada relevante o suficiente para
              responder com segurança.
            </p>
          </div>
        </section>

        {mensagem && (
          <div className="text-sm bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg px-4 py-2">
            {mensagem}
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={salvando}
            className="px-5 py-2.5 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700 disabled:opacity-60"
          >
            {salvando ? "Salvando..." : "Salvar configuração"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a aba Configuração do Agente por completo:
// Perfil da Empresa (com Área de Atuação e Endereço), Roteiro da Conversa
// e Regras de Atendimento (o guardrail deste projeto). Sem bloco de
// Desfecho da Venda — os destinos de encaminhamento (Setores) e o
// conteúdo consultável (Base de Conhecimento) têm suas próprias abas
// dedicadas, e os quatro templates Meta ficam na aba Canais.
// ==============================================================================

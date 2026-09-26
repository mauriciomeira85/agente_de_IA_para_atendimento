"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/canais/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Canais": onde a empresa conecta o número de WhatsApp que
// o agente vai usar para responder os clientes dela.
//
// O botão "Conectar WhatsApp" usa o WhatsApp Embedded Signup da Meta — a
// pessoa clica, faz login numa janela oficial da Meta e escolhe (ou cria)
// o número dela; a plataforma recebe o resultado sozinha, sem ninguém
// precisar copiar Phone Number ID, WABA ID ou token de acesso na mão (ver
// biblioteca/embeddedSignup.ts para o passo a passo técnico completo).
//
// Layout no padrão da aba Canais do Impulso AI Agent (26/09/2026, igual nos
// três agentes): o cartão do WhatsApp tem o selo de status, o número
// conectado, a data e a hora da última conexão e um ícone "?" que abre o
// guia passo a passo (canais/whatsapp/guia). Assim que o número está
// conectado, aparece o painel "Templates do WhatsApp"
// (componentes/PainelDeTemplates.tsx), com envio individual ou de todos os
// pendentes.
//
// Abaixo de tudo, uma ÚNICA conta (configurada no backend, ver
// email_com_acesso_a_conexao_manual_whatsapp em configuracoes.py) também
// enxerga um formulário de conexão manual — usado enquanto essa conta
// ainda não tem um número comercial de verdade disponível para concluir
// o Embedded Signup até o fim. Qualquer outra conta (por exemplo, alguém
// testando o projeto pelo GitHub) só vê o botão normal.
// ==============================================================================

import { useEffect, useRef, useState } from "react";
import {
  conectarCanalWhatsApp,
  conectarCanalWhatsAppManualmente,
  obterCanalWhatsApp,
  obterConfiguracaoEmbeddedSignup,
} from "@/biblioteca/api";
import {
  abrirJanelaDeConexao,
  escutarMensagensDoEmbeddedSignup,
  obterRedirectUriDoEmbeddedSignup,
  tentarFecharComoJanelaDeCallback,
  type DadosDoEmbeddedSignup,
} from "@/biblioteca/embeddedSignup";
import type { CanalWhatsApp } from "@/biblioteca/tipos";
import Icone from "@/componentes/Icones";
import PainelDeTemplates from "@/componentes/PainelDeTemplates";

function formatarDataEHora(iso: string) {
  const data = new Date(iso);
  const dia = data.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
  const hora = data.toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" });
  return `${dia} às ${hora}`;
}

const campo = "w-full rounded-lg border border-slate-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600";

export default function PaginaDeCanais() {
  const [canalWhatsapp, setCanalWhatsapp] = useState<CanalWhatsApp | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [conectando, setConectando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [mostrarConexaoManual, setMostrarConexaoManual] = useState(false);

  // Guarda os dados da configuração de login da Meta assim que a página
  // descobre eles (buscando no backend) — usado só quando a pessoa clica
  // no botão.
  const configuracaoMetaRef = useRef<{ appId: string; idConfiguracao: string; versaoApi: string } | null>(null);

  // A janela de conexão da Meta manda o número/WABA escolhidos por um
  // "recado" entre janelas (postMessage), que costuma chegar ANTES do
  // código de autorização (devolvido só quando a janela fecha de vez).
  // Por isso guardamos aqui o que já chegou, para juntar os dois pedaços
  // assim que o código também chegar.
  const dadosDoNumeroEscolhidoRef = useRef<DadosDoEmbeddedSignup | null>(null);

  useEffect(() => {
    // Antes de qualquer outra coisa: esta mesma página pode, na verdade,
    // ser a janela popup que a Meta acabou de redirecionar de volta (com
    // o código de autorização na URL). Se for, ela repassa o código e se
    // fecha sozinha — não deve carregar nada do resto do efeito.
    if (tentarFecharComoJanelaDeCallback()) return;

    async function iniciar() {
      const [canal, configuracao] = await Promise.all([
        obterCanalWhatsApp(),
        obterConfiguracaoEmbeddedSignup(),
      ]);
      setCanalWhatsapp(canal);
      setMostrarConexaoManual(configuracao.mostrar_conexao_manual);
      setCarregando(false);

      if (!configuracao.app_id || !configuracao.id_configuracao) return;
      configuracaoMetaRef.current = {
        appId: configuracao.app_id,
        idConfiguracao: configuracao.id_configuracao,
        versaoApi: configuracao.versao_api,
      };
    }
    iniciar();

    const pararDeEscutar = escutarMensagensDoEmbeddedSignup((dados) => {
      dadosDoNumeroEscolhidoRef.current = dados;
    });
    return pararDeEscutar;
  }, []);

  async function aoClicarEmConectar() {
    const configuracaoMeta = configuracaoMetaRef.current;
    if (!configuracaoMeta) return;
    setErro(null);
    setConectando(true);
    dadosDoNumeroEscolhidoRef.current = null;

    try {
      const codigo = await abrirJanelaDeConexao(
        configuracaoMeta.appId,
        configuracaoMeta.idConfiguracao,
        configuracaoMeta.versaoApi
      );
      if (!codigo) {
        // A pessoa fechou a janela sem terminar, ou cancelou no meio do
        // caminho — não é um erro de verdade, só não há nada a salvar.
        return;
      }

      // O "postMessage" que a Meta manda com o número/WABA escolhidos é
      // conhecidamente instável (às vezes o código chega e esse recado
      // nunca chega — ver biblioteca/embeddedSignup.ts) — por isso NÃO
      // bloqueamos mais nele: se chegou a tempo, ótimo, mandamos junto
      // (evita uma chamada extra à Graph API); se não chegou, o backend
      // descobre o número/WABA sozinho a partir só do código.
      const dadosDoNumero = dadosDoNumeroEscolhidoRef.current as DadosDoEmbeddedSignup | null;

      const salvo = await conectarCanalWhatsApp({
        codigo_de_autorizacao: codigo,
        // Precisa ser IDÊNTICO ao redirect_uri usado para abrir o diálogo
        // (dentro de abrirJanelaDeConexao) — por isso vem da mesma função,
        // nunca escrito na mão aqui.
        redirect_uri: obterRedirectUriDoEmbeddedSignup(),
        id_numero_telefone: dadosDoNumero?.idNumeroDeTelefone,
        id_waba: dadosDoNumero?.idWaba,
      });
      setCanalWhatsapp(salvo);
    } catch (falha) {
      // Mostra o motivo que o backend devolveu (padronizado a partir do
      // Agente de Cobrança) — a mensagem genérica sozinha escondia a causa.
      const motivo = falha instanceof Error && falha.message ? ` Motivo: ${falha.message}` : "";
      setErro(`Não foi possível concluir a conexão com o WhatsApp.${motivo}`);
    } finally {
      setConectando(false);
    }
  }

  if (carregando) return <p className="text-sm text-slate-500">Carregando canais...</p>;

  const conectado = !!canalWhatsapp;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-marca-escuro">
          <Icone nome="tomada" className="h-6 w-6 text-marca-600" /> Canais
        </h1>
        <p className="text-sm text-slate-500">
          Conecte o número de WhatsApp que o agente vai usar para responder os clientes da empresa.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-start justify-between gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-marca-50">
              <Icone nome="mensagem" className="h-5 w-5 text-marca-500" />
            </span>
            <div className="flex items-center gap-2">
              <a
                href="/canais/whatsapp/guia"
                target="_blank"
                rel="noreferrer"
                aria-label="Abrir guia de configuração do WhatsApp"
                title="Como configurar o WhatsApp"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-marca-700"
              >
                <Icone nome="ajuda" className="h-5 w-5" />
              </a>
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                  conectado ? "border-emerald-300 text-emerald-700" : "border-slate-300 text-slate-600"
                }`}
              >
                {conectado && <Icone nome="confirmado" className="h-3 w-3" />}
                {conectado ? "Conectado" : "Não conectado"}
              </span>
            </div>
          </div>
          <h2 className="mt-4 text-base font-semibold text-marca-escuro">WhatsApp</h2>
          <p className="text-sm text-slate-500">Número comercial usado pelo agente para conversar com os clientes.</p>

          <div className="mt-4 space-y-3">
            <div className="space-y-1">
              <label className="block text-sm font-medium text-slate-700">Número do WhatsApp conectado</label>
              <input
                value={canalWhatsapp?.numero_exibicao || ""}
                readOnly
                aria-readonly="true"
                placeholder="Será preenchido após a conexão com a Meta"
                className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-800"
              />
              {canalWhatsapp && (
                <p className="text-xs text-slate-500">Conectado em {formatarDataEHora(canalWhatsapp.conectado_em)}</p>
              )}
            </div>
            <button
              onClick={aoClicarEmConectar}
              disabled={conectando}
              className="w-full rounded-lg bg-marca-600 px-4 py-2 text-sm font-medium text-white hover:bg-marca-700 disabled:opacity-60"
            >
              {conectando ? "Conectando…" : conectado ? "Renovar autorização Meta" : "Conectar WhatsApp"}
            </button>
            <p className="text-xs text-slate-500">
              A empresa entra na Meta, escolhe ou cria sua conta do WhatsApp Business e confirma o número por SMS ou
              ligação. Ao concluir, o número autorizado aparece automaticamente aqui. WABA ID, Phone Number ID e token
              permanecem protegidos e não são exibidos.
            </p>
            {erro && <p className="text-xs text-red-600">{erro}</p>}
          </div>
        </section>

        <section className="flex flex-col rounded-xl border border-marca-100 bg-marca-50/60 p-6">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-white">
            <Icone nome="documento_ok" className="h-5 w-5 text-marca-500" />
          </span>
          <h2 className="mt-4 text-base font-semibold text-marca-escuro">Como ativar o WhatsApp</h2>
          <p className="mt-1 flex-1 text-sm text-slate-600">
            Conta Meta, portfólio empresarial, número confirmado, Configuração do Agente, setores, conexão e templates
            aprovados: o guia mostra cada passo na ordem, do zero até o primeiro atendimento automático.
          </p>
          <a
            href="/canais/whatsapp/guia"
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-flex items-center justify-center gap-2 rounded-lg border border-marca-600 bg-white px-4 py-2 text-sm font-medium text-marca-700 hover:bg-marca-50"
          >
            Abrir o guia passo a passo <Icone nome="link_externo" />
          </a>
        </section>
      </div>

      {canalWhatsapp && <PainelDeTemplates />}

      {mostrarConexaoManual && (
        <FormularioDeConexaoManual canalAtual={canalWhatsapp} aoConectar={setCanalWhatsapp} />
      )}
    </div>
  );
}

/**
 * Formulário de conexão manual — só é renderizado (ver PaginaDeCanais
 * acima) para a única conta autorizada em
 * email_com_acesso_a_conexao_manual_whatsapp (backend/app/configuracoes.py).
 * Usado para testar o agente com um número já existente (ex.: o número de
 * teste da Meta) enquanto não há um número comercial disponível para
 * concluir o botão "Conectar WhatsApp" até o fim.
 */
function FormularioDeConexaoManual({
  canalAtual,
  aoConectar,
}: {
  canalAtual: CanalWhatsApp | null;
  aoConectar: (canal: CanalWhatsApp) => void;
}) {
  const [idNumero, setIdNumero] = useState(canalAtual?.id_numero_telefone_meta || "");
  const [idWaba, setIdWaba] = useState("");
  const [numeroExibicao, setNumeroExibicao] = useState(canalAtual?.numero_exibicao || "");
  const [token, setToken] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);

  async function aoSalvar(evento: React.FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    setMensagem(null);
    try {
      const salvo = await conectarCanalWhatsAppManualmente({
        id_numero_telefone_meta: idNumero,
        id_waba_meta: idWaba || undefined,
        numero_exibicao: numeroExibicao || undefined,
        token_de_acesso: token,
      });
      aoConectar(salvo);
      setToken("");
      setMensagem("Número conectado manualmente com sucesso.");
    } catch {
      setMensagem("Não foi possível salvar a conexão manual.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <section className="bg-white border border-amber-200 rounded-xl p-6 space-y-4">
      <div>
        <h2 className="text-base font-semibold text-marca-escuro">Conexão manual (uso interno)</h2>
        <p className="text-sm text-slate-500">
          Cole aqui as credenciais de um número já existente no painel da Meta — útil para testar o agente
          antes de ter um número comercial disponível para o Embedded Signup.
        </p>
      </div>

      {mensagem && <p className="text-sm text-slate-600">{mensagem}</p>}

      <form onSubmit={aoSalvar} className="space-y-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Phone Number ID</label>
          <input required value={idNumero} onChange={(e) => setIdNumero(e.target.value)} className={campo} />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">WABA ID</label>
          <input value={idWaba} onChange={(e) => setIdWaba(e.target.value)} className={campo} />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Número de exibição</label>
          <input
            value={numeroExibicao}
            onChange={(e) => setNumeroExibicao(e.target.value)}
            className={campo}
            placeholder="+55 11 99999-0000"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Token de acesso do System User</label>
          <input
            required={!canalAtual}
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className={campo}
            placeholder={canalAtual ? "Deixe em branco para manter o token atual" : ""}
          />
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={salvando}
            className="px-4 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700 disabled:opacity-60"
          >
            {salvando ? "Salvando..." : "Salvar conexão manual"}
          </button>
        </div>
      </form>
    </section>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a aba Canais no layout do Impulso AI Agent (igual
// nos três agentes): o cartão do WhatsApp (selo de status, número, data e
// hora da última conexão, ícone do guia e o botão que abre a janela de
// login da Meta via biblioteca/embeddedSignup.ts e conclui a conexão em
// POST /api/canais/whatsapp/conectar), um cartão que leva ao guia passo a
// passo e, depois de conectado, o painel de templates
// (componentes/PainelDeTemplates.tsx). Para a
// única conta autorizada pelo backend, FormularioDeConexaoManual permite
// colar credenciais existentes.
// ==============================================================================

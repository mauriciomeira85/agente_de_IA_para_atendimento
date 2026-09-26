"use client";

// ==============================================================================
// ARQUIVO: componentes/PainelDeTemplates.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Painel dos templates de WhatsApp da empresa, mostrado na aba Canais
// depois que o WhatsApp é conectado. É o MESMO arquivo nos três agentes
// (Cobrança, Comercial SDR e Atendimento); o que muda vem do backend (lista
// de templates, textos e legendas). Sem template editável (Atendimento),
// o bloco da primeira abordagem simplesmente não aparece. Segue o mesmo layout da aba Canais do
// Impulso AI Agent (26/09/2026, pedido do usuário), com a paleta deste
// projeto:
//
//   1. "Primeira abordagem personalizada": o único template editável. A
//      pessoa escolhe "Usar modelo recomendado" ou "Gerar com IA a partir da
//      Configuração", revisa o texto (com as variáveis {{n}}) e envia. O
//      texto fica bloqueado enquanto está em análise ou aprovado.
//   2. Os outros templates em cartões, cada um com o status, a "Mensagem
//      enviada à Meta" (texto real, com as variáveis), o que cada variável
//      recebe e o próprio botão "Enviar para análise".
//   3. "Enviar todos os templates pendentes para análise" envia de uma vez
//      os que ainda não foram enviados ou que foram rejeitados.
//   4. Todo envio passa por uma janela de confirmação com o texto final.
//   5. Um template REJEITADO mostra o motivo da Meta e volta a ter o botão de
//      envio: o backend edita o template existente (a Meta não aceita criar
//      outro com o mesmo nome).
//   6. O status atualiza sozinho: a Meta avisa o webhook, que avisa esta
//      tela na hora (WebSocket); "Atualizar status" consulta na hora, e a
//      consulta a cada minuto fica como reserva enquanto houver análise.
// ==============================================================================

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  enviarTemplate,
  enviarTodosOsTemplates,
  gerarRascunhoDeTemplateComIa,
  listarTemplatesDoPainel,
  obterUrlWebSocketDeConversas,
} from "@/biblioteca/api";
import type { TemplateDoPainel } from "@/biblioteca/tipos";
import Icone from "@/componentes/Icones";

const INTERVALO_DE_VERIFICACAO_MS = 60_000;
const LIMITE_DE_CARACTERES = 550;
const STATUS_BLOQUEADOS = ["APPROVED", "PENDING", "IN_APPEAL"];

function rotuloDoStatus(status: string | null) {
  if (status === "APPROVED") return { texto: "Aprovado", cor: "border-emerald-300 text-emerald-700" };
  if (status === "PENDING" || status === "IN_APPEAL") return { texto: "Em análise", cor: "border-amber-400 text-amber-700" };
  if (status === "REJECTED") return { texto: "Rejeitado", cor: "border-red-300 text-red-700" };
  if (status === "PAUSED" || status === "DISABLED") return { texto: "Pausado pela Meta", cor: "border-red-300 text-red-700" };
  return { texto: "Não enviado", cor: "border-slate-300 text-slate-600" };
}

function podeEnviar(template: TemplateDoPainel) {
  return !template.status || template.status === "REJECTED";
}

function Selo({ status }: { status: string | null }) {
  const rotulo = rotuloDoStatus(status);
  return (
    <span className={`shrink-0 inline-flex items-center gap-1 rounded-full border bg-white px-2.5 py-0.5 text-xs font-medium ${rotulo.cor}`}>
      {status === "APPROVED" && <Icone nome="confirmado" className="h-3 w-3" />}
      {rotulo.texto}
    </span>
  );
}

const botaoPrincipal =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-marca-600 px-4 py-2 text-sm font-medium text-white hover:bg-marca-700 disabled:opacity-50";
const botaoContorno =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50";

export default function PainelDeTemplates() {
  const [templates, setTemplates] = useState<TemplateDoPainel[] | null>(null);
  const [textoAbordagem, setTextoAbordagem] = useState("");
  const [fonteDoRascunho, setFonteDoRascunho] = useState<"recomendado" | "ia" | "editado">("recomendado");
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState<string[] | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro" | "atencao"; texto: string } | null>(null);
  const [erroDeCarga, setErroDeCarga] = useState<string | null>(null);

  const recarregar = useCallback(async (sincronizarTexto = false) => {
    try {
      const lista = await listarTemplatesDoPainel();
      setTemplates(lista);
      setErroDeCarga(null);
      const abordagem = lista.find((t) => t.editavel);
      if (abordagem) {
        setTextoAbordagem((atual) => (sincronizarTexto || !atual ? abordagem.texto || "" : atual));
        if (!sincronizarTexto && abordagem.texto && abordagem.texto !== abordagem.texto_padrao) {
          setFonteDoRascunho((atual) => (atual === "recomendado" ? "editado" : atual));
        }
      }
    } catch (falha) {
      setErroDeCarga(falha instanceof Error ? falha.message : "Não foi possível consultar os templates.");
    }
  }, []);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  // Tempo real: a Meta avisa o webhook quando analisa um template, e o
  // backend repassa um evento "template_atualizado" por este WebSocket.
  useEffect(() => {
    const url = obterUrlWebSocketDeConversas();
    if (!url) return;
    const soquete = new WebSocket(url);
    soquete.onmessage = (evento) => {
      try {
        if (JSON.parse(evento.data)?.tipo === "template_atualizado") recarregar();
      } catch {
        // mensagem que não é JSON: ignora
      }
    };
    return () => soquete.close();
  }, [recarregar]);

  const algumEmAnalise = templates?.some((t) => t.status === "PENDING" || t.status === "IN_APPEAL");
  useEffect(() => {
    if (!algumEmAnalise) return;
    const intervalo = setInterval(() => recarregar(), INTERVALO_DE_VERIFICACAO_MS);
    return () => clearInterval(intervalo);
  }, [algumEmAnalise, recarregar]);

  const abordagem = templates?.find((t) => t.editavel) ?? null;
  const operacionais = templates?.filter((t) => !t.editavel) ?? [];
  const abordagemBloqueada = !!abordagem && STATUS_BLOQUEADOS.includes(abordagem.status ?? "");
  const pendentes = useMemo(() => (templates ?? []).filter(podeEnviar).map((t) => t.chave), [templates]);

  function usarModeloRecomendado() {
    if (!abordagem?.texto_padrao) return;
    setTextoAbordagem(abordagem.texto_padrao);
    setFonteDoRascunho("recomendado");
    setAviso({ tipo: "ok", texto: "Modelo recomendado restaurado." });
  }

  async function gerarComIa() {
    setOcupado("rascunho");
    setAviso(null);
    try {
      const rascunho = await gerarRascunhoDeTemplateComIa();
      setTextoAbordagem(rascunho.texto);
      setFonteDoRascunho(rascunho.gerado_pela_ia ? "ia" : "recomendado");
      setAviso(
        rascunho.aviso
          ? { tipo: "atencao", texto: rascunho.aviso }
          : { tipo: "ok", texto: "Rascunho gerado com a Configuração do Agente." }
      );
    } catch (falha) {
      setAviso({ tipo: "erro", texto: falha instanceof Error ? falha.message : "Não foi possível gerar o rascunho." });
    } finally {
      setOcupado(null);
    }
  }

  async function enviar(chaves: string[]) {
    setOcupado("envio");
    setAviso(null);
    try {
      const textoParaEnviar = chaves.includes(abordagem?.chave ?? "") ? textoAbordagem : null;
      if (chaves.length === 1) {
        await enviarTemplate(chaves[0], textoParaEnviar);
        setAviso({ tipo: "ok", texto: "Template enviado para análise da Meta." });
      } else {
        const resultados = await enviarTodosOsTemplates(textoParaEnviar);
        const falhas = resultados.filter((r) => r.resultado === "erro");
        setAviso(
          falhas.length
            ? { tipo: "erro", texto: falhas.map((f) => `${f.nome}: ${f.detalhe}`).join(" · ") }
            : { tipo: "ok", texto: "Templates pendentes enviados para análise da Meta." }
        );
      }
      setConfirmar(null);
      await recarregar(true);
    } catch (falha) {
      setAviso({ tipo: "erro", texto: falha instanceof Error ? falha.message : "Falha ao enviar o template." });
    } finally {
      setOcupado(null);
    }
  }

  if (!templates) {
    return erroDeCarga ? (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <p className="text-sm text-red-600">{erroDeCarga}</p>
      </section>
    ) : null;
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-col justify-between gap-3 p-6 pb-2 sm:flex-row sm:items-start">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-marca-escuro">
            <Icone nome="mensagem" className="h-5 w-5 text-marca-500" /> Templates do WhatsApp
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Cada empresa envia os modelos para aprovação na própria conta do WhatsApp Business.{" "}
            {abordagem
              ? "O agente só inicia contatos depois que a primeira abordagem estiver aprovada."
              : "Eles avisam o setor humano quando um atendimento é encaminhado e retomam conversas que pararam."}
          </p>
        </div>
        <button type="button" className={botaoContorno} disabled={ocupado !== null} onClick={() => recarregar()}>
          <Icone nome="atualizar" /> Atualizar status
        </button>
      </div>

      <div className="space-y-5 p-6 pt-4">
        {aviso && (
          <div
            className={`flex gap-2 rounded-lg border p-3 text-sm ${
              aviso.tipo === "ok"
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : aviso.tipo === "atencao"
                  ? "border-amber-300 bg-amber-50 text-amber-900"
                  : "border-red-200 bg-red-50 text-red-800"
            }`}
          >
            <Icone nome={aviso.tipo === "ok" ? "confirmado" : "alerta"} className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{aviso.texto}</span>
          </div>
        )}

        {abordagem && (
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold text-marca-escuro">Primeira abordagem personalizada</p>
                <p className="text-xs text-slate-500">
                  Categoria Marketing · Português (Brasil) ·{" "}
                  {fonteDoRascunho === "ia"
                    ? "rascunho gerado a partir da Configuração do Agente"
                    : fonteDoRascunho === "editado"
                      ? "rascunho editado pela empresa"
                      : "modelo recomendado"}
                </p>
              </div>
              <Selo status={abordagem.status} />
            </div>
            {abordagem.motivo && (
              <p className="mb-2 text-xs text-red-700">Motivo da rejeição pela Meta: {abordagem.motivo}</p>
            )}
            <textarea
              value={textoAbordagem}
              onChange={(e) => {
                setTextoAbordagem(e.target.value);
                setFonteDoRascunho("editado");
              }}
              disabled={abordagemBloqueada}
              rows={5}
              maxLength={LIMITE_DE_CARACTERES}
              aria-label="Texto do template de primeira abordagem"
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-marca-600 disabled:bg-slate-100 disabled:text-slate-600"
            />
            <div className="mt-2 flex flex-col justify-between gap-2 text-xs text-slate-500 sm:flex-row">
              <span>{abordagem.legenda}</span>
              <span className="shrink-0">
                {textoAbordagem.length}/{LIMITE_DE_CARACTERES}
              </span>
            </div>
            {!abordagemBloqueada && (
              <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <button type="button" className={botaoContorno} disabled={ocupado !== null} onClick={usarModeloRecomendado}>
                  <Icone nome="restaurar" /> Usar modelo recomendado
                </button>
                <button type="button" className={botaoContorno} disabled={ocupado !== null} onClick={gerarComIa}>
                  <Icone nome="ia" /> {ocupado === "rascunho" ? "Gerando…" : "Gerar com IA a partir da Configuração"}
                </button>
                <button
                  type="button"
                  className={botaoPrincipal}
                  disabled={ocupado !== null || !textoAbordagem.trim()}
                  onClick={() => setConfirmar([abordagem.chave])}
                >
                  <Icone nome="enviar" /> Revisar e enviar para análise
                </button>
              </div>
            )}
            {abordagemBloqueada && (
              <p className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                <Icone nome="relogio" /> O texto fica bloqueado enquanto está em análise ou aprovado.
              </p>
            )}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-2">
          {operacionais.map((template) => (
            <div key={template.chave} className="flex flex-col rounded-xl border border-slate-200 p-4">
              <div className="flex items-start justify-between gap-2">
                <p className="font-medium text-marca-escuro">{template.titulo}</p>
                <Selo status={template.status} />
              </div>
              <p className="mt-2 flex-1 text-xs text-slate-500">{template.descricao}</p>
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Mensagem enviada à Meta
                </p>
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-800">{template.texto}</p>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-500">{template.legenda}</p>
              {template.motivo && (
                <p className="mt-1 text-[11px] text-red-700">Motivo da rejeição pela Meta: {template.motivo}</p>
              )}
              {podeEnviar(template) && (
                <button
                  type="button"
                  className={`${botaoContorno} mt-3 py-1.5`}
                  disabled={ocupado !== null}
                  onClick={() => setConfirmar([template.chave])}
                >
                  {template.status === "REJECTED" ? "Reenviar para análise" : "Enviar para análise"}
                </button>
              )}
            </div>
          ))}
        </div>

        <button
          type="button"
          className={`${botaoPrincipal} w-full`}
          disabled={ocupado !== null || pendentes.length === 0}
          onClick={() => setConfirmar(pendentes)}
        >
          {ocupado === "envio"
            ? "Enviando…"
            : pendentes.length
              ? "Enviar todos os templates pendentes para análise"
              : "Todos os templates já foram enviados"}
        </button>
      </div>

      {confirmar && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => ocupado === null && setConfirmar(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-marca-escuro">Confirmar envio para análise da Meta</h3>
            <p className="mt-1 text-sm text-slate-500">
              Revise o conteúdo abaixo. Depois do envio, a Meta analisará cada modelo e ele não poderá ser usado até ser
              aprovado.
            </p>
            <div className="mt-4 space-y-3">
              {confirmar.map((chave) => {
                const template = templates.find((t) => t.chave === chave);
                if (!template) return null;
                return (
                  <div key={chave} className="rounded-lg border border-slate-200 p-3">
                    <p className="font-medium text-marca-escuro">{template.editavel ? "Primeira abordagem personalizada" : template.titulo}</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">
                      {template.editavel ? textoAbordagem : template.texto}
                    </p>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
              A aprovação pertence à conta do WhatsApp Business desta empresa. A plataforma acompanha o status
              {abordagem
                ? " e só libera a primeira abordagem automática quando o template de abordagem estiver aprovado."
                : " e só usa cada template depois que ele estiver aprovado."}
            </div>
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button type="button" className={botaoContorno} disabled={ocupado !== null} onClick={() => setConfirmar(null)}>
                Voltar e editar
              </button>
              <button type="button" className={botaoPrincipal} disabled={ocupado !== null} onClick={() => enviar(confirmar)}>
                <Icone nome="enviar" /> {ocupado === "envio" ? "Enviando…" : "Confirmar e enviar para análise"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Painel de templates no layout do Impulso AI Agent: abordagem editável
// (modelo recomendado ou rascunho da IA, bloqueada em análise/aprovada),
// cartões dos templates operacionais com o texto real enviado à Meta e
// botão individual, botão para enviar todos os pendentes, janela de
// confirmação antes de qualquer envio e reenvio de rejeitados. O status
// atualiza pelo WebSocket, pelo botão "Atualizar status" e, em análise, a
// cada minuto.
// ==============================================================================

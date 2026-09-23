"use client";

// ==============================================================================
// ARQUIVO: app/(plataforma)/conversas/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Esta é a aba "Conversas": mostra, em duas colunas, a lista de conversas
// (uma por atendimento, mais recente primeiro) à esquerda e o histórico
// completo de mensagens da conversa selecionada à direita — o formato
// clássico de tela de chat.
//
// A tela se atualiza SOZINHA, sem precisar recarregar a página: ela abre
// uma conexão WebSocket com o backend (ver
// backend/app/rotas/tempo_real.py) e, sempre que chega um evento —
// mensagem nova do cliente ou resposta do agente — busca de novo a lista
// de conversas e, se a conversa afetada for a que está aberta na tela,
// atualiza o histórico também.
// ==============================================================================

import { useEffect, useRef, useState } from "react";
import {
  atualizarConversa,
  excluirConversa,
  listarConversas,
  obterConversa,
  obterUrlDaMidiaDaMensagem,
  obterUrlWebSocketDeConversas,
} from "@/biblioteca/api";
import type { ConversaDetalhe, ConversaResumo, MensagemConversa } from "@/biblioteca/tipos";

const RÓTULO_DO_REMETENTE: Record<string, string> = {
  cliente: "Cliente",
  agente_ia: "Agente",
  atendente_humano: "Atendente",
  sistema: "Sistema",
};

/** Horário no formato "14:38", igual ao que aparece embaixo de cada balão no WhatsApp. */
function formatarHorario(criadoEm: string): string {
  return new Date(criadoEm).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/**
 * Rótulo do separador de dia entre mensagens ("Hoje", "Ontem" ou a data
 * completa) — mesmo padrão do WhatsApp, que agrupa as mensagens por dia em
 * vez de repetir a data em cada balão.
 */
function formatarSeparadorDeData(criadoEm: string): string {
  const data = new Date(criadoEm);
  const hoje = new Date();
  const ontem = new Date(hoje);
  ontem.setDate(hoje.getDate() - 1);

  const mesmoDia = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  if (mesmoDia(data, hoje)) return "Hoje";
  if (mesmoDia(data, ontem)) return "Ontem";
  return data.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// Cor do ícone de cada tipo de documento — mesma lógica de cores que o
// próprio WhatsApp usa (PDF vermelho, Word azul, Excel verde), pra ficar
// reconhecível de relance na lista de mensagens.
const COR_POR_EXTENSAO: Record<string, string> = {
  pdf: "bg-red-500",
  doc: "bg-blue-500",
  docx: "bg-blue-500",
  xls: "bg-emerald-600",
  xlsx: "bg-emerald-600",
  xlsm: "bg-emerald-600",
  txt: "bg-slate-500",
};

const EXTENSAO_POR_MIME_TYPE: Record<string, string> = {
  "application/pdf": "pdf",
  "application/msword": "doc",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
  "application/vnd.ms-excel": "xls",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
  "text/plain": "txt",
};

/** Descobre a extensão do arquivo pelo nome — e, se não tiver nome, pelo mime type (mesmo mapa usado pelo backend, ver agente/nos.py). */
function extensaoDoArquivo(nomeDoArquivo: string | null, mimeType: string | null): string {
  if (nomeDoArquivo?.includes(".")) return nomeDoArquivo.split(".").pop()!.toLowerCase();
  return (mimeType && EXTENSAO_POR_MIME_TYPE[mimeType]) || "";
}

/** Selo colorido com a extensão do arquivo — mesmo papel visual do ícone de PDF/Word/Excel que o WhatsApp mostra ao lado do nome do arquivo. */
function IconeDoArquivo({ nomeDoArquivo, mimeType }: { nomeDoArquivo: string | null; mimeType: string | null }) {
  const extensao = extensaoDoArquivo(nomeDoArquivo, mimeType);
  return (
    <span
      className={`shrink-0 w-8 h-8 rounded flex items-center justify-center text-[9px] font-bold text-white uppercase ${
        COR_POR_EXTENSAO[extensao] || "bg-slate-400"
      }`}
    >
      {extensao || "📄"}
    </span>
  );
}

const VELOCIDADES_DE_REPRODUCAO = [1, 1.5, 2] as const;

/** Formata segundos como "1:05", igual ao relógio de duração do WhatsApp. */
function formatarDuracao(segundos: number): string {
  if (!isFinite(segundos) || segundos < 0) return "0:00";
  const minutos = Math.floor(segundos / 60);
  const resto = Math.floor(segundos % 60)
    .toString()
    .padStart(2, "0");
  return `${minutos}:${resto}`;
}

/**
 * Player de áudio próprio (em vez do `<audio controls>` nativo) — o
 * controle nativo do navegador só oferece velocidade de reprodução
 * escondida num menu de "⋮", se é que oferece; aqui o botão de
 * velocidade (1x/1.5x/2x, alternando a cada clique) fica sempre visível,
 * do mesmo jeito que o player de áudio do WhatsApp.
 */
function PlayerDeAudio({ url }: { url: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [tocando, setTocando] = useState(false);
  const [velocidade, setVelocidade] = useState<(typeof VELOCIDADES_DE_REPRODUCAO)[number]>(1);
  const [duracao, setDuracao] = useState(0);
  const [tempoAtual, setTempoAtual] = useState(0);

  function alternarVelocidade() {
    const indiceAtual = VELOCIDADES_DE_REPRODUCAO.indexOf(velocidade);
    const proxima = VELOCIDADES_DE_REPRODUCAO[(indiceAtual + 1) % VELOCIDADES_DE_REPRODUCAO.length];
    setVelocidade(proxima);
    if (audioRef.current) audioRef.current.playbackRate = proxima;
  }

  return (
    <div className="flex items-center gap-2 w-64 max-w-full">
      <audio
        ref={audioRef}
        src={url}
        preload="metadata"
        onPlay={() => setTocando(true)}
        onPause={() => setTocando(false)}
        onEnded={() => setTocando(false)}
        onLoadedMetadata={(e) => setDuracao(e.currentTarget.duration)}
        onTimeUpdate={(e) => setTempoAtual(e.currentTarget.currentTime)}
        className="hidden"
      />
      <button
        type="button"
        onClick={() => (tocando ? audioRef.current?.pause() : audioRef.current?.play())}
        className="shrink-0 w-7 h-7 rounded-full bg-black/10 flex items-center justify-center text-xs"
        aria-label={tocando ? "Pausar" : "Reproduzir"}
      >
        {tocando ? "⏸" : "▶"}
      </button>
      <input
        type="range"
        min={0}
        max={duracao || 0}
        step={0.1}
        value={tempoAtual}
        onChange={(e) => {
          const novoTempo = Number(e.target.value);
          setTempoAtual(novoTempo);
          if (audioRef.current) audioRef.current.currentTime = novoTempo;
        }}
        className="flex-1 h-1 accent-current"
      />
      <span className="shrink-0 text-[10px] tabular-nums opacity-80 w-8">
        {formatarDuracao(tempoAtual > 0 ? tempoAtual : duracao)}
      </span>
      <button
        type="button"
        onClick={alternarVelocidade}
        className="shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-black/10"
      >
        {velocidade}x
      </button>
    </div>
  );
}

/**
 * Renderiza o conteúdo de UMA mensagem: mídia de verdade (imagem, vídeo/
 * GIF, áudio, documento) quando a mensagem tem uma — só o conteúdo
 * original, exatamente como aparece no WhatsApp, sem a descrição
 * automática que a IA gera internamente pra entender a mídia (essa
 * descrição nunca aparece na interface, é só um detalhe de implementação
 * — ver backend/app/agente/nos.py). Mensagem de texto puro (o caso mais
 * comum) mostra o texto normalmente.
 */
function ConteudoDaMensagem({ mensagem }: { mensagem: MensagemConversa }) {
  const urlDaMidia = mensagem.mime_type_da_midia ? obterUrlDaMidiaDaMensagem(mensagem.id) : null;

  if (!urlDaMidia) {
    return <p>{mensagem.conteudo}</p>;
  }

  if (mensagem.tipo_conteudo === "imagem") {
    const ehVideo = mensagem.mime_type_da_midia?.startsWith("video/");
    return ehVideo ? (
      <video controls src={urlDaMidia} className="max-w-full max-h-64 rounded-lg" />
    ) : (
      <img src={urlDaMidia} alt="Mídia enviada pelo cliente" className="max-w-full max-h-64 rounded-lg" />
    );
  }

  if (mensagem.tipo_conteudo === "audio") {
    return <PlayerDeAudio url={urlDaMidia} />;
  }

  if (mensagem.tipo_conteudo === "documento") {
    return (
      <a
        href={urlDaMidia}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2.5 rounded-lg bg-black/5 px-2.5 py-2 hover:bg-black/10"
      >
        <IconeDoArquivo nomeDoArquivo={mensagem.nome_do_arquivo_da_midia} mimeType={mensagem.mime_type_da_midia} />
        <span className="flex-1 min-w-0 text-xs font-medium truncate">
          {mensagem.nome_do_arquivo_da_midia || "Abrir arquivo"}
        </span>
      </a>
    );
  }

  return <p>{mensagem.conteudo}</p>;
}

export default function PaginaDeConversas() {
  const [conversas, setConversas] = useState<ConversaResumo[]>([]);
  const [conversaSelecionada, setConversaSelecionada] = useState<ConversaDetalhe | null>(null);
  const [carregando, setCarregando] = useState(true);
  // Qual conversa tem o menu de três pontinhos aberto no momento (só uma por vez).
  const [menuAbertoParaId, setMenuAbertoParaId] = useState<number | null>(null);

  // Guardado em uma "ref" (e não em um state) porque é lido de dentro do
  // callback do WebSocket, que é criado uma única vez — usar state ali
  // capturaria sempre o valor do momento em que o WebSocket foi aberto.
  const idDaConversaAbertaRef = useRef<number | null>(null);

  async function abrirConversa(id: number) {
    idDaConversaAbertaRef.current = id;
    const detalhe = await obterConversa(id);
    setConversaSelecionada(detalhe);
  }

  async function aoRenomear(conversa: ConversaResumo) {
    setMenuAbertoParaId(null);
    const novoApelido = window.prompt("Novo nome para esta conversa:", conversa.apelido ?? conversa.nome_atendimento);
    if (novoApelido === null) return; // cancelou
    const atualizada = await atualizarConversa(conversa.id, { apelido: novoApelido.trim() || null });
    setConversas((atual) => atual.map((c) => (c.id === atualizada.id ? atualizada : c)));
    if (conversaSelecionada?.id === atualizada.id) {
      setConversaSelecionada({ ...conversaSelecionada, apelido: atualizada.apelido });
    }
  }

  async function aoFixarOuDesafixar(conversa: ConversaResumo) {
    setMenuAbertoParaId(null);
    const atualizada = await atualizarConversa(conversa.id, { fixada: !conversa.fixada });
    // Reordena: fixadas primeiro, igual o backend devolve em listarConversas().
    setConversas((atual) =>
      [...atual.map((c) => (c.id === atualizada.id ? atualizada : c))].sort((a, b) =>
        a.fixada === b.fixada ? 0 : a.fixada ? -1 : 1
      )
    );
  }

  async function aoExcluir(conversa: ConversaResumo) {
    setMenuAbertoParaId(null);
    if (!confirm(`Excluir a conversa com "${conversa.apelido ?? conversa.nome_atendimento}"? Esta ação não pode ser desfeita.`))
      return;
    await excluirConversa(conversa.id);
    setConversas((atual) => atual.filter((c) => c.id !== conversa.id));
    if (conversaSelecionada?.id === conversa.id) {
      idDaConversaAbertaRef.current = null;
      setConversaSelecionada(null);
    }
  }

  useEffect(() => {
    listarConversas()
      .then((dados) => {
        setConversas(dados);
        if (dados.length > 0) abrirConversa(dados[0].id);
      })
      .finally(() => setCarregando(false));
  }, []);

  // Conexão WebSocket: sempre que um evento chega, recarrega a lista de
  // conversas e, se for a conversa aberta no momento, o histórico também.
  useEffect(() => {
    const url = obterUrlWebSocketDeConversas();
    if (!url) return;

    const soquete = new WebSocket(url);
    soquete.onmessage = () => {
      listarConversas().then(setConversas);
      if (idDaConversaAbertaRef.current !== null) {
        obterConversa(idDaConversaAbertaRef.current).then(setConversaSelecionada);
      }
    };

    return () => soquete.close();
  }, []);

  return (
    <div>
      {/* Fecha o menu de três pontinhos ao clicar em qualquer lugar fora dele. */}
      {menuAbertoParaId !== null && (
        <div className="fixed inset-0 z-[5]" onClick={() => setMenuAbertoParaId(null)} />
      )}

      <h1 className="text-2xl font-semibold text-marca-escuro mb-4">Conversas</h1>

      <div
        className="flex w-full bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm"
        style={{ height: "calc(100vh - 140px)" }}
      >
        <div className="w-72 shrink-0 bg-slate-50 border-r border-slate-200 overflow-y-auto">
          {carregando && <p className="p-4 text-sm text-slate-400">Carregando...</p>}
          {!carregando && conversas.length === 0 && (
            <p className="p-4 text-sm text-slate-400">Nenhuma conversa ainda.</p>
          )}
          {conversas.map((conversa) => {
            const selecionada = conversaSelecionada?.id === conversa.id;
            const inicial = (conversa.apelido ?? conversa.nome_atendimento).trim().charAt(0).toUpperCase();
            return (
            <div
              key={conversa.id}
              className={`relative flex items-center border-l-2 border-b border-slate-100 transition-colors ${
                selecionada ? "border-l-marca-600 bg-white" : "border-l-transparent hover:bg-white/70"
              }`}
            >
              <button onClick={() => abrirConversa(conversa.id)} className="flex-1 min-w-0 flex items-center gap-3 text-left px-4 py-3">
                <span className="shrink-0 w-9 h-9 rounded-full bg-marca-600 text-white text-sm font-semibold flex items-center justify-center">
                  {inicial}
                </span>
                <span className="min-w-0">
                  <p className="text-sm font-medium text-marca-escuro truncate">
                    {conversa.fixada && "📌 "}
                    {conversa.apelido ?? conversa.nome_atendimento}
                  </p>
                  <p className="text-xs text-slate-400 truncate">{conversa.ultima_mensagem || "Sem mensagens"}</p>
                </span>
              </button>

              <div className="relative pr-2">
                <button
                  onClick={() => setMenuAbertoParaId(menuAbertoParaId === conversa.id ? null : conversa.id)}
                  className="px-2 py-1 text-slate-400 hover:text-slate-700"
                  aria-label="Mais opções"
                >
                  ⋮
                </button>
                {menuAbertoParaId === conversa.id && (
                  <div className="absolute right-2 top-8 z-10 w-40 bg-white border border-slate-200 rounded-lg shadow-lg py-1">
                    <button
                      onClick={() => aoFixarOuDesafixar(conversa)}
                      className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                    >
                      {conversa.fixada ? "Desafixar" : "Fixar"}
                    </button>
                    <button
                      onClick={() => aoRenomear(conversa)}
                      className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                    >
                      Renomear
                    </button>
                    <button
                      onClick={() => aoExcluir(conversa)}
                      className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                    >
                      Excluir
                    </button>
                  </div>
                )}
              </div>
            </div>
            );
          })}
        </div>

        <div className="flex-1 flex flex-col">
          {!conversaSelecionada && (
            <div className="flex-1 flex items-center justify-center text-sm text-slate-400">
              Selecione uma conversa para ver o histórico.
            </div>
          )}
          {conversaSelecionada && (() => {
            const mensagensVisiveis = conversaSelecionada.mensagens.filter((mensagem) => mensagem.remetente !== "sistema");
            return (
            <>
              <div className="flex items-center gap-3 px-5 py-3.5 border-b border-slate-200 bg-slate-50">
                <span className="shrink-0 w-9 h-9 rounded-full bg-marca-600 text-white text-sm font-semibold flex items-center justify-center">
                  {(conversaSelecionada.apelido ?? conversaSelecionada.nome_atendimento).trim().charAt(0).toUpperCase()}
                </span>
                <p className="text-base font-semibold text-marca-escuro">
                  {conversaSelecionada.apelido ?? conversaSelecionada.nome_atendimento}
                </p>
              </div>
              <div className="flex-1 overflow-y-auto p-5 space-y-3 bg-white">
                {/*
                  Mensagens de SISTEMA ("Resolvido com a Base de Conhecimento",
                  "Encaminhado para um setor humano") existem no banco só como
                  marcador interno de desfecho — nunca foram pensadas pra
                  aparecer como um balão de chat (renderizavam exatamente como
                  um balão do Agente, confundindo quem está lendo a conversa
                  real). Filtradas daqui, não do banco: continuam existindo
                  pra quem precisar auditar o histórico direto no banco.
                */}
                {mensagensVisiveis.map((mensagem, indice) => {
                  const doCliente = mensagem.remetente === "cliente";
                  const mensagemAnterior = mensagensVisiveis[indice - 1];
                  const mudouDeDia =
                    !mensagemAnterior ||
                    formatarSeparadorDeData(mensagemAnterior.criado_em) !== formatarSeparadorDeData(mensagem.criado_em);

                  return (
                    <div key={mensagem.id}>
                      {mudouDeDia && (
                        <div className="flex justify-center py-1">
                          <span className="text-[11px] text-slate-500 bg-slate-100 rounded-full px-3 py-1">
                            {formatarSeparadorDeData(mensagem.criado_em)}
                          </span>
                        </div>
                      )}
                      <div className={`flex ${doCliente ? "justify-start" : "justify-end"}`}>
                        <div
                          className={`max-w-md rounded-xl px-3 py-2 text-sm ${
                            doCliente ? "bg-slate-100 text-slate-800" : "bg-marca-600 text-white"
                          }`}
                        >
                          <p className="text-[11px] opacity-60 mb-0.5">{RÓTULO_DO_REMETENTE[mensagem.remetente]}</p>
                          <ConteudoDaMensagem mensagem={mensagem} />
                          <p className={`text-[10px] mt-1 text-right ${doCliente ? "text-slate-400" : "opacity-60"}`}>
                            {formatarHorario(mensagem.criado_em)}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
            );
          })()}
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a aba Conversas: lista à esquerda (uma linha
// por atendimento) e histórico completo de mensagens à direita, sempre
// que uma conversa é selecionada — e mantém tudo atualizado sozinho
// através da conexão WebSocket com o backend. O histórico mostra horário
// em cada balão e um separador de dia ("Hoje", "Ontem" ou a data) entre
// mensagens de dias diferentes, no mesmo padrão visual do WhatsApp. O
// painel usa altura relativa à janela (100vh) e toda a largura
// disponível, em vez de um tamanho fixo pequeno, para aproveitar melhor o
// espaço da tela. ConteudoDaMensagem reproduz a mídia de verdade (imagem,
// vídeo/GIF, áudio, documento) recebida de um cliente direto na tela, sem
// precisar abrir o WhatsApp — ver backend/app/armazenamento_midia.py.
// ==============================================================================

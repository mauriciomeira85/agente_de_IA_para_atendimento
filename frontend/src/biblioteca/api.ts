// ==============================================================================
// ARQUIVO: biblioteca/api.ts
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Este arquivo concentra toda a comunicação do frontend com o backend
// (a API em FastAPI). Em vez de espalhar chamadas "fetch" soltas por
// dezenas de componentes, cada tela chama uma função específica daqui —
// por exemplo, "obterPainel()" ou "editarAtendimento(id, dados)" — o que
// deixa o código de cada página mais curto e mais fácil de entender.
//
// Todas as funções (exceto login/cadastro) automaticamente incluem o
// token de acesso salvo no navegador após o login, no cabeçalho
// "Authorization: Bearer <token>", exigido pelas rotas protegidas do
// backend.
// ==============================================================================

import type {
  RascunhoDeTemplate,
  ResultadoDoEnvioDeTemplate,
  TemplateDoPainel,
  Atendimento,
  CanalWhatsApp,
  ConfiguracaoAgente,
  ConfiguracaoEmbeddedSignup,
  ConversaDetalhe,
  ConversaResumo, // usado por atualizarConversa (renomear/fixar)
  IntegracaoSaida,
  ItemDeConhecimento,
  PainelDados,
  PreviaDoTemplate,
  Setor,
  StatusAtendimento,
  TemplateWhatsApp,
} from "./tipos";

// Endereço do backend. Em desenvolvimento local aponta para
// http://localhost:8000; em produção, é sobrescrito pela variável de
// ambiente NEXT_PUBLIC_API_URL definida no docker-compose.yml — lá ela
// vem em branco de propósito (""), porque o Caddy serve o frontend e o
// backend sob o MESMO endereço público (ver infra/caddy/Caddyfile), então
// um caminho relativo como "/api/atendimentos" já chega no lugar certo
// sozinho. Usamos "??" (e não "||") para diferenciar "variável não
// definida" (undefined, cai no localhost de desenvolvimento) de "variável
// definida como string vazia de propósito" (mantém vazio, ou seja, relativo).
const URL_BASE_API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ErroDaApi extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function obterToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("token_agente_atendimento");
}

export function salvarToken(token: string): void {
  window.localStorage.setItem("token_agente_atendimento", token);
}

export function limparToken(): void {
  window.localStorage.removeItem("token_agente_atendimento");
}

export function estaAutenticado(): boolean {
  return obterToken() !== null;
}

/**
 * Função central que faz a chamada HTTP de fato: monta a URL completa,
 * inclui o token de autenticação (quando existe) e trata erros de forma
 * padronizada, para que cada função de API abaixo fique bem enxuta.
 */
async function chamarApi<T>(
  caminho: string,
  opcoes: { metodo?: string; corpo?: unknown; comoFormulario?: FormData } = {}
): Promise<T> {
  const cabecalhos: Record<string, string> = {};
  const token = obterToken();
  if (token) cabecalhos["Authorization"] = `Bearer ${token}`;

  let corpoRequisicao: BodyInit | undefined;
  if (opcoes.comoFormulario) {
    corpoRequisicao = opcoes.comoFormulario; // o navegador define o Content-Type automaticamente
  } else if (opcoes.corpo !== undefined) {
    cabecalhos["Content-Type"] = "application/json";
    corpoRequisicao = JSON.stringify(opcoes.corpo);
  }

  const resposta = await fetch(`${URL_BASE_API}${caminho}`, {
    method: opcoes.metodo || "GET",
    headers: cabecalhos,
    body: corpoRequisicao,
  });

  if (!resposta.ok) {
    const detalhe = await resposta.json().catch(() => ({ detail: resposta.statusText }));
    throw new ErroDaApi(resposta.status, detalhe.detail || "Erro inesperado ao chamar a API.");
  }

  if (resposta.status === 204) return undefined as T;
  return resposta.json();
}

// --- Autenticação ---
export async function cadastrarEmpresa(dados: {
  nome_fantasia: string;
  nome_do_responsavel: string;
  email: string;
  senha: string;
}) {
  return chamarApi<{ token_de_acesso: string; nome_fantasia: string; nome_do_agente: string }>(
    "/api/autenticacao/cadastrar",
    { metodo: "POST", corpo: dados }
  );
}

export async function entrar(dados: { email: string; senha: string }) {
  return chamarApi<{ token_de_acesso: string; nome_fantasia: string; nome_do_agente: string }>(
    "/api/autenticacao/entrar",
    { metodo: "POST", corpo: dados }
  );
}

// --- Dashboard ---
// `periodo` é opcional — sem ele, o backend devolve todo o histórico (ver
// backend/app/rotas/painel.py para a regra de qual data cada cartão usa).
export async function obterPainel(periodo?: { dataInicio?: string; dataFim?: string }) {
  const parametros = new URLSearchParams();
  if (periodo?.dataInicio) parametros.set("data_inicio", periodo.dataInicio);
  if (periodo?.dataFim) parametros.set("data_fim", periodo.dataFim);
  const query = parametros.toString() ? `?${parametros.toString()}` : "";
  return chamarApi<PainelDados>(`/api/painel${query}`);
}

// --- Base de Atendimentos ---
// Sem criação manual nem importação em massa: um Atendimento só nasce de
// um jeito, automaticamente, na primeira mensagem recebida de um número
// novo (ver backend/app/agente/orquestrador.py).
export async function listarAtendimentos(filtros?: { status?: StatusAtendimento; busca?: string }) {
  const parametros = new URLSearchParams();
  if (filtros?.status) parametros.set("status_filtro", filtros.status);
  if (filtros?.busca) parametros.set("busca", filtros.busca);
  const query = parametros.toString() ? `?${parametros.toString()}` : "";
  return chamarApi<Atendimento[]>(`/api/atendimentos${query}`);
}

export async function editarAtendimento(id: number, dados: Partial<Atendimento>) {
  return chamarApi<Atendimento>(`/api/atendimentos/${id}`, { metodo: "PUT", corpo: dados });
}

export async function excluirAtendimento(id: number) {
  return chamarApi<void>(`/api/atendimentos/${id}`, { metodo: "DELETE" });
}

// --- Conversas ---
export async function listarConversas() {
  return chamarApi<ConversaResumo[]>("/api/conversas");
}

export async function obterConversa(id: number) {
  return chamarApi<ConversaDetalhe>(`/api/conversas/${id}`);
}

// Menu de três pontinhos da aba Conversas: renomear (apelido) e/ou
// fixar/desafixar — só os campos passados aqui são alterados no backend.
export async function atualizarConversa(id: number, dados: { apelido?: string | null; fixada?: boolean }) {
  return chamarApi<ConversaResumo>(`/api/conversas/${id}`, { metodo: "PATCH", corpo: dados });
}

export async function excluirConversa(id: number) {
  return chamarApi<void>(`/api/conversas/${id}`, { metodo: "DELETE" });
}

// --- Configuração do Agente ---
export async function obterConfiguracaoDoAgente() {
  return chamarApi<ConfiguracaoAgente>("/api/configuracao-agente");
}

export async function salvarConfiguracaoDoAgente(dados: ConfiguracaoAgente) {
  return chamarApi<ConfiguracaoAgente>("/api/configuracao-agente", { metodo: "PUT", corpo: dados });
}

// --- Setores ---
// A lista real de destinos válidos que a ferramenta encaminhar_para_setor
// (agente do backend) confere contra o guardrail antes de agir.
export async function listarSetores() {
  return chamarApi<Setor[]>("/api/setores");
}

export async function cadastrarSetor(dados: { nome: string; contato_nome: string; contato_telefone: string }) {
  return chamarApi<Setor>("/api/setores", { metodo: "POST", corpo: dados });
}

export async function editarSetor(
  id: number,
  dados: { nome: string; contato_nome: string; contato_telefone: string }
) {
  return chamarApi<Setor>(`/api/setores/${id}`, { metodo: "PUT", corpo: dados });
}

export async function removerSetor(id: number) {
  return chamarApi<void>(`/api/setores/${id}`, { metodo: "DELETE" });
}

// --- Base de Conhecimento ---
// O embedding de cada item é gerado no backend na hora de salvar — o
// frontend só lida com título e conteúdo em texto livre.
export async function listarItensDeConhecimento() {
  return chamarApi<ItemDeConhecimento[]>("/api/base-de-conhecimento");
}

export async function cadastrarItemDeConhecimento(dados: { titulo: string; conteudo: string }) {
  return chamarApi<ItemDeConhecimento>("/api/base-de-conhecimento", { metodo: "POST", corpo: dados });
}

export async function editarItemDeConhecimento(id: number, dados: { titulo: string; conteudo: string }) {
  return chamarApi<ItemDeConhecimento>(`/api/base-de-conhecimento/${id}`, { metodo: "PUT", corpo: dados });
}

export async function removerItemDeConhecimento(id: number) {
  return chamarApi<void>(`/api/base-de-conhecimento/${id}`, { metodo: "DELETE" });
}

// --- Canais (conexão do WhatsApp) ---
// Dados que o botão "Conectar WhatsApp" precisa para abrir a janela de
// login da Meta (ver biblioteca/embeddedSignup.ts, que usa esta função).
export async function obterConfiguracaoEmbeddedSignup() {
  return chamarApi<ConfiguracaoEmbeddedSignup>("/api/canais/whatsapp/config");
}

export async function obterCanalWhatsApp() {
  return chamarApi<CanalWhatsApp | null>("/api/canais/whatsapp");
}

// Chamada depois que a pessoa termina o login na janela da Meta: envia o
// código de autorização pro backend concluir a conexão de verdade (troca
// o código por um token de acesso, descobre o WABA/número e inscreve o
// webhook). id_numero_telefone/id_waba são opcionais — só vêm preenchidos
// se o "postMessage" da Meta chegou a tempo (recado instável, ver
// biblioteca/embeddedSignup.ts); quando não vêm, o backend descobre os
// dois sozinho a partir do código.
export async function conectarCanalWhatsApp(dados: {
  codigo_de_autorizacao: string;
  redirect_uri: string;
  id_numero_telefone?: string;
  id_waba?: string;
}) {
  return chamarApi<CanalWhatsApp>("/api/canais/whatsapp/conectar", { metodo: "POST", corpo: dados });
}

// Conexão manual — só some efeito quando `mostrar_conexao_manual` (ver
// obterConfiguracaoEmbeddedSignup) vier true para a conta logada.
export async function conectarCanalWhatsAppManualmente(dados: {
  id_numero_telefone_meta: string;
  id_waba_meta?: string;
  numero_exibicao?: string;
  token_de_acesso: string;
}) {
  return chamarApi<CanalWhatsApp>("/api/canais/whatsapp/manual", { metodo: "PUT", corpo: dados });
}

// Os quatro templates deste projeto são submetidos e consultados
// automaticamente via Graph API (ver
// backend/app/integracoes_externas/meta_templates.py) — a empresa não
// precisa visitar o painel da Meta para nada disso, e nenhum deles é
// editável (sem "criarTemplateDeAbordagem" como nos outros dois projetos
// da linhagem — este agente nunca inicia contato).

// Template de NOTIFICAÇÃO ao setor humano (primeiro encaminhamento).
export async function obterPreviaDoTemplateDeNotificacao() {
  return chamarApi<PreviaDoTemplate>("/api/canais/whatsapp/template-notificacao/previa");
}

export async function obterStatusDoTemplateDeNotificacao() {
  return chamarApi<TemplateWhatsApp>("/api/canais/whatsapp/template-notificacao");
}

export async function criarTemplateDeNotificacao() {
  return chamarApi<TemplateWhatsApp>("/api/canais/whatsapp/template-notificacao", { metodo: "POST" });
}

// Template de REENCAMINHAMENTO (a partir do segundo encaminhamento — um
// atendimento que já tinha sido passado adiante volta com algo novo):
// separado do template de notificação acima porque aquele abre com "Novo
// atendimento aguardando retorno", o que não faz sentido pra um
// atendimento que o setor já está tratando.
export async function obterPreviaDoTemplateDeReencaminhamento() {
  return chamarApi<PreviaDoTemplate>("/api/canais/whatsapp/template-reencaminhamento/previa");
}

export async function obterStatusDoTemplateDeReencaminhamento() {
  return chamarApi<TemplateWhatsApp>("/api/canais/whatsapp/template-reencaminhamento");
}

export async function criarTemplateDeReencaminhamento() {
  return chamarApi<TemplateWhatsApp>("/api/canais/whatsapp/template-reencaminhamento", { metodo: "POST" });
}

// Template de ATENÇÃO (guardrail de entrada detectou tentativa de
// manipulação do agente durante a conversa).
export async function obterPreviaDoTemplateDeAtencao() {
  return chamarApi<PreviaDoTemplate>("/api/canais/whatsapp/template-atencao/previa");
}

export async function obterStatusDoTemplateDeAtencao() {
  return chamarApi<TemplateWhatsApp>("/api/canais/whatsapp/template-atencao");
}

export async function criarTemplateDeAtencao() {
  return chamarApi<TemplateWhatsApp>("/api/canais/whatsapp/template-atencao", { metodo: "POST" });
}

// Template de REENGAJAMENTO (atendimento em silêncio há 3+ dias no meio
// de uma conversa em aberto).
export async function obterPreviaDoTemplateDeReengajamento() {
  return chamarApi<PreviaDoTemplate>("/api/canais/whatsapp/template-reengajamento/previa");
}

export async function obterStatusDoTemplateDeReengajamento() {
  return chamarApi<TemplateWhatsApp>("/api/canais/whatsapp/template-reengajamento");
}

export async function criarTemplateDeReengajamento() {
  return chamarApi<TemplateWhatsApp>("/api/canais/whatsapp/template-reengajamento", { metodo: "POST" });
}

// --- Integrações: conexão de saída (envia os dados do Dashboard pra fora) ---
// Diferente dos outros dois projetos da linhagem, não existe aqui uma
// metade de entrada (CRM externo) — este agente é receptivo, todo
// Atendimento nasce da própria mensagem do cliente no WhatsApp.
export async function listarIntegracoesDeSaida() {
  return chamarApi<IntegracaoSaida[]>("/api/integracoes/saida");
}

export async function cadastrarIntegracaoDeSaida(dados: { nome_da_conexao: string; url_webhook: string; chave_api?: string }) {
  return chamarApi<IntegracaoSaida>("/api/integracoes/saida", { metodo: "POST", corpo: dados });
}

export async function removerIntegracaoDeSaida(id: number) {
  return chamarApi<void>(`/api/integracoes/saida/${id}`, { metodo: "DELETE" });
}

export async function enviarDadosDoDashboardAgora(id: number) {
  return chamarApi<IntegracaoSaida>(`/api/integracoes/saida/${id}/enviar-agora`, { metodo: "POST" });
}

// --- Tempo real (WebSocket da aba Conversas) ---
/**
 * Monta o endereço do WebSocket usado pela aba Conversas para receber
 * atualizações em tempo real (ver backend/app/rotas/tempo_real.py).
 * Reaproveita o mesmo endereço configurado para a API, só trocando o
 * protocolo de "http(s)" para "ws(s)", e inclui o token de autenticação
 * como parâmetro de URL — WebSockets do navegador não permitem enviar o
 * cabeçalho "Authorization" como as chamadas HTTP normais.
 */
// --- Painel único de templates (aba Canais) ---
// Lista os templates do agente com status real na Meta, gera um rascunho do
// template de abordagem com IA e envia todos para análise num clique (ver
// backend/app/rotas/templates_whatsapp.py).
export async function listarTemplatesDoPainel() {
  return chamarApi<TemplateDoPainel[]>("/api/canais/whatsapp/templates");
}

export async function gerarRascunhoDeTemplateComIa() {
  return chamarApi<RascunhoDeTemplate>("/api/canais/whatsapp/templates/rascunho-ia", { metodo: "POST" });
}

export async function enviarTemplate(chave: string, textoAbordagem: string | null) {
  return chamarApi<ResultadoDoEnvioDeTemplate>("/api/canais/whatsapp/templates/enviar", {
    metodo: "POST",
    corpo: { chave, texto_abordagem: textoAbordagem },
  });
}

export async function enviarTodosOsTemplates(textoAbordagem: string | null) {
  return chamarApi<ResultadoDoEnvioDeTemplate[]>("/api/canais/whatsapp/templates/enviar-todos", {
    metodo: "POST",
    corpo: { texto_abordagem: textoAbordagem },
  });
}

export function obterUrlWebSocketDeConversas(): string | null {
  const token = obterToken();
  if (!token) return null;
  // Quando URL_BASE_API está vazia (produção, mesmo endereço do site),
  // montamos a base a partir da própria página (window.location.origin)
  // antes de trocar "http(s)" por "ws(s)" — assim funciona em qualquer
  // domínio público, sem precisar saber o endereço com antecedência.
  const baseAbsoluta = URL_BASE_API || window.location.origin;
  const urlComProtocoloWs = baseAbsoluta.replace(/^http/, "ws");
  return `${urlComProtocoloWs}/api/tempo-real/conversas?token=${encodeURIComponent(token)}`;
}

/**
 * Monta a URL dos bytes de verdade (foto, vídeo/GIF, áudio, documento) de
 * uma mensagem recebida de um cliente — usada direto como `src`/`href` em
 * tags HTML (`<img>`, `<audio>`, `<video>`, link de download) na aba
 * Conversas. Mesmo motivo do WebSocket acima: essas tags não enviam o
 * cabeçalho "Authorization", então o token vai como parâmetro de URL.
 */
export function obterUrlDaMidiaDaMensagem(idMensagem: number): string | null {
  const token = obterToken();
  if (!token) return null;
  return `${URL_BASE_API}/api/conversas/mensagens/${idMensagem}/midia?token=${encodeURIComponent(token)}`;
}

export { ErroDaApi };

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo é o único lugar do frontend que sabe montar URLs e
// cabeçalhos HTTP. A função interna chamarApi() cuida de anexar o token
// de autenticação e tratar erros; todas as outras funções exportadas
// (cadastrarEmpresa, obterPainel, listarAtendimentos, listarSetores,
// listarItensDeConhecimento, salvarConfiguracaoDoAgente, etc.) são atalhos
// específicos para cada endpoint do backend, e obterUrlWebSocketDeConversas()
// monta o endereço da conexão em tempo real usada pela aba Conversas.
// ==============================================================================

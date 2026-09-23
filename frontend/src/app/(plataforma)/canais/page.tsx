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
// Assim que o número está conectado, aparecem os QUATRO templates
// pré-aprovados que este projeto usa (ver
// backend/app/integracoes_externas/meta_templates.py) — notificação ao
// setor humano, reencaminhamento, atenção e reengajamento. Diferente dos
// outros dois projetos da linhagem, nenhum deles tem uma caixa de texto
// editável: o texto é fixo, só a prévia (com um exemplo) aparece antes de
// confirmar o envio para análise da Meta. Enquanto o status de um
// template ficar "Em análise", a seção correspondente verifica sozinha a
// cada minuto, sem precisar recarregar a página.
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
  criarTemplateDeAtencao,
  criarTemplateDeNotificacao,
  criarTemplateDeReencaminhamento,
  criarTemplateDeReengajamento,
  obterCanalWhatsApp,
  obterConfiguracaoEmbeddedSignup,
  obterPreviaDoTemplateDeAtencao,
  obterPreviaDoTemplateDeNotificacao,
  obterPreviaDoTemplateDeReencaminhamento,
  obterPreviaDoTemplateDeReengajamento,
  obterStatusDoTemplateDeAtencao,
  obterStatusDoTemplateDeNotificacao,
  obterStatusDoTemplateDeReencaminhamento,
  obterStatusDoTemplateDeReengajamento,
} from "@/biblioteca/api";
import {
  abrirJanelaDeConexao,
  escutarMensagensDoEmbeddedSignup,
  obterRedirectUriDoEmbeddedSignup,
  tentarFecharComoJanelaDeCallback,
  type DadosDoEmbeddedSignup,
} from "@/biblioteca/embeddedSignup";
import type { CanalWhatsApp, TemplateWhatsApp } from "@/biblioteca/tipos";

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
    } catch {
      setErro("Não foi possível concluir a conexão com o WhatsApp. Tente novamente.");
    } finally {
      setConectando(false);
    }
  }

  if (carregando) return <p className="text-sm text-slate-500">Carregando canais...</p>;

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <h1 className="text-2xl font-semibold text-marca-escuro">Canais</h1>

      <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <div>
          <h2 className="text-base font-semibold text-marca-escuro">WhatsApp</h2>
          <p className="text-sm text-slate-500">
            Conecte o número de WhatsApp que o agente vai usar para responder os clientes da empresa.
          </p>
        </div>

        {canalWhatsapp && (
          <p className="text-sm text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2">
            Conectado desde {new Date(canalWhatsapp.conectado_em).toLocaleDateString("pt-BR")}
            {canalWhatsapp.numero_exibicao ? ` — número ${canalWhatsapp.numero_exibicao}` : ""}
          </p>
        )}

        {erro && <p className="text-sm text-red-600">{erro}</p>}

        <button
          onClick={aoClicarEmConectar}
          disabled={conectando}
          className="px-4 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700 disabled:opacity-60"
        >
          {conectando ? "Conectando..." : canalWhatsapp ? "Reconectar WhatsApp" : "Conectar WhatsApp"}
        </button>
      </section>

      {canalWhatsapp && (
        <SecaoDeTemplate
          titulo="Template de notificação ao setor"
          descricao="Mensagem que a Meta exige, pré-aprovada, para avisar o setor humano quando um atendimento é encaminhado pela primeira vez — esse contato quase nunca tem uma janela de 24h aberta com o WhatsApp comercial da empresa."
          obterPrevia={obterPreviaDoTemplateDeNotificacao}
          obterStatus={obterStatusDoTemplateDeNotificacao}
          criar={criarTemplateDeNotificacao}
        />
      )}

      {canalWhatsapp && (
        <SecaoDeTemplate
          titulo="Template de reencaminhamento"
          descricao="Mensagem usada a partir do SEGUNDO encaminhamento em diante — quando um atendimento que já tinha sido passado adiante volta com algo novo."
          obterPrevia={obterPreviaDoTemplateDeReencaminhamento}
          obterStatus={obterStatusDoTemplateDeReencaminhamento}
          criar={criarTemplateDeReencaminhamento}
        />
      )}

      {canalWhatsapp && (
        <SecaoDeTemplate
          titulo="Template de atenção"
          descricao="Mensagem usada quando o guardrail de entrada detecta uma tentativa de manipulação do agente durante a conversa — avisa o setor humano para revisar o atendimento antes de tratá-lo como comum."
          obterPrevia={obterPreviaDoTemplateDeAtencao}
          obterStatus={obterStatusDoTemplateDeAtencao}
          criar={criarTemplateDeAtencao}
        />
      )}

      {canalWhatsapp && (
        <SecaoDeTemplate
          titulo="Template de reengajamento"
          descricao="Mensagem que a Meta exige, pré-aprovada, para o agente conseguir retomar contato com um atendimento que já estava numa conversa de verdade mas ficou 3 dias ou mais sem responder — sem ela, esse atendimento fica parado para sempre, já que a janela de 24h também fecha nesse caso."
          obterPrevia={obterPreviaDoTemplateDeReengajamento}
          obterStatus={obterStatusDoTemplateDeReengajamento}
          criar={criarTemplateDeReengajamento}
        />
      )}

      {mostrarConexaoManual && (
        <FormularioDeConexaoManual canalAtual={canalWhatsapp} aoConectar={setCanalWhatsapp} />
      )}
    </div>
  );
}

const RÓTULOS_DE_STATUS_DO_TEMPLATE: Record<string, { texto: string; cor: string }> = {
  PENDING: { texto: "Em análise pela Meta", cor: "text-amber-600 bg-amber-50 border-amber-200" },
  APPROVED: { texto: "Aprovado", cor: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  REJECTED: { texto: "Rejeitado pela Meta", cor: "text-red-600 bg-red-50 border-red-200" },
};

// Enquanto o template estiver "Em análise", a tela pergunta de novo para
// a Meta a cada 60 segundos — é a forma mais simples de o status
// atualizar sozinho na tela sem precisar recarregar a página. (Existe uma
// forma mais sofisticada — a Meta consegue avisar o nosso webhook em
// tempo real quando o status muda — mas isso exigiria assinar mais um
// campo no painel da Meta; essa verificação periódica já resolve bem o
// caso de uso, sem depender de configuração extra.)
const INTERVALO_DE_VERIFICACAO_MS = 60_000;

/**
 * Mostra o status de um dos quatro templates deste projeto e o fluxo de
 * criação com prévia: um botão monta o texto pronto (com um exemplo) para
 * conferência, e só então a pessoa confirma o envio de verdade para
 * análise da Meta. Diferente do Agente Comercial SDR e do Agente de
 * Cobrança, nenhum template deste projeto tem uma caixa de texto
 * editável — o conteúdo é fixo (ver backend/app/esquemas/canal.py),
 * então os QUATRO templates (notificação, reencaminhamento, atenção,
 * reengajamento) reaproveitam este mesmo componente, só trocando título,
 * descrição e as três funções de API.
 */
function SecaoDeTemplate({
  titulo,
  descricao,
  obterPrevia,
  obterStatus,
  criar,
}: {
  titulo: string;
  descricao: string;
  obterPrevia: () => Promise<{ texto: string }>;
  obterStatus: () => Promise<TemplateWhatsApp>;
  criar: () => Promise<TemplateWhatsApp>;
}) {
  const [template, setTemplate] = useState<TemplateWhatsApp | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [previa, setPrevia] = useState<string | null>(null);
  const [carregandoPrevia, setCarregandoPrevia] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    obterStatus()
      .then(setTemplate)
      .finally(() => setCarregando(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (template?.status !== "PENDING") return;
    const intervalo = setInterval(() => {
      obterStatus().then(setTemplate);
    }, INTERVALO_DE_VERIFICACAO_MS);
    return () => clearInterval(intervalo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template?.status]);

  async function aoPedirPrevia() {
    setErro(null);
    setCarregandoPrevia(true);
    try {
      const resultado = await obterPrevia();
      setPrevia(resultado.texto);
    } catch {
      setErro("Não foi possível montar a prévia do template. Tente novamente.");
    } finally {
      setCarregandoPrevia(false);
    }
  }

  async function aoConfirmarEnvio() {
    setErro(null);
    setEnviando(true);
    try {
      const resultado = await criar();
      setTemplate(resultado);
      setPrevia(null);
    } catch {
      setErro("Não foi possível enviar o template para análise da Meta. Tente novamente.");
    } finally {
      setEnviando(false);
    }
  }

  if (carregando) return null;

  const status = template?.status ? RÓTULOS_DE_STATUS_DO_TEMPLATE[template.status] : null;
  const podeCriar = !template?.status || template.status === "REJECTED";

  return (
    <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
      <div>
        <h2 className="text-base font-semibold text-marca-escuro">{titulo}</h2>
        <p className="text-sm text-slate-500">{descricao}</p>
      </div>

      {status && (
        <p className={`text-sm border rounded-lg px-4 py-2 ${status.cor}`}>
          {status.texto}
          {template?.status === "PENDING" && " — esta tela verifica sozinha a cada minuto."}
        </p>
      )}

      {erro && <p className="text-sm text-red-600">{erro}</p>}

      {!previa && podeCriar && (
        <button
          onClick={aoPedirPrevia}
          disabled={carregandoPrevia}
          className="px-4 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700 disabled:opacity-60"
        >
          {carregandoPrevia
            ? "Montando prévia..."
            : template?.status === "REJECTED"
              ? "Ver prévia e enviar novamente"
              : "Ver prévia do template"}
        </button>
      )}

      {previa && (
        <div className="border border-slate-200 rounded-lg p-4 space-y-3 bg-slate-50">
          <p className="text-xs text-slate-500">
            É exatamente isto que vai ser enviado à Meta para análise — confira antes de confirmar:
          </p>
          <p className="text-sm text-slate-800 bg-white border border-slate-200 rounded-lg p-3">{previa}</p>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setPrevia(null)}
              disabled={enviando}
              className="px-4 py-2 text-sm text-slate-600 hover:text-marca-700"
            >
              Cancelar
            </button>
            <button
              onClick={aoConfirmarEnvio}
              disabled={enviando}
              className="px-4 py-2 text-sm rounded-lg bg-marca-600 text-white hover:bg-marca-700 disabled:opacity-60"
            >
              {enviando ? "Enviando..." : "Confirmar e enviar para análise"}
            </button>
          </div>
        </div>
      )}
    </section>
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
// Este arquivo implementa a aba Canais: mostra o status da conexão do
// WhatsApp já salva e o botão "Conectar WhatsApp", que abre a janela de
// login da Meta (via biblioteca/embeddedSignup.ts), junta o código de
// autorização com o número/WABA escolhidos e envia tudo para o backend
// concluir a conexão (POST /api/canais/whatsapp/conectar). Uma vez
// conectado, o componente reaproveitável SecaoDeTemplate aparece quatro
// vezes — notificação, reencaminhamento, atenção e reengajamento — cada
// uma mostrando o status do template (verificando sozinha a cada minuto
// enquanto estiver "Em análise") e um fluxo de prévia (sem edição, texto
// fixo) antes de confirmar o envio de verdade para a Meta. Para a única
// conta autorizada pelo backend, mais um formulário
// (FormularioDeConexaoManual) permite colar credenciais existentes
// diretamente — usado só enquanto não há um número comercial disponível.
// Sem seção de integrações de calendário — não existe desfecho "Agendar
// reunião" neste domínio.
// ==============================================================================

// ==============================================================================
// ARQUIVO: biblioteca/embeddedSignup.ts
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Este arquivo isola toda a conversa com a janela de login do WhatsApp
// Embedded Signup da Meta. É aqui que mora a parte "esquisita" do fluxo:
//
//   1. abrirJanelaDeConexao() -> abre a janela de login de verdade
//      (window.open direto para o diálogo OAuth da Meta, com o parâmetro
//      "extras" que ativa a tela de escolha de número/WABA), espera a
//      pessoa terminar e devolve o código de autorização.
//   2. tentarFecharComoJanelaDeCallback() -> chamada pela PRÓPRIA página
//      (app/(plataforma)/canais/page.tsx) assim que ela carrega: se essa
//      instância da página é a janela popup recebendo o código de volta
//      (redirect_uri aponta pra ela mesma), repassa o código pra janela
//      que a abriu via postMessage e se fecha sozinha.
//   3. escutarMensagensDoEmbeddedSignup() -> a janela de login da Meta,
//      enquanto a pessoa está conectando o WhatsApp dela, manda o
//      resultado (o número e a WABA escolhidos) através de um "recado"
//      entre janelas (postMessage) — chega ANTES do código, direto da
//      página da Meta (não depende de nada deste arquivo). Esta função
//      "escuta" esse recado.
//
// HISTÓRICO — por que não usamos mais o SDK JavaScript da Meta
// (window.FB.login): a chamada FB.login() por trás das cortinas tenta usar
// o FedCM do Chrome (API nativa de login federado) para pedir o token, e
// o SDK da Meta tem um bug real e atual com isso — o parâmetro "nonce" é
// passado fora do lugar esperado pelo Chrome, o pedido de token falha
// ("Error retrieving a token.") e a Meta devolve um erro genérico
// ("Este app precisa pelo menos de uma supported permission" ou "A
// conexão foi cancelada"), mesmo com a conta, as permissões e a
// configuração 100% corretas do lado do app. Confirmado nesta sessão: o
// MESMO login, pela MESMA conta e configuração, completado com sucesso
// (autorização + escolha de número) quando feito por navegação direta ao
// diálogo OAuth da Meta (sem passar pelo FB.login()) — por isso a troca
// para abrir a janela "na mão" aqui, sem depender do SDK JavaScript da
// Meta (connect.facebook.net) nem do FedCM.
//
// Quem usa este arquivo é só a página app/(plataforma)/canais/page.tsx —
// as outras telas do sistema não precisam saber que isso existe.
// ==============================================================================

/** O que a janela de conexão da Meta informa sobre o número/WABA escolhidos. */
export interface DadosDoEmbeddedSignup {
  idNumeroDeTelefone: string;
  idWaba: string;
}

// Nome da mensagem que a JANELA POPUP (rodando esta mesma página, depois
// de ser redirecionada de volta pela Meta com o código na URL) manda para
// a janela original que a abriu — só um identificador para diferenciar
// esse "recado" dos recados nativos da Meta (tratados à parte, em
// escutarMensagensDoEmbeddedSignup).
const TIPO_DA_MENSAGEM_DE_CODIGO = "agente_atendimento:embedded_signup_code";

/**
 * O `redirect_uri` usado tanto para abrir o diálogo OAuth quanto, depois,
 * para trocar o código pelo token (ver `rotas/canais.py`,
 * `conectar_canal_whatsapp`) — a Meta exige que os dois batem
 * EXATAMENTE, senão recusa a troca com "Error validating verification
 * code". Centralizado aqui (em vez de cada lugar montar a string na mão)
 * justamente para não correr o risco dos dois valores um dia
 * divergirem.
 */
export function obterRedirectUriDoEmbeddedSignup(): string {
  return `${window.location.origin}/canais`;
}

/**
 * Fica "de ouvido em pé" esperando o recado que a janela de conexão da
 * Meta manda quando a pessoa termina de escolher o número/WABA dela. Esse
 * recado vem direto da página da Meta (facebook.com), independente de
 * como a janela foi aberta. Devolve uma função para parar de escutar
 * (chamada quando o componente React sai de tela, para não acumular
 * escutas repetidas).
 */
export function escutarMensagensDoEmbeddedSignup(
  aoReceberDados: (dados: DadosDoEmbeddedSignup) => void
): () => void {
  function tratarMensagem(evento: MessageEvent) {
    // Só aceitamos recados que vieram de verdade do domínio do Facebook —
    // qualquer outra origem é ignorada, por segurança.
    if (!evento.origin.endsWith("facebook.com")) return;

    try {
      const dados = JSON.parse(evento.data);
      if (dados.type !== "WA_EMBEDDED_SIGNUP" || dados.event !== "FINISH") return;

      aoReceberDados({
        idNumeroDeTelefone: dados.data.phone_number_id,
        idWaba: dados.data.waba_id,
      });
    } catch {
      // O Facebook também manda outras mensagens (não relacionadas ao
      // Embedded Signup) por postMessage — mensagens que não são um JSON
      // válido no formato esperado são simplesmente ignoradas.
    }
  }

  window.addEventListener("message", tratarMensagem);
  return () => window.removeEventListener("message", tratarMensagem);
}

/**
 * Abre de fato a janela de login da Meta, já configurada para o fluxo
 * específico de conexão do WhatsApp (não um login comum) — navegando
 * direto para o diálogo OAuth da Meta, sem depender do SDK JavaScript
 * (ver INTRODUÇÃO acima sobre por quê). Devolve o "código de autorização"
 * que o backend vai trocar por um token de acesso de verdade (ver
 * rotas/canais.py), ou null se a pessoa fechou a janela sem terminar.
 */
export function abrirJanelaDeConexao(
  appId: string,
  idConfiguracao: string,
  versaoApi: string
): Promise<string | null> {
  return new Promise((resolver) => {
    // A própria página de Canais serve de "redirect_uri": a Meta manda a
    // janela popup de volta pra cá (com o código na URL) assim que a
    // pessoa termina — e essa mesma instância da página se reconhece como
    // a janela popup (ver tentarFecharComoJanelaDeCallback) e repassa o
    // código pra janela original.
    const redirectUri = obterRedirectUriDoEmbeddedSignup();
    const extras = JSON.stringify({
      setup: {},
      featureType: "whatsapp_embedded_signup",
      sessionInfoVersion: "3",
    });
    const parametros = new URLSearchParams({
      client_id: appId,
      config_id: idConfiguracao,
      response_type: "code",
      override_default_response_type: "true",
      redirect_uri: redirectUri,
      extras,
    });
    const url = `https://www.facebook.com/${versaoApi}/dialog/oauth/?${parametros.toString()}`;

    const janela = window.open(url, "conexao-whatsapp", "width=620,height=780");
    if (!janela) {
      // O navegador bloqueou a janela (ex.: não foi um clique direto da
      // pessoa) — nada a fazer além de avisar que não deu certo.
      resolver(null);
      return;
    }

    let jaResolvida = false;

    function tratarMensagem(evento: MessageEvent) {
      if (evento.source !== janela) return;
      if (!evento.data || evento.data.type !== TIPO_DA_MENSAGEM_DE_CODIGO) return;
      finalizar(evento.data.codigo ?? null);
    }

    // Se a pessoa fechar a janela na mão (ex.: clicar no X) sem nunca
    // concluir, nenhuma mensagem chega — por isso verificamos
    // periodicamente se ela foi fechada, para não deixar a Promise
    // pendurada pra sempre.
    const verificador = setInterval(() => {
      if (janela.closed) finalizar(null);
    }, 500);

    function finalizar(codigo: string | null) {
      if (jaResolvida) return;
      jaResolvida = true;
      clearInterval(verificador);
      window.removeEventListener("message", tratarMensagem);
      resolver(codigo);
    }

    window.addEventListener("message", tratarMensagem);
  });
}

/**
 * Chamada assim que app/(plataforma)/canais/page.tsx carrega, antes de
 * qualquer outra coisa: reconhece se ESTA instância da página é, na
 * verdade, a janela popup que a Meta acabou de redirecionar de volta (com
 * "?code=..." na URL, depois que a pessoa terminou de escolher o
 * número/WABA dela). Se for, repassa o código pra janela original (que
 * está esperando, dentro de abrirJanelaDeConexao) e fecha a si mesma.
 * Devolve true nesse caso (a página que chamou não deve renderizar mais
 * nada, só está de passagem). Numa visita normal (não veio de dentro do
 * popup), window.opener é sempre null e a função não faz nada.
 */
export function tentarFecharComoJanelaDeCallback(): boolean {
  if (typeof window === "undefined" || !window.opener) return false;

  const codigo = new URLSearchParams(window.location.search).get("code");
  if (!codigo) return false;

  window.opener.postMessage({ type: TIPO_DA_MENSAGEM_DE_CODIGO, codigo }, window.location.origin);
  window.close();
  return true;
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo concentra a integração com o WhatsApp Embedded Signup da
// Meta, SEM depender do SDK JavaScript dela (connect.facebook.net/FB.login
// — abandonado por um bug real do SDK com o FedCM do Chrome, ver
// INTRODUÇÃO): abrirJanelaDeConexao monta a URL do diálogo OAuth na mão e
// abre a janela via window.open, tentarFecharComoJanelaDeCallback deixa a
// própria página de Canais reconhecer quando ela é essa janela popup
// recebendo o código de volta (e repassá-lo, fechando-se sozinha), e
// escutarMensagensDoEmbeddedSignup captura o número/WABA escolhidos,
// enviados pela janela da Meta via postMessage nativo (independente de
// como a janela foi aberta). A página app/(plataforma)/canais/page.tsx
// combina essas três peças para montar o botão "Conectar WhatsApp".
// ==============================================================================

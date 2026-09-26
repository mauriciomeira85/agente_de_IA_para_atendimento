# ==============================================================================
# ARQUIVO: integracoes_externas/meta_embedded_signup.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa o lado do BACKEND da conexão "um clique" do
# WhatsApp — o recurso da Meta chamado "WhatsApp Embedded Signup". Em vez
# de a empresa precisar entrar no painel do Meta for Developers e copiar
# manualmente o Phone Number ID, o WABA ID e um token de acesso (o jeito
# antigo, ainda documentado no README como alternativa), ela clica em
# "Conectar WhatsApp" na aba Canais, faz login com a conta do Facebook da
# empresa numa janela da própria Meta, e escolhe (ou cria) o número que
# quer usar. No final desse processo, o navegador recebe só um "código de
# autorização" — é este arquivo que troca esse código pelas informações
# reais de que o backend precisa para enviar mensagens:
#
#   1. trocar_codigo_por_token   -> troca o código pelo token de acesso
#   2. descobrir_waba_e_numero   -> descobre o WABA/número escolhidos DIRETO
#                                    na Graph API, a partir do próprio token
#                                    (ver nota abaixo sobre por que isso
#                                    existe, em vez de só confiar no
#                                    "postMessage" da Meta)
#   3. obter_numero_de_exibicao  -> descobre o número de telefone (formato
#                                    exibição) a partir do Phone Number ID
#   4. inscrever_webhook_da_waba -> avisa a Meta para mandar as mensagens
#                                    recebidas por esse número para o NOSSO
#                                    webhook central (ver rotas/canais.py)
#   5. registrar_numero_de_telefone -> ativa o número na Cloud API de fato
#                                    (sem isso, TODO envio falha com o erro
#                                    "Account not registered" — descoberto
#                                    em testes reais com o número conectado
#                                    manualmente, ver rotas/canais.py)
#
# HISTÓRICO — por que existe descobrir_waba_e_numero: a documentação da
# Meta descreve um "postMessage" (evento `WA_EMBEDDED_SIGNUP`/`FINISH`) que
# a própria janela de login manda pro navegador com o WABA/número
# escolhidos, ANTES do código de autorização chegar. Na prática, esse
# recado é frágil e falha silenciosamente em vários casos reais (terceiros
# relatam exatamente isso: "o código chega, o evento FINISH nunca chega") —
# confirmado neste projeto em teste real: o código de autorização chegava
# certinho, mas o WABA/número nunca chegavam, deixando a conexão sempre
# incompleta. Em vez de depender desse mecanismo, descobrir_waba_e_numero
# usa só o código de autorização (que SEMPRE chega, é parte do fluxo padrão
# de OAuth) pra perguntar direto à Graph API quais WABAs o token recém-
# trocado tem permissão de gerenciar (`/debug_token`, campo
# `granular_scopes`) e qual número de telefone está registrado nela
# (`/{waba_id}/phone_numbers`) — dado que a própria Meta já sabe e nem
# precisaria mandar de volta por um canal tão instável.
# ==============================================================================

from typing import Any

import httpx
import structlog

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()
logger = structlog.get_logger(__name__)

URL_BASE_GRAPH_API = f"https://graph.facebook.com/{configuracoes.meta_versao_api}"


async def trocar_codigo_por_token(codigo_de_autorizacao: str, redirect_uri: str) -> str:
    """
    Troca o código de autorização recebido pelo navegador (ao final da
    janela de login da Meta) por um token de acesso de verdade. Como
    escolhemos, ao criar a configuração de login no painel da Meta, o tipo
    "token de acesso do usuário do sistema" com validade "Nunca", o token
    devolvido aqui já nasce permanente — não precisa de nenhuma etapa
    extra de renovação.

    Essa troca exige o "App Secret" (meta_app_secret) — por isso ela só
    pode acontecer aqui no backend, nunca no navegador: expor o App Secret
    no frontend permitiria qualquer pessoa se passar pelo nosso app.

    `redirect_uri` PRECISA ser exatamente igual ao usado por
    `abrirJanelaDeConexao` (frontend/src/biblioteca/embeddedSignup.ts) na
    hora de abrir o diálogo OAuth — a Meta recusa a troca com
    "Error validating verification code [...] redirect_uri" se os dois
    não baterem, mesmo o valor não fazendo mais nenhum papel funcional
    nesse ponto (a Meta só usa isso pra confirmar que quem está trocando o
    código é o mesmo lugar que abriu o login, uma proteção padrão de
    OAuth). Por isso o frontend manda esse valor de volta pro backend
    junto com o código, em vez do backend tentar adivinhar/reconstruir
    (ver `esquemas/canal.py`, `ConectarCanalWhatsAppEntrada.redirect_uri`).
    """
    url = f"{URL_BASE_GRAPH_API}/oauth/access_token"
    parametros = {
        "client_id": configuracoes.meta_app_id,
        "client_secret": configuracoes.meta_app_secret,
        "code": codigo_de_autorizacao,
        "redirect_uri": redirect_uri,
    }

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.get(url, params=parametros)

    corpo = resposta.json()
    if resposta.status_code >= 400 or "access_token" not in corpo:
        logger.warning("falha_ao_trocar_codigo_por_token", status=resposta.status_code, corpo=corpo)
        raise ValueError("Não foi possível confirmar a conexão com a Meta. Tente novamente.")

    return corpo["access_token"]


async def _encontrar_waba_ja_conectada_a_este_app(
    cliente: httpx.AsyncClient, ids_de_waba: list[str], token_de_acesso: str
) -> str | None:
    """
    Desempate para quando `granular_scopes` devolve mais de uma WABA (ver
    docstring de descobrir_waba_e_numero, logo abaixo): confere, em cada
    WABA candidata, se o NOSSO app (`configuracoes.meta_app_id`) já está
    na lista de apps inscritos nela (`GET /{waba_id}/subscribed_apps`) —
    sinal forte de que é a mesma WABA que este projeto já usa (o caso mais
    comum na prática: reconectar a mesma WABA de teste compartilhada entre
    sessões/empresas de teste). Só usa esse desempate quando EXATAMENTE
    UMA das candidatas bate — zero ou mais de uma continuam ambíguas
    (devolve None), pela mesma razão de nunca adivinhar: uma WABA de outro
    projeto irmão (SDR, Cobrança) também pode, por acaso, já estar
    inscrita neste mesmo app se algum teste antigo tiver deixado essa
    inscrição pra trás.
    """
    candidatas_ja_conectadas = []
    for id_waba in ids_de_waba:
        resposta = await cliente.get(
            f"{URL_BASE_GRAPH_API}/{id_waba}/subscribed_apps",
            params={"access_token": token_de_acesso},
        )
        if resposta.status_code >= 400:
            continue
        apps_inscritos = resposta.json().get("data", [])
        ids_dos_apps_inscritos = {
            app.get("whatsapp_business_api_data", {}).get("id") for app in apps_inscritos
        }
        if configuracoes.meta_app_id in ids_dos_apps_inscritos:
            candidatas_ja_conectadas.append(id_waba)

    if len(candidatas_ja_conectadas) == 1:
        return candidatas_ja_conectadas[0]
    return None


async def _listar_wabas_dos_negocios_do_token(cliente: httpx.AsyncClient, token_de_acesso: str) -> list[str]:
    """
    Lista as WABAs (próprias e de clientes) de todos os portfólios
    empresariais que o token alcança: `/me/businesses` e, para cada negócio,
    `/{id}/owned_whatsapp_business_accounts` e
    `/{id}/client_whatsapp_business_accounts`. Só é usada quando
    `/debug_token` não traz `target_ids` (permissão concedida para todos os
    ativos). Precisa de `business_management` no token — sem essa permissão
    a Meta responde "(#100) Missing Permission" e a função devolve lista
    vazia (quem chama trata como "não deu para descobrir").
    """
    resposta = await cliente.get(
        f"{URL_BASE_GRAPH_API}/me/businesses",
        params={"access_token": token_de_acesso, "fields": "id", "limit": 100},
    )
    if resposta.status_code >= 400:
        logger.warning("falha_ao_listar_negocios_do_token", status=resposta.status_code, corpo=resposta.text)
        return []

    ids_de_waba: list[str] = []
    for negocio in resposta.json().get("data", []):
        for aresta in ("owned_whatsapp_business_accounts", "client_whatsapp_business_accounts"):
            resposta_wabas = await cliente.get(
                f"{URL_BASE_GRAPH_API}/{negocio['id']}/{aresta}",
                params={"access_token": token_de_acesso, "fields": "id", "limit": 100},
            )
            if resposta_wabas.status_code >= 400:
                continue
            for waba in resposta_wabas.json().get("data", []):
                if waba["id"] not in ids_de_waba:
                    ids_de_waba.append(waba["id"])
    return ids_de_waba


async def descobrir_waba_e_numero(token_de_acesso: str) -> tuple[str, str] | None:
    """
    Descobre sozinho, direto na Graph API, o WABA ID e o Phone Number ID
    que ficaram vinculados a este token — sem depender do "postMessage"
    frágil da Meta (ver INTRODUÇÃO acima). Dois passos:

    1. `/debug_token`: inspeciona o próprio token recém-trocado (usando um
       "token de app", no formato `app_id|app_secret`, que serve só pra
       autorizar a inspeção — não precisa buscar isso em outro lugar) e lê
       `granular_scopes`, a lista de permissões concedidas com os IDs
       específicos de cada uma. Procuramos a entrada de
       `whatsapp_business_management`, cujo `target_ids` é a lista de WABAs
       que a empresa autorizou nesta conexão.
    2. `/{waba_id}/phone_numbers`: lista os números já cadastrados naquela
       WABA — pegamos o primeiro (numa conexão nova via Embedded Signup,
       normalmente há só um, o que a empresa acabou de escolher/criar).

    ATENÇÃO — bug real já causado por isso: quando a conta do Facebook que
    faz login é admin em MAIS DE UM app/WABA da Meta (ex.: a mesma conta
    administra este projeto e outros projetos irmãos — ver Memoria.md),
    `target_ids` vem com TODAS as WABAs às quais aquela conta tem acesso,
    não só a desta conexão. Pegar `target_ids[0]` às cegas já conectou
    silenciosamente uma empresa à WABA de OUTRO projeto (mensagens reais
    indo pro webhook errado, sem erro nenhum). Por isso, se houver mais de
    um `target_id`, a função tenta um desempate seguro primeiro (ver
    `_encontrar_waba_ja_conectada_a_este_app`, acima) — só se ele também
    falhar é que recusa de vez e devolve `None`.

    Bug real #2 relacionado, encontrado em teste: como o `postMessage`
    nativo da Meta NUNCA chega de verdade com este fluxo (ver INTRODUÇÃO
    do arquivo), toda conexão passa OBRIGATORIAMENTE por aqui — então, com
    uma conta admin de múltiplos projetos, a recusa pura (sem desempate)
    bloqueava QUALQUER conexão nova pra sempre, sem "tentar de novo"
    nunca resolver.

    Devolve `None` se não conseguir descobrir nenhum dos dois (ex.: a
    permissão não foi concedida, a WABA ainda não tem número nenhum, ou há
    ambiguidade entre múltiplas WABAs) — quem chama decide o que fazer
    nesse caso.
    """
    token_de_app = f"{configuracoes.meta_app_id}|{configuracoes.meta_app_secret}"

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta_debug = await cliente.get(
            f"{URL_BASE_GRAPH_API}/debug_token",
            params={"input_token": token_de_acesso, "access_token": token_de_app},
        )
        if resposta_debug.status_code >= 400:
            logger.warning("falha_ao_inspecionar_token", status=resposta_debug.status_code, corpo=resposta_debug.text)
            return None

        escopos: list[dict[str, Any]] = resposta_debug.json().get("data", {}).get("granular_scopes", [])
        ids_de_waba: list[str] = next(
            (escopo.get("target_ids", []) for escopo in escopos if escopo.get("scope") == "whatsapp_business_management"),
            [],
        )
        if not ids_de_waba:
            # Plano C: `granular_scopes` sem `target_ids` quer dizer que a
            # permissão vale para TODOS os ativos (a Meta omite a lista nesse
            # caso) — bug real encontrado no teste do Cobrança em 24/09/2026:
            # o código chegava, o token vinha certo, mas sem nenhuma WABA
            # listada. Aí listamos nós mesmos as WABAs dos negócios que o
            # token alcança (exige `business_management` na configuração de
            # Embedded Signup — ver Informacoes/Configuracoes_Meta_*.md) e
            # seguimos para o mesmo desempate de sempre, logo abaixo.
            ids_de_waba = await _listar_wabas_dos_negocios_do_token(cliente, token_de_acesso)
            if not ids_de_waba:
                logger.warning("nenhuma_waba_autorizada_no_token", escopos=escopos)
                return None
            logger.info("wabas_descobertas_pelos_negocios_do_token", ids_de_waba=ids_de_waba)

        if len(ids_de_waba) > 1:
            id_waba_desempatada = await _encontrar_waba_ja_conectada_a_este_app(cliente, ids_de_waba, token_de_acesso)
            if id_waba_desempatada is None:
                logger.warning(
                    "ambiguidade_de_waba_no_token_nao_vamos_adivinhar",
                    ids_de_waba=ids_de_waba,
                )
                return None
            logger.info(
                "ambiguidade_de_waba_resolvida_por_ja_estar_inscrita_neste_app",
                id_waba=id_waba_desempatada,
                candidatas=ids_de_waba,
            )
            id_waba = id_waba_desempatada
        else:
            id_waba = ids_de_waba[0]

        resposta_numeros = await cliente.get(
            f"{URL_BASE_GRAPH_API}/{id_waba}/phone_numbers",
            params={"access_token": token_de_acesso},
        )
        if resposta_numeros.status_code >= 400:
            logger.warning(
                "falha_ao_listar_numeros_da_waba", id_waba=id_waba, status=resposta_numeros.status_code, corpo=resposta_numeros.text
            )
            return None

        numeros: list[dict[str, Any]] = resposta_numeros.json().get("data", [])
        if not numeros:
            logger.warning("waba_sem_nenhum_numero_cadastrado", id_waba=id_waba)
            return None

        return id_waba, numeros[0]["id"]


async def obter_numero_de_exibicao(id_numero_telefone: str, token_de_acesso: str) -> str | None:
    """
    Consulta a Graph API para descobrir o número de telefone (no formato
    exibido, ex.: "+55 11 99999-0000") do Phone Number ID que a empresa
    escolheu durante a conexão — assim a interface mostra o número certo
    sem precisar que ninguém digite isso manualmente.
    """
    url = f"{URL_BASE_GRAPH_API}/{id_numero_telefone}"
    parametros = {"fields": "display_phone_number", "access_token": token_de_acesso}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.get(url, params=parametros)

    if resposta.status_code >= 400:
        logger.warning("falha_ao_consultar_numero_de_exibicao", status=resposta.status_code, corpo=resposta.text)
        return None

    dados: dict[str, Any] = resposta.json()
    return dados.get("display_phone_number")


async def inscrever_webhook_da_waba(id_waba: str, token_de_acesso: str) -> bool:
    """
    Avisa a Meta que o NOSSO app deve receber, pelo webhook central já
    configurado (ver infra/cloudflare-webhook e rotas/whatsapp_webhook.py),
    os eventos de mensagem dessa WABA específica. Sem essa inscrição, o
    número fica conectado mas nenhuma mensagem recebida chegaria até a
    plataforma. Essa etapa acontece automaticamente aqui — a empresa não
    precisa configurar nada no painel da Meta para isso funcionar.
    """
    url = f"{URL_BASE_GRAPH_API}/{id_waba}/subscribed_apps"

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.post(url, params={"access_token": token_de_acesso})

    sucesso = resposta.status_code < 400
    if not sucesso:
        logger.warning("falha_ao_inscrever_webhook_da_waba", id_waba=id_waba, status=resposta.status_code, corpo=resposta.text)
    return sucesso


async def registrar_numero_de_telefone(id_numero_telefone: str, token_de_acesso: str) -> str | None:
    """
    Ativa de fato o número na Cloud API da Meta (endpoint POST .../register).
    Sem essa etapa, o número aparece como "conectado" na nossa tela, mas
    QUALQUER tentativa de envio falha com o erro "(#133010) Account not
    registered" — não é um erro sobre o destinatário, é sobre o número que
    está enviando.

    O fluxo "um clique" (Embedded Signup) normalmente já deixa o número
    registrado como parte do próprio login na Meta, mas chamar de novo aqui
    não tem efeito colateral (a Meta apenas confirma que já está
    registrado) — por isso rodamos sempre, tanto depois do Embedded Signup
    quanto depois da conexão manual (que foi onde o problema apareceu de
    verdade: o número de teste conectado manualmente nunca tinha passado
    por essa etapa). O PIN de verificação em duas etapas é fixo porque essa
    função só é usada nos fluxos de conexão automatizados desta plataforma
    (nunca digitado por uma pessoa) — ele só importa se o número precisar
    ser migrado para fora da nossa Cloud API no futuro.

    Devolve None quando deu certo, ou o motivo da falha. A falha mais comum
    é o número já ter a verificação em duas etapas ativa com OUTRO PIN
    (erro 133005): o registro é recusado e nenhuma mensagem sai. Antes o
    motivo só ia para o log e a conexão parecia concluída (26/09/2026).
    """
    url = f"{URL_BASE_GRAPH_API}/{id_numero_telefone}/register"
    corpo = {"messaging_product": "whatsapp", "pin": "123456"}
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.post(url, json=corpo, headers=cabecalhos)

    if resposta.status_code < 400:
        return None
    logger.warning("falha_ao_registrar_numero_de_telefone", status=resposta.status_code, corpo=resposta.text)
    erro = (resposta.json() if resposta.headers.get("content-type", "").startswith("application/json") else {}).get("error", {})
    if erro.get("code") == 133005:
        return (
            "Este número já tem a verificação em duas etapas ativa com outro PIN. Desative-a em WhatsApp Manager → "
            "Números de telefone → Configurações → Verificação em duas etapas e clique em Conectar WhatsApp de novo."
        )
    return f"A Meta não ativou o número na Cloud API: {erro.get('message') or resposta.text[:200]}"


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo concentra as chamadas à Graph API necessárias para deixar um
# número de WhatsApp pronto para uso: trocar_codigo_por_token (código ->
# token de acesso permanente), descobrir_waba_e_numero (WABA/número a
# partir só do token, sem depender do postMessage frágil da Meta —
# desempatando entre WABAs candidatas via
# _encontrar_waba_ja_conectada_a_este_app quando a conta tem acesso a mais
# de uma, e listando as WABAs dos negócios do token via
# _listar_wabas_dos_negocios_do_token quando /debug_token não traz nenhuma
# lista), obter_numero_de_exibicao (número no formato de exibição, para
# mostrar na tela), inscrever_webhook_da_waba (garante que as mensagens
# recebidas por esse número cheguem ao nosso webhook) e
# registrar_numero_de_telefone (ativa o número na Cloud API — sem isso,
# nenhum envio funciona). As rotas que orquestram essas chamadas ficam em
# rotas/canais.py.
# ==============================================================================

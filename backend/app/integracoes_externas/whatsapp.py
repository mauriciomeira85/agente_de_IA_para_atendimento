# ==============================================================================
# ARQUIVO: integracoes_externas/whatsapp.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo isola toda a comunicação com a WhatsApp Cloud API da Meta —
# tanto para ENVIAR mensagens (quando o agente aborda um atendimento ou responde
# algo) quanto para entender o formato das mensagens RECEBIDAS (quando um
# atendimento escreve para o número da empresa).
#
# Um ponto importante: como a plataforma atende várias empresas ao mesmo
# tempo (multi-tenant), toda função aqui recebe o "id_numero_telefone" e o
# "token_de_acesso" como parâmetro — eles vêm da tabela IntegracaoWhatsApp
# daquela empresa específica (ver app/modelos/integracao.py), nunca de uma
# configuração fixa e global.
# ==============================================================================

from typing import Any

import httpx
import structlog

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()
logger = structlog.get_logger(__name__)


class ErroPermanenteDoWhatsApp(ValueError):
    """
    Erro 4xx da Graph API (ex.: "número não está na lista de permissão",
    token inválido, template não aprovado) — a Meta recusou o PEDIDO em
    si, não uma instabilidade momentânea. Tentar de novo com o mesmo
    payload sempre vai falhar do mesmo jeito, então quem chama (ver
    tarefas/tarefas_conversa.py) NÃO deve fazer retry deste erro: bug real
    encontrado em produção onde um erro permanente (número de teste fora
    da lista de destinatários permitidos) fazia o Celery tentar de novo 3
    vezes, cada tentativa reprocessando a mensagem inteira pela IA do zero
    (custo 4x em tokens) e gravando uma mensagem de agente/sistema
    DUPLICADA no banco a cada tentativa — tudo isso sem nenhuma chance real
    de sucesso.
    """


def normalizar_numero_brasileiro(numero: str) -> str:
    """
    Garante o código do país (55) na frente do número, para a WhatsApp
    Cloud API aceitar — a empresa costuma digitar só DDD + número (ex.:
    "77999471710" em vez de "5577999471710") em qualquer campo de telefone
    da plataforma (atendimento, atendente configurado etc.).
    """
    numero_limpo = numero.strip()
    return numero_limpo if numero_limpo.startswith("55") else f"55{numero_limpo}"


def formatar_numero_para_exibicao(numero: str) -> str:
    """
    Formata um telefone brasileiro guardado como DDD+número (ex.:
    "77999471710") no formato de leitura humana "(77) 99947-1710" — usado
    quando o PRÓPRIO AGENTE precisa citar um número de contato dentro de
    uma mensagem ao atendimento (ver agente/prompts.py, mensagem de
    reencaminhamento definitivo). Diferente de normalizar_numero_brasileiro
    (acima), que prepara o número para a API, sem nenhuma formatação
    visual — as duas nunca se confundem porque servem propósitos opostos:
    uma é para a Meta ler, esta é para uma PESSOA ler.
    """
    digitos = "".join(caractere for caractere in numero if caractere.isdigit())
    if digitos.startswith("55") and len(digitos) > 11:
        digitos = digitos[2:]
    if len(digitos) < 10:
        return numero  # não é um DDD+número reconhecível — devolve como veio, sem tentar formatar
    ddd, resto = digitos[:2], digitos[2:]
    if len(resto) == 9:
        return f"({ddd}) {resto[:5]}-{resto[5:]}"
    return f"({ddd}) {resto[:4]}-{resto[4:]}"


async def enviar_mensagem_de_texto(
    id_numero_telefone: str, token_de_acesso: str, numero_destino: str, texto: str
) -> dict[str, Any]:
    """
    Envia uma mensagem de texto simples pela WhatsApp Cloud API.

    Importante (regra de negócio da Meta): isso só funciona de forma livre
    dentro da "janela de atendimento de 24 horas" — ou seja, depois que o
    cliente já mandou pelo menos uma mensagem para a empresa nas últimas 24
    horas. Fora dessa janela (ex.: cliente ficou em silêncio por dias, ou o
    setor humano nunca escreveu primeiro para este número), é obrigatório
    usar um modelo de mensagem (template) pré-aprovado pela Meta — ver
    enviar_mensagem_de_template abaixo.
    """
    url = (
        f"https://graph.facebook.com/{configuracoes.meta_versao_api}"
        f"/{id_numero_telefone}/messages"
    )
    corpo = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {"body": texto},
    }
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.post(url, json=corpo, headers=cabecalhos)

    if resposta.status_code >= 400:
        detalhe: dict[str, Any] = resposta.json().get("error", {})
        logger.warning("falha_ao_enviar_whatsapp", status=resposta.status_code, corpo=resposta.text)
        mensagem_de_erro = detalhe.get("error_user_msg") or detalhe.get("message") or "Falha ao enviar mensagem pelo WhatsApp."
        if resposta.status_code < 500:
            raise ErroPermanenteDoWhatsApp(mensagem_de_erro)
        raise ValueError(mensagem_de_erro)
    return resposta.json()


async def enviar_mensagem_de_template(
    id_numero_telefone: str,
    token_de_acesso: str,
    numero_destino: str,
    nome_do_template: str,
    idioma: str,
    parametros: list[str],
) -> dict[str, Any]:
    """
    Envia uma mensagem usando um TEMPLATE aprovado pela Meta — o único
    formato permitido fora da janela de 24h (ver enviar_mensagem_de_texto
    acima). Usado pelos quatro templates deste projeto: notificação e
    reencaminhamento (avisam o setor humano, que quase nunca tem uma
    janela de 24h aberta), reengajamento (retoma um atendimento em
    silêncio) e atenção (ver integracoes_externas/meta_templates.py). Os
    "parametros" preenchem as variáveis {{1}}, {{2}}, etc. definidas no
    template, na ordem em que aparecem.
    """
    url = (
        f"https://graph.facebook.com/{configuracoes.meta_versao_api}"
        f"/{id_numero_telefone}/messages"
    )
    corpo = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "template",
        "template": {
            "name": nome_do_template,
            "language": {"code": idioma},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": valor} for valor in parametros],
                }
            ],
        },
    }
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.post(url, json=corpo, headers=cabecalhos)

    if resposta.status_code >= 400:
        detalhe: dict[str, Any] = resposta.json().get("error", {})
        logger.warning("falha_ao_enviar_template", status=resposta.status_code, corpo=resposta.text)
        mensagem_de_erro = detalhe.get("error_user_msg") or detalhe.get("message") or "Falha ao enviar template pelo WhatsApp."
        if resposta.status_code < 500:
            raise ErroPermanenteDoWhatsApp(mensagem_de_erro)
        raise ValueError(mensagem_de_erro)
    return resposta.json()


def extrair_mensagens_do_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    A Meta manda o webhook em um formato bem aninhado (entry -> changes ->
    value -> messages). Esta função "desembrulha" esse formato e devolve
    uma lista simples de mensagens, já no formato que o restante do
    sistema usa. Se o evento for só uma atualização de status (mensagem
    "entregue"/"lida") em vez de uma mensagem nova, a lista de mensagens
    vem vazia — quem lida com status é extrair_status_do_payload, abaixo.

    Pra mensagens de mídia (imagem/áudio/documento), a Meta NUNCA manda o
    arquivo em si no payload do webhook — só um `id` de mídia, que precisa
    ser trocado por uma URL de download temporária depois (ver
    obter_url_de_download_da_midia/baixar_bytes_da_midia abaixo). Por isso
    capturamos aqui `media_id`/`mime_type`/`nome_do_arquivo`/`legenda` —
    sem isso, a mensagem de mídia chegava no banco como um texto vazio
    genérico, e o conteúdo de verdade nunca era processado.
    """
    mensagens_encontradas: list[dict[str, Any]] = []
    for entrada in payload.get("entry", []):
        for alteracao in entrada.get("changes", []):
            valor = alteracao.get("value", {})
            for mensagem in valor.get("messages", []):
                tipo = mensagem.get("type")
                dados_da_midia = mensagem.get(tipo, {}) if tipo in ("image", "audio", "document", "sticker", "video") else {}
                mensagens_encontradas.append(
                    {
                        "id_numero_telefone_destino": valor.get("metadata", {}).get("phone_number_id"),
                        "numero_do_remetente": mensagem.get("from"),
                        "id_mensagem_whatsapp": mensagem.get("id"),
                        "tipo": tipo,
                        "texto": mensagem.get("text", {}).get("body"),
                        "media_id": dados_da_midia.get("id"),
                        "mime_type": dados_da_midia.get("mime_type"),
                        "nome_do_arquivo": dados_da_midia.get("filename"),
                        "legenda": dados_da_midia.get("caption"),
                        "bruto": mensagem,
                    }
                )
    return mensagens_encontradas


async def obter_url_de_download_da_midia(media_id: str, token_de_acesso: str) -> str:
    """
    Primeiro passo pra baixar uma mídia recebida: troca o ID (o único dado
    que o webhook manda) por uma URL de download temporária — a Graph API
    exige essa troca antes de qualquer download de verdade, e essa URL
    expira em minutos, então precisa ser usada logo em seguida.
    """
    url = f"https://graph.facebook.com/{configuracoes.meta_versao_api}/{media_id}"
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.get(url, headers=cabecalhos)

    if resposta.status_code >= 400:
        logger.warning("falha_ao_obter_url_da_midia", status=resposta.status_code, corpo=resposta.text)
        raise ValueError("Não foi possível obter a URL de download da mídia recebida.")
    return resposta.json()["url"]


async def baixar_bytes_da_midia(url_de_download: str, token_de_acesso: str) -> bytes:
    """
    Baixa o arquivo de verdade a partir da URL temporária — importante: a
    Meta exige o MESMO token Bearer aqui, mesmo a URL já sendo "assinada";
    sem o header de autorização, o download é recusado.
    """
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}"}
    async with httpx.AsyncClient(timeout=30) as cliente:
        resposta = await cliente.get(url_de_download, headers=cabecalhos)

    if resposta.status_code >= 400:
        logger.warning("falha_ao_baixar_midia", status=resposta.status_code)
        raise ValueError("Não foi possível baixar o conteúdo da mídia recebida.")
    return resposta.content


def extrair_status_do_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Desembrulha eventos de status de entrega (sent/delivered/read/failed).
    Quando o status é "failed", a Meta manda também um campo "errors" com o
    motivo real da falha — sem isso, um envio recusado aparece só como
    "FALHOU" no banco, sem explicação nenhuma de por quê.
    """
    status_encontrados: list[dict[str, Any]] = []
    for entrada in payload.get("entry", []):
        for alteracao in entrada.get("changes", []):
            valor = alteracao.get("value", {})
            for status in valor.get("statuses", []):
                status_encontrados.append(
                    {
                        "id_mensagem_whatsapp": status.get("id"),
                        "status": status.get("status"),
                        "erros": status.get("errors", []),
                    }
                )
    return status_encontrados


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo concentra toda a integração com a WhatsApp Cloud API:
# normalizar_numero_brasileiro (acerta o prefixo "55" que falta em números
# digitados manualmente, para a API) e formatar_numero_para_exibicao (o
# oposto: formata para leitura humana, "(77) 99947-1710", quando o próprio
# agente precisa citar um número numa mensagem), enviar_mensagem_de_texto
# (respostas dentro da janela de 24h), enviar_mensagem_de_template (os
# quatro templates deste projeto, obrigatórios fora da janela de 24h) e
# as funções extrair_mensagens_do_payload /
# extrair_status_do_payload, que traduzem o formato bruto do webhook da
# Meta para algo simples de usar no resto do backend.
# ==============================================================================

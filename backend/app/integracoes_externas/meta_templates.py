# ==============================================================================
# ARQUIVO: integracoes_externas/meta_templates.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo automatiza a criação de QUATRO templates pré-aprovados pela
# Meta, exigidos em situações em que a WhatsApp Cloud API não aceita
# mensagem de texto livre (fora da janela de atendimento de 24h, só dá pra
# escrever usando um template já aprovado):
#
#   1) Template de NOTIFICAÇÃO: para avisar de verdade o setor humano para
#      onde um atendimento foi encaminhado — esse número quase nunca tem
#      uma janela de 24h aberta com o WhatsApp comercial da empresa (ele
#      nunca "escreveu primeiro" para esse número), então uma notificação
#      de texto livre falha silenciosamente (Meta código 131047,
#      "re-engagement message") até que a empresa converse com ele por
#      outro canal — um template resolve isso de vez. É um texto ÚNICO,
#      genérico o bastante para servir a qualquer setor que o agente
#      decidir encaminhar (a empresa não precisa de um template por setor).
#   2) Template de REENGAJAMENTO: para retomar contato com um atendimento
#      que já estava numa conversa de verdade mas ficou 3+ dias sem
#      responder — a mesma janela de 24h fecha nesse caso também.
#   3) Template de REENCAMINHAMENTO: para o SEGUNDO encaminhamento em
#      diante, quando um atendimento que já tinha sido passado adiante
#      volta com algo novo.
#   4) Template de ATENÇÃO: quando o guardrail de entrada detecta uma
#      tentativa de manipulação do agente.
#
# Diferente dos outros dois projetos da linhagem, NÃO existe aqui um
# template de ABORDAGEM — este agente é receptivo, nunca inicia contato
# (ver Informacoes/Arquitetura.md, seção 2 e 4.5).
#
# Em vez de pedir para cada empresa entrar no painel de desenvolvedor da
# Meta e submeter isso na mão — o mesmo tipo de fricção técnica que o
# botão "Conectar WhatsApp" já elimina para a conexão do número — este
# arquivo manda os templates prontos direto pela Graph API.
# ==============================================================================

from typing import Any

import httpx
import structlog

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()
logger = structlog.get_logger(__name__)

URL_BASE_GRAPH_API = f"https://graph.facebook.com/{configuracoes.meta_versao_api}"


def _montar_texto_do_template_de_notificacao(nome_do_agente: str, nome_da_empresa: str) -> str:
    """
    Monta o texto do template com o nome do agente e da empresa já
    embutidos como texto FIXO (não como variável {{n}}) — um template
    pertence a uma única empresa (cada empresa submete o seu próprio, com
    seu próprio nome), então esses dois dados nunca mudam entre uma
    notificação e outra da mesma empresa. As 3 variáveis reais (nome,
    WhatsApp, resumo escrito pelo modelo) mudam a cada encaminhamento.
    """
    return (
        f"🔔 Novo atendimento aguardando retorno — agente {nome_do_agente or 'Assistente de Atendimento'}, da {nome_da_empresa}.\n\n"
        "Nome do cliente: {{1}}\n"
        "WhatsApp do cliente: {{2}}\n\n"
        "Resumo do atendimento: {{3}}\n\n"
        "Acompanhe a conversa completa na plataforma."
    )


def montar_previa_do_template_de_notificacao(nome_do_agente: str, nome_da_empresa: str) -> str:
    """Monta o texto do template de notificação já preenchido com um exemplo realista, para conferência antes de submeter de verdade."""
    return (
        _montar_texto_do_template_de_notificacao(nome_do_agente, nome_da_empresa)
        .replace("{{1}}", "Maria")
        .replace("{{2}}", "5511987654321")
        .replace(
            "{{3}}",
            "Perguntou sobre a política de troca e não encontrou a resposta na Base de Conhecimento.",
        )
    )


async def criar_template_de_notificacao(
    id_waba: str,
    token_de_acesso: str,
    nome_do_template: str,
    nome_do_agente: str,
    nome_da_empresa: str,
) -> None:
    """
    Submete o template de notificação (encaminhamento para um setor
    humano) para análise da Meta. Categoria "UTILITY" (não "MARKETING")
    porque este avisa um MEMBRO DA PRÓPRIA EMPRESA sobre uma atualização
    operacional — não é uma mensagem promocional para um cliente externo.
    """
    url = f"{URL_BASE_GRAPH_API}/{id_waba}/message_templates"
    texto = _montar_texto_do_template_de_notificacao(nome_do_agente, nome_da_empresa)
    corpo = {
        "name": nome_do_template,
        "language": "pt_BR",
        "category": "UTILITY",
        "components": [
            {
                "type": "BODY",
                "text": texto,
                "example": {
                    "body_text": [
                        [
                            "Maria",
                            "5511987654321",
                            "Perguntou sobre a política de troca e não encontrou a resposta na Base de Conhecimento.",
                        ]
                    ]
                },
            }
        ],
    }
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.post(url, json=corpo, headers=cabecalhos)

    if resposta.status_code >= 400:
        detalhe: dict[str, Any] = resposta.json().get("error", {})
        logger.warning("falha_ao_criar_template_de_notificacao", status=resposta.status_code, corpo=resposta.text)
        raise ValueError(
            detalhe.get("error_user_msg")
            or detalhe.get("message")
            or "Não foi possível enviar o template de notificação para análise da Meta."
        )


# Texto do template usado para retomar contato com um atendimento que já
# estava numa conversa de verdade mas ficou 3+ dias sem responder — a
# janela de 24h fecha nesse caso, então esta mensagem TAMBÉM precisa ser
# um template aprovado (ver
# agente/ferramentas_monitoramento.py:reengajar_atendimento_silencioso).
# Exportado (não é "_"-privado) porque agente/orquestrador.py precisa dele
# para gravar o texto REAL enviado no histórico da conversa.
#
# 3 variáveis (nome do cliente, nome do agente, nome da empresa) —
# diferente do template de notificação (lido só pela própria empresa,
# onde nome do agente/empresa entram como texto FIXO), aqui quem lê é o
# CLIENTE, então erramos pelo lado de soar pessoal, com os três como
# variável.
TEXTO_PADRAO_DO_TEMPLATE_DE_REENGAJAMENTO = (
    "Oi, {{1}}! Aqui é {{2}}, da {{3}}. "
    "Passando pra saber se você ainda precisa de ajuda com o seu atendimento — "
    "fico à disposição se quiser retomar de onde paramos ou tirar alguma dúvida."
)


def montar_previa_do_template_de_reengajamento(nome_do_agente: str, nome_da_empresa: str) -> str:
    """Monta o texto já preenchido com um exemplo, para conferência antes do envio de verdade."""
    return (
        TEXTO_PADRAO_DO_TEMPLATE_DE_REENGAJAMENTO
        .replace("{{1}}", "Maria")
        .replace("{{2}}", nome_do_agente or "Assistente de Atendimento")
        .replace("{{3}}", nome_da_empresa)
    )


async def criar_template_de_reengajamento(
    id_waba: str,
    token_de_acesso: str,
    nome_do_template: str,
    nome_do_agente: str,
    nome_da_empresa: str,
) -> None:
    """Submete o template de reengajamento para análise da Meta. Categoria "MARKETING" — é uma mensagem para um cliente externo, não um aviso interno."""
    url = f"{URL_BASE_GRAPH_API}/{id_waba}/message_templates"
    texto = TEXTO_PADRAO_DO_TEMPLATE_DE_REENGAJAMENTO
    corpo = {
        "name": nome_do_template,
        "language": "pt_BR",
        "category": "MARKETING",
        "components": [
            {
                "type": "BODY",
                "text": texto,
                "example": {
                    "body_text": [["Maria", nome_do_agente or "Assistente de Atendimento", nome_da_empresa]]
                },
            }
        ],
    }
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.post(url, json=corpo, headers=cabecalhos)

    if resposta.status_code >= 400:
        detalhe: dict[str, Any] = resposta.json().get("error", {})
        logger.warning("falha_ao_criar_template_de_reengajamento", status=resposta.status_code, corpo=resposta.text)
        raise ValueError(
            detalhe.get("error_user_msg")
            or detalhe.get("message")
            or "Não foi possível enviar o template de reengajamento para análise da Meta."
        )


def _montar_texto_do_template_de_reencaminhamento(nome_do_agente: str, nome_da_empresa: str) -> str:
    """
    Mesma estrutura do template de notificação (agente/empresa como texto
    FIXO, 3 variáveis nome/WhatsApp/resumo) — usado especificamente quando
    o atendimento JÁ TINHA sido encaminhado antes e volta com algo novo
    (ver agente/ferramentas.py:montar_ferramentas_de_reengajamento).
    Template SEPARADO do de notificação original: o texto do de
    notificação abre com "Novo atendimento aguardando retorno", o que não
    faz sentido para um atendimento que o setor já está tratando.
    """
    return (
        f"🔁 Atendimento REENCAMINHADO pelo agente {nome_do_agente or 'Assistente de Atendimento'}, da {nome_da_empresa} "
        "— já tinha sido encaminhado antes e voltou com algo novo.\n\n"
        "Nome do cliente: {{1}}\n"
        "WhatsApp do cliente: {{2}}\n\n"
        "Resumo do atendimento: {{3}}\n\n"
        "Acompanhe a conversa completa na plataforma."
    )


def montar_previa_do_template_de_reencaminhamento(nome_do_agente: str, nome_da_empresa: str) -> str:
    """Monta o texto do template de reencaminhamento já preenchido com um exemplo, para conferência antes do envio."""
    return (
        _montar_texto_do_template_de_reencaminhamento(nome_do_agente, nome_da_empresa)
        .replace("{{1}}", "Maria")
        .replace("{{2}}", "5511987654321")
        .replace(
            "{{3}}",
            "Já tinha sido encaminhado antes, mas voltou dizendo que não recebeu retorno.",
        )
    )


async def criar_template_de_reencaminhamento(
    id_waba: str,
    token_de_acesso: str,
    nome_do_template: str,
    nome_do_agente: str,
    nome_da_empresa: str,
) -> None:
    """
    Submete o template de reencaminhamento (segundo encaminhamento em
    diante) para análise da Meta. Categoria "UTILITY", mesmo motivo do
    template de notificação: avisa um MEMBRO DA PRÓPRIA EMPRESA.
    """
    url = f"{URL_BASE_GRAPH_API}/{id_waba}/message_templates"
    texto = _montar_texto_do_template_de_reencaminhamento(nome_do_agente, nome_da_empresa)
    corpo = {
        "name": nome_do_template,
        "language": "pt_BR",
        "category": "UTILITY",
        "components": [
            {
                "type": "BODY",
                "text": texto,
                "example": {
                    "body_text": [
                        [
                            "Maria",
                            "5511987654321",
                            "Já tinha sido encaminhado antes, mas voltou dizendo que não recebeu retorno.",
                        ]
                    ]
                },
            }
        ],
    }
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.post(url, json=corpo, headers=cabecalhos)

    if resposta.status_code >= 400:
        detalhe: dict[str, Any] = resposta.json().get("error", {})
        logger.warning("falha_ao_criar_template_de_reencaminhamento", status=resposta.status_code, corpo=resposta.text)
        raise ValueError(
            detalhe.get("error_user_msg")
            or detalhe.get("message")
            or "Não foi possível enviar o template de reencaminhamento para análise da Meta."
        )


def _montar_texto_do_template_de_atencao(nome_do_agente: str, nome_da_empresa: str) -> str:
    """
    Mesma estrutura dos templates de notificação/reencaminhamento (agente/
    empresa como texto FIXO, 3 variáveis nome/WhatsApp/resumo) — usado
    quando o guardrail de entrada (ver
    agente/guardrails.py:detectar_tentativa_de_manipulacao_do_atendimento)
    detecta que o cliente tentou manipular o agente durante a conversa. A
    introdução aqui é deliberadamente NEUTRA (não usa a palavra "fraude"):
    o guardrail detecta um PADRÃO de tentativa de manipulação, não prova
    de má-fé — quem decide como tratar o caso é sempre o setor humano.
    """
    return (
        f"⚠️ Atenção: comportamento atípico detectado pelo agente {nome_do_agente or 'Assistente de Atendimento'}, "
        f"da {nome_da_empresa} — revise antes de tratar como atendimento comum.\n\n"
        "Nome do cliente: {{1}}\n"
        "WhatsApp do cliente: {{2}}\n\n"
        "Resumo do atendimento: {{3}}\n\n"
        "Acompanhe a conversa completa na plataforma."
    )


def montar_previa_do_template_de_atencao(nome_do_agente: str, nome_da_empresa: str) -> str:
    """Monta o texto do template de atenção já preenchido com um exemplo, para conferência antes do envio."""
    return (
        _montar_texto_do_template_de_atencao(nome_do_agente, nome_da_empresa)
        .replace("{{1}}", "Maria")
        .replace("{{2}}", "5511987654321")
        .replace(
            "{{3}}",
            "Tentou fazer o agente ignorar as instruções e confirmar um reembolso fora da política.",
        )
    )


async def criar_template_de_atencao(
    id_waba: str,
    token_de_acesso: str,
    nome_do_template: str,
    nome_do_agente: str,
    nome_da_empresa: str,
) -> None:
    """
    Submete o template de atenção (encaminhamento por suspeita de
    manipulação do agente) para análise da Meta. Categoria "UTILITY",
    mesmo motivo dos outros templates internos.
    """
    url = f"{URL_BASE_GRAPH_API}/{id_waba}/message_templates"
    texto = _montar_texto_do_template_de_atencao(nome_do_agente, nome_da_empresa)
    corpo = {
        "name": nome_do_template,
        "language": "pt_BR",
        "category": "UTILITY",
        "components": [
            {
                "type": "BODY",
                "text": texto,
                "example": {
                    "body_text": [
                        [
                            "Maria",
                            "5511987654321",
                            "Tentou fazer o agente ignorar as instruções e confirmar um reembolso fora da política.",
                        ]
                    ]
                },
            }
        ],
    }
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.post(url, json=corpo, headers=cabecalhos)

    if resposta.status_code >= 400:
        detalhe: dict[str, Any] = resposta.json().get("error", {})
        logger.warning("falha_ao_criar_template_de_atencao", status=resposta.status_code, corpo=resposta.text)
        raise ValueError(
            detalhe.get("error_user_msg")
            or detalhe.get("message")
            or "Não foi possível enviar o template de atenção para análise da Meta."
        )


async def consultar_status_do_template(id_waba: str, token_de_acesso: str, nome_do_template: str) -> str | None:
    """
    Consulta, na Graph API, o status atual do template (PENDING, APPROVED
    ou REJECTED). Devolve None se o template ainda nem foi submetido.
    """
    url = f"{URL_BASE_GRAPH_API}/{id_waba}/message_templates"
    parametros = {"name": nome_do_template, "fields": "name,status,category"}
    cabecalhos = {"Authorization": f"Bearer {token_de_acesso}"}

    async with httpx.AsyncClient(timeout=15) as cliente:
        resposta = await cliente.get(url, params=parametros, headers=cabecalhos)

    if resposta.status_code >= 400:
        logger.warning("falha_ao_consultar_template", status=resposta.status_code, corpo=resposta.text)
        return None

    resultados: list[dict[str, Any]] = resposta.json().get("data", [])
    if not resultados:
        return None
    return resultados[0].get("status")


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo automatiza os QUATRO templates deste projeto via Graph API
# (sem template de abordagem — este agente nunca inicia contato):
# "_de_notificacao" cuida do PRIMEIRO aviso ao setor humano (categoria
# UTILITY, texto único e genérico o bastante para servir a qualquer
# setor), "_de_reencaminhamento" cuida do SEGUNDO aviso em diante — quando
# um atendimento que já tinha sido encaminhado volta com algo novo
# (também UTILITY) —, "_de_reengajamento" cuida de retomar contato com um
# cliente em silêncio (categoria MARKETING, diferente dos outros três por
# falar com o cliente, não com a empresa) e "_de_atencao" cuida do aviso
# de suspeita de manipulação (UTILITY). Cada grupo segue o mesmo desenho:
# montar_previa_do_template_* devolve o texto já preenchido com um
# exemplo, para a pessoa conferir antes de enviar de verdade;
# criar_template_* submete o template para análise. As rotas que usam
# essas funções ficam em rotas/canais.py.
# ==============================================================================

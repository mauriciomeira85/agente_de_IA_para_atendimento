# ==============================================================================
# ARQUIVO: integracoes_externas/envio_dashboard.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Envia os dados do Dashboard (cartões de quantidade/taxa e o funil — ver
# rotas/painel.py) para uma URL externa configurada na aba Integrações
# (botão "Enviar agora"). Sempre a mesma direção: plataforma -> fora.
# Diferente dos outros dois projetos da linhagem, não existe aqui uma
# conexão de CRM externo na direção inversa (trazer contatos pra dentro) —
# este agente é receptivo, todo Atendimento nasce da própria mensagem do
# cliente no WhatsApp (ver Informacoes/Arquitetura.md, seção 2).
# ==============================================================================

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


async def enviar_dados_do_dashboard(url_webhook: str, chave_api: str | None, dados: dict[str, Any]) -> bool:
    """POSTa o payload do Dashboard na URL configurada. Devolve True/False conforme o destino aceitou (2xx) ou não."""
    cabecalhos = {"Content-Type": "application/json"}
    if chave_api:
        cabecalhos["Authorization"] = f"Bearer {chave_api}"

    try:
        async with httpx.AsyncClient(timeout=15) as cliente:
            resposta = await cliente.post(url_webhook, headers=cabecalhos, json=dados)
    except httpx.HTTPError as erro:
        logger.error("falha_ao_enviar_dados_do_dashboard", url=url_webhook, erro=str(erro))
        return False

    if resposta.status_code >= 400:
        logger.warning("destino_rejeitou_envio_do_dashboard", url=url_webhook, status=resposta.status_code)
        return False

    return True


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# enviar_dados_do_dashboard() faz o POST de saída da aba Integrações —
# nunca falha com exceção (erros de rede ou status de erro só viram False),
# para que a rota que chama isto sempre consiga registrar o resultado do
# envio (ultimo_envio_em/ultimo_envio_com_sucesso) sem quebrar a requisição.
# ==============================================================================

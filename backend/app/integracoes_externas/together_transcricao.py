# ==============================================================================
# ARQUIVO: integracoes_externas/together_transcricao.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Transcreve áudio recebido de um atendimento no WhatsApp (comum: um áudio
# gravado explicando algo em vez de digitar) — usado por
# agente/nos.py:interpretar_midia.
#
# Usamos a Together AI hospedando o Whisper Large v3 (o mesmo modelo de
# transcrição que a própria OpenAI usa, só que mais barato lá) em vez da
# DeepSeek, que não tem NENHUM suporte a áudio — nem para transcrever, nem
# para gerar. É uma transcrição em LOTE (o áudio já chegou gravado do
# WhatsApp, não é uma chamada de voz ao vivo), por isso usamos o endpoint
# comum de transcrição, não a variante "streaming" (essa é para áudio
# contínuo, tipo uma ligação, um caso de uso diferente do nosso).
# ==============================================================================

from typing import Any

import httpx
import structlog

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()
logger = structlog.get_logger(__name__)

URL_TRANSCRICAO = "https://api.together.ai/v1/audio/transcriptions"


async def transcrever_audio(conteudo_do_audio: bytes, nome_do_arquivo: str, mime_type: str) -> str | None:
    """
    Transcreve o áudio pra texto em português. Devolve None se a
    transcrição falhar (sem credencial configurada, erro da API etc.) —
    quem chama decide como avisar o atendimento nesse caso (ver
    agente/nos.py:interpretar_midia).
    """
    if not configuracoes.together_chave_api:
        logger.warning("together_nao_configurado_audio_nao_transcrito")
        return None

    cabecalhos = {"Authorization": f"Bearer {configuracoes.together_chave_api}"}
    arquivos = {"file": (nome_do_arquivo, conteudo_do_audio, mime_type)}
    dados: dict[str, Any] = {
        "model": configuracoes.together_modelo_transcricao,
        "language": "pt",
        # "verbose_json" (em vez de "json") é o único formato que a
        # Together devolve com a duração do áudio (em segundos) — a
        # Together cobra a transcrição por MINUTO de áudio, não por token,
        # então é essa duração (não tokens) que precisamos registrar para
        # estimar custo.
        "response_format": "verbose_json",
    }

    async with httpx.AsyncClient(timeout=60) as cliente:
        resposta = await cliente.post(URL_TRANSCRICAO, headers=cabecalhos, files=arquivos, data=dados)

    if resposta.status_code >= 400:
        logger.error("falha_ao_transcrever_audio", status=resposta.status_code, corpo=resposta.text)
        return None

    corpo_da_resposta = resposta.json()
    logger.info("duracao_de_audio_transcrito_together", segundos=corpo_da_resposta.get("duration"))

    return corpo_da_resposta.get("text", "").strip() or None


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# transcrever_audio manda o áudio (bytes, já baixado da WhatsApp Cloud API
# — ver integracoes_externas/whatsapp.py:baixar_bytes_da_midia) para o
# Whisper Large v3 hospedado na Together AI, e devolve o texto
# transcrito, pronto para entrar na conversa como se o atendimento tivesse
# digitado.
# ==============================================================================

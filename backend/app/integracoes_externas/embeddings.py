# ==============================================================================
# ARQUIVO: integracoes_externas/embeddings.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Gera o "embedding" de um texto — um vetor de números que representa o
# SIGNIFICADO daquele texto — usado em dois momentos: (1) ao salvar um item
# da Base de Conhecimento (rotas/base_de_conhecimento.py), pra guardar o
# vetor junto do texto; (2) a cada pergunta que o agente faz à base (ver
# agente/ferramentas.py:_ferramenta_consultar_base_de_conhecimento), pra
# comparar o vetor da pergunta com os vetores já guardados e achar os
# trechos mais PARECIDOS EM SIGNIFICADO, não em palavras exatas — é isso
# que permite a base responder "vocês entregam no fim de semana?" mesmo que
# o texto cadastrado diga "horário de entregas" sem usar a palavra
# "fim de semana" literalmente.
#
# Usa a mesma conta OpenAI já usada no Agente Comercial SDR (gpt-luna, para
# imagem/PDF) — reaproveitamento de credencial, não uma integração nova do
# zero.
#
# HISTÓRICO — por que OpenAI e não Together AI: a primeira versão deste
# arquivo usava a Together AI (mesma conta já usada pra transcrição de
# áudio, ver together_transcricao.py), tentando reaproveitar ainda mais
# credencial. Mas um teste real (Base de Conhecimento, 16/09/2026) mostrou
# que a Together AI não oferece mais NENHUM modelo de embeddings em modo
# serverless (pay-per-uso) — só "endpoint dedicado", com custo fixo por
# hora, independente do uso. A transcrição de áudio (Whisper) continua
# serverless normalmente na Together AI; só embeddings mudaram. A OpenAI
# (text-embedding-3-small) resolve isso: é serverless, barata e
# multilíngue de verdade (ao contrário do BAAI/bge-base-en-v1.5 da
# Together, otimizado só pra inglês) — por pedido explícito do usuário,
# reaproveitando a MESMA conta OpenAI já usada no SDR.
# ==============================================================================

import httpx
import structlog

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()
logger = structlog.get_logger(__name__)

URL_EMBEDDINGS = "https://api.openai.com/v1/embeddings"


async def gerar_embedding(texto: str) -> list[float] | None:
    """
    Gera o vetor de embedding de um texto. Devolve None se a chave da
    OpenAI não estiver configurada, ou se a chamada falhar — quem chama
    decide o que fazer (ex.: salvar o item sem embedding, deixando-o de
    fora das buscas por enquanto, ou tratar a pergunta como "sem resultado
    na base").
    """
    if not configuracoes.openai_chave_api:
        logger.warning("openai_nao_configurado_embedding_nao_gerado")
        return None

    texto_limpo = texto.strip()
    if not texto_limpo:
        return None

    cabecalhos = {"Authorization": f"Bearer {configuracoes.openai_chave_api}"}
    corpo = {"model": configuracoes.openai_modelo_embeddings, "input": texto_limpo}

    try:
        async with httpx.AsyncClient(timeout=30) as cliente:
            resposta = await cliente.post(URL_EMBEDDINGS, headers=cabecalhos, json=corpo)
    except httpx.HTTPError as erro:
        logger.error("falha_de_rede_ao_gerar_embedding", erro=str(erro))
        return None

    if resposta.status_code >= 400:
        logger.error("falha_ao_gerar_embedding", status=resposta.status_code, corpo=resposta.text)
        return None

    corpo_da_resposta = resposta.json()
    dados = corpo_da_resposta.get("data") or []
    if not dados:
        return None

    return dados[0].get("embedding")


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# gerar_embedding() manda um texto para o endpoint de embeddings da OpenAI
# e devolve o vetor resultante (ou None em qualquer falha) — usado tanto
# para indexar itens da Base de Conhecimento quanto para transformar a
# pergunta do cliente no mesmo tipo de vetor, na hora da busca por
# similaridade. Trocado da Together AI para a OpenAI depois que um teste
# real mostrou que a Together não oferece mais embeddings em modo
# serverless (ver histórico acima).
# ==============================================================================

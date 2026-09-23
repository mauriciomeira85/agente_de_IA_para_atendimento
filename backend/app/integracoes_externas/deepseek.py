# ==============================================================================
# ARQUIVO: integracoes_externas/deepseek.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo isola toda a comunicação com a API da DeepSeek — o provedor
# de modelo de linguagem que dá "inteligência" ao Agente Comercial SDR. A
# API da DeepSeek é compatível com o formato da OpenAI (o mesmo padrão
# "chat completions" usado por várias ferramentas de IA), então usamos a
# biblioteca langchain-openai apontando para o endereço da DeepSeek em vez
# do endereço da OpenAI — assim ganhamos, de graça, toda a integração do
# LangGraph com "ferramentas" (tool calling) sem escrever esse código na
# mão.
#
# UM modelo só faz os dois papéis desde o DeepSeek-V4.1-Flash
# ("deepseek-flash", 10/09/2026) — antes eram dois modelos separados
# (deepseek-v4-flash pra texto, deepseek-v4-flash-vision-exp pra imagem);
# hoje esses nomes antigos só redirecionam pro mesmo modelo novo. Mantemos
# montar_modelo_de_texto/montar_modelo_de_visao como funções separadas
# porque cada uma usa uma temperatura diferente (visão é mais factual,
# temperatura mais baixa), não porque sejam modelos diferentes.
# ==============================================================================

import base64

import structlog
from langchain_openai import ChatOpenAI

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()
logger = structlog.get_logger(__name__)


def montar_modelo_de_texto(temperatura: float = 0.4) -> ChatOpenAI:
    """
    Monta o cliente do modelo de texto da DeepSeek (deepseek-v4-flash),
    pronto para ser usado dentro dos nós do LangGraph. A temperatura baixa
    (0.4) deixa as respostas mais previsíveis e alinhadas ao roteiro de
    conversa configurado pela empresa — importante em um agente comercial,
    que não deve "inventar" promessas sobre o produto.
    """
    return ChatOpenAI(
        model=configuracoes.deepseek_modelo_texto,
        api_key=configuracoes.deepseek_chave_api,
        base_url=configuracoes.deepseek_url_base,
        temperature=temperatura,
    )


def montar_modelo_de_visao() -> ChatOpenAI:
    """
    Monta o cliente do modelo com capacidade de leitura de imagem
    (deepseek-flash). É usado quando um atendimento manda uma foto, sticker,
    frame extraído de vídeo ou página de PDF escaneada (ver
    app/agente/nos.py — nó "interpretar_midia").
    """
    return ChatOpenAI(
        model=configuracoes.deepseek_modelo_visao,
        api_key=configuracoes.deepseek_chave_api,
        base_url=configuracoes.deepseek_url_base,
        temperature=0.2,
    )


async def descrever_imagem(conteudo_da_imagem: bytes, mime_type: str) -> str | None:
    """
    Descreve em 1-2 frases o que aparece numa imagem enviada por um atendimento
    (foto, sticker, frame de vídeo ou página de PDF renderizada). Devolve
    None se falhar — quem chama decide o texto de aviso pro atendimento nesse caso
    (ver agente/nos.py:interpretar_midia).
    """
    imagem_em_base64 = base64.b64encode(conteudo_da_imagem).decode("ascii")
    try:
        resposta = await montar_modelo_de_visao().ainvoke(
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Descreva em 1 ou 2 frases, em português, o que aparece nesta imagem enviada por um atendimento em uma conversa comercial.",
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{imagem_em_base64}"}},
                    ],
                }
            ]
        )
    except Exception as erro:  # noqa: BLE001 — qualquer falha na leitura de imagem deve virar aviso gracioso, nunca quebrar a conversa
        logger.error("falha_ao_descrever_imagem_deepseek", erro=str(erro))
        return None

    uso = resposta.usage_metadata or {}
    logger.info(
        "uso_de_tokens_de_visao",
        tokens_de_entrada=uso.get("input_tokens", 0),
        tokens_de_saida=uso.get("output_tokens", 0),
        tokens_de_entrada_em_cache=uso.get("input_token_details", {}).get("cache_read", 0),
    )

    conteudo = resposta.content
    return conteudo.strip() if isinstance(conteudo, str) and conteudo.strip() else None


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo expõe montar_modelo_de_texto (o cérebro principal do
# agente, usado por agente/loop_de_ferramentas.py), montar_modelo_de_visao
# e descrever_imagem (interpretação de imagem, usada por
# agente/nos.py:interpretar_midia) — todas conversando com a API da
# DeepSeek usando o formato compatível com OpenAI, via langchain-openai.
# ==============================================================================

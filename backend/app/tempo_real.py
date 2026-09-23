# ==============================================================================
# ARQUIVO: tempo_real.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo cuida da parte "tempo real" da aba Conversas: quando uma
# mensagem nova chega (do atendimento) ou é enviada (pelo agente), a tela de
# quem está com aquela conversa aberta deve atualizar sozinha, sem
# precisar apertar F5.
#
# O desafio de arquitetura aqui é que a mensagem pode ser gravada em DOIS
# processos diferentes: o próprio servidor da API (quando o backend
# processa e responde na hora) ou o worker do Celery (processo separado,
# que roda a IA em segundo plano — ver app/tarefas/tarefas_conversa.py).
# Um WebSocket, porém, só existe dentro do processo da API, que é onde o
# navegador está conectado.
#
# A solução — e o motivo de o Redis já fazer parte do projeto para além
# da fila do Celery — é usar o mecanismo de "publicar/assinar" (pub/sub)
# do Redis: qualquer processo pode PUBLICAR um evento em um canal, e o
# processo da API, que mantém a conexão WebSocket com o navegador, fica
# OUVINDO esse canal e repassa cada evento adiante. Isso desacopla quem
# gera o evento de quem entrega o evento ao navegador.
# ==============================================================================

import json
from typing import Any

import redis.asyncio as redis_assincrono

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()


def _nome_do_canal(id_empresa: int) -> str:
    """Cada empresa tem seu próprio canal — assim, uma empresa nunca recebe eventos de outra."""
    return f"conversas:{id_empresa}"


async def publicar_evento_de_conversa(id_empresa: int, evento: dict[str, Any]) -> None:
    """
    Publica um evento (ex.: "chegou mensagem nova") no canal Redis da
    empresa. Chamado tanto pelo webhook do WhatsApp (quando o atendimento
    escreve) quanto pelo orquestrador do agente (quando a resposta da IA
    é gravada) — em qualquer um dos dois processos, publicar é a mesma
    linha de código.
    """
    cliente = redis_assincrono.from_url(configuracoes.url_redis)
    try:
        await cliente.publish(_nome_do_canal(id_empresa), json.dumps(evento))
    finally:
        await cliente.aclose()


def obter_canal_de_escuta(id_empresa: int):
    """
    Devolve um "pubsub" do Redis já pronto para ouvir o canal da empresa —
    usado pela rota WebSocket (app/rotas/tempo_real.py) para repassar cada
    evento recebido diretamente para o navegador conectado.
    """
    cliente = redis_assincrono.from_url(configuracoes.url_redis)
    pubsub = cliente.pubsub()
    return cliente, pubsub, _nome_do_canal(id_empresa)


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo implementa a comunicação em tempo real entre os diferentes
# processos do backend (API e worker do Celery) usando o pub/sub do
# Redis: publicar_evento_de_conversa() envia um evento, e
# obter_canal_de_escuta() prepara a escuta desse mesmo canal — usada pela
# rota WebSocket para repassar os eventos até o navegador.
# ==============================================================================

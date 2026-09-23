# ==============================================================================
# ARQUIVO: tarefas/asyncio_util.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# As tarefas do Celery (tarefas_conversa.py, tarefas_monitoramento.py) são
# funções síncronas que precisam rodar código assíncrono (o grafo do
# agente, as chamadas HTTP às IAs de interpretação de mídia). Elas usavam
# asyncio.run(), que cria um event loop novo a cada chamada e o FECHA assim
# que a corrotina termina — mas os clientes httpx.AsyncClient usados nas
# integrações (OpenAI, Together, WhatsApp) agendam uma limpeza interna da
# conexão em segundo plano que nem sempre termina a tempo, gerando
# "RuntimeError: Event loop is closed" nos logs (inofensivo na prática: a
# chamada HTTP em si já tinha terminado com sucesso — é só a limpeza da
# conexão que chega tarde e encontra o loop já fechado).
#
# A correção é reaproveitar UM loop por processo do worker, sem nunca
# fechá-lo entre tarefas — cada processo do Celery (modo "prefork", o
# padrão deste projeto) roda uma tarefa de cada vez, então não há risco de
# duas corrotinas concorrentes disputando o mesmo loop.
# ==============================================================================

import asyncio
from collections.abc import Coroutine
from typing import Any

_loop: asyncio.AbstractEventLoop | None = None


def executar(corrotina: Coroutine[Any, Any, Any]) -> Any:
    """Roda uma corrotina até o fim, reaproveitando o mesmo event loop entre chamadas (substitui asyncio.run() nas tarefas do Celery)."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(corrotina)


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# executar() substitui asyncio.run() dentro das tarefas do Celery, mantendo
# um único event loop vivo por processo do worker em vez de criar e fechar
# um novo a cada chamada — evita o "Event loop is closed" que aparecia nos
# logs quando um httpx.AsyncClient ainda estava limpando conexões em
# segundo plano no momento em que o loop seria fechado.
# ==============================================================================

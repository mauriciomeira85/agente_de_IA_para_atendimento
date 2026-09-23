# ==============================================================================
# ARQUIVO: tarefas/tarefas_conversa.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo define a tarefa do Celery que processa, em segundo plano,
# cada mensagem recebida de um atendimento. Ela é disparada pelo webhook do
# WhatsApp (app/rotas/whatsapp_webhook.py) logo depois de a mensagem ser
# gravada no banco, e é o que garante que o webhook responda rápido para o
# Worker do Cloudflare, sem esperar a IA terminar de pensar.
# ==============================================================================

import structlog
from celery.exceptions import MaxRetriesExceededError

from app.agente.orquestrador import enviar_fallback_apos_falha_permanente, processar_mensagem_recebida
from app.banco_dados import SessaoLocal
from app.integracoes_externas.whatsapp import ErroPermanenteDoWhatsApp
from app.tarefas.asyncio_util import executar
from app.tarefas.celery_app import aplicativo_celery

logger = structlog.get_logger(__name__)


@aplicativo_celery.task(name="app.tarefas.tarefas_conversa.processar_mensagem_em_segundo_plano", bind=True, max_retries=3)
def processar_mensagem_em_segundo_plano(self, id_mensagem: int) -> None:
    """
    Tarefa assíncrona: abre sua própria sessão de banco de dados (tarefas
    do Celery rodam em processos separados do servidor web, então não
    podem reaproveitar a sessão da requisição HTTP original) e chama o
    orquestrador do agente. Se algo falhar (ex.: a DeepSeek ocasionalmente
    devolve um JSON malformado — comportamento conhecido de modelos de
    raciocínio — ou uma instabilidade momentânea da API da Meta), a tarefa
    tenta de novo automaticamente até 3 vezes. O intervalo é curto (2s):
    a chamada à IA em si já é rápida (1-3s), então não faz sentido o atendimento
    esperar mais por causa de um retry — um countdown longo aqui é a
    diferença entre o agente parecer "rápido" ou "lento" no WhatsApp.

    Se as 3 tentativas esgotarem sem sucesso (bug real encontrado em
    teste: o modelo gerou uma chamada de ferramenta sem um argumento
    obrigatório, e o retry quase esgotou antes de dar certo), o atendimento NÃO
    fica em silêncio total — enviar_fallback_apos_falha_permanente avisa
    ele diretamente, sem depender da IA (que é justamente o que falhou).

    EXCEÇÃO IMPORTANTE: se a falha foi um ErroPermanenteDoWhatsApp (a Meta
    recusou o envio por um motivo que não muda tentando de novo — ex.:
    "número não está na lista de permissão" de um número de teste, token
    inválido, template não aprovado), NÃO tentamos de novo. Bug real
    encontrado em produção: antes desta checagem, um erro permanente
    disparava as 3 tentativas normalmente, e cada uma reprocessava a
    mensagem inteira pela IA do zero (processar_mensagem_recebida grava a
    resposta do agente no banco ANTES de tentar enviar — ver
    orquestrador.py) — resultado: até 4 mensagens de agente/sistema
    DUPLICADAS na tela de Conversas para uma única mensagem do cliente,
    sem nenhuma chance real de qualquer uma delas ser entregue.
    """
    sessao = SessaoLocal()
    try:
        executar(processar_mensagem_recebida(sessao, id_mensagem))
    except ErroPermanenteDoWhatsApp as erro:
        logger.error("falha_permanente_ao_enviar_whatsapp_sem_retry", id_mensagem=id_mensagem, erro=str(erro))
        sessao.rollback()
        executar(enviar_fallback_apos_falha_permanente(sessao, id_mensagem))
    except Exception as erro:  # noqa: BLE001 — qualquer outra falha aqui deve acionar nova tentativa, não derrubar o worker
        logger.error("falha_ao_processar_mensagem", id_mensagem=id_mensagem, erro=str(erro))
        try:
            raise self.retry(exc=erro, countdown=2) from erro
        except MaxRetriesExceededError:
            sessao.rollback()
            executar(enviar_fallback_apos_falha_permanente(sessao, id_mensagem))
            raise
    finally:
        sessao.close()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a tarefa processar_mensagem_em_segundo_plano, que
# roda fora do ciclo de requisição HTTP: ela abre sua própria conexão com
# o banco, chama o orquestrador do agente (agente/orquestrador.py) e
# tenta novamente, de forma automática, em caso de falha temporária.
# ==============================================================================

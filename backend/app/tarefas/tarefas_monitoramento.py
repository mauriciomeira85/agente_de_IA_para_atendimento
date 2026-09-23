# ==============================================================================
# ARQUIVO: tarefas/tarefas_monitoramento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a tarefa periódica (agendada no Celery Beat, ver
# tarefas/celery_app.py) que reengaja sozinha, sem nenhum clique humano, os
# atendimentos que ficaram em silêncio no meio de uma conversa.
#
# Diferente dos outros dois projetos da linhagem (ver
# Informacoes/Arquitetura.md, seção 2), esta varredura NÃO cobre "casos
# novos" nem "follow-up de abordagem" — não existe abordagem automática
# neste domínio receptivo. A ÚNICA coisa que ela verifica, a cada 15
# minutos, é: existe algum atendimento EM_ATENDIMENTO que ficou 3+ dias sem
# resposta do cliente à última mensagem do agente? Se sim, agrupa por
# empresa e roda UM turno do agente sobre essa lista (ver
# agente/monitoramento.py) — é o próprio modelo quem decide, atendimento
# por atendimento, se reengaja agora ou aguarda, em vez de um "for" em
# Python decidir isso sozinho.
# ==============================================================================

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select

from app.agente.monitoramento import executar_monitoramento_de_atendimentos
from app.banco_dados import SessaoLocal
from app.modelos.atendimento import Atendimento, StatusAtendimento
from app.modelos.empresa import Empresa
from app.tarefas.asyncio_util import executar
from app.tarefas.celery_app import aplicativo_celery

logger = structlog.get_logger(__name__)

# Depois de quantos dias de silêncio um atendimento EM_ATENDIMENTO (uma
# conversa de verdade em andamento) é considerado elegível para um
# reengajamento — fixo, não configurável pela empresa (diferente do
# intervalo de follow-up dos outros dois projetos, que cobre um cenário
# totalmente diferente: alguém que nunca chegou a responder nada).
DIAS_DE_SILENCIO_PARA_REENGAJAR = 3


def _agrupar_atendimentos_pendentes_por_empresa(sessao) -> dict[int, list[Atendimento]]:
    """Consulta o banco por atendimentos EM_ATENDIMENTO silenciosos há 3+ dias e agrupa por empresa."""
    agora = datetime.now(timezone.utc)
    limite_de_silencio = agora - timedelta(days=DIAS_DE_SILENCIO_PARA_REENGAJAR)

    atendimentos_silenciosos = sessao.scalars(
        select(Atendimento).where(
            Atendimento.status == StatusAtendimento.EM_ATENDIMENTO,
            Atendimento.whatsapp.is_not(None),
            Atendimento.reengajamento_por_silencio_enviado.is_(False),
            Atendimento.ultima_atividade_em.is_not(None),
            Atendimento.ultima_atividade_em <= limite_de_silencio,
        )
    ).all()

    atendimentos_por_empresa: dict[int, list[Atendimento]] = {}
    for atendimento in atendimentos_silenciosos:
        atendimentos_por_empresa.setdefault(atendimento.id_empresa, []).append(atendimento)
    return atendimentos_por_empresa


@aplicativo_celery.task(name="app.tarefas.tarefas_monitoramento.verificar_atendimentos_pendentes_de_atencao")
def verificar_atendimentos_pendentes_de_atencao() -> None:
    """
    Roda a cada 15 minutos (ver beat_schedule em celery_app.py). Para cada
    empresa com pelo menos um atendimento silencioso, roda UM turno do
    agente (ver agente/monitoramento.py:executar_monitoramento_de_atendimentos)
    cobrindo todos os atendimentos pendentes dela de uma vez.
    """
    sessao = SessaoLocal()
    try:
        atendimentos_por_empresa = _agrupar_atendimentos_pendentes_por_empresa(sessao)

        for id_empresa, atendimentos_pendentes in atendimentos_por_empresa.items():
            empresa = sessao.get(Empresa, id_empresa)
            configuracao = empresa.configuracao_agente if empresa else None
            if empresa is None or configuracao is None:
                continue

            try:
                executar(
                    executar_monitoramento_de_atendimentos(
                        sessao, empresa, configuracao.nome_do_agente, atendimentos_pendentes
                    )
                )
            except Exception as erro:  # noqa: BLE001 — uma falha numa empresa não pode travar a varredura das demais
                sessao.rollback()
                logger.error("falha_no_monitoramento_de_atendimentos", id_empresa=id_empresa, erro=str(erro))

        logger.info("varredura_de_monitoramento_concluida", empresas_com_atendimentos_pendentes=len(atendimentos_por_empresa))
    finally:
        sessao.close()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a tarefa verificar_atendimentos_pendentes_de_atencao,
# disparada automaticamente pelo Celery Beat a cada 15 minutos. Ela agrupa
# por empresa todos os atendimentos EM_ATENDIMENTO silenciosos há 3+ dias e
# delega a decisão sobre cada um — reengajar agora ou aguardar — para UM
# turno do agente por empresa (agente/monitoramento.py), em vez de decidir
# isso sozinha em código Python. Bem mais simples que a tarefa equivalente
# nos outros dois projetos da linhagem, sem nenhuma lógica de abordagem.
# ==============================================================================

# ==============================================================================
# ARQUIVO: agente/ferramentas_monitoramento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Ferramentas que o modelo usa durante a VARREDURA PERIÓDICA de
# atendimentos (ver agente/monitoramento.py) — a rotina que roda sozinha,
# sem clique humano, para decidir se um atendimento em silêncio merece ser
# reengajado agora ou se é melhor aguardar mais um pouco.
#
# Diferente dos outros dois projetos da linhagem, só existem DUAS
# ferramentas aqui (não quatro): não há "abordar"/"desistir de follow-up",
# porque não existe abordagem automática neste domínio receptivo (ver
# Informacoes/Arquitetura.md, seção 2) — a varredura só cuida de
# atendimentos que JÁ estão em andamento e ficaram em silêncio.
#
# Diferente das ferramentas da conversa reativa (agente/ferramentas.py),
# estas EXECUTAM o efeito colateral de verdade na hora em que são
# chamadas (mandam WhatsApp, atualizam o banco) — a varredura periódica já
# roda direto numa tarefa do Celery, com acesso normal à sessão do banco.
# ==============================================================================

from dataclasses import dataclass, field

import structlog
from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session

from app.agente.orquestrador import enviar_reengajamento_por_silencio
from app.modelos.atendimento import Atendimento

logger = structlog.get_logger(__name__)


@dataclass
class RodadaDeMonitoramento:
    """
    Acumula o que o modelo decidiu durante uma varredura, para o log final
    (ver agente/monitoramento.py) — não é lido por mais ninguém além
    disso, já que os efeitos de verdade (WhatsApp enviado, banco
    atualizado) já acontecem dentro de cada ferramenta.
    """

    atendimentos_reengajados: list[int] = field(default_factory=list)
    atendimentos_aguardados: list[tuple[int, str]] = field(default_factory=list)


def montar_ferramentas_de_monitoramento(
    sessao: Session,
    empresa_id: int,
    atendimentos_por_id: dict[int, Atendimento],
    rodada: RodadaDeMonitoramento,
) -> list[BaseTool]:
    """
    Monta as duas ferramentas disponíveis durante uma varredura, fechando
    sobre a sessão do banco e o dicionário de atendimentos desta rodada
    específica (montado em agente/monitoramento.py a partir da consulta ao
    banco — o modelo nunca recebe nem manipula objetos do banco
    diretamente, só o ID de cada atendimento).
    """

    @tool
    async def reengajar_atendimento_silencioso(id_atendimento: int) -> str:
        """
        Retoma contato, por template aprovado, com um atendimento em aberto
        que ficou 3+ dias em silêncio depois da última mensagem sua — uma
        chance ÚNICA NA VIDA DESTE ATENDIMENTO de retomar antes de
        considerar que o cliente perdeu o interesse (se ele responder e
        depois ficar em silêncio de novo mais tarde, não há uma segunda
        chance).
        """
        atendimento = atendimentos_por_id.get(id_atendimento)
        if atendimento is None:
            return f"Atendimento #{id_atendimento} não está na lista desta varredura."
        try:
            await enviar_reengajamento_por_silencio(sessao, atendimento, empresa_id)
            rodada.atendimentos_reengajados.append(id_atendimento)
            return f"Atendimento #{id_atendimento} reengajado com sucesso."
        except Exception as erro:  # noqa: BLE001 — uma falha aqui não pode travar a decisão sobre os demais atendimentos
            sessao.rollback()
            logger.error("falha_ao_reengajar_atendimento_silencioso", id_atendimento=id_atendimento, erro=str(erro))
            return f"Falha ao reengajar o atendimento #{id_atendimento}: {erro}"

    @tool
    async def aguardar_atendimento(id_atendimento: int, motivo: str = "") -> str:
        """Decide NÃO reengajar este atendimento nesta varredura — ele continua pendente e pode ser reavaliado na próxima (em 15 minutos). Explique o motivo em uma frase curta."""
        # Valor padrão "" evita que o modelo esquecer de preencher o motivo
        # derrube a varredura INTEIRA da empresa com erro de validação —
        # aqui o impacto de uma falha é maior que numa conversa individual,
        # já que este turno decide sobre TODOS os atendimentos pendentes de uma vez.
        motivo = motivo or "sem motivo detalhado pelo modelo"
        rodada.atendimentos_aguardados.append((id_atendimento, motivo))
        return f"Atendimento #{id_atendimento} não será reengajado agora: {motivo}"

    return [reengajar_atendimento_silencioso, aguardar_atendimento]


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define as duas ferramentas que o modelo usa durante a
# varredura periódica de atendimentos: reengajar_atendimento_silencioso
# (retoma contato de verdade pelo WhatsApp — só uma vez em toda a vida do
# atendimento, ver Atendimento.reengajamento_por_silencio_enviado em
# modelos/atendimento.py) e aguardar_atendimento (não faz nada agora, só
# registra o motivo). RodadaDeMonitoramento acumula o que foi decidido,
# para o log final em agente/monitoramento.py.
# ==============================================================================

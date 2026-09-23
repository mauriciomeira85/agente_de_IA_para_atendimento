# ==============================================================================
# ARQUIVO: agente/monitoramento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a varredura periódica dos atendimentos EM ABERTO
# do jeito AGÊNTICO: em vez de um código Python decidir sozinho, atendimento
# por atendimento, se deve reengajar ou não, a plataforma monta o contexto
# de todos os atendimentos pendentes de uma empresa e deixa O MODELO
# decidir, chamando ferramentas reais (ver agente/ferramentas_monitoramento.py)
# — o mesmo padrão de tool calling livre já usado na conversa reativa (ver
# agente/nos.py), aplicado agora à varredura periódica.
#
# Diferença fundamental em relação ao Agente Comercial SDR e ao Agente de
# Cobrança (ver Informacoes/Arquitetura.md, seção 2): este agente é
# RECEPTIVO — não existe "abordar um caso novo" (não há base para
# importar, todo atendimento já nasceu de uma mensagem do cliente). A ÚNICA
# decisão que esta varredura toma é: um atendimento EM_ATENDIMENTO que
# ficou 3+ dias sem resposta do cliente merece um reengajamento por
# silêncio, ou é melhor aguardar mais um pouco? Isso simplifica bastante
# esta varredura em relação aos outros dois projetos da linhagem — não há
# "abordar_lead"/"desistir_do_lead" aqui, só "reengajar" ou "aguardar".
# ==============================================================================

from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.agente.ferramentas_monitoramento import RodadaDeMonitoramento, montar_ferramentas_de_monitoramento
from app.agente.loop_de_ferramentas import rodar_loop_de_ferramentas
from app.modelos.atendimento import Atendimento
from app.modelos.empresa import Empresa

logger = structlog.get_logger(__name__)

# Uma varredura pode decidir sobre vários atendimentos na mesma rodada —
# cada ferramenta chamada conta como um passo.
NUMERO_MAXIMO_DE_PASSOS_DO_MONITORAMENTO = 12


def _descrever_atendimento(atendimento: Atendimento) -> str:
    """Resume, em texto, os dados de UM atendimento relevantes para a decisão do modelo — nunca o objeto do banco em si."""
    dias_desde_ultima_atividade = (
        (datetime.now(timezone.utc) - atendimento.ultima_atividade_em).days if atendimento.ultima_atividade_em else 0
    )
    return (
        f"- Atendimento #{atendimento.id} ({atendimento.nome}): em aberto, em SILÊNCIO há "
        f"{dias_desde_ultima_atividade} dia(s) desde a última mensagem sua."
    )


async def executar_monitoramento_de_atendimentos(
    sessao: Session, empresa: Empresa, nome_do_agente: str, atendimentos: list[Atendimento]
) -> RodadaDeMonitoramento:
    """
    Roda UM turno do agente cobrindo TODOS os atendimentos em silêncio
    pendentes de UMA empresa — o modelo decide, atendimento por
    atendimento, se reengaja agora ou aguarda a próxima varredura, usando
    as ferramentas reais de agente/ferramentas_monitoramento.py.
    """
    rodada = RodadaDeMonitoramento()
    atendimentos_por_id = {atendimento.id: atendimento for atendimento in atendimentos}
    ferramentas = montar_ferramentas_de_monitoramento(sessao, empresa.id, atendimentos_por_id, rodada)

    lista_de_atendimentos_em_texto = "\n".join(_descrever_atendimento(atendimento) for atendimento in atendimentos)

    mensagens = [
        {
            "role": "system",
            "content": (
                f"Você é {nome_do_agente}, o agente de atendimento da {empresa.nome_fantasia}, responsável "
                "por retomar contato sozinho com atendimentos em silêncio, sem supervisão humana constante. "
                "Para cada atendimento listado abaixo, decida chamando UMA ferramenta: "
                "reengajar_atendimento_silencioso (retomar contato — use quando o silêncio já passou de 3 "
                "dias e vale a pena tentar de novo) ou aguardar_atendimento (não faz nada agora, explicando "
                "o motivo — use quando ainda for cedo, ou quando reengajar não parecer útil neste caso). "
                "Você pode chamar ferramentas para vários atendimentos diferentes nesta mesma rodada. Evite "
                "disparar muitos contatos de uma vez se isso parecer artificial ou repetitivo demais — "
                "prefira espaçar quando fizer sentido, para não acionar bloqueios de spam da própria Meta."
            ),
        },
        {"role": "user", "content": f"Atendimentos em silêncio agora:\n\n{lista_de_atendimentos_em_texto}"},
    ]

    await rodar_loop_de_ferramentas(
        mensagens,
        ferramentas,
        numero_maximo_de_passos=NUMERO_MAXIMO_DE_PASSOS_DO_MONITORAMENTO,
        id_para_log=empresa.id,
    )

    logger.info(
        "monitoramento_de_atendimentos_concluido",
        id_empresa=empresa.id,
        total_de_atendimentos=len(atendimentos),
        reengajados=len(rodada.atendimentos_reengajados),
        aguardados=len(rodada.atendimentos_aguardados),
    )
    return rodada


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define executar_monitoramento_de_atendimentos(), chamada
# pela tarefa periódica do Celery (ver app/tarefas/tarefas_monitoramento.py)
# — monta a lista de atendimentos em silêncio de uma empresa em texto, dá
# ao modelo as ferramentas de ação (reengajar/aguardar) e roda o mesmo loop
# de turno/passo da conversa reativa, deixando o modelo decidir. Bem mais
# simples que a varredura equivalente nos outros dois projetos da
# linhagem, porque não existe "abordar caso novo" neste domínio receptivo.
# ==============================================================================

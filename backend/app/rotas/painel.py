# ==============================================================================
# ARQUIVO: rotas/painel.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo calcula tudo que aparece na aba "Dashboard": os quatro
# cartões de quantidade, os três cartões de taxa percentual, os dois
# gráficos de barras horizontais, o gráfico de volume por dia e o ranking
# de setores mais acionados. Todo o cálculo acontece aqui, no backend — o
# frontend só desenha o que recebe.
#
# Diferente dos outros dois projetos da linhagem, o status de um
# Atendimento não é uma cadeia linear — ele termina em ENCAMINHADO OU
# RESOLVIDO, nunca os dois ao mesmo tempo. Por isso as contagens aqui não
# seguem o padrão "quem está neste status ou além" (que só funciona numa
# cadeia linear); em vez disso, cada card conta um subconjunto explícito
# de status (ver esquemas/painel.py).
#
# FILTRO DE PERÍODO (data_inicio/data_fim, opcionais): um atendimento
# pode atravessar várias datas (ex.: começou dia 9, foi resolvido dia 12)
# — não existe UMA data única que sirva pra filtrar tudo igual. Por isso
# cada grupo de cartão usa a data que responde à pergunta que ELE faz:
#   - Total de atendimentos / Em atendimento -> filtram por `criado_em`
#     (quando a conversa NASCEU). Respondem "quantos atendimentos novos
#     chegaram/estão em aberto nesse período".
#   - Encaminhados / Resolvidos sem humano -> filtram por
#     `ultima_atividade_em` (aproximação segura do momento do desfecho:
#     nada mexe num atendimento depois de marcado resolvido/encaminhado
#     sem também atualizar esse campo de novo — reabertura, reengajamento
#     etc.). Respondem "quantos foram FECHADOS nesse período", mesmo que
#     tenham começado antes.
#   - Taxa de reabertura -> tratada como coorte por `criado_em` (mesmo
#     critério de Total): "dos atendimentos que começaram nesse período,
#     quantos foram reabertos depois de resolvidos".
# Sem período informado (nenhum dos dois parâmetros), o comportamento é
# "todo o histórico", igual a antes deste filtro existir.
# ==============================================================================

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.esquemas.painel import (
    CartoesDeQuantidade,
    CartoesDeTaxa,
    EtapaDoFunil,
    PainelSaida,
    PontoDeVolumePorDia,
)
from app.modelos.atendimento import Atendimento, StatusAtendimento
from app.modelos.setor import Setor
from app.seguranca import exigir_id_empresa_do_usuario

roteador = APIRouter(prefix="/api/painel", tags=["Dashboard"])

# Quantos dias o gráfico de volume ao longo do tempo cobre QUANDO NÃO HÁ
# período selecionado — 14 dias é curto o bastante pra caber legível num
# gráfico de barras simples, sem precisar de zoom/scroll, e longo o
# bastante pra mostrar uma tendência real. Com período selecionado, o
# gráfico cobre exatamente o período (ver _construir_volume_por_dia).
NUMERO_DE_DIAS_NO_GRAFICO_DE_VOLUME = 14

# Teto de segurança: um período personalizado muito longo (ex.: "todo o
# histórico" digitado manualmente como datas) não deveria virar um
# gráfico de centenas de barras ilegíveis — acima disso, mostra só os
# últimos N dias do próprio período escolhido.
NUMERO_MAXIMO_DE_DIAS_NO_GRAFICO_COM_PERIODO = 60


def _calcular_taxa(numerador: int, denominador: int) -> float:
    """Calcula um percentual com segurança, devolvendo 0 quando o denominador é zero (evita divisão por zero)."""
    if denominador == 0:
        return 0.0
    return round((numerador / denominador) * 100, 1)


def _filtro_de_periodo(coluna: ColumnElement, data_inicio: date | None, data_fim: date | None) -> list[ColumnElement]:
    """
    Devolve as condições de data pra usar num WHERE, dado o par
    data_inicio/data_fim (qualquer um dos dois pode faltar) e a coluna de
    data/hora a filtrar (`criado_em` ou `ultima_atividade_em`, conforme o
    card — ver INTRODUÇÃO acima). `data_fim` é tratada como o dia INTEIRO
    (até 23:59:59), não só o instante 00:00 dela.
    """
    condicoes: list[ColumnElement] = []
    if data_inicio is not None:
        condicoes.append(coluna >= datetime.combine(data_inicio, datetime.min.time(), tzinfo=timezone.utc))
    if data_fim is not None:
        fim_exclusivo = datetime.combine(data_fim + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        condicoes.append(coluna < fim_exclusivo)
    return condicoes


@roteador.get("", response_model=PainelSaida)
def obter_painel(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
    data_inicio: date | None = Query(None, description="Início do período (AAAA-MM-DD), inclusive. Vazio = todo o histórico."),
    data_fim: date | None = Query(None, description="Fim do período (AAAA-MM-DD), inclusive. Vazio = todo o histórico."),
) -> PainelSaida:
    """Calcula e devolve todos os números da aba Dashboard para a empresa logada, no período pedido (ou todo o histórico)."""

    filtro_por_criacao = _filtro_de_periodo(Atendimento.criado_em, data_inicio, data_fim)
    filtro_por_desfecho = _filtro_de_periodo(Atendimento.ultima_atividade_em, data_inicio, data_fim)

    def contar(status_incluidos: list[StatusAtendimento], filtro_de_data: list[ColumnElement]) -> int:
        consulta = select(func.count(Atendimento.id)).where(
            Atendimento.id_empresa == id_empresa, Atendimento.status.in_(status_incluidos), *filtro_de_data
        )
        return sessao.scalar(consulta) or 0

    total_de_atendimentos = contar(list(StatusAtendimento), filtro_por_criacao)
    em_atendimento = contar([StatusAtendimento.RECEBIDO, StatusAtendimento.EM_ATENDIMENTO], filtro_por_criacao)
    encaminhados = contar([StatusAtendimento.ENCAMINHADO], filtro_por_desfecho)
    resolvidos = contar([StatusAtendimento.RESOLVIDO], filtro_por_desfecho)
    finalizados = encaminhados + resolvidos

    # Taxa de reabertura tratada como coorte por data de CRIAÇÃO (mesmo
    # critério do Total/Em atendimento) — ver INTRODUÇÃO acima.
    reabertos = sessao.scalar(
        select(func.count(Atendimento.id)).where(
            Atendimento.id_empresa == id_empresa, Atendimento.numero_de_reaberturas > 0, *filtro_por_criacao
        )
    ) or 0
    resolvidos_da_coorte = contar([StatusAtendimento.RESOLVIDO], filtro_por_criacao)
    ja_resolvidos_alguma_vez = resolvidos_da_coorte + reabertos

    cartoes_de_quantidade = CartoesDeQuantidade(
        total_de_atendimentos=total_de_atendimentos,
        em_atendimento=em_atendimento,
        encaminhados=encaminhados,
        resolvidos=resolvidos,
    )

    cartoes_de_taxa = CartoesDeTaxa(
        taxa_de_encaminhamento=_calcular_taxa(encaminhados, finalizados),
        taxa_de_resolucao_automatica=_calcular_taxa(resolvidos, finalizados),
        taxa_de_reabertura=_calcular_taxa(reabertos, ja_resolvidos_alguma_vez),
    )

    funil_de_encaminhamento = [
        EtapaDoFunil(etapa="Atendimentos", quantidade=total_de_atendimentos),
        EtapaDoFunil(etapa="Em atendimento", quantidade=em_atendimento),
        EtapaDoFunil(etapa="Encaminhados", quantidade=encaminhados),
    ]
    funil_de_resolucao = [
        EtapaDoFunil(etapa="Atendimentos", quantidade=total_de_atendimentos),
        EtapaDoFunil(etapa="Em atendimento", quantidade=em_atendimento),
        EtapaDoFunil(etapa="Resolvidos sem humano", quantidade=resolvidos),
    ]

    volume_por_dia = _construir_volume_por_dia(sessao, id_empresa, data_inicio, data_fim)

    # Ranking de setores mais acionados — mesmo critério de data dos
    # cartões de desfecho (Encaminhados). Só entram setores com pelo
    # menos 1 encaminhamento no período (um setor cadastrado, mas nunca
    # acionado, não precisa aparecer disputando espaço no gráfico).
    linhas_de_setor = sessao.execute(
        select(Setor.nome, func.count(Atendimento.id))
        .join(Atendimento, Atendimento.id_setor == Setor.id)
        .where(Setor.id_empresa == id_empresa, Atendimento.status == StatusAtendimento.ENCAMINHADO, *filtro_por_desfecho)
        .group_by(Setor.nome)
        .order_by(func.count(Atendimento.id).desc())
    ).all()
    setores_mais_acionados = [EtapaDoFunil(etapa=nome, quantidade=quantidade) for nome, quantidade in linhas_de_setor]

    return PainelSaida(
        cartoes_de_quantidade=cartoes_de_quantidade,
        cartoes_de_taxa=cartoes_de_taxa,
        funil_de_encaminhamento=funil_de_encaminhamento,
        funil_de_resolucao=funil_de_resolucao,
        volume_por_dia=volume_por_dia,
        setores_mais_acionados=setores_mais_acionados,
    )


def _construir_volume_por_dia(
    sessao: Session, id_empresa: int, data_inicio: date | None, data_fim: date | None
) -> list[PontoDeVolumePorDia]:
    """
    Monta a série do gráfico "Volume de Atendimentos por Dia" — cobre
    exatamente o período escolhido (limitado a
    NUMERO_MAXIMO_DE_DIAS_NO_GRAFICO_COM_PERIODO dias, contados a partir
    do fim, pra não virar um gráfico ilegível com um período muito longo),
    ou os últimos NUMERO_DE_DIAS_NO_GRAFICO_DE_VOLUME dias quando nenhum
    período foi escolhido. Dias sem nenhum atendimento aparecem com
    quantidade 0, não somem do gráfico, pra não distorcer o espaçamento
    entre as barras.
    """
    hoje = datetime.now(timezone.utc).date()
    ultimo_dia = data_fim or hoje
    if data_inicio is not None:
        primeiro_dia = max(data_inicio, ultimo_dia - timedelta(days=NUMERO_MAXIMO_DE_DIAS_NO_GRAFICO_COM_PERIODO - 1))
    else:
        primeiro_dia = ultimo_dia - timedelta(days=NUMERO_DE_DIAS_NO_GRAFICO_DE_VOLUME - 1)

    contagem_por_dia = dict(
        sessao.execute(
            select(func.date(Atendimento.criado_em), func.count(Atendimento.id)).where(
                Atendimento.id_empresa == id_empresa,
                *_filtro_de_periodo(Atendimento.criado_em, primeiro_dia, ultimo_dia),
            )
            .group_by(func.date(Atendimento.criado_em))
        ).all()
    )

    volume_por_dia = []
    dia = primeiro_dia
    while dia <= ultimo_dia:
        volume_por_dia.append(PontoDeVolumePorDia(data=dia.isoformat(), quantidade=contagem_por_dia.get(dia, 0)))
        dia += timedelta(days=1)
    return volume_por_dia


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo expõe a rota GET /api/painel, que aceita um período
# opcional (data_inicio/data_fim) e devolve os quatro cartões de
# quantidade, os três cartões de taxa (encaminhamento, resolução
# automática, reabertura), os dois gráficos de barras horizontais
# (funil_de_encaminhamento e funil_de_resolucao), a série de volume por
# dia e o ranking de setores mais acionados. Cada grupo de número usa a
# data que faz sentido pra pergunta que ele responde (criação vs.
# desfecho) — ver INTRODUÇÃO no topo do arquivo.
# ==============================================================================

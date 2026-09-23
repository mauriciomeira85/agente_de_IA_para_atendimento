# ==============================================================================
# ARQUIVO: esquemas/painel.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Define o formato de dado devolvido para a aba "Dashboard": os quatro
# cartões de quantidade (primeira fileira), os dois cartões de taxa
# percentual (segunda fileira) e os números do funil usados para desenhar
# o gráfico de pirâmide.
#
# Diferente dos outros dois projetos da linhagem, o funil aqui NÃO é uma
# cadeia linear de status (o Atendimento termina em ENCAMINHADO OU
# RESOLVIDO, nunca os dois — ver modelos/atendimento.py:StatusAtendimento).
# Por isso, em vez de UM funil de 3 degraus, o Dashboard mostra DOIS
# gráficos de barras lado a lado, cada um com o mesmo par TOTAL/EM
# ATENDIMENTO na base e um terceiro degrau diferente: um termina em
# ENCAMINHADOS, o outro em RESOLVIDOS SEM HUMANO — a métrica mais
# importante deste domínio: quanto do volume a IA resolveu sem gerar
# trabalho pra um setor humano, comparado lado a lado com quanto precisou
# de um humano.
#
# Repare que os NOMES dos campos aqui foram escolhidos para bater
# exatamente com os cartões pedidos na tela — isso deixa o componente do
# frontend simples: ele só precisa "ler e mostrar", sem calcular nada
# sozinho (todo o cálculo acontece no backend, em app/rotas/painel.py).
# ==============================================================================

from pydantic import BaseModel


class CartoesDeQuantidade(BaseModel):
    """Primeira fileira do Dashboard: quantidades absolutas."""

    total_de_atendimentos: int
    em_atendimento: int
    encaminhados: int
    resolvidos: int


class CartoesDeTaxa(BaseModel):
    """Segunda fileira do Dashboard: percentuais."""

    taxa_de_encaminhamento: float  # encaminhados / (encaminhados + resolvidos)
    taxa_de_resolucao_automatica: float  # resolvidos / (encaminhados + resolvidos)
    # % de atendimentos que já foram marcados RESOLVIDO em algum momento e
    # o cliente escreveu de novo depois — sinal de "resolvido" que não se
    # confirmou na prática (ver Atendimento.numero_de_reaberturas).
    taxa_de_reabertura: float


class EtapaDoFunil(BaseModel):
    """Um degrau de um gráfico de barras horizontais (nome + quantidade)."""

    etapa: str
    quantidade: int


class PontoDeVolumePorDia(BaseModel):
    """Um ponto do gráfico de volume ao longo do tempo."""

    data: str  # "AAAA-MM-DD"
    quantidade: int


class PainelSaida(BaseModel):
    """Formato completo devolvido pela rota GET /api/painel."""

    cartoes_de_quantidade: CartoesDeQuantidade
    cartoes_de_taxa: CartoesDeTaxa
    funil_de_encaminhamento: list[EtapaDoFunil]
    funil_de_resolucao: list[EtapaDoFunil]
    volume_por_dia: list[PontoDeVolumePorDia]
    setores_mais_acionados: list[EtapaDoFunil]


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define o formato de resposta da aba Dashboard: os cartões de
# quantidade (total, em atendimento, encaminhados, resolvidos), os três
# cartões de taxa (encaminhamento, resolução automática e reabertura), os
# dois gráficos de barras (funil_de_encaminhamento e funil_de_resolucao,
# cada um com 3 degraus), a série de volume por dia e o ranking de setores
# mais acionados.
# ==============================================================================

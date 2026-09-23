# ==============================================================================
# ARQUIVO: esquemas/setor.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Define o formato de dado usado pela aba "Setores": cadastro, edição e
# listagem dos departamentos humanos de uma empresa (ver
# modelos/setor.py) — o destino real para onde o agente encaminha um
# atendimento.
# ==============================================================================

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SetorEntrada(BaseModel):
    """Dados para criar ou editar um setor."""

    nome: str
    contato_nome: str
    contato_telefone: str


class SetorSaida(BaseModel):
    """Formato de um setor devolvido pela API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    contato_nome: str
    contato_telefone: str
    criado_em: datetime


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define os formatos de entrada (SetorEntrada) e saída
# (SetorSaida) usados pelo CRUD de Setores — a lista real de destinos
# válidos que a ferramenta encaminhar_para_setor confere contra o
# guardrail antes de agir.
# ==============================================================================

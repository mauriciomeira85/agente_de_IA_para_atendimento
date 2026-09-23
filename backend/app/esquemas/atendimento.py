# ==============================================================================
# ARQUIVO: esquemas/atendimento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Define o formato de dado usado pela aba "Base de Atendimentos": como um
# atendimento é devolvido para a tabela da tela e como ele pode ser editado
# manualmente (ex.: corrigir o nome de um cliente). Diferente dos outros
# dois projetos da linhagem, não existe "entrada" de importação em massa
# aqui — todo atendimento nasce sozinho, na primeira mensagem recebida (ver
# app/agente/orquestrador.py), então o único formato de entrada é edição
# pontual de um atendimento já existente.
# ==============================================================================

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modelos.atendimento import StatusAtendimento


class AtendimentoEdicao(BaseModel):
    """Dados para editar manualmente um atendimento já existente (ex.: corrigir nome/e-mail)."""

    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    whatsapp: str | None = None


class AtendimentoSaida(BaseModel):
    """Formato de um atendimento devolvido pela API (usado para montar a tabela na tela)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str | None
    telefone: str | None
    whatsapp: str | None
    status: StatusAtendimento
    id_setor: int | None
    resumo_do_atendimento: str | None
    # Quantas vezes este atendimento foi reaberto depois de marcado
    # RESOLVIDO — mostrado na tela como um selo pequeno ao lado do status
    # (ver Atendimento.numero_de_reaberturas), pensado como referência
    # visual pra uma futura cobrança por ciclo.
    numero_de_reaberturas: int
    ultima_atividade_em: datetime | None
    criado_em: datetime


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define os formatos de entrada e saída da Base de
# Atendimentos: AtendimentoEdicao (correção manual pontual) e
# AtendimentoSaida (o que alimenta a tabela da tela, incluindo o setor para
# onde foi encaminhado e o resumo gerado ao final do atendimento).
# ==============================================================================

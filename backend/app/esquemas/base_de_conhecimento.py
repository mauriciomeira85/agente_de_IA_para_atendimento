# ==============================================================================
# ARQUIVO: esquemas/base_de_conhecimento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Define o formato de dado usado pela aba "Base de Conhecimento": cadastro,
# edição e listagem dos itens (FAQ, políticas, descrição de produtos) que o
# agente consulta para responder dúvidas (ver modelos/item_de_conhecimento.py
# e agente/ferramentas.py:_ferramenta_consultar_base_de_conhecimento).
#
# O campo "embedding" nunca aparece nestes esquemas — é um detalhe interno
# de implementação (o vetor usado na busca por similaridade), gerado pelo
# backend na hora de salvar (ver integracoes_externas/embeddings.py), nunca
# algo que a empresa digita ou vê na tela.
# ==============================================================================

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ItemDeConhecimentoEntrada(BaseModel):
    """Dados para criar ou editar um item da Base de Conhecimento."""

    titulo: str
    conteudo: str


class ItemDeConhecimentoSaida(BaseModel):
    """Formato de um item devolvido pela API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    conteudo: str
    criado_em: datetime
    atualizado_em: datetime


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define os formatos de entrada (ItemDeConhecimentoEntrada) e
# saída (ItemDeConhecimentoSaida) usados pelo CRUD da Base de Conhecimento —
# nunca expõe o embedding em si, só título e conteúdo em texto livre.
# ==============================================================================

# ==============================================================================
# ARQUIVO: modelos/item_de_conhecimento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo define a tabela "itens_de_conhecimento" — a Base de
# Conhecimento de cada empresa (FAQ, políticas de atendimento, descrição de
# produtos/serviços). É a peça tecnicamente nova deste projeto: nem o
# Agente Comercial SDR nem o Agente de Cobrança precisam de busca
# semântica, porque respondem sobre uma única "oferta" configurada em texto
# livre; aqui, uma empresa pode ter dezenas de itens cadastrados, e o
# agente precisa recuperar só os 3-5 mais relevantes para cada pergunta,
# não ler tudo de uma vez.
#
# Cada item guarda, junto do texto, um "embedding" — um vetor de números
# que representa o SIGNIFICADO daquele texto (gerado por
# integracoes_externas/embeddings.py, via OpenAI). Perguntas do
# cliente também viram um vetor na hora, e a ferramenta
# consultar_base_de_conhecimento (agente/ferramentas.py) busca os itens com
# vetor mais PRÓXIMO do vetor da pergunta — essa é a "busca semântica": ela
# encontra o texto mais parecido em SIGNIFICADO, não em palavras exatas.
#
# A coluna "embedding" usa o tipo Vector da extensão pgvector do Postgres
# (ver docker-compose.yml — a imagem precisa ser "pgvector/pgvector:pg16")
# — decisão de simplicidade: em vez de um serviço de banco vetorial à
# parte (Qdrant, como o roadmap original deste projeto sugeria), reaproveita
# o MESMO Postgres já usado por tudo o mais, sem container novo pra operar.
# ==============================================================================

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco_dados import Base

# Dimensão do vetor gerado pelo modelo de embeddings configurado em
# openai_modelo_embeddings (app/configuracoes.py) — 1536 é a dimensão do
# padrão atual, text-embedding-3-small da OpenAI (ver
# integracoes_externas/embeddings.py para o histórico de por que é OpenAI
# e não Together AI). Se o modelo for trocado por um com dimensão
# diferente, esta constante (e a migração que cria a coluna) precisam
# acompanhar.
DIMENSAO_DO_EMBEDDING = 1536


class ItemDeConhecimento(Base):
    """Um item da Base de Conhecimento de uma empresa (FAQ, política, descrição de produto)."""

    __tablename__ = "itens_de_conhecimento"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)

    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)

    # Nulo enquanto o embedding ainda não foi gerado (ex.: falha temporária
    # na Together AI) — nesse caso o item simplesmente não aparece nas
    # buscas por similaridade até ser regravado com sucesso.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(DIMENSAO_DO_EMBEDDING), nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    empresa: Mapped["Empresa"] = relationship()


from app.modelos.empresa import Empresa  # noqa: E402

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a tabela "itens_de_conhecimento": título + texto
# livre + embedding (vetor pgvector) de cada item da Base de Conhecimento
# de uma empresa. É contra esta tabela que a ferramenta
# consultar_base_de_conhecimento faz a busca por similaridade que sustenta
# as respostas do agente sobre produtos/serviços/políticas da empresa.
# ==============================================================================

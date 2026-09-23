# ==============================================================================
# ARQUIVO: modelos/conversa.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo define duas tabelas que trabalham juntas para guardar o
# histórico de conversas que aparece na aba "Conversas" da interface:
#
#   - Conversa: representa a "sala de bate-papo" com um atendimento específico
#     (um atendimento tem, no máximo, uma conversa aberta por vez).
#   - Mensagem: cada mensagem individual trocada dentro dessa conversa —
#     seja ela enviada pelo cliente, pelo agente de IA, ou por um atendente
#     humano depois de um encaminhamento.
#
# Separar em duas tabelas (em vez de guardar tudo em uma lista dentro do
# atendimento) é o que permite mostrar o histórico completo, calcular a "última
# atividade" de um atendimento automaticamente, e evitar mensagens duplicadas
# quando a Meta reenvia o mesmo evento de webhook mais de uma vez.
# ==============================================================================

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco_dados import Base


class RemetenteMensagem(str, enum.Enum):
    """Quem enviou a mensagem dentro da conversa."""

    CLIENTE = "cliente"
    AGENTE_IA = "agente_ia"
    ATENDENTE_HUMANO = "atendente_humano"
    SISTEMA = "sistema"  # avisos internos, ex: "conversa encaminhada"


class TipoConteudoMensagem(str, enum.Enum):
    """O tipo de conteúdo da mensagem, conforme o produto multimodal exige."""

    TEXTO = "texto"
    AUDIO = "audio"
    IMAGEM = "imagem"
    DOCUMENTO = "documento"


class StatusEntregaMensagem(str, enum.Enum):
    """Status de entrega reportado pela WhatsApp Cloud API."""

    ENVIADA = "sent"
    ENTREGUE = "delivered"
    LIDA = "read"
    FALHOU = "failed"


class Conversa(Base):
    """Uma conversa (thread) entre a plataforma e um atendimento específico."""

    __tablename__ = "conversas"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    id_atendimento: Mapped[int] = mapped_column(ForeignKey("atendimentos.id"), nullable=False, index=True)

    canal: Mapped[str] = mapped_column(String(30), default="whatsapp")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Apelido opcional escolhido pela empresa para essa conversa (ex.: "João
    # - decisor"), que substitui o nome do atendimento na lista quando preenchido.
    # "Fixada" mantém a conversa no topo da lista, independente da data da
    # última mensagem — os dois vêm do menu de três pontinhos da aba Conversas.
    apelido: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fixada: Mapped[bool] = mapped_column(Boolean, default=False)

    atendimento: Mapped["Atendimento"] = relationship(back_populates="conversas")
    mensagens: Mapped[list["Mensagem"]] = relationship(
        back_populates="conversa", cascade="all, delete-orphan", order_by="Mensagem.criado_em"
    )


class Mensagem(Base):
    """Uma mensagem individual dentro de uma Conversa."""

    __tablename__ = "mensagens"
    __table_args__ = (
        # Garante que a mesma mensagem da Meta nunca seja gravada duas
        # vezes, mesmo que o webhook reenvie o mesmo evento (isso acontece
        # de vez em quando por natureza do protocolo — é uma exigência
        # explícita da documentação da Meta lidar com isso).
        UniqueConstraint("id_mensagem_whatsapp", name="uq_mensagem_whatsapp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    id_conversa: Mapped[int] = mapped_column(ForeignKey("conversas.id"), nullable=False, index=True)

    remetente: Mapped[RemetenteMensagem] = mapped_column(Enum(RemetenteMensagem, name="remetente_mensagem"))
    tipo_conteudo: Mapped[TipoConteudoMensagem] = mapped_column(
        Enum(TipoConteudoMensagem, name="tipo_conteudo_mensagem"), default=TipoConteudoMensagem.TEXTO
    )
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)

    # Referência à mídia de verdade quando tipo_conteudo != TEXTO — a
    # Meta manda só um ID (não o arquivo em si); esses três campos guardam
    # o necessário pra baixar e interpretar o conteúdo depois, dentro do
    # turno do agente (ver agente/nos.py:interpretar_midia). Ficam vazios
    # pra mensagens de texto.
    id_midia_whatsapp: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mime_type_da_midia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nome_do_arquivo_da_midia: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ID único que a WhatsApp Cloud API atribui a cada mensagem — usado
    # para deduplicação (ver __table_args__ acima) e para casar eventos de
    # status ("entregue", "lida") com a mensagem correta.
    id_mensagem_whatsapp: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status_entrega: Mapped[StatusEntregaMensagem | None] = mapped_column(
        Enum(StatusEntregaMensagem, name="status_entrega_mensagem"), nullable=True
    )

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversa: Mapped["Conversa"] = relationship(back_populates="mensagens")


from app.modelos.atendimento import Atendimento  # noqa: E402

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define "conversas" (uma thread por atendimento) e "mensagens"
# (cada mensagem trocada dentro de uma thread, com remetente, tipo de
# conteúdo e status de entrega). A restrição de unicidade em
# id_mensagem_whatsapp é o mecanismo que impede respostas duplicadas
# quando a Meta reenvia o mesmo evento de webhook mais de uma vez.
# ==============================================================================

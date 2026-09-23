# ==============================================================================
# ARQUIVO: modelos/setor.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo define a tabela "setores" — os departamentos humanos que uma
# empresa cadastra na aba "Setores" (ex.: Vendas, Financeiro, Suporte
# Técnico, ou qualquer nome que a empresa quiser). É o substituto direto do
# "desfecho único" que o Agente Comercial SDR e o Agente de Cobrança têm:
# lá, a empresa configura UM destino fixo para todos os casos; aqui o
# destino certo muda de atendimento para atendimento (uma dúvida sobre
# compra vai pra Vendas, uma sobre fatura vai pra Financeiro), então cada
# empresa cadastra quantos setores quiser, cada um com seu próprio contato
# humano de WhatsApp.
#
# Quando o agente decide encaminhar um atendimento (ferramenta
# encaminhar_para_setor, ver agente/ferramentas.py), o NOME do setor
# escolhido pelo modelo é conferido contra esta tabela em código —
# agente/guardrails_de_atendimento.py:validar_setor_de_encaminhamento — para
# garantir que o modelo nunca "invente" um setor que a empresa não
# cadastrou de verdade.
# ==============================================================================

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco_dados import Base


class Setor(Base):
    """Um departamento humano de uma empresa, para onde atendimentos podem ser encaminhados."""

    __tablename__ = "setores"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)

    nome: Mapped[str] = mapped_column(String(100), nullable=False)

    # Contato humano de verdade que recebe o WhatsApp real de encaminhamento
    # (ver agente/ferramentas.py:_ferramenta_encaminhar_para_setor).
    contato_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    contato_telefone: Mapped[str] = mapped_column(String(30), nullable=False)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped["Empresa"] = relationship()


from app.modelos.empresa import Empresa  # noqa: E402

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a tabela "setores": os departamentos humanos que cada
# empresa cadastra (nome + contato de WhatsApp), usados pela ferramenta de
# encaminhamento do agente como o destino real de um atendimento — no lugar
# do desfecho único e fixo usado pelos outros dois projetos da linhagem.
# ==============================================================================

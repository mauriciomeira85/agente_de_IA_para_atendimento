# ==============================================================================
# ARQUIVO: modelos/empresa.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# "Empresa" é a tabela mais importante do ponto de vista de arquitetura do
# sistema: ela representa cada CLIENTE da plataforma (uma empresa que se
# cadastrou para usar o Agente de Atendimento). Todo o resto do sistema
# (usuários, atendimentos, setores, base de conhecimento, conversas,
# configurações) está sempre "amarrado" a uma Empresa através da coluna
# id_empresa.
#
# É essa amarração que resolve o desafio central do produto: permitir que
# várias empresas entrem na plataforma ao mesmo tempo, cada uma com o seu
# próprio Agente de Atendimento funcionando de forma isolada, sem precisar
# criar uma aplicação nova do zero para cada cliente.
# ==============================================================================

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco_dados import Base


class Empresa(Base):
    """Representa uma empresa cliente da plataforma (um "tenant" do SaaS)."""

    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Nome que aparece no painel administrativo da empresa.
    nome_fantasia: Mapped[str] = mapped_column(String(150), nullable=False)

    # E-mail principal da conta (usado como referência da empresa, não é o
    # login de um usuário específico — cada colaborador tem seu próprio
    # usuário, ver modelos/usuario.py).
    email_conta: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relacionamentos ---
    # "cascade='all, delete-orphan'" garante que, se uma empresa for
    # excluída, todos os seus dados (atendimentos, conversas etc.) são removidos
    # junto — nenhuma informação de uma empresa fica "órfã" no banco.
    usuarios: Mapped[list["Usuario"]] = relationship(
        back_populates="empresa", cascade="all, delete-orphan"
    )
    atendimentos: Mapped[list["Atendimento"]] = relationship(
        back_populates="empresa", cascade="all, delete-orphan"
    )
    configuracao_agente: Mapped["ConfiguracaoAgente"] = relationship(
        back_populates="empresa", cascade="all, delete-orphan", uselist=False
    )
    setores: Mapped[list["Setor"]] = relationship(cascade="all, delete-orphan")
    itens_de_conhecimento: Mapped[list["ItemDeConhecimento"]] = relationship(cascade="all, delete-orphan")


# Importações no fim do arquivo apenas para o SQLAlchemy resolver os tipos
# usados nas anotações acima (evita import circular entre os modelos).
from app.modelos.configuracao_agente import ConfiguracaoAgente  # noqa: E402
from app.modelos.atendimento import Atendimento  # noqa: E402
from app.modelos.item_de_conhecimento import ItemDeConhecimento  # noqa: E402
from app.modelos.setor import Setor  # noqa: E402
from app.modelos.usuario import Usuario  # noqa: E402

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a tabela "empresas", que representa cada cliente do
# SaaS. Todas as outras tabelas do sistema guardam uma referência ao ID de
# uma Empresa, o que garante que os dados de clientes diferentes nunca se
# misturem — cada empresa "vive" isolada dentro da mesma plataforma.
# ==============================================================================

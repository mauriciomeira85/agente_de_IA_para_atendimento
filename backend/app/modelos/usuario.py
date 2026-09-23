# ==============================================================================
# ARQUIVO: modelos/usuario.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo define a tabela de usuários: as pessoas que efetivamente
# fazem login na plataforma (tela de Cadastro / Login). Cada usuário
# pertence a exatamente UMA empresa (id_empresa), e é essa ligação que o
# sistema usa, em toda consulta ao banco, para mostrar somente os dados
# daquela empresa.
# ==============================================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco_dados import Base


class Usuario(Base):
    """Uma pessoa com acesso de login à plataforma, vinculada a uma empresa."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)

    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)

    # A senha NUNCA é guardada em texto puro — apenas o resultado de um hash
    # (ver função gerar_hash_senha em app/seguranca.py).
    hash_senha: Mapped[str] = mapped_column(String(255), nullable=False)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped["Empresa"] = relationship(back_populates="usuarios")


from app.modelos.empresa import Empresa  # noqa: E402

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a tabela "usuarios": quem loga na plataforma. Cada
# registro guarda nome, e-mail, senha (em hash, nunca em texto puro) e o
# id_empresa ao qual pertence — essa última coluna é a base do isolamento
# entre clientes diferentes do SaaS.
# ==============================================================================

# ==============================================================================
# ARQUIVO: alembic/env.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo conecta o Alembic (a ferramenta de migrações) ao restante
# do projeto: ele lê a URL do banco a partir das mesmas configurações
# usadas pelo backend (app/configuracoes.py) e aponta para os modelos
# SQLAlchemy (app/modelos/) para que o comando
# "alembic revision --autogenerate" consiga detectar sozinho as tabelas
# que ainda não existem no banco.
# ==============================================================================

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.banco_dados import Base
from app.configuracoes import obter_configuracoes

# Garante que todas as tabelas do projeto sejam importadas antes do
# autogenerate rodar (ver modelos/__init__.py).
import app.modelos  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

configuracoes = obter_configuracoes()
config.set_main_option("sqlalchemy.url", configuracoes.url_banco_de_dados)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera o SQL das migrações sem se conectar de fato ao banco (modo "offline")."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Conecta de fato ao banco e aplica as migrações (modo normal, usado no deploy)."""
    conectavel = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)

    with conectavel.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo é o ponto de entrada do Alembic dentro do projeto: importa
# os modelos, pega a URL do banco das configurações centrais e decide
# entre gerar apenas o SQL (offline) ou aplicar as mudanças de verdade
# (online) — o modo usado no deploy real, via "alembic upgrade head".
# ==============================================================================

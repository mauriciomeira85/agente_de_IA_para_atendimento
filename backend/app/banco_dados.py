# ==============================================================================
# ARQUIVO: banco_dados.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo prepara a conexão do backend com o banco de dados PostgreSQL.
# Pense nele como a "porta de entrada" para o banco: qualquer parte do
# sistema que precise ler ou gravar informação (atendimentos, conversas,
# configurações da empresa) passa por aqui.
#
# Usamos o SQLAlchemy, uma biblioteca que permite representar tabelas do
# banco como classes Python comuns (ver a pasta "modelos/"), evitando a
# necessidade de escrever SQL manualmente na maior parte do código.
# ==============================================================================

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()

# O "engine" é o objeto que sabe como falar com o PostgreSQL de fato
# (endereço, usuário, senha — tudo isso já está embutido na URL de conexão).
motor_banco = create_engine(configuracoes.url_banco_de_dados, pool_pre_ping=True)

# A "SessionLocal" é uma fábrica de sessões: cada requisição da API abre
# uma sessão nova, faz suas leituras/gravações, e fecha a sessão no final.
SessaoLocal = sessionmaker(autocommit=False, autoflush=False, bind=motor_banco)


class Base(DeclarativeBase):
    """
    Classe-base da qual todas as tabelas (modelos) do projeto herdam.
    É a partir dela que o SQLAlchemy descobre quais tabelas existem e
    consegue gerar as migrações do banco de dados (ver pasta "alembic/").
    """


def obter_sessao() -> Generator[Session, None, None]:
    """
    Função de "dependência" usada pelas rotas do FastAPI. Ela abre uma
    sessão de banco de dados, entrega essa sessão para a rota usar, e
    garante que a sessão seja fechada no final — mesmo se der erro no meio
    do caminho. Exemplo de uso em uma rota:

        @roteador.get("/atendimentos")
        def listar_atendimentos(sessao: Session = Depends(obter_sessao)):
            ...
    """
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo cria a conexão (engine) com o PostgreSQL, define a classe
# Base que todas as tabelas do projeto usam, e expõe a função
# obter_sessao(), que entrega uma sessão de banco de dados pronta para uso
# em qualquer rota da API, fechando-a automaticamente ao final.
# ==============================================================================

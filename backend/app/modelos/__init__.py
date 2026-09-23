# ==============================================================================
# ARQUIVO: modelos/__init__.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo existe só para reunir, em um único lugar, a importação de
# todas as tabelas (modelos) do banco de dados. Isso é importante porque a
# ferramenta que gera as migrações do banco (Alembic) precisa "enxergar"
# todas as tabelas de uma vez para saber o que criar.
# ==============================================================================

from app.modelos.conversa import Conversa, Mensagem  # noqa: F401
from app.modelos.empresa import Empresa  # noqa: F401
from app.modelos.configuracao_agente import ConfiguracaoAgente  # noqa: F401
from app.modelos.integracao import IntegracaoWhatsApp, IntegracaoSaida  # noqa: F401
from app.modelos.item_de_conhecimento import ItemDeConhecimento  # noqa: F401
from app.modelos.setor import Setor  # noqa: F401
from app.modelos.atendimento import Atendimento  # noqa: F401
from app.modelos.usuario import Usuario  # noqa: F401

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Ao importar este pacote (app.modelos), o Python automaticamente carrega
# todas as classes de tabela do sistema: Empresa, Usuario, Atendimento,
# Setor, ItemDeConhecimento, Conversa, Mensagem, ConfiguracaoAgente,
# IntegracaoWhatsApp e IntegracaoSaida.
# ==============================================================================

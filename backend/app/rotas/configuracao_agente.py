# ==============================================================================
# ARQUIVO: rotas/configuracao_agente.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a aba "Configuração do Agente": buscar a
# configuração atual da empresa (para preencher o formulário quando a tela
# abre) e salvar as alterações feitas pelo usuário. Como cada empresa tem
# exatamente uma ConfiguracaoAgente (criada automaticamente no cadastro,
# ver app/rotas/autenticacao.py), esta rota nunca precisa de um "id" na
# URL — ela sempre trabalha com a configuração da empresa logada.
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.esquemas.configuracao_agente import AreaDeAtuacao, ConfiguracaoAgenteEntrada, ConfiguracaoAgenteSaida
from app.modelos.configuracao_agente import ConfiguracaoAgente
from app.seguranca import exigir_id_empresa_do_usuario

roteador = APIRouter(prefix="/api/configuracao-agente", tags=["Configuração do Agente"])


def _buscar_ou_criar(sessao: Session, id_empresa: int) -> ConfiguracaoAgente:
    """
    Busca a configuração da empresa logada. Na teoria ela sempre existe
    (é criada junto com a empresa no cadastro), mas criamos uma nova aqui
    como rede de segurança, caso o registro tenha sido removido por algum
    motivo — assim a tela nunca quebra por falta de configuração.
    """
    configuracao = sessao.scalar(
        select(ConfiguracaoAgente).where(ConfiguracaoAgente.id_empresa == id_empresa)
    )
    if configuracao is None:
        configuracao = ConfiguracaoAgente(id_empresa=id_empresa)
        sessao.add(configuracao)
        sessao.commit()
        sessao.refresh(configuracao)
    return configuracao


def _para_saida(configuracao: ConfiguracaoAgente) -> ConfiguracaoAgenteSaida:
    """Converte o modelo do banco (que guarda a área de atuação como dict solto) para o esquema de saída."""
    dados = ConfiguracaoAgenteSaida.model_validate(configuracao, from_attributes=True).model_dump()
    dados["area_atuacao"] = AreaDeAtuacao(**(configuracao.area_atuacao or {}))
    return ConfiguracaoAgenteSaida(**dados)


@roteador.get("", response_model=ConfiguracaoAgenteSaida)
def obter_configuracao(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> ConfiguracaoAgenteSaida:
    """Devolve a configuração atual do agente, para preencher o formulário da tela."""
    configuracao = _buscar_ou_criar(sessao, id_empresa)
    return _para_saida(configuracao)


@roteador.put("", response_model=ConfiguracaoAgenteSaida)
def salvar_configuracao(
    dados: ConfiguracaoAgenteEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> ConfiguracaoAgenteSaida:
    """
    Salva as alterações feitas no formulário da aba Configuração do
    Agente. A partir do próximo turno de conversa, o agente já passa a se
    comportar conforme o que foi salvo aqui — não é necessário reiniciar
    nada, porque o backend lê esta tabela a cada mensagem recebida (ver
    app/rotas/whatsapp_webhook.py).
    """
    configuracao = _buscar_ou_criar(sessao, id_empresa)

    valores = dados.model_dump()
    valores["area_atuacao"] = valores["area_atuacao"]  # já está em formato de dict simples

    for campo, valor in valores.items():
        setattr(configuracao, campo, valor)

    sessao.commit()
    sessao.refresh(configuracao)
    return _para_saida(configuracao)


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo expõe GET e PUT /api/configuracao-agente — respectivamente,
# carregar e salvar o formulário da aba Configuração do Agente. Como o
# agente lê essa tabela diretamente do banco a cada mensagem, qualquer
# alteração salva aqui entra em vigor imediatamente na próxima conversa,
# sem precisar reiniciar o backend.
# ==============================================================================

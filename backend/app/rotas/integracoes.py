# ==============================================================================
# ARQUIVO: rotas/integracoes.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a aba "Integrações": enviar os dados do
# Dashboard (aba Painel) para um sistema externo da empresa.
#
# Diferente dos outros dois projetos da linhagem, não existe aqui a metade
# de ENTRADA ("trazer contatos de um CRM externo") — não existe importação
# de contatos neste domínio, todo atendimento nasce automaticamente da
# primeira mensagem recebida (ver Informacoes/Arquitetura.md, seção 2).
# ==============================================================================

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.esquemas.integracao_saida import IntegracaoSaidaEntrada, IntegracaoSaidaSaida
from app.integracoes_externas.envio_dashboard import enviar_dados_do_dashboard
from app.modelos.integracao import IntegracaoSaida
from app.seguranca import exigir_id_empresa_do_usuario

roteador = APIRouter(prefix="/api/integracoes", tags=["Integrações"])


@roteador.get("/saida", response_model=list[IntegracaoSaidaSaida])
def listar_integracoes_de_saida(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> list[IntegracaoSaida]:
    """Lista os destinos já cadastrados para envio dos dados do Dashboard."""
    consulta = select(IntegracaoSaida).where(IntegracaoSaida.id_empresa == id_empresa)
    return list(sessao.scalars(consulta))


@roteador.post("/saida", response_model=IntegracaoSaidaSaida, status_code=status.HTTP_201_CREATED)
def cadastrar_integracao_de_saida(
    dados: IntegracaoSaidaEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> IntegracaoSaida:
    """Cadastra um novo destino externo para envio dos dados do Dashboard."""
    integracao = IntegracaoSaida(
        id_empresa=id_empresa,
        nome_da_conexao=dados.nome_da_conexao,
        url_webhook=dados.url_webhook,
        chave_api=dados.chave_api,
    )
    sessao.add(integracao)
    sessao.commit()
    sessao.refresh(integracao)
    return integracao


@roteador.delete("/saida/{id_integracao}", status_code=status.HTTP_204_NO_CONTENT)
def remover_integracao_de_saida(
    id_integracao: int,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> None:
    """Remove um destino de envio cadastrado."""
    integracao = sessao.get(IntegracaoSaida, id_integracao)
    if integracao is None or integracao.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integração não encontrada.")

    sessao.delete(integracao)
    sessao.commit()


@roteador.post("/saida/{id_integracao}/enviar-agora", response_model=IntegracaoSaidaSaida)
async def enviar_dados_do_dashboard_agora(
    id_integracao: int,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> IntegracaoSaida:
    """Monta o payload atual do Dashboard e envia agora mesmo para o destino configurado."""
    from app.rotas.painel import obter_painel  # import local: evita ciclo (painel.py não precisa conhecer integracoes.py)

    integracao = sessao.get(IntegracaoSaida, id_integracao)
    if integracao is None or integracao.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integração não encontrada.")

    painel = obter_painel(sessao=sessao, id_empresa=id_empresa)
    payload = {
        "id_empresa": id_empresa,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        **painel.model_dump(),
    }

    sucesso = await enviar_dados_do_dashboard(integracao.url_webhook, integracao.chave_api, payload)

    integracao.ultimo_envio_em = datetime.now(timezone.utc)
    integracao.ultimo_envio_com_sucesso = sucesso
    sessao.commit()
    sessao.refresh(integracao)
    return integracao


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo expõe /api/integracoes/saida: cadastro, remoção e envio sob
# demanda dos destinos externos configurados para receber os dados do
# Dashboard. Não existe metade de entrada (CRM externo) neste projeto — ver
# introdução.
# ==============================================================================

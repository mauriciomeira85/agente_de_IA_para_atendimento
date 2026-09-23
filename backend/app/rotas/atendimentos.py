# ==============================================================================
# ARQUIVO: rotas/atendimentos.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a aba "Base de Atendimentos": listar com filtros
# e editar/excluir um atendimento manualmente.
#
# Diferente dos outros dois projetos da linhagem, NÃO existe aqui rota de
# criação manual nem de importação em massa — um Atendimento só nasce de um
# jeito, automaticamente, na primeira mensagem recebida de um número novo
# (ver app/agente/orquestrador.py:processar_mensagem_recebida). Isso é a
# consequência direta de este ser o primeiro agente RECEPTIVO da linhagem
# (ver Informacoes/Arquitetura.md, seção 2) — não existe "abordagem" nem
# "base para importar antes de contatar".
#
# Toda rota aqui recebe "id_empresa" através da dependência
# exigir_id_empresa_do_usuario (ver app/seguranca.py) e usa esse valor em
# TODA consulta ao banco — é assim que garantimos que uma empresa nunca
# veja ou altere os atendimentos de outra.
# ==============================================================================

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.esquemas.atendimento import AtendimentoEdicao, AtendimentoSaida
from app.modelos.atendimento import Atendimento, StatusAtendimento
from app.seguranca import exigir_id_empresa_do_usuario

roteador = APIRouter(prefix="/api/atendimentos", tags=["Base de Atendimentos"])


@roteador.get("", response_model=list[AtendimentoSaida])
def listar_atendimentos(
    status_filtro: StatusAtendimento | None = None,
    busca: str | None = None,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> list[Atendimento]:
    """
    Lista os atendimentos da empresa logada, com dois filtros opcionais
    usados pela tabela da tela: por status (o mesmo status que aparece nos
    cartões do Dashboard) e por busca livre (nome, e-mail ou telefone).
    """
    consulta = select(Atendimento).where(Atendimento.id_empresa == id_empresa)

    if status_filtro is not None:
        consulta = consulta.where(Atendimento.status == status_filtro)

    if busca:
        termo = f"%{busca.lower()}%"
        consulta = consulta.where(
            Atendimento.nome.ilike(termo) | Atendimento.email.ilike(termo) | Atendimento.telefone.ilike(termo)
        )

    consulta = consulta.order_by(Atendimento.criado_em.desc())
    return list(sessao.scalars(consulta))


@roteador.put("/{id_atendimento}", response_model=AtendimentoSaida)
def editar_atendimento(
    id_atendimento: int,
    dados: AtendimentoEdicao,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> Atendimento:
    """Corrige os dados cadastrais de um atendimento já existente (ex.: nome/e-mail digitados errado)."""
    atendimento = sessao.get(Atendimento, id_atendimento)
    if atendimento is None or atendimento.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atendimento não encontrado.")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(atendimento, campo, valor)

    sessao.commit()
    sessao.refresh(atendimento)
    return atendimento


@roteador.delete("/{id_atendimento}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_atendimento(
    id_atendimento: int,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> None:
    """Exclui um atendimento da base."""
    atendimento = sessao.get(Atendimento, id_atendimento)
    if atendimento is None or atendimento.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atendimento não encontrado.")

    sessao.delete(atendimento)
    sessao.commit()


@roteador.post("/marcar-ultima-atividade/{id_atendimento}", response_model=AtendimentoSaida)
def marcar_ultima_atividade(
    id_atendimento: int,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> Atendimento:
    """
    Atualiza manualmente a data/hora da última atividade de um atendimento
    — usada internamente pelo webhook do WhatsApp a cada mensagem nova (ver
    app/rotas/whatsapp_webhook.py), e exposta aqui também para eventuais
    ajustes manuais feitos pela própria empresa.
    """
    atendimento = sessao.get(Atendimento, id_atendimento)
    if atendimento is None or atendimento.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atendimento não encontrado.")

    atendimento.ultima_atividade_em = datetime.now(timezone.utc)
    sessao.commit()
    sessao.refresh(atendimento)
    return atendimento


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo implementa a Base de Atendimentos: listar com filtros de
# status e busca, corrigir dados cadastrais e excluir. Sem criação manual
# nem importação — todo atendimento nasce automaticamente na primeira
# mensagem recebida (ver app/agente/orquestrador.py).
# ==============================================================================

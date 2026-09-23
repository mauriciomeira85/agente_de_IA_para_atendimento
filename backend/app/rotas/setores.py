# ==============================================================================
# ARQUIVO: rotas/setores.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a aba "Setores" — CRUD simples dos departamentos
# humanos que uma empresa cadastra (ver modelos/setor.py). É essa lista que
# a ferramenta encaminhar_para_setor (agente/ferramentas.py) usa para
# decidir para onde mandar um atendimento, e que o guardrail
# (agente/guardrails_de_atendimento.py) usa para confirmar que o modelo não
# inventou um setor inexistente.
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.esquemas.setor import SetorEntrada, SetorSaida
from app.modelos.setor import Setor
from app.seguranca import exigir_id_empresa_do_usuario

roteador = APIRouter(prefix="/api/setores", tags=["Setores"])


@roteador.get("", response_model=list[SetorSaida])
def listar_setores(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> list[Setor]:
    """Lista os setores cadastrados pela empresa logada."""
    consulta = select(Setor).where(Setor.id_empresa == id_empresa).order_by(Setor.nome)
    return list(sessao.scalars(consulta))


@roteador.post("", response_model=SetorSaida, status_code=status.HTTP_201_CREATED)
def cadastrar_setor(
    dados: SetorEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> Setor:
    """Cadastra um novo setor (ex.: Vendas, Financeiro, Suporte Técnico)."""
    setor = Setor(id_empresa=id_empresa, **dados.model_dump())
    sessao.add(setor)
    sessao.commit()
    sessao.refresh(setor)
    return setor


@roteador.put("/{id_setor}", response_model=SetorSaida)
def editar_setor(
    id_setor: int,
    dados: SetorEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> Setor:
    """Edita nome ou contato de um setor já cadastrado."""
    setor = sessao.get(Setor, id_setor)
    if setor is None or setor.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setor não encontrado.")

    for campo, valor in dados.model_dump().items():
        setattr(setor, campo, valor)

    sessao.commit()
    sessao.refresh(setor)
    return setor


@roteador.delete("/{id_setor}", status_code=status.HTTP_204_NO_CONTENT)
def remover_setor(
    id_setor: int,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> None:
    """
    Remove um setor. Atendimentos já encaminhados para ele mantêm o
    histórico (id_setor vira referência "quebrada" só na exibição — o
    registro da conversa e do encaminhamento em si não é apagado).
    """
    setor = sessao.get(Setor, id_setor)
    if setor is None or setor.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setor não encontrado.")

    sessao.delete(setor)
    sessao.commit()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo implementa o CRUD completo de Setores: listar, cadastrar,
# editar e remover — a lista real de destinos válidos de encaminhamento
# para cada empresa.
# ==============================================================================

# ==============================================================================
# ARQUIVO: rotas/base_de_conhecimento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a aba "Base de Conhecimento": CRUD dos itens (FAQ,
# políticas, descrição de produtos) que o agente consulta para responder
# dúvidas dos clientes (ver modelos/item_de_conhecimento.py e
# agente/ferramentas.py:_ferramenta_consultar_base_de_conhecimento).
#
# Ao criar ou editar um item, esta rota gera o embedding do texto NA HORA
# (ver integracoes_externas/embeddings.py) e já grava o vetor junto — assim
# o item fica disponível para busca por similaridade imediatamente, sem
# precisar de um processo de indexação separado rodando em segundo plano.
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.esquemas.base_de_conhecimento import ItemDeConhecimentoEntrada, ItemDeConhecimentoSaida
from app.integracoes_externas.embeddings import gerar_embedding
from app.modelos.item_de_conhecimento import ItemDeConhecimento
from app.seguranca import exigir_id_empresa_do_usuario

roteador = APIRouter(prefix="/api/base-de-conhecimento", tags=["Base de Conhecimento"])


def _texto_para_embedding(titulo: str, conteudo: str) -> str:
    """Junta título e conteúdo antes de gerar o embedding — o título sozinho costuma carregar bastante do significado (ex.: 'Política de troca'), e incluí-lo melhora a busca."""
    return f"{titulo}\n\n{conteudo}"


@roteador.get("", response_model=list[ItemDeConhecimentoSaida])
def listar_itens(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> list[ItemDeConhecimento]:
    """Lista os itens da Base de Conhecimento da empresa logada."""
    consulta = (
        select(ItemDeConhecimento)
        .where(ItemDeConhecimento.id_empresa == id_empresa)
        .order_by(ItemDeConhecimento.titulo)
    )
    return list(sessao.scalars(consulta))


@roteador.post("", response_model=ItemDeConhecimentoSaida, status_code=status.HTTP_201_CREATED)
async def cadastrar_item(
    dados: ItemDeConhecimentoEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> ItemDeConhecimento:
    """Cadastra um novo item na Base de Conhecimento, já gerando o embedding."""
    embedding = await gerar_embedding(_texto_para_embedding(dados.titulo, dados.conteudo))

    item = ItemDeConhecimento(id_empresa=id_empresa, embedding=embedding, **dados.model_dump())
    sessao.add(item)
    sessao.commit()
    sessao.refresh(item)
    return item


@roteador.put("/{id_item}", response_model=ItemDeConhecimentoSaida)
async def editar_item(
    id_item: int,
    dados: ItemDeConhecimentoEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> ItemDeConhecimento:
    """Edita um item já cadastrado, regravando o embedding com o texto novo."""
    item = sessao.get(ItemDeConhecimento, id_item)
    if item is None or item.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado.")

    item.titulo = dados.titulo
    item.conteudo = dados.conteudo
    item.embedding = await gerar_embedding(_texto_para_embedding(dados.titulo, dados.conteudo))

    sessao.commit()
    sessao.refresh(item)
    return item


@roteador.delete("/{id_item}", status_code=status.HTTP_204_NO_CONTENT)
def remover_item(
    id_item: int,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> None:
    """Remove um item da Base de Conhecimento."""
    item = sessao.get(ItemDeConhecimento, id_item)
    if item is None or item.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado.")

    sessao.delete(item)
    sessao.commit()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo implementa o CRUD completo da Base de Conhecimento: listar,
# cadastrar, editar e remover — gerando (ou regravando) o embedding do
# texto a cada criação/edição, para que o item fique disponível na busca
# por similaridade usada pelo agente imediatamente.
# ==============================================================================

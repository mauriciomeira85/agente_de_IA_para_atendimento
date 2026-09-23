# ==============================================================================
# ARQUIVO: rotas/conversas.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a aba "Conversas": a lista de conversas em
# aberto (uma por atendimento, ordenada pela mais recente) e o histórico completo
# de mensagens de uma conversa específica, exatamente como aparece na
# tela de chat da interface — incluindo a mídia de verdade (foto, vídeo/
# GIF, áudio, documento) que um atendimento mandou, reexibida direto pela
# interface (ver armazenamento_midia.py e a rota "/mensagens/{id}/midia"
# abaixo), sem precisar abrir o WhatsApp.
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.armazenamento_midia import ler_midia
from app.banco_dados import obter_sessao
from app.configuracoes import obter_configuracoes
from app.esquemas.conversa import (
    ConversaAtualizarEntrada,
    ConversaDetalheSaida,
    ConversaResumoSaida,
    MensagemSaida,
)
from app.modelos.conversa import Conversa, Mensagem
from app.seguranca import exigir_id_empresa_do_usuario

configuracoes = obter_configuracoes()

roteador = APIRouter(prefix="/api/conversas", tags=["Conversas"])


@roteador.get("", response_model=list[ConversaResumoSaida])
def listar_conversas(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> list[ConversaResumoSaida]:
    """
    Lista todas as conversas da empresa logada — as fixadas (menu de três
    pontinhos) sempre no topo, e dentro de cada grupo (fixadas/não
    fixadas), as mais recentes primeiro.
    """
    consulta = (
        select(Conversa)
        .where(Conversa.id_empresa == id_empresa)
        .options(joinedload(Conversa.atendimento), joinedload(Conversa.mensagens))
        .order_by(Conversa.fixada.desc(), Conversa.atualizado_em.desc())
    )
    conversas = sessao.scalars(consulta).unique().all()

    return [
        ConversaResumoSaida(
            id=conversa.id,
            id_atendimento=conversa.id_atendimento,
            nome_atendimento=conversa.atendimento.nome,
            apelido=conversa.apelido,
            fixada=conversa.fixada,
            ultima_mensagem=conversa.mensagens[-1].conteudo if conversa.mensagens else None,
            atualizado_em=conversa.atualizado_em,
        )
        for conversa in conversas
    ]


def _buscar_conversa_da_empresa(sessao: Session, id_conversa: int, id_empresa: int) -> Conversa:
    """Busca a conversa garantindo que ela pertence à empresa logada — usado pelas três rotas abaixo."""
    conversa = sessao.get(Conversa, id_conversa)
    if conversa is None or conversa.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    return conversa


@roteador.get("/{id_conversa}", response_model=ConversaDetalheSaida)
def obter_conversa(
    id_conversa: int,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> ConversaDetalheSaida:
    """Devolve o histórico completo de mensagens de uma conversa específica."""
    conversa = _buscar_conversa_da_empresa(sessao, id_conversa, id_empresa)

    return ConversaDetalheSaida(
        id=conversa.id,
        id_atendimento=conversa.id_atendimento,
        nome_atendimento=conversa.atendimento.nome,
        apelido=conversa.apelido,
        fixada=conversa.fixada,
        mensagens=[MensagemSaida.model_validate(mensagem) for mensagem in conversa.mensagens],
    )


@roteador.patch("/{id_conversa}", response_model=ConversaResumoSaida)
def atualizar_conversa(
    id_conversa: int,
    dados: ConversaAtualizarEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> ConversaResumoSaida:
    """
    Usado pelo menu de três pontinhos da aba Conversas: renomear (apelido)
    e/ou fixar/desafixar — só os campos enviados no corpo são alterados.
    """
    conversa = _buscar_conversa_da_empresa(sessao, id_conversa, id_empresa)

    dados_enviados = dados.model_dump(exclude_unset=True)
    if "apelido" in dados_enviados:
        conversa.apelido = dados_enviados["apelido"]
    if "fixada" in dados_enviados:
        conversa.fixada = dados_enviados["fixada"]

    sessao.commit()
    sessao.refresh(conversa)

    return ConversaResumoSaida(
        id=conversa.id,
        id_atendimento=conversa.id_atendimento,
        nome_atendimento=conversa.atendimento.nome,
        apelido=conversa.apelido,
        fixada=conversa.fixada,
        ultima_mensagem=conversa.mensagens[-1].conteudo if conversa.mensagens else None,
        atualizado_em=conversa.atualizado_em,
    )


@roteador.delete("/{id_conversa}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_conversa(
    id_conversa: int,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> None:
    """Exclui a conversa e todo o histórico de mensagens (usado pelo menu de três pontinhos)."""
    conversa = _buscar_conversa_da_empresa(sessao, id_conversa, id_empresa)
    sessao.delete(conversa)
    sessao.commit()


@roteador.get("/mensagens/{id_mensagem}/midia")
def obter_midia_da_mensagem(
    id_mensagem: int,
    token: str = Query(...),
    sessao: Session = Depends(obter_sessao),
) -> Response:
    """
    Devolve os bytes de verdade (foto, vídeo/GIF, áudio, documento) de uma
    mensagem recebida de um atendimento — ver armazenamento_midia.py. Usada como
    `src`/`href` direto em tags HTML (`<img>`, `<audio>`, `<video>`, link de
    download) na aba Conversas, por isso a autenticação vem por parâmetro
    de URL (?token=...) em vez do cabeçalho "Authorization": nenhuma dessas
    tags permite mandar cabeçalhos customizados — mesmo motivo documentado
    em rotas/tempo_real.py, para o WebSocket.
    """
    erro_de_autenticacao = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")
    try:
        payload = jwt.decode(token, configuracoes.chave_secreta_jwt, algorithms=[configuracoes.algoritmo_jwt])
        id_empresa = int(payload["id_empresa"])
    except (JWTError, KeyError, ValueError) as erro:
        raise erro_de_autenticacao from erro

    mensagem = sessao.get(Mensagem, id_mensagem)
    if mensagem is None or mensagem.conversa.id_empresa != id_empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mensagem não encontrada.")

    if not mensagem.id_midia_whatsapp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Esta mensagem não tem mídia.")

    conteudo = ler_midia(mensagem.id_midia_whatsapp)
    if conteudo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de mídia não encontrado.")

    return Response(content=conteudo, media_type=mensagem.mime_type_da_midia or "application/octet-stream")


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo expõe as rotas da aba Conversas: GET /api/conversas (lista
# resumida, fixadas primeiro), GET /api/conversas/{id} (histórico
# completo), PATCH /api/conversas/{id} (renomear/fixar, usado pelo menu de
# três pontinhos), DELETE /api/conversas/{id} (excluir a conversa inteira)
# e GET /api/conversas/mensagens/{id}/midia (bytes de uma mídia recebida,
# autenticada por token na URL — ver introdução da rota). A gravação de
# novas mensagens acontece em outro lugar — no webhook do WhatsApp (ver
# app/rotas/whatsapp_webhook.py) — já que é de lá que as mensagens
# realmente chegam.
# ==============================================================================

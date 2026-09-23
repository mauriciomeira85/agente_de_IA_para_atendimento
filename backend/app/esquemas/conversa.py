# ==============================================================================
# ARQUIVO: esquemas/conversa.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Define o formato de dado usado pela aba "Conversas": a lista de
# conversas em aberto (uma por atendimento) e o histórico de mensagens de cada
# uma, exatamente como aparecem na tela de chat da interface.
# ==============================================================================

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modelos.conversa import RemetenteMensagem, StatusEntregaMensagem, TipoConteudoMensagem


class MensagemSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    remetente: RemetenteMensagem
    tipo_conteudo: TipoConteudoMensagem
    conteudo: str
    status_entrega: StatusEntregaMensagem | None
    criado_em: datetime
    # Preenchidos só quando a mensagem tem mídia de verdade salva em disco
    # (ver armazenamento_midia.py) — o frontend usa `mime_type_da_midia`
    # pra decidir como reproduzir (imagem/vídeo/áudio) e monta a URL da
    # mídia a partir do `id` acima (ver rotas/conversas.py, rota
    # "/mensagens/{id}/midia"). `id_midia_whatsapp` (o identificador da
    # Meta) nunca é exposto ao frontend — não é necessário lá.
    mime_type_da_midia: str | None = None
    nome_do_arquivo_da_midia: str | None = None


class ConversaResumoSaida(BaseModel):
    """Formato usado na lista lateral de conversas (uma linha por atendimento)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    id_atendimento: int
    nome_atendimento: str
    apelido: str | None
    fixada: bool
    ultima_mensagem: str | None
    atualizado_em: datetime


class ConversaDetalheSaida(BaseModel):
    """Formato usado ao abrir uma conversa específica, com todo o histórico."""

    id: int
    id_atendimento: int
    nome_atendimento: str
    apelido: str | None
    fixada: bool
    mensagens: list[MensagemSaida]


class ConversaAtualizarEntrada(BaseModel):
    """
    Corpo do PATCH usado pelo menu de três pontinhos (Renomear/Fixar).
    Os dois campos são opcionais e independentes: renomear não mexe em
    fixada, e vice-versa — só o que for enviado é alterado.
    """

    apelido: str | None = Field(default=None, max_length=100)
    fixada: bool | None = None


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define três formatos: MensagemSaida (uma mensagem
# individual), ConversaResumoSaida (a lista de conversas na barra lateral)
# e ConversaDetalheSaida (o histórico completo de uma conversa aberta),
# usados pela aba Conversas da interface.
# ==============================================================================

# ==============================================================================
# ARQUIVO: rotas/templates_whatsapp.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Painel ÚNICO dos templates de WhatsApp da empresa (aba Canais), criado na
# padronização dos três agentes (25/09/2026) — mesmo módulo dos Agentes de
# Cobrança e Comercial SDR, SEM o template de abordagem (este agente nunca
# inicia contato: só responde quem escreve primeiro). Por isso aqui não há
# rascunho pela IA nem texto editável — os 4 templates têm texto fixo. O
# fluxo é:
#
#   1. A empresa preenche a Configuração do Agente e conecta o WhatsApp.
#   2. GET  /api/canais/whatsapp/templates              -> lista os 4
#      templates, com status real na Meta (uma única chamada à Graph API) e
#      o texto de prévia de cada um.
#   3. POST /api/canais/whatsapp/templates/enviar -> envia UM template
#      (botão de cada cartão). POST .../enviar-todos -> envia todos os
#      pendentes num clique. Nos dois, um template REJEITADO é reenviado
#      editando o existente (a Meta não aceita criar outro com o mesmo nome).
#   4. A Meta avisa o resultado pelo webhook (message_template_status_update,
#      ver rotas/whatsapp_webhook.py), que atualiza a tela em tempo real.
#
# As rotas antigas, de um template por vez (rotas/canais.py), continuam
# existindo e funcionando — este módulo só reaproveita as mesmas funções de
# integracoes_externas/meta_templates.py.
# ==============================================================================

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.integracoes_externas.meta_templates import (
    TEXTO_PADRAO_DO_TEMPLATE_DE_REENGAJAMENTO,
    _montar_texto_do_template_de_atencao,
    _montar_texto_do_template_de_notificacao,
    _montar_texto_do_template_de_reencaminhamento,
    consultar_templates_da_waba,
    criar_template_de_atencao,
    criar_template_de_notificacao,
    criar_template_de_reencaminhamento,
    criar_template_de_reengajamento,
    montar_previa_do_template_de_atencao,
    montar_previa_do_template_de_notificacao,
    montar_previa_do_template_de_reencaminhamento,
    montar_previa_do_template_de_reengajamento,
)
from app.modelos.configuracao_agente import ConfiguracaoAgente
from app.modelos.empresa import Empresa
from app.modelos.integracao import IntegracaoWhatsApp
from app.seguranca import exigir_id_empresa_do_usuario

logger = structlog.get_logger(__name__)

roteador = APIRouter(prefix="/api/canais/whatsapp/templates", tags=["Templates do WhatsApp"])


# ------------------------------------------------------------------------------
# Registro dos templates deste agente
# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class DefinicaoDeTemplate:
    chave: str
    titulo: str
    descricao: str
    categoria: str
    campo_do_nome: str  # coluna de ConfiguracaoAgente que guarda o nome do template
    editavel: bool
    montar_previa: Callable[[ConfiguracaoAgente, Empresa], str]
    criar: Callable[..., Awaitable[None]]
    # Texto REAL enviado à Meta, com as variáveis {{n}}, e o que cada
    # variável recebe no envio (cartões do painel).
    montar_texto: Callable[[ConfiguracaoAgente, Empresa], str] = lambda c, e: ""
    legenda: str = ""


def _nome_do_agente(configuracao: ConfiguracaoAgente) -> str:
    return configuracao.nome_do_agente or "Assistente de Atendimento"


TEMPLATES_DESTE_AGENTE: list[DefinicaoDeTemplate] = [
    DefinicaoDeTemplate(
        chave="notificacao",
        titulo="Aviso ao setor humano",
        descricao="Avisa o contato do setor quando um atendimento é encaminhado.",
        categoria="UTILITY",
        campo_do_nome="nome_do_template_encaminhamento",
        editavel=False,
        montar_previa=lambda c, e: montar_previa_do_template_de_notificacao(_nome_do_agente(c), e.nome_fantasia),
        criar=criar_template_de_notificacao,
        montar_texto=lambda c, e: _montar_texto_do_template_de_notificacao(_nome_do_agente(c), e.nome_fantasia),
        legenda="As variáveis recebem nome e WhatsApp do cliente e um resumo do atendimento no momento do envio.",
    ),
    DefinicaoDeTemplate(
        chave="reencaminhamento",
        titulo="Reencaminhamento",
        descricao="Avisa o setor quando um atendimento já encaminhado volta com algo novo.",
        categoria="UTILITY",
        campo_do_nome="nome_do_template_reencaminhamento",
        editavel=False,
        montar_previa=lambda c, e: montar_previa_do_template_de_reencaminhamento(_nome_do_agente(c), e.nome_fantasia),
        criar=criar_template_de_reencaminhamento,
        montar_texto=lambda c, e: _montar_texto_do_template_de_reencaminhamento(_nome_do_agente(c), e.nome_fantasia),
        legenda="As variáveis recebem nome e WhatsApp do cliente e um resumo do atendimento no momento do envio.",
    ),
    DefinicaoDeTemplate(
        chave="atencao",
        titulo="Atenção: suspeita de manipulação",
        descricao="Avisa o setor quando o cliente tenta manipular o agente.",
        categoria="UTILITY",
        campo_do_nome="nome_do_template_atencao",
        editavel=False,
        montar_previa=lambda c, e: montar_previa_do_template_de_atencao(_nome_do_agente(c), e.nome_fantasia),
        criar=criar_template_de_atencao,
        montar_texto=lambda c, e: _montar_texto_do_template_de_atencao(_nome_do_agente(c), e.nome_fantasia),
        legenda="As variáveis recebem nome e WhatsApp do cliente e um resumo do atendimento no momento do envio.",
    ),
    DefinicaoDeTemplate(
        chave="reengajamento",
        titulo="Reengajamento",
        descricao="Retoma o contato com um cliente que parou de responder no meio do atendimento.",
        categoria="MARKETING",
        campo_do_nome="nome_do_template_reengajamento",
        editavel=False,
        montar_previa=lambda c, e: montar_previa_do_template_de_reengajamento(_nome_do_agente(c), e.nome_fantasia),
        criar=criar_template_de_reengajamento,
        montar_texto=lambda c, e: TEXTO_PADRAO_DO_TEMPLATE_DE_REENGAJAMENTO,
        legenda="As variáveis recebem nome do cliente, nome do agente e empresa no momento do envio.",
    ),
]


# ------------------------------------------------------------------------------
# Esquemas (os mesmos dos outros dois agentes, para o painel do frontend
# ser idêntico nos três)
# ------------------------------------------------------------------------------
class TemplateDoPainelSaida(BaseModel):
    chave: str
    titulo: str
    descricao: str
    categoria: str
    nome: str
    editavel: bool
    texto: str | None = None
    previa: str
    status: str | None  # None = ainda não enviado | PENDING | APPROVED | REJECTED | ...
    motivo: str | None  # motivo da rejeição, quando houver
    exemplos: list[str] | None = None
    legenda: str = ""
    id: str | None = None
    texto_padrao: str | None = None


class EnviarTodosEntrada(BaseModel):
    texto_abordagem: str | None = None  # ignorado aqui (sem template de abordagem)


class EnviarUmEntrada(BaseModel):
    chave: str
    texto_abordagem: str | None = None  # ignorado aqui (sem template de abordagem)


class ResultadoDoEnvioSaida(BaseModel):
    chave: str
    nome: str
    resultado: str  # "enviado" | "ja_existia" | "erro"
    detalhe: str | None = None


# ------------------------------------------------------------------------------
# Rotas
# ------------------------------------------------------------------------------
def _carregar(sessao: Session, id_empresa: int) -> tuple[Empresa, ConfiguracaoAgente, IntegracaoWhatsApp]:
    empresa = sessao.get(Empresa, id_empresa)
    configuracao = sessao.scalar(select(ConfiguracaoAgente).where(ConfiguracaoAgente.id_empresa == id_empresa))
    integracao = sessao.scalar(select(IntegracaoWhatsApp).where(IntegracaoWhatsApp.id_empresa == id_empresa))
    if empresa is None or configuracao is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preencha e salve a Configuração do Agente primeiro.")
    if integracao is None or not integracao.id_waba_meta:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conecte o WhatsApp (aba Canais) primeiro.")
    return empresa, configuracao, integracao


@roteador.get("", response_model=list[TemplateDoPainelSaida])
async def listar_templates(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> list[TemplateDoPainelSaida]:
    """Lista os templates deste agente com o status real na Meta (uma chamada só à Graph API)."""
    empresa, configuracao, integracao = _carregar(sessao, id_empresa)
    na_meta = await consultar_templates_da_waba(integracao.id_waba_meta, integracao.token_de_acesso) or {}
    saida = []
    for definicao in TEMPLATES_DESTE_AGENTE:
        nome = getattr(configuracao, definicao.campo_do_nome)
        info = na_meta.get(nome, {})
        saida.append(
            TemplateDoPainelSaida(
                chave=definicao.chave,
                titulo=definicao.titulo,
                descricao=definicao.descricao,
                categoria=definicao.categoria,
                nome=nome,
                editavel=definicao.editavel,
                texto=definicao.montar_texto(configuracao, empresa),
                legenda=definicao.legenda,
                id=info.get("id"),
                previa=definicao.montar_previa(configuracao, empresa),
                status=info.get("status"),
                motivo=info.get("motivo"),
            )
        )
    return saida


STATUS_QUE_PERMITEM_ENVIO = (None, "REJECTED")


async def _enviar_um(
    definicao: DefinicaoDeTemplate,
    empresa: Empresa,
    configuracao: ConfiguracaoAgente,
    integracao: IntegracaoWhatsApp,
    na_meta: dict,
) -> ResultadoDoEnvioSaida:
    """
    Envia um template para análise: cria se ainda não existe na WABA, ou
    EDITA o existente se ele foi rejeitado. Em análise ou aprovado não é
    reenviado.
    """
    nome = getattr(configuracao, definicao.campo_do_nome)
    info = na_meta.get(nome) or {}
    if info.get("status") not in STATUS_QUE_PERMITEM_ENVIO:
        return ResultadoDoEnvioSaida(chave=definicao.chave, nome=nome, resultado="ja_existia", detalhe=info.get("status"))
    try:
        await definicao.criar(
            id_waba=integracao.id_waba_meta,
            token_de_acesso=integracao.token_de_acesso,
            nome_do_template=nome,
            nome_do_agente=_nome_do_agente(configuracao),
            nome_da_empresa=empresa.nome_fantasia,
            id_template_existente=info.get("id") if info.get("status") == "REJECTED" else None,
        )
        return ResultadoDoEnvioSaida(chave=definicao.chave, nome=nome, resultado="enviado")
    except ValueError as erro:
        return ResultadoDoEnvioSaida(chave=definicao.chave, nome=nome, resultado="erro", detalhe=str(erro))


@roteador.post("/enviar", response_model=ResultadoDoEnvioSaida)
async def enviar_um(
    dados: EnviarUmEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> ResultadoDoEnvioSaida:
    """Envia UM template para análise (botão de cada cartão do painel)."""
    definicao = next((d for d in TEMPLATES_DESTE_AGENTE if d.chave == dados.chave), None)
    if definicao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template desconhecido.")
    empresa, configuracao, integracao = _carregar(sessao, id_empresa)
    na_meta = await consultar_templates_da_waba(integracao.id_waba_meta, integracao.token_de_acesso) or {}
    resultado = await _enviar_um(definicao, empresa, configuracao, integracao, na_meta)
    if resultado.resultado == "erro":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=resultado.detalhe)
    logger.info("template_enviado", id_empresa=id_empresa, resultado=resultado.model_dump())
    return resultado


@roteador.post("/enviar-todos", response_model=list[ResultadoDoEnvioSaida])
async def enviar_todos(
    dados: EnviarTodosEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> list[ResultadoDoEnvioSaida]:
    """
    Um clique: envia para análise todos os templates deste agente que ainda
    não existem na WABA ou que foram rejeitados (estes são editados).
    """
    empresa, configuracao, integracao = _carregar(sessao, id_empresa)
    na_meta = await consultar_templates_da_waba(integracao.id_waba_meta, integracao.token_de_acesso) or {}
    resultados = list(
        await asyncio.gather(*(_enviar_um(d, empresa, configuracao, integracao, na_meta) for d in TEMPLATES_DESTE_AGENTE))
    )
    logger.info("templates_enviados_em_lote", id_empresa=id_empresa, resultados=[r.model_dump() for r in resultados])
    return resultados


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Painel único de templates (sem abordagem — o agente só responde): GET lista
# os 4 templates com status, motivo de rejeição e texto real (uma chamada à
# Meta), POST /enviar envia um template e POST /enviar-todos envia todos os
# pendentes. Um template rejeitado é reenviado editando o existente. O status é atualizado em tempo real pelo webhook da Meta
# (rotas/whatsapp_webhook.py).
# ==============================================================================

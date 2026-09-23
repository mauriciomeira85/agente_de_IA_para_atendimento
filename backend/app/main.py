# ==============================================================================
# ARQUIVO: main.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este é o arquivo que "liga" o backend: cria a aplicação FastAPI,
# habilita o CORS (para o frontend, rodando em outro endereço, conseguir
# chamar a API) e conecta todas as rotas construídas nos outros arquivos
# da pasta app/rotas/. É este arquivo que o servidor (Uvicorn) executa
# quando o container do backend sobe.
# ==============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.configuracoes import obter_configuracoes
from app.rotas import (
    atendimentos,
    autenticacao,
    base_de_conhecimento,
    canais,
    configuracao_agente,
    conversas,
    integracoes,
    painel,
    setores,
    tempo_real,
    whatsapp_webhook,
)

configuracoes = obter_configuracoes()

aplicativo = FastAPI(
    title=configuracoes.nome_da_aplicacao,
    description="API do Agente de Atendimento — um agente de IA multi-tenant que responde clientes finais pelo WhatsApp de cada empresa, usando uma base de conhecimento própria e encaminhando para o setor humano certo.",
    version="1.0.0",
)

# Libera o navegador do frontend (que roda em outro endereço/porta) a
# chamar esta API. Em produção, a lista de origens deve ser restrita ao
# domínio público real da plataforma (ver variável de ambiente
# ORIGENS_PERMITIDAS no .env, lida abaixo).
aplicativo.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if configuracoes.ambiente == "desenvolvimento" else [configuracoes.url_publica_da_plataforma],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cada arquivo dentro de app/rotas/ define um "roteador" — um conjunto de
# rotas relacionadas (ex.: tudo sobre atendimentos, tudo sobre o painel). Aqui
# eles são todos conectados na aplicação principal.
aplicativo.include_router(autenticacao.roteador)
aplicativo.include_router(painel.roteador)
aplicativo.include_router(atendimentos.roteador)
aplicativo.include_router(setores.roteador)
aplicativo.include_router(base_de_conhecimento.roteador)
aplicativo.include_router(conversas.roteador)
aplicativo.include_router(configuracao_agente.roteador)
aplicativo.include_router(canais.roteador)
aplicativo.include_router(integracoes.roteador)
aplicativo.include_router(whatsapp_webhook.roteador)
aplicativo.include_router(tempo_real.roteador)


@aplicativo.get("/api/saude", tags=["Saúde"])
def verificar_saude() -> dict:
    """
    Rota simples de "health check" — usada pelo Docker/Caddy para saber se
    o backend está de pé e respondendo, sem precisar de autenticação.
    """
    return {"status": "ok", "aplicacao": configuracoes.nome_da_aplicacao, "ambiente": configuracoes.ambiente}


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo cria a aplicação FastAPI (variável "aplicativo"), conecta
# todas as rotas do sistema (autenticação, painel, atendimentos, setores,
# base de conhecimento, conversas, configuração do agente, canais,
# integrações, o webhook do WhatsApp e o WebSocket de tempo real) e expõe
# uma rota de health check em /api/saude. Para rodar localmente:
#   uvicorn app.main:aplicativo --reload
# ==============================================================================

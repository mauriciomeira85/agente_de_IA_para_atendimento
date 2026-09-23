# ==============================================================================
# ARQUIVO: rotas/tempo_real.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo expõe o endpoint WebSocket que a aba "Conversas" do
# frontend usa para atualizar a tela sozinha, assim que uma mensagem nova
# chega ou é enviada — sem precisar ficar recarregando a página.
#
# WebSockets não enviam cabeçalhos HTTP customizados a partir do
# navegador (a API nativa "WebSocket" do JavaScript não permite isso), por
# isso a autenticação aqui é feita pelo token JWT enviado como parâmetro
# de URL (?token=...) em vez do cabeçalho "Authorization" usado pelas
# rotas normais da API.
# ==============================================================================

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.configuracoes import obter_configuracoes
from app.tempo_real import obter_canal_de_escuta

configuracoes = obter_configuracoes()

roteador = APIRouter(prefix="/api/tempo-real", tags=["Tempo real"])


@roteador.websocket("/conversas")
async def conversas_em_tempo_real(websocket: WebSocket, token: str = Query(...)) -> None:
    """
    Abre uma conexão WebSocket para a empresa autenticada e repassa, em
    tempo real, todo evento publicado no canal Redis daquela empresa (ver
    app/tempo_real.py) — novas mensagens de atendimentos e respostas do agente.
    """
    try:
        payload = jwt.decode(token, configuracoes.chave_secreta_jwt, algorithms=[configuracoes.algoritmo_jwt])
        id_empresa = int(payload["id_empresa"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4401)
        return

    await websocket.accept()

    cliente_redis, pubsub, canal = obter_canal_de_escuta(id_empresa)
    await pubsub.subscribe(canal)

    try:
        async for mensagem in pubsub.listen():
            if mensagem["type"] != "message":
                continue
            dados = mensagem["data"]
            await websocket.send_text(dados.decode() if isinstance(dados, bytes) else dados)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(canal)
        await pubsub.aclose()
        await cliente_redis.aclose()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo implementa a rota WebSocket /api/tempo-real/conversas:
# autentica pelo token na URL, assina o canal Redis da empresa e repassa
# cada evento publicado diretamente para o navegador conectado, até a
# conexão ser encerrada.
# ==============================================================================

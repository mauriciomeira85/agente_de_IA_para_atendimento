# ==============================================================================
# ARQUIVO: rotas/canais.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa a aba "Canais": onde a empresa conecta o
# WhatsApp que o agente vai usar para responder os clientes dela.
#
# O caminho principal é o botão "Conectar WhatsApp": a empresa faz login
# numa janela oficial da Meta e escolhe o número dela, sem copiar nenhuma
# credencial na mão. Existe também um formulário de conexão manual
# (Phone Number ID/WABA ID/token colados à mão) — mas ele só aparece para
# UMA conta específica (ver email_com_acesso_a_conexao_manual_whatsapp em
# configuracoes.py), usado enquanto essa conta ainda não tem um número
# comercial de verdade disponível para concluir o botão até o fim.
#
#   GET  /api/canais/whatsapp/config    -> dados que o botão precisa para
#                                           abrir a janela de login da Meta
#                                           (e se a conexão manual deve aparecer)
#   POST /api/canais/whatsapp/conectar  -> recebe o resultado do login e
#                                           conclui a conexão de verdade
#   PUT  /api/canais/whatsapp/manual    -> conexão manual, restrita a uma conta
#   GET  /api/canais/whatsapp           -> status da conexão já salva
#
# Depois de conectado o número, ainda faltam QUATRO peças que a Meta exige
# como template pré-aprovado (ver introdução de
# integracoes_externas/meta_templates.py — SEM o template de abordagem que
# os outros dois projetos da linhagem têm, este agente nunca inicia
# contato): notificação, reencaminhamento, atenção e reengajamento. Em vez
# de pedir para a empresa submeter isso na mão no painel da Meta, estas
# doze rotas automatizam:
#
#   GET  /api/canais/whatsapp/template-notificacao/previa      -> notificação: prévia
#   POST /api/canais/whatsapp/template-notificacao             -> notificação: submete
#   GET  /api/canais/whatsapp/template-notificacao             -> notificação: status
#   GET  /api/canais/whatsapp/template-reencaminhamento/previa -> reencaminhamento: prévia
#   POST /api/canais/whatsapp/template-reencaminhamento        -> reencaminhamento: submete
#   GET  /api/canais/whatsapp/template-reencaminhamento        -> reencaminhamento: status
#   GET  /api/canais/whatsapp/template-atencao/previa          -> atenção: prévia
#   POST /api/canais/whatsapp/template-atencao                 -> atenção: submete
#   GET  /api/canais/whatsapp/template-atencao                 -> atenção: status
#   GET  /api/canais/whatsapp/template-reengajamento/previa    -> reengajamento: prévia
#   POST /api/canais/whatsapp/template-reengajamento           -> reengajamento: submete
#   GET  /api/canais/whatsapp/template-reengajamento           -> reengajamento: status
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.configuracoes import obter_configuracoes
from app.esquemas.canal import (
    CanalWhatsAppSaida,
    ConectarCanalWhatsAppEntrada,
    ConectarCanalWhatsAppManualEntrada,
    ConfiguracaoEmbeddedSignupSaida,
    PreviaDoTemplateSaida,
    TemplateWhatsAppSaida,
)
from app.integracoes_externas.meta_embedded_signup import (
    descobrir_waba_e_numero,
    inscrever_webhook_da_waba,
    obter_numero_de_exibicao,
    registrar_numero_de_telefone,
    trocar_codigo_por_token,
)
from app.integracoes_externas.meta_templates import (
    consultar_status_do_template,
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
from app.modelos.usuario import Usuario
from app.seguranca import exigir_id_empresa_do_usuario, usuario_atual

configuracoes = obter_configuracoes()

roteador = APIRouter(prefix="/api/canais", tags=["Canais"])


@roteador.get("/whatsapp/config", response_model=ConfiguracaoEmbeddedSignupSaida)
def obter_configuracao_do_botao_whatsapp(
    usuario: Usuario = Depends(usuario_atual),
) -> ConfiguracaoEmbeddedSignupSaida:
    """Dados (não secretos) que o botão "Conectar WhatsApp" usa para montar a janela de login da Meta."""
    mostrar_conexao_manual = bool(configuracoes.email_com_acesso_a_conexao_manual_whatsapp) and (
        usuario.email == configuracoes.email_com_acesso_a_conexao_manual_whatsapp
    )
    return ConfiguracaoEmbeddedSignupSaida(
        app_id=configuracoes.meta_app_id,
        id_configuracao=configuracoes.meta_id_configuracao_embedded_signup,
        versao_api=configuracoes.meta_versao_api,
        mostrar_conexao_manual=mostrar_conexao_manual,
    )


@roteador.get("/whatsapp", response_model=CanalWhatsAppSaida | None)
def obter_canal_whatsapp(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> IntegracaoWhatsApp | None:
    """Devolve os dados (sem o token) do WhatsApp já conectado pela empresa, se houver."""
    return sessao.scalar(select(IntegracaoWhatsApp).where(IntegracaoWhatsApp.id_empresa == id_empresa))


@roteador.post("/whatsapp/conectar", response_model=CanalWhatsAppSaida, status_code=status.HTTP_201_CREATED)
async def conectar_canal_whatsapp(
    dados: ConectarCanalWhatsAppEntrada,
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> IntegracaoWhatsApp:
    """
    Conclui a conexão "um clique" do WhatsApp: troca o código de
    autorização por um token de acesso permanente, descobre o WABA/número
    de telefone escolhidos, inscreve a WABA no nosso webhook central (para
    as mensagens recebidas chegarem até a plataforma) e salva tudo isso
    vinculado à empresa logada — substituindo qualquer conexão anterior.
    """
    try:
        token_de_acesso = await trocar_codigo_por_token(dados.codigo_de_autorizacao, dados.redirect_uri)
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro)) from erro

    id_numero_telefone, id_waba = dados.id_numero_telefone, dados.id_waba
    if not id_numero_telefone or not id_waba:
        # O frontend não recebeu o "postMessage" da Meta com o WABA/número
        # escolhidos (recado conhecidamente instável — ver INTRODUÇÃO de
        # meta_embedded_signup.py) — descobrimos os dois sozinhos, direto
        # na Graph API, a partir do token que acabamos de obter.
        descoberta = await descobrir_waba_e_numero(token_de_acesso)
        if descoberta is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível identificar o número do WhatsApp conectado. Tente novamente.",
            )
        id_waba, id_numero_telefone = descoberta

    numero_de_exibicao = await obter_numero_de_exibicao(id_numero_telefone, token_de_acesso)
    await inscrever_webhook_da_waba(id_waba, token_de_acesso)
    await registrar_numero_de_telefone(id_numero_telefone, token_de_acesso)

    integracao = sessao.scalar(select(IntegracaoWhatsApp).where(IntegracaoWhatsApp.id_empresa == id_empresa))
    if integracao is None:
        integracao = IntegracaoWhatsApp(id_empresa=id_empresa)
        sessao.add(integracao)

    integracao.id_numero_telefone_meta = id_numero_telefone
    integracao.id_waba_meta = id_waba
    integracao.numero_exibicao = numero_de_exibicao
    integracao.token_de_acesso = token_de_acesso

    sessao.commit()
    sessao.refresh(integracao)
    return integracao


@roteador.put("/whatsapp/manual", response_model=CanalWhatsAppSaida)
async def conectar_canal_whatsapp_manualmente(
    dados: ConectarCanalWhatsAppManualEntrada,
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(usuario_atual),
) -> IntegracaoWhatsApp:
    """
    Conexão manual (Phone Number ID/WABA ID/token colados à mão) — a
    mesma checagem de e-mail que decide se o formulário aparece na tela
    (ver obter_configuracao_do_botao_whatsapp) também é aplicada aqui, do
    lado do backend: mesmo que alguém tente chamar esta rota direto, sem
    passar pela tela, ela só funciona para a conta autorizada.
    """
    if (
        not configuracoes.email_com_acesso_a_conexao_manual_whatsapp
        or usuario.email != configuracoes.email_com_acesso_a_conexao_manual_whatsapp
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conexão manual não disponível para esta conta.",
        )

    integracao = sessao.scalar(
        select(IntegracaoWhatsApp).where(IntegracaoWhatsApp.id_empresa == usuario.id_empresa)
    )
    if integracao is None:
        integracao = IntegracaoWhatsApp(id_empresa=usuario.id_empresa)
        sessao.add(integracao)

    integracao.id_numero_telefone_meta = dados.id_numero_telefone_meta
    integracao.id_waba_meta = dados.id_waba_meta
    integracao.numero_exibicao = dados.numero_exibicao
    integracao.token_de_acesso = dados.token_de_acesso

    # Dois passos que faltavam e causavam problemas reais em todo envio
    # feito por uma conexão manual (o Embedded Signup faz os dois sozinho,
    # mas a conexão manual pulava ambos):
    #   1) registrar_numero_de_telefone: sem isso, TODO envio falhava com
    #      "(#133010) Account not registered".
    #   2) inscrever_webhook_da_waba: sem isso, a WABA só manda eventos de
    #      status (entregue/lido/falhou) pro app interno da Meta usado no
    #      painel de teste — nunca pro nosso app.
    await registrar_numero_de_telefone(dados.id_numero_telefone_meta, dados.token_de_acesso)
    await inscrever_webhook_da_waba(dados.id_waba_meta, dados.token_de_acesso)

    sessao.commit()
    sessao.refresh(integracao)
    return integracao


def _carregar_dados_do_template(
    sessao: Session, id_empresa: int
) -> tuple[Empresa, ConfiguracaoAgente, IntegracaoWhatsApp]:
    """Busca os três registros necessários para lidar com um template — devolve erro 400 se algo faltar."""
    empresa = sessao.get(Empresa, id_empresa)
    configuracao = sessao.scalar(select(ConfiguracaoAgente).where(ConfiguracaoAgente.id_empresa == id_empresa))
    integracao = sessao.scalar(select(IntegracaoWhatsApp).where(IntegracaoWhatsApp.id_empresa == id_empresa))

    if empresa is None or configuracao is None or integracao is None or not integracao.id_waba_meta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conecte o WhatsApp (aba Canais) antes de criar um template.",
        )
    return empresa, configuracao, integracao


@roteador.get("/whatsapp/template-notificacao/previa", response_model=PreviaDoTemplateSaida)
def obter_previa_do_template_de_notificacao(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> PreviaDoTemplateSaida:
    """Monta o texto do template de notificação com um exemplo, para conferência antes do envio de verdade."""
    empresa, configuracao, _ = _carregar_dados_do_template(sessao, id_empresa)
    texto = montar_previa_do_template_de_notificacao(configuracao.nome_do_agente, empresa.nome_fantasia)
    return PreviaDoTemplateSaida(texto=texto)


@roteador.get("/whatsapp/template-notificacao", response_model=TemplateWhatsAppSaida)
async def obter_status_do_template_de_notificacao(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> TemplateWhatsAppSaida:
    """Consulta, na Meta, se o template de notificação ao setor já foi submetido e qual o status atual."""
    _, configuracao, integracao = _carregar_dados_do_template(sessao, id_empresa)
    status_atual = await consultar_status_do_template(
        integracao.id_waba_meta, integracao.token_de_acesso, configuracao.nome_do_template_encaminhamento
    )
    return TemplateWhatsAppSaida(nome=configuracao.nome_do_template_encaminhamento, status=status_atual)


@roteador.post(
    "/whatsapp/template-notificacao", response_model=TemplateWhatsAppSaida, status_code=status.HTTP_201_CREATED
)
async def criar_template_whatsapp_de_notificacao(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> TemplateWhatsAppSaida:
    """Monta e submete o template de notificação ao setor humano para análise da Meta."""
    empresa, configuracao, integracao = _carregar_dados_do_template(sessao, id_empresa)
    try:
        await criar_template_de_notificacao(
            id_waba=integracao.id_waba_meta,
            token_de_acesso=integracao.token_de_acesso,
            nome_do_template=configuracao.nome_do_template_encaminhamento,
            nome_do_agente=configuracao.nome_do_agente,
            nome_da_empresa=empresa.nome_fantasia,
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro)) from erro

    return TemplateWhatsAppSaida(nome=configuracao.nome_do_template_encaminhamento, status="PENDING")


@roteador.get("/whatsapp/template-reencaminhamento/previa", response_model=PreviaDoTemplateSaida)
def obter_previa_do_template_de_reencaminhamento(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> PreviaDoTemplateSaida:
    """Monta o texto do template de reencaminhamento (2º encaminhamento em diante) com um exemplo, para conferência."""
    empresa, configuracao, _ = _carregar_dados_do_template(sessao, id_empresa)
    texto = montar_previa_do_template_de_reencaminhamento(configuracao.nome_do_agente, empresa.nome_fantasia)
    return PreviaDoTemplateSaida(texto=texto)


@roteador.get("/whatsapp/template-reencaminhamento", response_model=TemplateWhatsAppSaida)
async def obter_status_do_template_de_reencaminhamento(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> TemplateWhatsAppSaida:
    """Consulta, na Meta, se o template de reencaminhamento já foi submetido e qual o status atual."""
    _, configuracao, integracao = _carregar_dados_do_template(sessao, id_empresa)
    status_atual = await consultar_status_do_template(
        integracao.id_waba_meta, integracao.token_de_acesso, configuracao.nome_do_template_reencaminhamento
    )
    return TemplateWhatsAppSaida(nome=configuracao.nome_do_template_reencaminhamento, status=status_atual)


@roteador.post(
    "/whatsapp/template-reencaminhamento", response_model=TemplateWhatsAppSaida, status_code=status.HTTP_201_CREATED
)
async def criar_template_whatsapp_de_reencaminhamento(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> TemplateWhatsAppSaida:
    """
    Monta e submete, para análise da Meta, o template usado a partir do
    SEGUNDO encaminhamento em diante — quando um atendimento que já tinha
    sido passado adiante volta com algo novo (ver
    agente/ferramentas.py:montar_ferramentas_de_reengajamento).
    """
    empresa, configuracao, integracao = _carregar_dados_do_template(sessao, id_empresa)
    try:
        await criar_template_de_reencaminhamento(
            id_waba=integracao.id_waba_meta,
            token_de_acesso=integracao.token_de_acesso,
            nome_do_template=configuracao.nome_do_template_reencaminhamento,
            nome_do_agente=configuracao.nome_do_agente,
            nome_da_empresa=empresa.nome_fantasia,
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro)) from erro

    return TemplateWhatsAppSaida(nome=configuracao.nome_do_template_reencaminhamento, status="PENDING")


@roteador.get("/whatsapp/template-atencao/previa", response_model=PreviaDoTemplateSaida)
def obter_previa_do_template_de_atencao(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> PreviaDoTemplateSaida:
    """Monta o texto do template de atenção (suspeita de manipulação do agente) com um exemplo, para conferência."""
    empresa, configuracao, _ = _carregar_dados_do_template(sessao, id_empresa)
    texto = montar_previa_do_template_de_atencao(configuracao.nome_do_agente, empresa.nome_fantasia)
    return PreviaDoTemplateSaida(texto=texto)


@roteador.get("/whatsapp/template-atencao", response_model=TemplateWhatsAppSaida)
async def obter_status_do_template_de_atencao(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> TemplateWhatsAppSaida:
    """Consulta, na Meta, se o template de atenção já foi submetido e qual o status atual."""
    _, configuracao, integracao = _carregar_dados_do_template(sessao, id_empresa)
    status_atual = await consultar_status_do_template(
        integracao.id_waba_meta, integracao.token_de_acesso, configuracao.nome_do_template_atencao
    )
    return TemplateWhatsAppSaida(nome=configuracao.nome_do_template_atencao, status=status_atual)


@roteador.post(
    "/whatsapp/template-atencao", response_model=TemplateWhatsAppSaida, status_code=status.HTTP_201_CREATED
)
async def criar_template_whatsapp_de_atencao(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> TemplateWhatsAppSaida:
    """
    Monta e submete, para análise da Meta, o template usado quando o
    guardrail de entrada detecta uma tentativa de manipulação do agente
    durante a conversa (ver agente/guardrails.py e agente/orquestrador.py).
    """
    empresa, configuracao, integracao = _carregar_dados_do_template(sessao, id_empresa)
    try:
        await criar_template_de_atencao(
            id_waba=integracao.id_waba_meta,
            token_de_acesso=integracao.token_de_acesso,
            nome_do_template=configuracao.nome_do_template_atencao,
            nome_do_agente=configuracao.nome_do_agente,
            nome_da_empresa=empresa.nome_fantasia,
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro)) from erro

    return TemplateWhatsAppSaida(nome=configuracao.nome_do_template_atencao, status="PENDING")


@roteador.get("/whatsapp/template-reengajamento/previa", response_model=PreviaDoTemplateSaida)
def obter_previa_do_template_de_reengajamento(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> PreviaDoTemplateSaida:
    """Monta o texto do template de reengajamento com um exemplo, para conferência antes do envio de verdade."""
    empresa, configuracao, _ = _carregar_dados_do_template(sessao, id_empresa)
    texto = montar_previa_do_template_de_reengajamento(configuracao.nome_do_agente, empresa.nome_fantasia)
    return PreviaDoTemplateSaida(texto=texto)


@roteador.get("/whatsapp/template-reengajamento", response_model=TemplateWhatsAppSaida)
async def obter_status_do_template_de_reengajamento(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> TemplateWhatsAppSaida:
    """Consulta, na Meta, se o template de reengajamento já foi submetido e qual o status atual."""
    _, configuracao, integracao = _carregar_dados_do_template(sessao, id_empresa)
    status_atual = await consultar_status_do_template(
        integracao.id_waba_meta, integracao.token_de_acesso, configuracao.nome_do_template_reengajamento
    )
    return TemplateWhatsAppSaida(nome=configuracao.nome_do_template_reengajamento, status=status_atual)


@roteador.post(
    "/whatsapp/template-reengajamento", response_model=TemplateWhatsAppSaida, status_code=status.HTTP_201_CREATED
)
async def criar_template_whatsapp_de_reengajamento(
    sessao: Session = Depends(obter_sessao),
    id_empresa: int = Depends(exigir_id_empresa_do_usuario),
) -> TemplateWhatsAppSaida:
    """Monta e submete o template de reengajamento para análise da Meta — usado para retomar contato com um atendimento em silêncio (ver agente/ferramentas_monitoramento.py)."""
    empresa, configuracao, integracao = _carregar_dados_do_template(sessao, id_empresa)
    try:
        await criar_template_de_reengajamento(
            id_waba=integracao.id_waba_meta,
            token_de_acesso=integracao.token_de_acesso,
            nome_do_template=configuracao.nome_do_template_reengajamento,
            nome_do_agente=configuracao.nome_do_agente,
            nome_da_empresa=empresa.nome_fantasia,
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro)) from erro

    return TemplateWhatsAppSaida(nome=configuracao.nome_do_template_reengajamento, status="PENDING")


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo expõe as rotas da aba Canais: os dados públicos que o botão
# "Conectar WhatsApp" precisa (GET /whatsapp/config), a conclusão da
# conexão em si depois do login na Meta (POST /whatsapp/conectar), o
# status da conexão já salva (GET /whatsapp), a conexão manual restrita a
# uma única conta (PUT /whatsapp/manual) e os QUATRO templates
# pré-aprovados exigidos pela Meta neste domínio — notificação ao setor
# humano (/whatsapp/template-notificacao*, primeiro encaminhamento),
# reencaminhamento (/whatsapp/template-reencaminhamento*, segundo
# encaminhamento em diante), atenção (/whatsapp/template-atencao*) e
# reengajamento de atendimento silencioso
# (/whatsapp/template-reengajamento*) — cada um com prévia para
# conferência antes de submeter de verdade para análise via Graph API. SEM
# template de abordagem (ver introdução) — este agente nunca inicia
# contato.
# ==============================================================================
